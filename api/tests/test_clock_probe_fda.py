"""Pre-flight validation for the clock_probe FDA documents (Phase 31 Plan 12, Task 1).

Both `clock_probe_short` and `clock_probe_soak` are validated here BEFORE any hardware time is
spent on them -- a rejected FDA discovered on the rig costs a session. These tests exercise the
exact same hard-error gate `POST /api/task-definitions` runs (`fda_validation.collect_hard_errors`,
the body `reject_if_hard_errors` calls after its own toolkit lookup) against the REAL
hardware_modules / hardware_lib_versions rows for modules 5/6/24 -- read-only queries only,
no writes, no dependency on the clock_probe toolkit actually existing yet in the database (a
SimpleNamespace stands in for the not-yet-created TaskToolkit row, exactly the way
test_task_definitions_validation.py's `make_toolkit()` does for router-level tests).

The FDA documents are intentionally NOT imported from tools/seed_clock_probe.py: that script
runs on the host against the API over HTTP (it needs `requests`/`jwt`, and `tools/` is not
copied into the api Docker image -- see api/Dockerfile's `COPY . .` from the `api/` build
context only). The two documents below are kept byte-for-byte in sync with the ones the seeder
posts; if you change one, change the other, and re-run both this file and the seeder's
--verify-only flag.

The three trap tests are the point of this file (see the plan's <known_traps>):
  1. no `{"param": ...}` argument anywhere (dead on the Pi)
  2. no `INC_TRIAL_COUNTER` special anywhere (silent no-op, kills graduation)
  3. every condition_tree operand is `{"view": "TIMER"}` or a literal (never rig-exercised
     otherwise)
"""
import json
from types import SimpleNamespace

# Module ids reused from the DB, verified 2026-08-24 (plan's <the_hardware> table):
#   5 Mid_LED (Digital_Out, lib 8)   6 TIMER (lib 11)   24 COMPUTE (ComputeOps, lib 45)
# Retargeted 2026-08-24: modules 65/64 (Opto_Trigger/Nose_Poke_IR) exist in the backend
# registry but are absent from pilot/prefs.template.json, so on a real rig they
# instantiate with pin=None and the FDA build fails. Mid_LED is a Digital_Out the
# template does define, with record=True -- the one property the probe needs.
# Keep this list identical to tools/seed_clock_probe.py:HARDWARE_MODULE_IDS.
# 7 LICKER (Touch_Detector, lib 9) + 8 TOUCH_INT (Digital_In, lib 8) added 2026-08-24 so the
# INPUT edge path can be confirmed by hand on a fresh rig -- Mid_LED is an output and proves
# only the command->pin direction. Neither FDA references them; they are present so a touch
# dispatches its Hardware_Event (execute_trigger does that unconditionally, independent of
# trigger_assignments). That is why widening this set must NOT widen what the FDAs may say --
# see test_every_action_ref_is_in_the_toolkit.
CLOCK_PROBE_MODULE_IDS = [5, 6, 7, 8, 24]
CLOCK_PROBE_MODULE_NAMES = {"Mid_LED", "TIMER", "LICKER", "TOUCH_INT", "COMPUTE"}

# The refs the two clock FDAs are actually allowed to use. Deliberately NOT the full toolkit:
# adding hardware for a human to poke must not silently license the probe's state machine to
# start driving it, which would change what the clock evidence means.
CLOCK_PROBE_FDA_REFS = {"Mid_LED", "TIMER"}


