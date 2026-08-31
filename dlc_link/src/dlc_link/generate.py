"""The D-15 generation-time validation gate plus `generate()` (D-11..D-13, D-39).

`generate()` turns a `BodypartSource` (`dlc_link.config_read`) plus an explicit bodypart
selection into a paired `ExternalHardware` lib source and signal map, refusing every
declaration that would fail late and lethally on the rig. CLI/argparse and the D-44/D-46
write-location refusal live in `dlc_link.generate_cli` (split out to hold this file under
its line budget); `main` is re-exported here so the declared console script
(`dlc-link-generate = dlc_link.generate:main`, pyproject.toml) keeps working unchanged.
"""
import ast
import hashlib
import re
import sys
from datetime import datetime, timezone

from dlc_link.config_read import select, warn_multianimal_identity
from dlc_link.decimate import RECOMMENDED_DEFAULTS
from dlc_link.names import build_name_map, flat_signal_names
from dlc_link.templates import render_lib_source, render_signal_map

GENERATOR_NAME = "dlc-link-generate"
GENERATOR_VERSION = "0.1.0"

_LEGAL_STALE_POLICIES = frozenset({"hold_last", "return_default", "return_none"})
# T-35-72: a lib that enqueues nothing via `self.send(item)` (the only enqueue path,
# `external_hardware.py:186-188`) can never flip `_egress_failed` True, so
# `recompute_alive`'s conjunction collapses to inbound liveness alone -- but only if none
# of these ever appear in the rendered text.
_NO_EGRESS_MARKERS = ("self.send(", "_egress_probe", "def on_run_start", "def on_run_stop")
_SOURCE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_CLASS_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SIGNAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class GenerationError(Exception):
    """Raised for every generation-time refusal (D-15, D-39, D-44/D-46, T-35-72)."""


class GenerationResult(object):
    __slots__ = ("lib_source", "map_source", "lib_sha256", "name_map", "provenance")

    def __init__(self, lib_source, map_source, lib_sha256, name_map, provenance):
        self.lib_source = lib_source
        self.map_source = map_source
        self.lib_sha256 = lib_sha256
        self.name_map = name_map
        self.provenance = provenance


def default_class_name(source_id):
    parts = [p for p in source_id.split("_") if p]
    return "".join(p.capitalize() for p in parts) or "GeneratedDlcLib"


def _extract_signal_specs(lib_source):
    """Re-parse rendered lib source; {name: {stale_after_ms, stale_policy,
    has_default_zero, has_float_return}} per `@signal`-decorated method. Never trusts the
    template -- the D-15(c)/(f) re-parse gate."""
    tree = ast.parse(lib_source)
    specs = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            for dec in item.decorator_list:
                is_signal = (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Name)
                    and dec.func.id == "signal"
                )
                if not is_signal:
                    continue
                kwargs = {kw.arg: kw.value for kw in dec.keywords if kw.arg is not None}

                def _const(key):
                    node = kwargs.get(key)
                    return node.value if isinstance(node, ast.Constant) else None

                specs[item.name] = {
                    "stale_after_ms": _const("stale_after_ms"),
                    "stale_policy": _const("stale_policy"),
                    "has_default_zero": _const("default") == 0.0,
                    "has_float_return": isinstance(item.returns, ast.Name) and item.returns.id == "float",
                }
    return specs


