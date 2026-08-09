"""AST-only extraction of @signal/@event/@command/@decoder metadata (EXTLINK-09, plan 18-07).

Works purely on source text -- never imports the target module. The backend has no `autopilot`,
no `pigpio`, and no rig hardware, so every value this module emits is string-typed: a real Python
`type` object is never obtainable here and must not be faked.
"""
import ast

EXTLINK_DECORATORS = ("signal", "event", "command", "decoder")


def _kwarg_value(node: ast.expr):
    """Convert a decorator keyword's value node into a JSON-safe value.

    Pitfall 5: `@event(payload={"object": str, "confidence": float})` is NOT
    `ast.literal_eval`-safe -- bare type names are `ast.Name` nodes, not literals. Dict values are
    therefore always rendered via `ast.unparse` into a string, never evaluated.
    """
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        result = {}
        for key_node, value_node in zip(node.keys, node.values):
            key = key_node.value if isinstance(key_node, ast.Constant) else ast.unparse(key_node)
            result[key] = ast.unparse(value_node)
        return result
    return ast.unparse(node)


def _decorator_call(dec: ast.expr) -> tuple[str | None, ast.Call | None]:
    """Return (decorator_name, call_node) for a bare `@name` or `@name(...)` decorator."""
    if isinstance(dec, ast.Name):
        return dec.id, None
    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
        return dec.func.id, dec
    return None, None


def _signal_dtype(item: ast.FunctionDef, kwargs: dict) -> str | None:
    """Resolve from the return annotation first, then `type(default)`, then None.

    Mirrors the Pi-side `resolve_dtype` chain (EXTLINK-12). Raising here would be wrong -- this
    extractor describes, it does not enforce; the real `TypeError` belongs at class-build time on
    the Pi, where the actual annotation object exists.
    """
    if item.returns is not None:
        return ast.unparse(item.returns)
    if "default" in kwargs:
        return type(kwargs["default"]).__name__
    return None


def _command_args(item: ast.FunctionDef) -> list[dict]:
    args = []
    for arg in item.args.args:
        if arg.arg == "self":
            continue
        args.append({
            "name": arg.arg,
            "dtype": ast.unparse(arg.annotation) if arg.annotation else None,
        })
    return args


def extract_extlink_metadata(source_or_tree) -> dict:
    """Extract `@signal`/`@event`/`@command`/`@decoder` metadata, keyed by class name.

    Accepts either source text or an already-parsed tree, so a caller that already parsed the
    source for another purpose (`api/routers/hardware_libs.py`) can reuse it instead of
    re-parsing. A class is only present in the result if it declares at least one of the four
    decorators -- a plain hardware class with none of them is omitted entirely (EXTLINK-18: a
    zero-`@signal` control-only class is still legal and gets `signals: {}`, but a class with NO
    extlink decorators at all was never an `ExternalHardware` subclass and has no extlink shape).
    """
    tree = ast.parse(source_or_tree) if isinstance(source_or_tree, str) else source_or_tree

    result: dict = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        class_meta = {"signals": {}, "events": {}, "commands": {}, "decoder": None}
        has_extlink = False

        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            for dec in item.decorator_list:
                name, call = _decorator_call(dec)
                if name not in EXTLINK_DECORATORS:
                    continue
                has_extlink = True
                kwargs = {
                    kw.arg: _kwarg_value(kw.value)
                    for kw in (call.keywords if call else [])
                    if kw.arg is not None
                }

                if name == "signal":
                    class_meta["signals"][item.name] = {
                        "dtype": _signal_dtype(item, kwargs), **kwargs,
                    }
                elif name == "event":
                    class_meta["events"][item.name] = kwargs
                elif name == "command":
                    class_meta["commands"][item.name] = {
                        "args": _command_args(item),
                        "returns": ast.unparse(item.returns) if item.returns else None,
                    }
                elif name == "decoder":
                    class_meta["decoder"] = item.name

        if has_extlink:
            result[node.name] = class_meta

    return result