def _build_short_fda() -> dict:
    return {
        "version": 2,
        "initial_state": "start",
        "description": (
            "clock_probe_short -- ~10 minute regression asset. Toggles Mid_LED at ~1 Hz "
            "so every edge produces two dispatched records (logging_utils.py:97 and task.py:283 "
            "routes) if the module is configured record=True + trigger. Cannot fail the "
            "monotonicity check (C1) on its own -- 10 minutes contains no 32-bit tick wrap; "
            "only clock_probe_soak tests the wrap. Literal args only, TIMER-only conditions, no "
            "trial counter -- see tools/seed_clock_probe.py module docstring for why."
        ),
        # Mirrors tools/seed_clock_probe.py:build_licker_trigger_assignments(). Kept literal
        # here (not imported) because this file is the independent statement of what the two
        # task definitions must contain -- importing the seeder would make it agree with
        # itself by construction.
        "variables": {"pin_number": {}, "level": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "hardware",
                        "ref": "LICKER",
                        "method": "detect_change",
                        "args": [],
                        "output": ["pin_number", "level"],
                    },
                    {
                        "type": "if",
                        "condition": {"op": "!=", "left": {"flag": "pin_number"}, "right": None},
                        "then": [
                            {
                                "type": "view",
                                "source_ref": "LICKER",
                                "key_template": "{device_name}{pin_number}",
                                "value": {"flag": "level"},
                            }
                        ],
                    },
                ],
            }
        ],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Mid_LED", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [1], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Mid_LED", "args": [False], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [1], "type": "timer", "method": "set"},
                ]
            },
        },
        "transitions": [
            {"from": "start", "to": "pulse_on", "description": "begin the pulse loop"},
            {
                "from": "pulse_on",
                "to": "pulse_off",
                "description": "pulse has been high 1 s",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
            {
                "from": "pulse_off",
                "to": "pulse_on",
                "description": "pulse has been low 1 s - next cycle",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
        ],
    }


def _build_soak_fda() -> dict:
    return {
        "version": 2,
        "initial_state": "start",
        "description": (
            "clock_probe_soak -- >= 4 h 30 m. Same pulse loop as clock_probe_short, slower "
            "(TIMER.set(5) instead of 1) so the index gets a few thousand documents rather than "
            "hundreds of thousands. 3 wrap crossings = 3 x 4294.967296 s = 3 h 34 m 45 s minimum "
            "-- scheduled duration leaves margin at both ends. Nothing in this FDA changes for "
            "the forced wall-clock step (Task 4 Step 4); the task simply keeps pulsing across "
            "it. Literal args only, TIMER-only conditions, no trial counter -- see "
            "tools/seed_clock_probe.py module docstring for why."
        ),
        # Mirrors tools/seed_clock_probe.py:build_licker_trigger_assignments(). Kept literal
        # here (not imported) because this file is the independent statement of what the two
        # task definitions must contain -- importing the seeder would make it agree with
        # itself by construction.
        "variables": {"pin_number": {}, "level": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "hardware",
                        "ref": "LICKER",
                        "method": "detect_change",
                        "args": [],
                        "output": ["pin_number", "level"],
                    },
                    {
                        "type": "if",
                        "condition": {"op": "!=", "left": {"flag": "pin_number"}, "right": None},
                        "then": [
                            {
                                "type": "view",
                                "source_ref": "LICKER",
                                "key_template": "{device_name}{pin_number}",
                                "value": {"flag": "level"},
                            }
                        ],
                    },
                ],
            }
        ],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Mid_LED", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [5], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Mid_LED", "args": [False], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [5], "type": "timer", "method": "set"},
                ]
            },
        },
        "transitions": [
            {"from": "start", "to": "pulse_on", "description": "begin the pulse loop"},
            {
                "from": "pulse_on",
                "to": "pulse_off",
                "description": "pulse has been high 5 s",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
            {
                "from": "pulse_off",
                "to": "pulse_on",
                "description": "pulse has been low 5 s - next cycle",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
        ],
    }


SHORT_FDA = _build_short_fda()
SOAK_FDA = _build_soak_fda()
BOTH_FDAS = {"clock_probe_short": SHORT_FDA, "clock_probe_soak": SOAK_FDA}

FAKE_TOOLKIT = SimpleNamespace(
    flags={},
    semantic_hardware={},
    callable_methods=[],
    hardware_module_ids=CLOCK_PROBE_MODULE_IDS,
    is_backend_authored=True,
)


def _real_hw_caps():
    """Read-only resolution against the REAL hardware_modules/hardware_lib_versions rows for
    modules 5/6/24, via the exact functions `reject_if_hard_errors` itself calls. No writes.
    """
    from db import engine
    from detector_keys import module_detector_channels
    from extlink_keys import module_extlink_signals
    from hw_introspect import toolkit_hw_capabilities
    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        caps = toolkit_hw_capabilities(db, CLOCK_PROBE_MODULE_IDS)
        module_names = set(caps["module_names"])
        detector_keys = (
            {key for entry in module_detector_channels(db, sorted(module_names)) for key in entry["keys"]}
            if module_names else set()
        )
        extlink_keys = (
            {key for entry in module_extlink_signals(db, sorted(module_names)) for key in entry["keys"]}
            if module_names else set()
        )
        return caps, module_names, detector_keys, extlink_keys
    finally:
        db.close()


def test_real_modules_resolve_to_clock_probe_names():
    """Sanity check the fixture itself: modules 5/6/24 really do resolve to the names the
    FDA documents reference. If this fails, the module ids in the plan drifted and every other
    test in this file is testing against the wrong hardware.
    """
    _caps, module_names, _dk, _ek = _real_hw_caps()
    assert module_names == CLOCK_PROBE_MODULE_NAMES


def test_short_fda_passes_the_hard_error_gate():
    """Same gate POST /api/task-definitions runs (fda_validation.collect_hard_errors, the body
    reject_if_hard_errors calls after its own toolkit-by-id lookup)."""
    from fda_validation import collect_hard_errors

    caps, module_names, detector_keys, extlink_keys = _real_hw_caps()
    errors = collect_hard_errors(
        SHORT_FDA, FAKE_TOOLKIT, module_names, caps["module_methods"],
        {t["hw_id"] for t in caps["trigger_sources"]}, set(caps["detector_refs"]),
        detector_keys, extlink_keys,
    )
    assert errors == []


def test_soak_fda_passes_the_hard_error_gate():
    from fda_validation import collect_hard_errors

    caps, module_names, detector_keys, extlink_keys = _real_hw_caps()
    errors = collect_hard_errors(
        SOAK_FDA, FAKE_TOOLKIT, module_names, caps["module_methods"],
        {t["hw_id"] for t in caps["trigger_sources"]}, set(caps["detector_refs"]),
        detector_keys, extlink_keys,
    )
    assert errors == []


def test_every_entry_action_ref_is_a_toolkit_module():
    for name, fda in BOTH_FDAS.items():
        for state_name, state in fda["states"].items():
            for action in state.get("entry_actions", []):
                assert action["ref"] in CLOCK_PROBE_FDA_REFS, (
                    f"{name}/{state_name}: entry_action ref {action['ref']!r} is not a module "
                    f"in the clock FDAs' allowed refs ({sorted(CLOCK_PROBE_FDA_REFS)})"
                )


# ---------------------------------------------------------------------------
# Trap tests -- the point of this file (see module docstring)
# ---------------------------------------------------------------------------

def test_trap1_no_param_reference_anywhere():
    """Trap 1: FDA `{"param": ...}` args are dead on the Pi -- self.params is never assigned."""
    for name, fda in BOTH_FDAS.items():
        blob = json.dumps(fda)
        assert '"param"' not in blob, f"{name}: contains a dead {{'param': ...}} reference"


def test_trap2_no_inc_trial_counter_special():
    """Trap 2: special: INC_TRIAL_COUNTER sends {} and the orchestrator drops it on the missing
    'subject' key -- a GUI-built task definition can never graduate. Neither probe may depend on
    graduation, trial counting, or protocol advancement."""
    for name, fda in BOTH_FDAS.items():
        blob = json.dumps(fda)
        assert "INC_TRIAL_COUNTER" not in blob, f"{name}: references INC_TRIAL_COUNTER (trap 2)"


def test_trap3_condition_operands_are_view_timer_or_literal():
    """Trap 3: {"view": <hardware>} as a condition operand was deployed but never rig-exercised.
    Every condition_tree operand in either FDA must be {"view": "TIMER"} or a plain literal."""
    allowed_operand = {"view": "TIMER"}
    for name, fda in BOTH_FDAS.items():
        for transition in fda["transitions"]:
            condition_tree = transition.get("condition_tree")
            if not condition_tree:
                continue
            for side in ("left", "right"):
                operand = condition_tree[side]
                if isinstance(operand, dict):
                    assert operand == allowed_operand, (
                        f"{name}/{transition['from']}->{transition['to']}: condition operand "
                        f"{operand!r} is neither a literal nor {{'view': 'TIMER'}} (trap 3)"
                    )


def _walk_actions(actions):
    """Flatten nested action lists (an `if` action carries its own `then` list)."""
    for action in actions or []:
        yield action
        for key in ("then", "else"):
            yield from _walk_actions(action.get(key))

# ---------------------------------------------------------------------------
# Licker (MPR121) trigger assignment -- ported from task definition 186
# ---------------------------------------------------------------------------

def test_licker_trigger_fires_on_touch_int_and_reads_the_licker():
    """TOUCH_INT is the IRQ line; LICKER is the I2C detector it tells the task to read.
    Both names must be the hardware_modules names, because the Pi keys _semantic_hw on
    the MODULE name -- task definition 186 said 'MPR121', which is no module at all."""
    for name, fda in BOTH_FDAS.items():
        assignments = fda["trigger_assignments"]
        assert len(assignments) == 1, f"{name}: expected exactly one trigger assignment"
        ta = assignments[0]
        assert ta["trigger_name"] == "TOUCH_INT", f"{name}: trigger is {ta['trigger_name']!r}"
        refs = {a.get("ref") or a.get("source_ref") for a in _walk_actions(ta["actions"])}
        refs.discard(None)
        assert refs == {"LICKER"}, f"{name}: trigger refs {sorted(refs)} -- must be the module name"


def test_licker_reads_before_it_publishes():
    """The regression this port exists to fix. Task definition 186 ordered the actions
    [if, detect_change], and _build_trigger_action_list runs them in list order -- so the
    `if` read pin_number BEFORE detect_change wrote it. Every touch was labelled with the
    PREVIOUS touch's channel and the first touch did nothing at all."""
    for name, fda in BOTH_FDAS.items():
        actions = fda["trigger_assignments"][0]["actions"]
        read_idx = next(
            i for i, a in enumerate(actions)
            if a.get("type") == "hardware" and a.get("method") == "detect_change"
        )
        publish_idx = next(
            i for i, a in enumerate(actions)
            if a.get("type") == "if"
        )
        assert read_idx < publish_idx, (
            f"{name}: detect_change is at index {read_idx} but the `if` that consumes its "
            f"output is at {publish_idx} -- the read must come first"
        )


def test_licker_output_names_match_the_key_template_token():
    """key_template resolves {device_name} from the hardware object; EVERY other token is
    looked up among the task's flags/variables by name (RUNTIME_KEY_TEMPLATE_TOKENS).
    So detect_change's output names and the template must agree, or the view write raises
    KeyError at run time inside the trigger callback."""
    import re as _re
    for name, fda in BOTH_FDAS.items():
        actions = fda["trigger_assignments"][0]["actions"]
        outputs = set()
        for a in actions:
            outputs.update(a.get("output") or [])
        assert outputs, f"{name}: detect_change declares no output"
        assert outputs <= set(fda["variables"]), (
            f"{name}: outputs {sorted(outputs)} are not all declared variables "
            f"{sorted(fda['variables'])}"
        )
        for action in _walk_actions(actions):
            template = action.get("key_template")
            if not template:
                continue
            tokens = set(_re.findall(r"\{(\w+)\}", template))
            unresolved = tokens - {"device_name"} - set(fda["variables"])
            assert not unresolved, (
                f"{name}: key_template {template!r} uses {sorted(unresolved)}, which is "
                f"neither {{device_name}} nor a declared variable"
            )


def test_licker_does_not_touch_the_clock_loop():
    """The probe measures pulse timing. Adding hardware for a human to poke must not let it
    into the state machine, or the timing evidence changes meaning."""
    for name, fda in BOTH_FDAS.items():
        for state_name, state in fda["states"].items():
            for action in state.get("entry_actions", []):
                assert action["ref"] != "LICKER", f"{name}/{state_name} drives the licker"
        for transition in fda["transitions"]:
            blob = json.dumps(transition)
            assert "LICKER" not in blob and "TOUCH_INT" not in blob, (
                f"{name}: transition {transition['from']}->{transition['to']} depends on the licker"
            )