def _validate_rendered_lib(lib_source, expected_signal_names):
    """The D-15 gate, run against the RENDERED TEXT -- never trusts the template.
    Module-scope so tests can inject a malformed rendered source directly, independent
    of whether the real template could ever produce it."""
    try:
        ast.parse(lib_source)
    except SyntaxError as exc:
        raise GenerationError("rendered lib source does not parse: {}".format(exc))

    for marker in _NO_EGRESS_MARKERS:
        if marker in lib_source:
            raise GenerationError(
                "rendered lib source contains {!r} -- an emitted lib must have NO egress "
                "path (T-35-72), or <source_id>.alive would no longer mean inbound "
                "liveness only".format(marker)
            )

    specs = _extract_signal_specs(lib_source)
    actual_names, expected_names = set(specs), set(expected_signal_names)
    if actual_names != expected_names:
        raise GenerationError(
            "rendered signal set {!r} does not equal the expected set {!r} -- missing "
            "{!r}, extra {!r}".format(
                sorted(actual_names), sorted(expected_names),
                sorted(expected_names - actual_names), sorted(actual_names - expected_names),
            )
        )

    for name, spec in specs.items():
        if not _SIGNAL_NAME_PATTERN.match(name):
            raise GenerationError(
                "signal name {!r} does not match ^[a-z][a-z0-9_]*$ -- refusing to write "
                "source that will be exec'd on the Pi".format(name)
            )
        if not spec["stale_after_ms"] or spec["stale_after_ms"] <= 0:
            raise GenerationError(
                "signal {!r} has stale_after_ms == 0 (or unresolved), which means NEVER "
                "STALE in resolve_stale_value and silently deletes DLC-05's occlusion "
                "semantic".format(name)
            )
        if spec["stale_policy"] == "return_none":
            raise GenerationError(
                "signal {!r} uses stale_policy='return_none', which raises TypeError out "
                "of the FDA's unguarded comparison (all(expr() for expr in expr_list) / "
                "operator.gt) -- refused for every signal this generator emits".format(name)
            )
        if spec["stale_policy"] not in _LEGAL_STALE_POLICIES:
            raise GenerationError(
                "signal {!r} has stale_policy {!r}, which is not one of {} -- an illegal "
                "value raises ValueError inside FDA evaluation on the rig, mid-run".format(
                    name, spec["stale_policy"], sorted(_LEGAL_STALE_POLICIES)
                )
            )
        if not spec["has_float_return"] or not spec["has_default_zero"]:
            raise GenerationError(
                "signal {!r} must declare both a '-> float' return annotation and "
                "default=0.0 -- the class-build-time TypeError gate (resolve_dtype) made "
                "visible at generation time".format(name)
            )


