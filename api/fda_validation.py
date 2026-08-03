"""Hard (422-worthy) validation for trigger_assignments and variables in FDA JSON.

Phase 24 dropped the old `handler` enum: a `trigger_assignments` entry carries `trigger_name`
plus `actions` and nothing else. This is the ONE enforcement point for the trigger action
vocabulary across four runtimes (Pi `_build_action_callable`, the Pi CLI `validate_fda.py`,
React's `ActionEditor`, and this module). True cross-language single-sourcing would need
codegen (out of scope — see 24-RESEARCH.md's note on TRIGA-10); the honest fix is that THIS
module is the enforcement point, so React/Pi vocabulary drift fails at save time with a 422
instead of silently at Pi session start.

Deliberately separate from the SOFT `_validate_task_definition` in `routers/toolkits.py`
(state-body hw-lib-drift badge, always 200). This module's callers raise HTTPException(422).

View-key RESOLUTION is out of scope here — only key_template SHAPE is checked (non-empty
string, every `{token}` names a declared variable/flag). Valid keys like LICKER0..LICKER3 are
derived at runtime from a specific pilot's prefs.json (device_name x num_detectors via
check_for_detectors), so resolving here would falsely reject a definition targeting a
differently configured pilot. Authoritative resolution belongs to Phase 13's pilot-specific
preflight (api/routers/toolkit_dispatch.py::preflight_validate), which keys off pilot_id and
reads pilot_hardware_config — the only place that knows a given pilot's hardware shape.

DVK-11 (Plan 25-01) draws the identical split for a `view_detector` condition operand
({"view_detector": {"ref": "MPR121", "channel": 2}}): REF + SHAPE are checked here (is `ref` a
detector on this toolkit at all, is `channel` a non-negative int) via validate_condition_operands,
because those are toolkit facts, not pilot facts. Whether `channel` is in range for a SPECIFIC
pilot's wiring stays with preflight, same reason as key_template resolution above.
"""
import re

from fastapi import HTTPException

from detector_keys import module_detector_channels
from fda_utils import scan_fda_condition_operands
from hw_introspect import toolkit_hw_capabilities
from models import TaskToolkit

# {device_name} is resolved on the Pi at runtime from the source hardware's own attribute
# (fda_vocabulary.RUNTIME_KEY_TEMPLATE_TOKENS is the source of truth; the two languages cannot
# import from each other, so the token is listed here explicitly rather than inferred).
RUNTIME_KEY_TEMPLATE_TOKENS = {"device_name"}

VALID_ACTION_TYPES = {"hardware", "flag", "timer", "special", "method", "if", "view", "compute"}
VALID_SPECIALS = {"INC_TRIAL_COUNTER"}
VALID_TRIGGER_CONTEXT_KEYS = {"level", "tick"}
# No handler constant: the `handler` enum was dropped in Phase 24. `actions` is the only vocabulary.


def validate_variables(fda_json: dict, toolkit) -> list[str]:
    """Validate the top-level `variables` registry. Empty/absent = no errors."""
    if toolkit is None:
        return []
    variables = fda_json.get("variables")
    if not variables:
        return []
    if not isinstance(variables, dict):
        return [f"variables must be an object, got {type(variables).__name__}"]

    flag_names = set((toolkit.flags or {}).keys())
    return [
        f"variable '{name}' collides with an existing toolkit flag"
        for name in variables
        if name in flag_names
    ]


