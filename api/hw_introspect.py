"""AST-based hardware capability introspection for hardware-lib source files.

Hardware classes (gpio.py, i2c.py, timer.py, ...) all subclass an imported `Hardware` base, so
a class's ancestor chain is NEVER fully closed inside one lib source file. Every function here
reports that honestly via a `closed` flag instead of guessing at an unresolvable base.

Stdlib `ast` only — no FastAPI/DB imports. `toolkit_hw_capabilities` takes a caller-owned `db`
session (same pattern as fda_validation._module_names) so this module never opens a connection.
"""
import ast
from functools import lru_cache

from sqlalchemy import text as sa_text


@lru_cache(maxsize=256)
def _parse_classes(source_code: str) -> dict[str, ast.ClassDef]:
    """Top-level class name -> ClassDef. Empty dict on a parse failure — never raises.

    lru_cache is keyed on the source string itself (Python hashes it for the cache), so a lib
    version shared across many toolkit rows is parsed once per process, not once per toolkit.
    """
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, ValueError):
        return {}
    return {node.name: node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)}


def _base_name(base: ast.expr) -> str | None:
    # ast.Attribute bases (e.g. gpio.Digital_Out written from another module) are not resolved —
    # only a bare Name can point at a class defined in this same source file.
    return base.id if isinstance(base, ast.Name) else None


def resolve_class_methods(source_code: str, class_name: str) -> tuple[set[str], bool]:
    """Method names on `class_name` including bases DEFINED IN THE SAME SOURCE.

    `closed` is True only when every ancestor was resolvable in this file — a cycle or an
    ancestor outside the file (the common case: Hardware is always imported) both count as
    unresolved, so callers never reject an unknown method as if the set were exhaustive.
    """
    return _resolve_methods(_parse_classes(source_code), class_name, frozenset())


def _resolve_methods(classes: dict[str, ast.ClassDef], name: str, seen: frozenset) -> tuple[set[str], bool]:
    if name not in classes or name in seen:
        return set(), False
    node = classes[name]
    seen = seen | {name}
    methods = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    closed = True
    for base in node.bases:
        base_name = _base_name(base)
        if base_name is None:
            continue
        base_methods, base_closed = _resolve_methods(classes, base_name, seen)
        methods |= base_methods
        closed = closed and base_closed
    return methods, closed


def _resolve_flags(classes: dict[str, ast.ClassDef], name: str, seen: frozenset) -> tuple[bool, str | None]:
    if name not in classes or name in seen:
        return False, None
    node = classes[name]
    seen = seen | {name}
    is_trigger, direction = False, None
    for item in node.body:
        target = None
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            target, value = item.targets[0].id, item.value
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            target, value = item.target.id, item.value
        else:
            continue
        if not (isinstance(value, ast.Constant) and value.value is True):
            continue
        if target == "is_trigger":
            is_trigger = True
        elif target == "input":
            direction = "input"
        elif target == "output":
            direction = "output"
    for base in node.bases:
        base_name = _base_name(base)
        if base_name is None:
            continue
        base_trigger, base_direction = _resolve_flags(classes, base_name, seen)
        is_trigger = is_trigger or base_trigger
        direction = direction or base_direction
    return is_trigger, direction


def class_capabilities(source_code: str, class_name: str) -> dict:
    """{is_trigger, direction, is_detector, methods, closed} for one class.

    is_trigger : class-level `is_trigger = True` on the class or an in-file ancestor.
    direction  : "input"/"output" from a truthful class-level `input`/`output` flag, else None —
                 real attributes on gpio.Digital_In / Digital_Out, never inferred from the name.
    is_detector: `detect_change` is in the resolved method set. A CAPABILITY check, NOT the same
                 predicate as the Pi's runtime check_for_detectors (which also tests
                 num_detectors/device_name/read() on a live instance — static AST cannot see
                 attribute values). They agree today because Touch_Detector is the only class
                 defining detect_change; a future class defining it without being a real
                 detector would make the editor offer it while the Pi silently skips it. Do not
                 "unify" the two predicates without re-reading this note.
    """
    classes = _parse_classes(source_code)
    if class_name not in classes:
        return {"is_trigger": False, "direction": None, "is_detector": False, "methods": set(), "closed": False}
    methods, closed = _resolve_methods(classes, class_name, frozenset())
    is_trigger, direction = _resolve_flags(classes, class_name, frozenset())
    return {
        "is_trigger": is_trigger,
        "direction": direction,
        "is_detector": "detect_change" in methods,
        "methods": methods,
        "closed": closed,
    }


def toolkit_hw_capabilities(db, hardware_module_ids: list[int]) -> dict:
    """{"trigger_sources": [...], "detector_refs": [...], "module_methods": {name: (methods,
    closed)}, "module_names": [...]}

    One SQL join over hardware_modules -> hardware_libs -> hardware_lib_versions
    (active_version_id.source_code), parsing each distinct version once per call (memoised by
    _parse_classes across calls). A module whose lib has no active version, or whose class is
    missing from that version's source, is skipped silently — never a 500 on a toolkit read.

    `module_names` is every module NAME this toolkit has (regardless of whether its source
    resolved), so a caller can feed it straight to `detector_keys.module_detector_channels`
    without a second query. Plan 25-03: it must be present on BOTH returns below — the early
    return (98 of 112 task_toolkits rows have no hardware_module_ids and take it) is the one
    that matters most; dropping the key there turns `caps["module_names"]` into a `KeyError`
    on every module-less toolkit read.
    """
    if not hardware_module_ids:
        return {"trigger_sources": [], "detector_refs": [], "module_methods": {}, "module_names": []}

    rows = db.execute(
        sa_text(
            "SELECT hm.id, hm.name, hm.class_name, hlv.source_code "
            "FROM hardware_modules hm "
            "JOIN hardware_libs hl ON hl.id = hm.hardware_lib_id "
            "LEFT JOIN hardware_lib_versions hlv ON hlv.id = hl.active_version_id "
            "WHERE hm.id = ANY(:ids)"
        ),
        {"ids": list(hardware_module_ids)},
    ).fetchall()

    # Collected from `rows` before the per-row `source_code` guard below — a module whose lib
    # has no active version still HAS a name, and dropping it here would silently make its
    # detector channels vanish from module_detector_channels' input.
    module_names = [row.name for row in rows]

    trigger_sources: list[dict] = []
    detector_refs: list[str] = []
    module_methods: dict[str, tuple[set[str], bool]] = {}

    for row in rows:
        if not row.source_code:
            continue
        caps = class_capabilities(row.source_code, row.class_name)
        module_methods[row.name] = (caps["methods"], caps["closed"])
        if caps["is_trigger"]:
            trigger_sources.append({
                "hw_id": row.name, "module_id": row.id,
                "class_name": row.class_name, "direction": caps["direction"],
            })
        if caps["is_detector"]:
            detector_refs.append(row.name)

    order = {"input": 0, "output": 1, None: 2}
    trigger_sources.sort(key=lambda t: (order.get(t["direction"], 2), t["hw_id"]))
    detector_refs.sort()

    return {
        "trigger_sources": trigger_sources,
        "detector_refs": detector_refs,
        "module_methods": module_methods,
        "module_names": module_names,
    }
