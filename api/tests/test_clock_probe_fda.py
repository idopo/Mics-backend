"""Pre-flight validation for the clock_probe FDA documents (Phase 31 Plan 12, Task 1).

Both `clock_probe_short` and `clock_probe_soak` are validated here BEFORE any hardware time is
spent on them -- a rejected FDA discovered on the rig costs a session. These tests exercise the
exact same hard-error gate `POST /api/task-definitions` runs (`fda_validation.collect_hard_errors`,
the body `reject_if_hard_errors` calls after its own toolkit lookup) against the REAL
hardware_modules / hardware_lib_versions rows for modules 65/64/6/24 -- read-only queries only,
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
#   65 Opto_Trigger (Digital_Out, lib 8)   64 Nose_Poke_IR (Digital_In, lib 8)
#    6 TIMER (lib 11)                      24 COMPUTE (ComputeOps, lib 45)
CLOCK_PROBE_MODULE_IDS = [65, 64, 6, 24]
CLOCK_PROBE_MODULE_NAMES = {"Opto_Trigger", "Nose_Poke_IR", "TIMER", "COMPUTE"}


def _build_short_fda() -> dict:
    return {
        "version": 2,
        "initial_state": "start",
        "description": (
            "clock_probe_short -- ~10 minute regression asset. Toggles Opto_Trigger at ~1 Hz "
            "so every edge produces two dispatched records (logging_utils.py:97 and task.py:283 "
            "routes) if the module is configured record=True + trigger. Cannot fail the "
            "monotonicity check (C1) on its own -- 10 minutes contains no 32-bit tick wrap; "
            "only clock_probe_soak tests the wrap. Literal args only, TIMER-only conditions, no "
            "trial counter -- see tools/seed_clock_probe.py module docstring for why."
        ),
        "variables": {},
        "trigger_assignments": [],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [1], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [False], "type": "hardware", "method": "set"},
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
        "variables": {},
        "trigger_assignments": [],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [5], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [False], "type": "hardware", "method": "set"},
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
    modules 65/64/6/24, via the exact functions `reject_if_hard_errors` itself calls. No writes.
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
    """Sanity check the fixture itself: modules 65/64/6/24 really do resolve to the names the
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
                assert action["ref"] in CLOCK_PROBE_MODULE_NAMES, (
                    f"{name}/{state_name}: entry_action ref {action['ref']!r} is not a module "
                    f"in the toolkit ({sorted(CLOCK_PROBE_MODULE_NAMES)})"
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