def validate_trigger_assignments(
    fda_json: dict,
    toolkit,
    module_names: set[str] | None = None,
    module_methods: dict[str, tuple[set[str], bool]] | None = None,
    trigger_sources: set[str] | None = None,
) -> list[str]:
    """Validate `trigger_assignments`. Absent/null/[] is backward-compatible and returns [].

    `module_names` carries the toolkit's backend-authored Modules hardware (resolved by the
    caller, which owns the DB session). A backend-authored toolkit declares hardware as
    hardware_modules rows rather than SEMANTIC_HARDWARE, so without these `known_hw` is empty
    and the lenient posture lets every hardware ref through.

    `module_methods` (name -> (resolved method set, closed)) and `trigger_sources` (hw_id set)
    are resolved by the caller via hw_introspect, which needs a DB session this module
    deliberately never opens itself. When omitted, `trigger_sources` falls back to
    getattr(toolkit, "trigger_sources", None) for backward compat with callers/tests that stub
    it directly onto the toolkit object.
    """
    if toolkit is None:
        return []
    trigger_assignments = fda_json.get("trigger_assignments")
    if not trigger_assignments:
        return []
    if not isinstance(trigger_assignments, list):
        return [f"trigger_assignments must be a list, got {type(trigger_assignments).__name__}"]

    known_hw = set((toolkit.semantic_hardware or {}).keys()) | (module_names or set())
    callable_methods = set(getattr(toolkit, "callable_methods", None) or [])
    valid_names = _valid_flag_names(fda_json, toolkit)
    # Enforce only when trigger_sources is known AND non-empty — same posture as
    # callable_methods, so a toolkit predating Plan 08's derivation is never falsely rejected.
    if trigger_sources is None:
        trigger_sources = {t["hw_id"] for t in (getattr(toolkit, "trigger_sources", None) or [])}

    errors: list[str] = []
    for i, ta in enumerate(trigger_assignments):
        if not isinstance(ta, dict):
            errors.append(f"trigger_assignments[{i}]: must be an object")
            continue

        raw_name = ta.get("trigger_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            errors.append(f"trigger_assignments[{i}]: trigger_name is required and must be a non-empty string")
            label = f"[{i}]"
        else:
            label = raw_name
            if trigger_sources and raw_name not in trigger_sources:
                errors.append(
                    f"Trigger '{raw_name}': unknown trigger_name. "
                    f"Valid trigger sources: {sorted(trigger_sources)}"
                )

        actions = ta.get("actions")
        if not actions:
            errors.append(
                f"Trigger '{label}': actions is required (the `handler` enum is gone, "
                f"`actions` is the only vocabulary)"
            )
            continue
        if not isinstance(actions, list):
            errors.append(f"Trigger '{label}': actions must be a list")
            continue

        for j, action in enumerate(actions):
            errors.extend(
                _validate_action(f"Trigger '{label}'", j, action, known_hw, callable_methods, valid_names, module_methods)
            )

    return errors


def validate_state_actions(
    fda_json: dict, toolkit, module_methods: dict[str, tuple[set[str], bool]] | None = None
) -> list[str]:
    """Hard-validate every state's entry_actions against the SAME method rule TRIGA-16 applies
    to trigger actions (empty/unresolvable method = silent no-op on the Pi).

    Deliberately narrower than validate_trigger_assignments: ref/flag/view/output checks stay
    with the soft drift-badge path (_validate_task_definition in routers/toolkits.py) — widening
    those into a hard gate is out of scope here, so `_validate_action` is called with
    method_only=True.
    """
    if toolkit is None:
        return []
    states = fda_json.get("states")
    if isinstance(states, dict):
        items = list(states.items())
    elif isinstance(states, list):
        items = [(s.get("name") or f"[{i}]", s) for i, s in enumerate(states) if isinstance(s, dict)]
    else:
        return []

    errors: list[str] = []
    for name, state in items:
        if not isinstance(state, dict):
            continue
        for j, action in enumerate(state.get("entry_actions") or []):
            errors.extend(
                _validate_action(f"State '{name}'", j, action, set(), set(), set(), module_methods, method_only=True)
            )
    return errors


def validate_condition_operands(fda_json: dict, detector_refs: set[str] | None = None) -> list[str]:
    """DVK-11: hard-validate every `view_detector` condition operand
    ({"view_detector": {"ref": <detector name>, "channel": <non-negative int>}}).

    Every other operand shape ({"view": ...}, {"flag": ...}, literals) is ignored here — this
    pass adds exactly one rule and must not become a general operand validator. `channel` RANGE
    (is it valid for a specific pilot's wiring) is preflight's job, not this pass's — see the
    module docstring's DVK-11 paragraph.
    """
    errors: list[str] = []
    for entry in scan_fda_condition_operands(fda_json):
        operand = entry["operand"]
        if not isinstance(operand, dict) or "view_detector" not in operand:
            continue
        location = entry["location"]
        value = operand["view_detector"]
        if not isinstance(value, dict):
            errors.append(f"{location}: view_detector must be an object with 'ref' and 'channel'")
            continue

        ref = value.get("ref")
        if not isinstance(ref, str) or not ref:
            errors.append(f"{location}: view_detector.ref must be a non-empty string")

        channel = value.get("channel")
        if isinstance(channel, bool) or not isinstance(channel, int) or channel < 0:
            errors.append(f"{location}: view_detector.channel must be a non-negative integer")

        if detector_refs and isinstance(ref, str) and ref and ref not in detector_refs:
            errors.append(
                f"{location}: view_detector ref '{ref}' is not a detector on this toolkit. "
                f"Detectors: {sorted(detector_refs)}"
            )
    return errors


def validate_compute_variables(
    fda_json: dict,
    toolkit,
    module_names: set[str] | None = None,
    detector_keys: set[str] | None = None,
) -> list[str]:
    """CMP-10: two independent hard checks over the `variables` registry and every condition
    operand — the compute-era additions to the save-time gate.

    Collision half: a declared variable name must not collide with the toolkit's semantic
    hardware, a backend-authored module name, or a detector-derived view key. Each of those is
    resolved through the exact same `{"view": name}` / `{"flag": name}` operand shape a variable
    is, so an un-caught collision would make one silently shadow the other. The flag-collision
    half already lives in `validate_variables` — not duplicated here.

    Reference half: every `{"view": name}` / `{"flag": name}` condition operand (transitions,
    `wait_condition`, `if`-action conditions — all reached via `scan_fda_condition_operands`)
    must name something resolvable: a toolkit flag, a declared variable, `trial_counter`, a
    module name, or a detector view key. `{"view_detector": ...}` operands are plan 25-01's own
    shape and are skipped entirely (matched neither key below); literal operands are ignored.
    """
    if toolkit is None:
        return []
    errors: list[str] = []
    module_names = module_names or set()
    detector_keys = detector_keys or set()

    variables = fda_json.get("variables") or {}
    if isinstance(variables, dict):
        semantic_hw = set((getattr(toolkit, "semantic_hardware", None) or {}).keys())
        for name in variables:
            if name in semantic_hw:
                errors.append(f"variable '{name}' collides with a toolkit hardware name")
            elif name in module_names:
                errors.append(f"variable '{name}' collides with a hardware module name")
            elif name in detector_keys:
                errors.append(f"variable '{name}' collides with a detector-derived view key")

    valid_names = _valid_flag_names(fda_json, toolkit) | module_names | detector_keys
    for entry in scan_fda_condition_operands(fda_json):
        operand = entry["operand"]
        if not isinstance(operand, dict):
            continue
        if "view" in operand:
            name = operand["view"]
        elif "flag" in operand:
            name = operand["flag"]
        else:
            continue
        if not isinstance(name, str) or name not in valid_names:
            errors.append(f"{entry['location']}: references unknown variable/flag '{name}'")

    return errors


def collect_hard_errors(
    fda_json: dict,
    toolkit,
    module_names: set[str] | None = None,
    module_methods: dict[str, tuple[set[str], bool]] | None = None,
    trigger_sources: set[str] | None = None,
    detector_refs: set[str] | None = None,
    detector_keys: set[str] | None = None,
) -> list[str]:
    """Every hard (422-worthy) error for this FDA."""
    if not fda_json or toolkit is None:
        return []
    return (
        validate_variables(fda_json, toolkit)
        + validate_trigger_assignments(fda_json, toolkit, module_names, module_methods, trigger_sources)
        + validate_state_actions(fda_json, toolkit, module_methods)
        + validate_condition_operands(fda_json, detector_refs)
        + validate_compute_variables(fda_json, toolkit, module_names, detector_keys)
    )


def reject_if_hard_errors(db, fda_json: dict, toolkit_id: int | None) -> None:
    """Raise HTTPException(422) if fda_json has hard trigger-assignment/variable errors.

    Looks up the toolkit itself so both POST and PUT call sites in routers/toolkits.py stay to
    a single line each — toolkits.py's net-growth budget for this plan is tight (<=15 lines).
    """
    if not fda_json:
        return
    toolkit = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none() if toolkit_id else None
    caps = toolkit_hw_capabilities(db, getattr(toolkit, "hardware_module_ids", None) or []) if toolkit else None
    module_methods = caps["module_methods"] if caps else None
    trigger_sources = {t["hw_id"] for t in caps["trigger_sources"]} if caps else None
    detector_refs = set(caps["detector_refs"]) if caps else None
    module_names = set(caps["module_names"]) if caps else set()
    # module_detector_channels is a single call keyed on module_names alone (no pilot_id needed)
    # — per-pilot channel RANGE stays with preflight, same split as key_template resolution.
    detector_keys = (
        {key for entry in module_detector_channels(db, sorted(module_names)) for key in entry["keys"]}
        if module_names else set()
    )
    errors = collect_hard_errors(
        fda_json, toolkit, module_names, module_methods, trigger_sources, detector_refs, detector_keys
    )
    if errors:
        raise HTTPException(422, detail={"errors": errors})


def _valid_flag_names(fda_json: dict, toolkit) -> set[str]:
    """Names usable as a flag ref / output slot / key_template token / condition operand."""
    return (
        set((toolkit.flags or {}).keys())
        | set((fda_json.get("variables") or {}).keys())
        | {"trial_counter"}
    )


def _validate_action_method(context_label, idx, action, module_methods) -> list[str]:
    """The TRIGA-16 rule: a hardware/timer action's `method` must be a non-empty string, and —
    only when the resolved method set is provably closed — a known one. Shared by the trigger
    path and validate_state_actions' method_only path so the rule can never drift between them.
    """
    ref = action.get("ref")
    method = action.get("method")
    if not isinstance(method, str) or not method.strip():
        return [
            f"{context_label} action[{idx}]: hardware ref '{ref}' has no method — "
            f"this saves cleanly and does nothing on the Pi"
        ]
    if module_methods is not None:
        allowed, closed = module_methods.get(ref, (set(), False))
        if closed and method not in allowed:
            return [f"{context_label} action[{idx}]: '{ref}' has no method '{method}'. Known: {sorted(allowed)}"]
    return []


def _validate_action(
    context_label, idx, action, known_hw, callable_methods, valid_names, module_methods=None, method_only=False
) -> list[str]:
    if not isinstance(action, dict):
        return [] if method_only else [f"{context_label} action[{idx}]: action must be an object"]

    action_type = action.get("type")

    if action_type == "if":
        errors: list[str] = []
        for j, sub in enumerate(action.get("then") or []):
            errors.extend(_validate_action(context_label, f"{idx}.then[{j}]", sub, known_hw, callable_methods, valid_names, module_methods, method_only))
        for j, sub in enumerate(action.get("else") or []):
            errors.extend(_validate_action(context_label, f"{idx}.else[{j}]", sub, known_hw, callable_methods, valid_names, module_methods, method_only))
        return errors

    if method_only:
        # State-body hard validation is scoped to the method rule only — ref/flag/view/output
        # checks stay with the soft drift path. Non-hardware actions have nothing to check here.
        return _validate_action_method(context_label, idx, action, module_methods) if action_type in ("hardware", "timer", "compute") else []

    if action_type not in VALID_ACTION_TYPES:
        return [
            f"{context_label} action[{idx}]: unknown action type '{action_type}'. "
            f"Allowed: {', '.join(sorted(VALID_ACTION_TYPES))}"
        ]

    errors = []
    ref = action.get("ref")

    if action_type in ("hardware", "timer"):
        # An explicit "group" key is direct-ref (GUI-built) format — _build_action_callable
        # resolves it via self.hardware[group][ref], which this module cannot verify without
        # a DB join to hardware_modules. Skip, matching _validate_fda_against_toolkit's posture.
        if "group" not in action and known_hw and ref not in known_hw:
            errors.append(f"{context_label} action[{idx}]: unknown hardware ref '{ref}'")
        errors.extend(_validate_action_method(context_label, idx, action, module_methods))
    elif action_type == "compute":
        # A compute module IS a hardware_modules row (CMP-03/12) — same ref/method rule as
        # hardware, plus one unconditional rule the hardware branch does not need: an `output`
        # is mandatory on compute (a compute op that writes nowhere is a no-op).
        if "group" not in action and known_hw and ref not in known_hw:
            errors.append(f"{context_label} action[{idx}]: unknown compute ref '{ref}'")
        errors.extend(_validate_action_method(context_label, idx, action, module_methods))
        out = action.get("output")
        if not out or (isinstance(out, list) and not out):
            errors.append(
                f"{context_label} action[{idx}]: compute action '{ref}.{action.get('method')}' "
                f"requires an 'output' naming a declared variable — a compute op that writes "
                f"nowhere is a no-op"
            )
    elif action_type == "method":
        if callable_methods and ref not in callable_methods:
            errors.append(f"{context_label} action[{idx}]: method '{ref}' not in toolkit callable_methods")
    elif action_type == "special":
        if ref not in VALID_SPECIALS:
            errors.append(
                f"{context_label} action[{idx}]: unknown special '{ref}'. "
                f"Allowed: {', '.join(sorted(VALID_SPECIALS))}"
            )
    elif action_type == "flag":
        if ref not in valid_names:
            errors.append(f"{context_label} action[{idx}]: flag '{ref}' not declared")
    elif action_type == "view":
        key_template = action.get("key_template")
        if not key_template or not isinstance(key_template, str):
            errors.append(f"{context_label} action[{idx}]: view action requires a key_template")
        else:
            source_ref = action.get("source_ref")
            tokens = set(re.findall(r"\{(\w+)\}", key_template))
            for token in tokens - RUNTIME_KEY_TEMPLATE_TOKENS:
                if token not in valid_names:
                    errors.append(f"{context_label} action[{idx}]: key_template token '{token}' not declared")
            if tokens & RUNTIME_KEY_TEMPLATE_TOKENS and not (isinstance(source_ref, str) and source_ref.strip()):
                errors.append(f"{context_label} action[{idx}]: key_template uses {{device_name}} but source_ref is missing")
            if isinstance(source_ref, str) and source_ref.strip() and known_hw and source_ref not in known_hw:
                errors.append(f"{context_label} action[{idx}]: unknown source_ref '{source_ref}'")

    output = action.get("output")
    if output is not None:
        names = output if isinstance(output, list) else [output]
        for name in names:
            if name not in valid_names:
                errors.append(f"{context_label} action[{idx}]: output slot '{name}' not declared")

    for operand in list(action.get("args") or []) + list((action.get("kwargs") or {}).values()):
        if isinstance(operand, dict) and "trigger" in operand:
            key = operand["trigger"]
            if key not in VALID_TRIGGER_CONTEXT_KEYS:
                errors.append(
                    f"{context_label} action[{idx}]: unknown trigger context key '{key}'. "
                    f"Allowed: {', '.join(sorted(VALID_TRIGGER_CONTEXT_KEYS))}"
                )

    return errors