def generate(
    source,
    pose_order,
    pose_order_source,
    wanted,
    coords_for,
    source_id,
    stale_after_ms=100,
    class_name=None,
    liveness_hook="clock-consistent",
    allow_signals=6,
):
    """Pure: no file I/O. Returns a `GenerationResult`. Raises `GenerationError` (or a
    `dlc_link.config_read.ConfigReadError` surfaced from `select()`/`build_name_map()`,
    never swallowed) for every D-15/D-39 refusal."""
    if pose_order_source not in ("probe", "config-declared-UNVERIFIED"):
        raise GenerationError(
            "pose_order_source must be 'probe' or 'config-declared-UNVERIFIED', got "
            "{!r}".format(pose_order_source)
        )
    if not isinstance(stale_after_ms, int) or isinstance(stale_after_ms, bool) or stale_after_ms <= 0:
        raise GenerationError(
            "stale_after_ms must be an int > 0; got {!r}. stale_after_ms == 0 means NEVER "
            "STALE in resolve_stale_value and silently deletes DLC-05's entire occlusion "
            "semantic: a keypoint that stops updating keeps its last confident value "
            "forever and an FDA gated on it stays latched, with no runtime "
            "symptom.".format(stale_after_ms)
        )
    wanted = list(wanted)
    if not wanted:
        raise GenerationError(
            "an explicit, non-empty bodypart selection is required (D-39); there is "
            "deliberately no flag that emits every candidate"
        )

    class_name = class_name or default_class_name(source_id)
    if not _SOURCE_ID_PATTERN.match(source_id):
        raise GenerationError(
            "source_id {!r} does not match ^[a-z][a-z0-9_]*$ -- this becomes an "
            "identifier in source stored in hardware_lib_versions.source_code and "
            "exec'd on the Pi".format(source_id)
        )
    if not _CLASS_NAME_PATTERN.match(class_name):
        raise GenerationError("class_name {!r} does not match ^[A-Z][A-Za-z0-9]*$".format(class_name))

    # select() raises SentinelSelectedError/UnknownBodypartsError (both ConfigReadError)
    # by itself; this generator SURFACES that error rather than swallowing it (D-15h).
    bodypart_class = dict(select(source, wanted))

    # The D-39 "must not select every candidate" gate is meaningless in explicit-list
    # mode (D-10): there is no larger config-declared universe to narrow FROM -- the
    # source's own candidate list IS the --bodyparts the researcher just typed, by
    # construction, so it would always equal `wanted` and make D-10's escape hatch
    # permanently unusable for its documented purpose.
    distinct_selectable = (
        set(source.bodyparts) | set(source.multianimal_bodyparts) | set(source.unique_bodyparts)
    )
    if source.source_format != "explicit-list" and distinct_selectable and set(wanted) >= distinct_selectable:
        raise GenerationError(
            "wanted bodyparts cover every candidate this source offers ({} distinct "
            "names; {} total candidates counting per-individual replication -- D-39). "
            "Against the ~60 msg/s decimated envelope this is structural, not advisory: "
            "an explicit, narrower selection is required and there is no flag that emits "
            "everything.".format(len(distinct_selectable), source.candidate_count())
        )

    # build_name_map raises InvalidBodypartName (ValueError) directly if `wanted` is not
    # a subset of `pose_order` -- surfaced, not swallowed, same posture as select() above.
    name_map = build_name_map(pose_order, wanted, coords_for)

    signal_count = len(flat_signal_names(name_map))
    hz_cap = 1000.0 / RECOMMENDED_DEFAULTS["min_interval_ms"]
    if signal_count > allow_signals:
        raise GenerationError(
            "selection emits {sc} signals; at the decimator's {hz:g} Hz per-signal cap "
            "that is {sc} x {hz:g} = {total:g} msg/s against a proven ~60 msg/s envelope, "
            "exceeding --allow-signals={limit} (={limit} x {hz:g} = {budget:g} msg/s). "
            "Narrow the selection, or pass --allow-signals to override this budget "
            "deliberately (D-39).".format(
                sc=signal_count, hz=hz_cap, total=signal_count * hz_cap,
                limit=allow_signals, budget=allow_signals * hz_cap,
            )
        )

    identity_warning = warn_multianimal_identity(source)
    if identity_warning:
        print(identity_warning, file=sys.stderr)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lib_source = render_lib_source(
        class_name=class_name, source_id=source_id, name_map=name_map, wanted=wanted,
        stale_after_ms=stale_after_ms, liveness_hook=liveness_hook, source=source,
        generated_at=generated_at, generator_version=GENERATOR_VERSION,
    )

    expected_signal_names = flat_signal_names(name_map)
    _validate_rendered_lib(lib_source, expected_signal_names)
    lib_sha256 = hashlib.sha256(lib_source.encode("utf-8")).hexdigest()

    map_source = render_signal_map(
        source_id=source_id, class_name=class_name, name_map=name_map, wanted=wanted,
        bodypart_class=bodypart_class, stale_after_ms=stale_after_ms, source=source,
        pose_order=pose_order, pose_order_source=pose_order_source, lib_sha256=lib_sha256,
        generated_at=generated_at, generator_version=GENERATOR_VERSION,
    )
    try:
        ast.parse(map_source)
    except SyntaxError as exc:
        raise GenerationError("rendered signal-map source does not parse: {}".format(exc))

    provenance = {
        "generator_name": GENERATOR_NAME, "generator_version": GENERATOR_VERSION,
        "generated_at": generated_at, "source_format": source.source_format,
        "engine": source.engine, "config_path": source.path, "config_sha256": source.sha256,
        "multianimal": source.multianimal, "source_id": source_id, "class_name": class_name,
        "pose_order_source": pose_order_source,
    }
    return GenerationResult(
        lib_source=lib_source, map_source=map_source, lib_sha256=lib_sha256,
        name_map=name_map, provenance=provenance,
    )


def main(argv=None):
    """Thin re-export so `dlc-link-generate = dlc_link.generate:main` (pyproject.toml)
    keeps working; the real CLI lives in `dlc_link.generate_cli` (import deferred to
    avoid a module-load-time circular import, since that module imports from here)."""
    from dlc_link.generate_cli import main as _main

    return _main(argv)


if __name__ == "__main__":
    sys.exit(main())
