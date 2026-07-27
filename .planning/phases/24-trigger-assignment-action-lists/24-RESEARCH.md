# Phase 24: Trigger Assignment Action Lists - Research

> ⚠️ **SUPERSEDED IN PART (2026-07-27).** This research doc is the historical record that produced
> the plans; Plans 01/04 are authoritative where they differ. Two specifics below are now WRONG and
> must not be copied into code:
> 1. The `view` action carries **no** `kwargs.pi_timestamp` — the Pi injects `pi_timestamp` from the
>    trigger tick implicitly (Plan 01 `<implicit_pi_timestamp>`). The key prefix is `LICKER`, not
>    `MPR121` (`device_name` × `num_detectors`, Plan 06).
> 2. The trigger context is a **thread-local `self._trigger_ctx` cleared in a `finally`**, NOT plain
>    `self._trigger_level` / `self._trigger_tick` attributes, and `trigger_lock` does NOT make the
>    attribute version safe — it serialises trigger-vs-trigger only, while state bodies run on the
>    stage thread (Plan 04 `<trigger_context_lifetime>`).
> 3. There is **no `handler` field**. This doc predates the 2026-07-26 reversal that dropped the enum
>    outright (24-CONTEXT.md); an entry is `trigger_name` + `actions` and nothing else, and a
>    handler-only entry is a 422 at the API and a `ValueError` on the Pi. This also invalidates §1's
>    `elif assignment.get("actions"):` snippet — `actions` is not an extra branch on a handler chain,
>    it is the only path, and the chain itself is deleted (Plan 04).
> 4. `trigger_name` is not free text: it must name hardware whose class sets `is_trigger` (the
>    predicate `init_hardware` uses before `assign_cb`), reported in HANDSHAKE as `trigger_sources`
>    and rendered as a dropdown (TRIGA-15, Plan 08).

**Researched:** 2026-07-26
**Domain:** Pi FDA runtime (action-callable dispatch) + FastAPI backend validation + React task-editor
**Confidence:** HIGH (all findings verified by direct code read on both `~/pi-mirror/` and `~/mics-backend/`, not from training-data assumptions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**The reference case defines "done."** `learning_cage.py:162 detectedLick` is the acceptance target:
```python
pin_number, level = self.hardware['I2C']['MPR121'].detect_change()
if pin_number is None:
    return
device_name = self.hardware['I2C']['MPR121'].device_name
device_str = f'{device_name}{pin_number}'
self.view.view[device_str].set(level, pi_timestamp=tick)
```
**Success gate:** this behaviour runs on the rig from a UI-assigned action list, with **no `detectedLick` method in the task class.**

**Backward compatibility is required.** Task definitions already stored in the DB must keep loading and running. `apply_trigger_assignments` already documents the contract that an absent/empty `trigger_assignments` leaves `self.triggers` untouched — that must survive.

**Existing Pi unit tests must keep passing.** `~/pi-mirror/tests/test_trigger_assignments.py` (12 KB) covers the current handler behaviour.

**Value-capture must be consistent with Phase 23.** If this phase introduces a way to capture a method's return value into a named slot, it must use the same shape Phase 23 will use for `variables` / `compute` `output`. Two competing mechanisms for "put a value somewhere and read it back" is the outcome to avoid. Phase 23 is planned but not executed, so it can still be aligned to whatever this phase lands on — but the decision must be made deliberately, in this phase, and written down.

**Verification posture (project hard rule).** Backend and React are agent-driven inside the docker compose stack. **Pi-side work is edit-in-mirror only** (`~/pi-mirror/`). Every Pi `<verify>` block returns commands for the **user** to run. The agent never runs git on the Pi, never starts/stops the pilot process, and never runs Python on the Pi.

### Claude's Discretion

Not explicitly separated in CONTEXT.md — the entire `<open_decisions>` block (4 questions) is Claude's-discretion-with-justification territory: the planner (informed by this research) must pick one answer per question and write down why, not present a menu.

### Deferred Ideas (OUT OF SCOPE)

- Phase 23 `compute` primitives and the `variables` registry proper — separate phase; only the *shape* of value capture is coordinated here.
- New trigger *sources* / trigger creation from the UI.
- Any change to the unconditional `Hardware_Event` logging path in `execute_trigger()`.
- Rewriting `execute_trigger` dispatch semantics in `task.py`.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| TRIGA-01 | Trigger `actions` list uses same schema as `entry_actions`, built via `_build_action_callable` | Confirmed dispatch signature at `mics_task.py:525-575`; recommended wiring in Architecture Patterns §1 |
| TRIGA-02 | Composed trigger callable declares `level`/`tick`; `_resolve_arg` gains `{"trigger": ...}` form | `execute_trigger`'s `inspect.signature` contract read at `task.py:268-298`; wiring design in Architecture Patterns §2 |
| TRIGA-03 | New `view` action type writes `self.view.view[key]`, supports `pi_timestamp` | `check_for_detectors`/`init_flags` asymmetry confirmed at `mics_task.py:241-280`; design + Tracker-vs-Hardware pitfall in Architecture Patterns §3 and Common Pitfalls |
| TRIGA-04 | Return-value capture shape-compatible with Phase 23 `variables`/`compute` `output` | Phase 23's exact mechanism read from `23-01-PLAN.md`; recommendation to build `variables` registry now, in Open Decision 4 |
| TRIGA-05 | `detectedLick`'s dynamic-tracker-naming pattern expressible from UI | Real `detect_change()` return shape read from `i2c.py:831-842`; recommendation + justification in Open Decision 1 |
| TRIGA-06 | Backward compat: stored definitions + existing handlers keep working; Pi tests pass | Additive `actions` field recommendation in Open Decision 2 |
| TRIGA-07 | Backend validates `trigger_assignments` on save, returns 422 | Existing soft- vs hard-validation split found in `api/routers/toolkits.py:661-809` vs `:892-925`; recommendation in Open Decision 4 |
| TRIGA-08 | `fda_utils.py` ref scanner covers trigger hardware refs | Current scanner scope confirmed (`states.entry_actions` only) at `fda_utils.py:1-38`; extension plan in Architecture Patterns §5 |
| TRIGA-09 | Trigger panel hosts same `ActionEditor`/`ArgInput` as state body | Component prop contracts read from `ActionEditor.tsx`, `StateBodyPanel.tsx`; reuse plan in Architecture Patterns §4 |
| TRIGA-10 | Allowed handler/action list single-sourced | Divergence points enumerated (3 Pi/React copies) in Common Pitfalls; realistic cross-language recommendation in Open Decision-adjacent note |
| TRIGA-11 | Rig proof: lick detection from UI action list, no `detectedLick` method; invalid config rejected at save | End-to-end wiring in Architecture Patterns; SEMANTIC_HARDWARE prerequisite flagged as a Pitfall/Wave-0 item |

</phase_requirements>

## Summary

This phase does not add a new external library or framework — it extends an already-working internal
DSL (the FDA-JSON-v2 action vocabulary) to a second call site (hardware triggers) that today only has
two hard-coded Python handlers. All the load-bearing logic already exists and is well-factored:
`_build_action_callable` (`mics_task.py:525`) is a clean, recursive, zero-arg-callable builder that
already validates refs at load time and already supports `if`-nesting. The job is: (1) let
`apply_trigger_assignments` build a trigger's callback through that same function instead of its own
two special-cased builders, (2) close four small, concrete gaps between what that vocabulary can
express and what `detectedLick` actually does, (3) validate the new `trigger_assignments.actions`
shape on the backend with a hard 422 (a validation posture that does not exist anywhere in `api/`
today for `trigger_assignments`), and (4) host the existing `ActionEditor` React component inside the
existing `TriggerAssignmentPanel` instead of building a second, parallel action editor.

The four gaps are real, and one of them is more interesting than CONTEXT.md's framing suggests: the
existing `touch_detector` trigger handler (`_build_touch_detector_callback`, `mics_task.py:1089`) and
its own unit test both model `MPR121.detect_change()` as returning a **list of per-channel values**.
The actual, running `MPR121.detect_change()` implementation (`hardware/i2c.py:831`) returns a single
**`(changed_index, new_value)` tuple** — exactly what `detectedLick` unpacks. This means the
already-shipped `touch_detector` handler has never matched real hardware behavior; it is validated
only against a mock that encodes the wrong mental model. This is decisive evidence for Open Decision 1:
option (c) ("keep `touch_detector` built-in") is not a safe fallback — it is standing on a latent bug —
and option (a) (generic return-value capture + a new `view` action + key templating) is the only path
that is both faithful to the reference case and does not require first fixing unrelated hardware-driver
code.

The other three gaps are: no action type can write into a `self.view.view` Tracker (the touch-channel
trackers created by `check_for_detectors` live only there, never in `self.flags`); `_hw_call` silently
discards every hardware call's return value; and `_resolve_arg` has no way for an action to read the
trigger invocation's own `level`/`tick` context, because the composed callable it needs to declare those
parameter names is not zero-arg the way the individual action callables are.

**Primary recommendation:** Build the `variables` top-level registry (generic `Tracker` in both
`self.flags` and `self.view.view`, per Phase 23's already-designed shape) *now*, in this phase, as the
one value-capture mechanism; add an optional `output` field (string or list-of-strings, for
tuple-unpacking) to `hardware`/`method` actions that writes into it; add a new `view` action type with
`{name}`-token key templating for writing into *pre-existing* view keys (the touch-channel trackers);
add `{"trigger": "level"|"tick"}` to `_resolve_arg`, fed by a per-invocation instance-attribute stash set
by the composed trigger callable (safe under the existing `trigger_lock`); make `trigger_assignments[*].actions`
strictly additive alongside the existing `handler` enum; and give trigger validation a genuinely new,
hard-422 code path in the backend (the existing `_validate_task_definition` hook is soft-by-design and
must not be repurposed for this).

## Architecture Patterns

### Recommended data shape (FDA-JSON-v2 additions)

```jsonc
{
  "variables": { "pin_number": {}, "level": {} },   // NEW top-level registry (Phase 23's shape, built now)
  "trigger_assignments": [
    {
      "trigger_name": "TOUCH_INT",
      "actions": [                                    // NEW — same schema as entry_actions
        {
          "type": "hardware", "group": "I2C", "ref": "MPR121", "method": "detect_change",
          "args": [], "output": ["pin_number", "level"]   // NEW: list = positional tuple-unpack capture
        },
        {
          "type": "if",
          "condition": { "left": {"flag": "pin_number"}, "op": "!=", "right": null },
          "then": [
            {
              "type": "view",                          // NEW action type
              "key_template": "MPR121{pin_number}",     // NEW: {name} tokens resolved from flags/variables
              "value": {"flag": "level"},
              "kwargs": { "pi_timestamp": {"trigger": "tick"} }   // NEW _resolve_arg form
            }
          ],
          "else": []
        }
      ]
    }
  ]
}
```

This is a 1:1 executable translation of `detectedLick`, expressed entirely in the existing/extended
action vocabulary, requiring zero Python method on the task class.

### §1 — Trigger callback built through `_build_action_callable`, not a special handler

Current: `apply_trigger_assignments` (`mics_task.py:1037`) has an `if/elif` chain that special-cases
`touch_detector`/`digital_input` via two dedicated builder methods (`:1089`, `:1139`). Add one more
branch:

```python
elif assignment.get("actions"):
    callback = self._build_trigger_action_list(trigger_name, assignment["actions"])
```

`_build_trigger_action_list` should:
1. Build `action_callables = [self._build_action_callable(a) for a in actions]` — this is the whole
   point of TRIGA-01: it is *the same call* `_build_state_method` makes at `mics_task.py:645`, so every
   existing action type (`hardware`/`flag`/`timer`/`special`/`method`/`if`) works identically in a
   trigger, with the same load-time `ValueError` on bad refs (already true for state bodies; now also
   true for triggers, which today only validate at `_build_touch_detector_callback`/`_build_digital_input_callback`
   call time for their two special cases).
2. Return a composed callable (see §2) rather than looping and calling each in the outer scope, so the
   `level`/`tick` context can be stashed once per invocation.

### §2 — `level`/`tick` wiring: named params on the composed callable, instance-attribute handoff to `_resolve_arg`

`execute_trigger` (`task.py:268-298`) does:
```python
sig = inspect.signature(trig)
if "level" in sig.parameters and "tick" in sig.parameters:
    trig(level=level, tick=tick)
elif "level" in sig.parameters: trig(level=level)
elif "tick" in sig.parameters: trig(tick=tick)
else: trig()
```
`inspect.signature` inspects the *declared parameter names*, not whether the function actually uses
them — a `**kwargs` catch-all would NOT satisfy `"level" in sig.parameters` (it shows up as a single
`VAR_KEYWORD` parameter named `kwargs`). The composed trigger callable must therefore explicitly declare
`level=None, tick=None` as named parameters:

```python
def _build_trigger_action_list(self, trigger_name, actions):
    action_callables = [self._build_action_callable(a) for a in actions]

    def _run_trigger_actions(level=None, tick=None, _callables=action_callables, _self=self):
        _self._trigger_level = level
        _self._trigger_tick = tick
        for fn in _callables:
            fn()
    return _run_trigger_actions
```

The inner `action_callables` remain zero-arg (unchanged contract with `_build_action_callable`/`_build_if_action`).
An action that needs the invocation context reads it via a new `_resolve_arg` branch:
```python
if "trigger" in arg:
    key = arg["trigger"]   # "level" or "tick"
    return getattr(self, f"_trigger_{key}", None)
```
**Thread-safety:** ⚠️ **this paragraph was wrong — see the SUPERSEDED note at the top.**
`process_queue` (`task.py:262-266`) serialises trigger-vs-trigger only; state bodies run on the stage
thread, and nothing cleared the stash between invocations, so a fired trigger's tick leaked into
later state-body `view` writes. The shipped design is a thread-local context cleared in a `finally`
(Plan 04 `<trigger_context_lifetime>`).

### §3 — New `view` action type: target is a *pre-existing* Tracker, not a new variable

`check_for_detectors` (`mics_task.py:241-266`) creates per-channel touch trackers via
`self.view.add_Tracker(device_str, curr_vals[i])` — these live **only** in `self.view.view`, never in
`self.flags`. Contrast `init_flags` (`:268-280`), which writes the **same object** into both dicts. No
existing action type (`hardware`/`flag`/`timer`/`special`/`method`) can reach a view-only key. Add:

```python
elif atype == "view":
    key_template = action.get("key_template", action.get("key", ""))
    value_spec = action.get("value")
    kwargs_spec = action.get("kwargs", {})
    def _view_call(_tmpl=key_template, _value=value_spec, _kwargs=kwargs_spec, _action=action):
        key = self._resolve_key_template(_tmpl)
        tracker = self.view.view[key]
        value = self._resolve_arg(_value)
        kwargs = {k: self._resolve_arg(v) for k, v in _kwargs.items()}
        tracker.set(value, **kwargs)
    return _view_call
```
`_resolve_key_template` substitutes `{name}` tokens against `self.flags` (covers both toolkit `FLAGS`
and the new `variables` registry, since both live there — see §5/Open Decision 4):
```python
import re
def _resolve_key_template(self, template: str) -> str:
    def _sub(m):
        name = m.group(1)
        if name not in self.flags:
            raise KeyError(f"_resolve_key_template: '{name}' not in self.flags. Available: {list(self.flags.keys())}")
        return str(self.flags[name].value)
    return re.sub(r"\{(\w+)\}", _sub, template)
```
Static parts of the template (e.g. `"MPR121"` in `"MPR121{pin_number}"`) match `device_name` exactly
because `check_for_detectors` builds tracker keys as `f"{detector.device_name}{i}"` — the researcher
supplies the literal prefix in the UI (they already know their hardware's `device_name`), so no new
device-name resolution machinery is needed.

### §4 — UI: host `ActionEditor` inside `TriggerAssignmentPanel`

`ActionEditor` (`web_ui/react-src/src/components/ActionEditor.tsx:139`) has a self-contained prop
contract already used identically by `StateBodyPanel` (`:132-138`) and recursively by itself via
`IfActionEditor` (`components/IfActionEditor.tsx:27`):
```ts
interface Props {
  action: FdaAction
  toolkit: ToolkitRead | null
  hwModules: HardwareModule[]
  taskDefId?: number
  versionStamp?: string
  onChange: (updated: FdaAction) => void
}
```
`TaskEditor.tsx` already fetches `hwModules`, `numId` (taskDefId), and `versionStamp` at the top level
and passes them into `StateBodyPanel` at `:720-728`; the exact same values thread into
`TriggerAssignmentPanel` at `:739-745` today (minus `hwModules`/`taskDefId`/`versionStamp`, which the
panel doesn't currently accept). The concrete change: extend `TriggerAssignmentPanel`'s `Props` to match,
and for each assignment render a small `actions: FdaAction[]` list the same way `StateBodyPanel` renders
`entry_actions` (`:106-150`) — add/remove/reorder buttons, one `<ActionEditor>` per entry. Because the
trigger panel is *always visible* at the bottom of the right rail regardless of what's selected
(`TaskEditor.tsx:735-747`), and a full action list can be visually heavy, keep each assignment's action
list collapsed-by-default with an expand toggle (a UI-only affordance; no prop contract changes needed
beyond adding one).

**New UI gap:** `ArgInput` (`ArgInput.tsx`) currently supports exactly three arg modes — `literal` /
`param` / `flag` (`detectMode`, `:30-36`) — there is no `trigger` mode for `{"trigger": "level"|"tick"}`.
This form only makes sense inside a trigger's action list (never in a state body), so add a 4th mode
gated by a new optional prop, e.g. `allowTriggerContext?: boolean`, passed `true` only from the
trigger-hosted `ActionEditor` call site (`ActionEditor` already receives all its props from its parent,
so this threads through cleanly: `TriggerAssignmentPanel` → `ActionEditor` → `ArgInput`).

### §5 — Backend: reference-scanning and validation extension points

`scan_fda_for_refs` (`api/fda_utils.py:5-19`) walks `fda_json["states"][*]["entry_actions"]` only —
`trigger_assignments` is invisible to it today (confirmed: it is not referenced anywhere in
`fda_utils.py`, and a full-repo `grep -rn "trigger" api/` before this research returns only the four
existing `trigger_assignments` reads in `toolkits.py`'s POST/PUT/push handlers, none of which validate
its *contents*). TRIGA-08 requires extending the scanner to also walk each
`trigger_assignments[*].actions` (and its nested `if` branches) through the **same** `_scan_actions`
recursion already used for states — this is a pure extension, not a rewrite:
```python
def scan_fda_for_refs(fda_json: dict) -> list[dict]:
    results = []
    ...  # existing states loop, unchanged
    for i, ta in enumerate(fda_json.get("trigger_assignments") or []):
        results.extend(_scan_actions(f"trigger[{ta.get('trigger_name','?')}]", ta.get("actions") or []))
    return results
```
`_scan_actions` already recurses into `if` action branches (`fda_utils.py:35-37`), so nested guards
inside a trigger's action list are covered for free.

**Validation has two existing, structurally different code paths in `api/routers/toolkits.py` — do not
conflate them:**

| Path | Function | Trigger | Behavior on error | Used by |
|---|---|---|---|---|
| Soft / informational | `_validate_task_definition` (`:661-757`) | Every `PUT /task-definitions/{id}` | Sets `validation_status='broken'` + `validation_message`, returns **200** | State-body hardware-lib-version drift detection (Phase 12) |
| Hard / rejecting | `_validate_fda_against_toolkit` (`:892-925`) | `POST /task-definitions/{id}/push` only | Raises **`HTTPException(422, ...)`** | Push-to-pilot gate only — never runs on save |

TRIGA-07 explicitly wants **422 on save**. That is neither of the above verbatim: it needs the *hard*
posture of `_validate_fda_against_toolkit` but triggered from the *save* path (`PUT`), which today only
runs the soft check. Recommendation: add a new function (see Open Decision 4) called from inside
`update_task_definition` (`:760-809`) **before** the DB write, that raises `HTTPException(422, ...)` on
hard trigger-assignment errors (unknown handler/action type, `hardware_ref` unresolved, `method` not in
`CALLABLE_METHODS`, referenced view/flag key not declared). Leave the existing soft state-body check
untouched — do not change its return-200 semantics, since other flows (broken-badge UI, Phase 12
hw-lib-version diffing) depend on it staying soft.

**File-size guardrail:** `api/routers/toolkits.py` is already 925 lines (hard limit is 500 per project
coding standards) — this is pre-existing debt. Phase 23's own plan (`23-01-PLAN.md` references a sibling
module) already establishes the pattern: put new validation logic in a new `api/fda_validation.py`
module, imported into `toolkits.py` as "import + call only." Recommend Phase 24 create this file now
(Phase 23, which runs after, will then extend it rather than needing to invent its own).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Action execution (hardware/flag/timer/special/method/if) in a trigger | A second, parallel action interpreter for triggers | `self._build_action_callable` (`mics_task.py:525`), unchanged | It already recurses, already validates refs at load time, and is the entire point of TRIGA-01 — a second interpreter reintroduces exactly the divergence TRIGA-10 is trying to kill |
| Value capture ("put a method's return value somewhere, read it later") | A trigger-only capture mechanism (e.g. a dict on `self` keyed ad hoc) | The `variables` registry shape from Phase 23 (`23-01-PLAN.md` Task 2) — generic `Tracker` in both `self.flags` and `self.view.view` | CONTEXT.md is explicit: two competing "put a value somewhere" mechanisms is the outcome to avoid; Phase 23's shape is already fully designed and not yet built, so there is nothing to migrate |
| Trigger action editing UI | A second action-editing form inside `TriggerAssignmentPanel` | `ActionEditor.tsx` + `ArgInput.tsx`, hosted with the same props `StateBodyPanel` already passes | TRIGA-09 explicit requirement; the component is already prop-driven and reused recursively (`IfActionEditor`) — it is designed to be hosted, not state-body-specific |
| Allowed-type enforcement | A frontend-only "assume the list is right" approach | Backend hard-422 validation (new `api/fda_validation.py`) as the actual enforcement point | Given four separate runtimes (Pi, Pi CLI tool, Python API, TypeScript SPA) a single shared constant is not achievable without cross-language codegen (out of scope) — the realistic fix is making the backend the enforcement point so drift fails fast at save time instead of silently at Pi session start |

**Key insight:** every piece of machinery this phase needs except four small additions
(`view` action type, `output` capture + `variables` registry, `{"trigger": ...}` arg form, key
templating) already exists and already works for state bodies. The temptation to build "trigger-specific"
versions of any of this should be resisted — it is precisely what produced the current
`apply_trigger_assignments`/`_build_touch_detector_callback` duplication this phase exists to retire.

## Common Pitfalls

### Pitfall 1: `_build_touch_detector_callback` is validated against a mock that doesn't match real hardware
**What goes wrong:** Trusting the existing `touch_detector` handler (or its test) as a model for how
`MPR121.detect_change()` behaves.
**Why it happens:** `_build_touch_detector_callback` (`mics_task.py:1118-1130`) does
`changed = hw.detect_change(); for i in range(hw.num_detectors): ... changed[i]` — treating `changed` as
a per-channel array. Its own unit test (`test_trigger_assignments.py:326`) mocks
`mock_hw.detect_change.return_value = [1, 0]` to match. But the real `MPR121.detect_change()`
(`hardware/i2c.py:831-842`) returns a single `changes[0] if changes else (None, None)` — a 2-tuple
`(changed_index, new_value)`, exactly what `detectedLick` unpacks (`pin_number, level = ...detect_change()`).
`changed[i]` for `i >= 2` on a 2-tuple raises `IndexError`, which the handler silently swallows
(`except (IndexError, TypeError): pass`) — so on real hardware with `num_detectors > 1` this handler
would silently update at most 2 of N channels, and only by accident (index 0/1 happening to alias
tuple position 0/1).
**How to avoid:** Do not extend or copy `_build_touch_detector_callback`'s mental model. Build the
reference case's semantics fresh from the real `detect_change()` contract (Architecture Patterns §1/§5,
Open Decision 1).
**Warning signs:** Any new code that indexes a hardware method's return value with `for i in range(n): x[i]` without first confirming the method's actual return shape in `hardware/i2c.py` (or the relevant hardware module) directly.

> **⚠ ORCHESTRATOR CORRECTION (2026-07-26, from the user — overrides any contrary reading of this pitfall):**
>
> 1. **`hardware/i2c.py` MUST NOT BE CHANGED.** Not `detect_change()`, not `Touch_Detector`, not any
>    signature. Any design requiring an edit there is disqualified.
> 2. **The 2-tuple return is CORRECT AND INTENTIONAL, not a bug.** There is deliberately no hardware
>    object per electrode: four electrodes share ONE `i2c.Touch_Detector` and ONE GPIO interrupt
>    (`pilot/prefs.json`: `MPR121 {num_detectors:4, device_name:"LICKER"}` + `TOUCH_INT {pin:8}`). The
>    interrupt says *something* was touched; the I2C query says *which electrode*. Per-electrode
>    abstraction is created later in the **view** by `check_for_detectors` (`mics_task.py:241-266`).
>    This is the project's deliberate standardization layer.
> 3. **The defect is confined to `_build_touch_detector_callback` and its unit test** — they misread a
>    correct hardware contract. Fix the handler and the test; never the hardware.
> 4. **Open Decision 1 option (b) ("per-channel hardware API with fixed keys") is RULED OUT** — it would
>    invent per-electrode hardware objects, inverting the standardization above and requiring an
>    `i2c.py` edit. Do not propose it.
>
> Full rationale in `24-CONTEXT.md` → "The touch architecture is intentional".

### Pitfall 2: `self.view.view` is a heterogeneous dict — not every entry is a `Tracker`
**What goes wrong:** A `view` action's `key_template` resolves to a key that maps to a `Hardware`
instance (registered by `load_fda_from_json` at `mics_task.py:773-774`:
`self.view.view[friendly_name] = hw` for every SEMANTIC_HARDWARE entry) rather than a `Tracker`.
Calling `.set(value, pi_timestamp=...)` on that object dispatches to whatever `.set()` the specific
hardware subclass defines — which may not accept `pi_timestamp`, or worse, may **physically actuate**
the device (many `Hardware.set()` implementations open valves / drive GPIO).
**Why it happens:** `self.view.view` is deliberately shared between Trackers (flags, `variables`, touch
trackers) and raw hardware objects (for transition reads like `{"view": "some_semantic_name"}`) — see
`View.get_value` (`core/View.py:43-44`), which just calls `.get_state()`/whatever the object exposes.
**How to avoid:** Scope the `view` action's key options in the UI to known Tracker-backed keys only
(touch-channel keys from `check_for_detectors`, `variables` registry names, `FLAGS` names) — never
offer `SEMANTIC_HARDWARE` friendly names as `view`-action targets. At runtime, defensively check
`isinstance(tracker, Tracker)` before calling `.set()` and raise a clear error otherwise, since dynamic
`key_template` values can't always be statically checked at load time.
**Warning signs:** A `view` action whose `key_template` resolves to a SEMANTIC_HARDWARE name.

### Pitfall 3: `learning_cage` has no `SEMANTIC_HARDWARE` entry for `MPR121` — the rig proof cannot resolve the hardware ref without one
**What goes wrong:** Assuming any UI-built `{"type": "hardware", "ref": "MPR121", ...}` action resolves
automatically, the way it does for backend-authored toolkits with `hardware_module_ids`.
**Why it happens:** `learning_cage` (`tasks/learning_cage.py:24-125`) is a classic/HANDSHAKE-registered
toolkit with no `SEMANTIC_HARDWARE` class attribute at all. `_build_action_callable`'s hardware branch
(`mics_task.py:538-550`) resolves via `self.hardware[group][ref]` **only if** the action carries a
`"group"` key (direct-ref / GUI-built format); otherwise it falls back to
`self._semantic_hw[ref]` (legacy semantic format), which raises `KeyError` for any ref not declared in
`SEMANTIC_HARDWARE`. The React `ActionEditor` (`:340-349`) only offers a free-text ref input for
non-backend-authored toolkits (no dropdown, and it never sets a `"group"` key — `FdaAction` has no
`group` field in `types/index.ts:230-241`) — so today there is no UI path that produces a resolvable
hardware ref for this toolkit's MPR121 without a class-level change.
**How to avoid:** Add one line to `learning_cage`'s (or `mics_task`'s) Python source in the Pi mirror:
`SEMANTIC_HARDWARE = {"MPR121": ("I2C", "MPR121")}` (or similar), matching the project's existing,
established convention ("SEMANTIC_HARDWARE defined in code by developer" — `STATE.md` Decisions Made
table). Deploy + restart so the next HANDSHAKE carries the updated dict into `task_toolkits.semantic_hardware`,
after which the existing `ActionEditor` hardware-ref dropdown (`:341-345`) picks it up with zero new
plumbing. This is a small, necessary **prerequisite task**, not a new mechanism — sequence it early
(Wave 0/1) since the rig proof (TRIGA-11) cannot exercise anything without it.
**Warning signs:** `ValueError`/`KeyError` from `_semantic_hw['MPR121']` at load time on the Pi, or the
ActionEditor showing a free-text input instead of a dropdown for the hardware ref.

### Pitfall 4: Soft vs. hard validation are structurally different functions — don't repurpose the soft one
**What goes wrong:** Adding trigger-assignment checks into `_validate_task_definition`
(`toolkits.py:661-757`) and expecting a 422. That function's caller (`update_task_definition`, `:797-799`)
always stores whatever status it returns and always responds 200 — it was designed as a soft,
informational drift-detector (Phase 12's hw-lib-version-change badge), not a save-time gate.
**Why it happens:** It is the only validation hook currently wired into the PUT path, so it's the
obvious (wrong) place to reach for.
**How to avoid:** Add a distinct, new function (Architecture Patterns §5) that raises `HTTPException(422)`
directly, called from `update_task_definition` before the DB write — modeled on
`_validate_fda_against_toolkit` (`:892-925`), which already has the right (hard) posture, just wired
to the wrong endpoint (`push`, not `PUT`).
**Warning signs:** A test asserting 422 on `PUT /task-definitions/{id}` failing with 200 + `validation_status: "broken"` in the response body instead.

### Pitfall 5: Late-binding closures in the trigger-assignment loop
**What goes wrong:** `apply_trigger_assignments` iterates `assignments` in a `for` loop; if the new
`actions`-based branch captures loop variables (`trigger_name`, `assignment`) by reference instead of by
default-argument, every built trigger callback silently closes over the *last* loop iteration's values.
**Why it happens:** Classic Python closure-in-a-loop bug. The existing code already avoids this for
`_build_touch_detector_callback`/`_build_digital_input_callback` because those are separate function
calls per iteration (each call creates a fresh local scope) — but a new inline closure written directly
in the loop body would not get that protection automatically.
**How to avoid:** Match the existing codebase convention exactly: build the composed callable via a
helper method call (`self._build_trigger_action_list(trigger_name, actions)`) so each iteration gets a
genuinely fresh closure, or use explicit default-argument capture (`_trigger_name=trigger_name`) as done
throughout `_build_action_callable` (e.g. `mics_task.py:546`, `554`, `567`) and the DNF transition builder
(`:842`, noted in `STATE.md`'s Phase 15 decisions: "single `_dnf` callable with default arg capture to
avoid late-binding closures in loop").
**Warning signs:** All trigger assignments firing the same (last-declared) action list regardless of which pin fired.

## Code Examples

### `_resolve_arg` extension (TRIGA-02)
```python
# Source: mics_task.py:401-430, extended
def _resolve_arg(self, arg):
    if isinstance(arg, dict):
        if "param" in arg: ...          # unchanged
        if "flag" in arg: ...           # unchanged
        if "now" in arg: ...            # unchanged
        if "trigger" in arg:            # NEW
            key = arg["trigger"]        # "level" or "tick"
            if key not in ("level", "tick"):
                raise ValueError(f"_resolve_arg: unknown trigger context key '{key}'. Allowed: level, tick")
            return getattr(self, f"_trigger_{key}", None)
        if "view" in arg:                # NEW (also needed by Phase 23's variable-as-arg path — build once, here)
            key = arg["view"]
            return self.view.view[key].value
    return arg
```

### Existing composed-trigger-callable contract this phase must satisfy (`task.py:268-298`, unchanged)
```python
# Source: task.py:285-298 (read-only reference — do not modify per CONTEXT.md deferred scope)
try:
    triggers = self.triggers[pin] if isinstance(self.triggers[pin], list) else [self.triggers[pin]]
    for trig in triggers:
        sig = inspect.signature(trig)
        if "level" in sig.parameters and "tick" in sig.parameters:
            trig(level=level, tick=tick)
        elif "level" in sig.parameters:
            trig(level=level)
        elif "tick" in sig.parameters:
            trig(tick=tick)
        else:
            trig()
except KeyError:
    self.logger.debug(f"No valid trigger for {pin}")
```

### `variables` registry instantiation (Phase 23's already-designed shape, to build now — TRIGA-04)
```python
# Source: 23-01-PLAN.md Task 2 (design, not yet implemented) — mirrors init_flags() (mics_task.py:268-280)
# Place in load_fda_from_json, after _semantic_hw is built, BEFORE state methods/transitions are built.
for name in definition.get("variables", {}):
    if name in self.flags:
        raise ValueError(f"load_fda_from_json: variable '{name}' collides with an existing flag")
    tracker = Tracker(info_type=name, initial_value=None, event_dispatcher=self.event_dispatcher)
    self.flags[name] = tracker
    self.view.view[name] = tracker   # SAME object in both — not a copy
```

### `output` capture on a hardware action, single- and multi-value forms (TRIGA-04/05)
```python
# Source: extends _hw_call at mics_task.py:546-550
def _hw_call(_hw=hw, _method=method, _action=action):
    args   = [self._resolve_arg(a) for a in _action.get("args", [])]
    kwargs = {k: self._resolve_arg(v) for k, v in _action.get("kwargs", {}).items()}
    result = getattr(_hw, _method)(*args, **kwargs)
    output = _action.get("output")
    if output is None:
        return
    if isinstance(output, list):        # positional tuple/list unpack — covers detect_change()'s (idx, level)
        for name, value in zip(output, result):
            self.flags[name].set(value)
    else:                                # single-value capture
        self.flags[output].set(result)
return _hw_call
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Trigger callbacks are hard-coded Python methods assigned in `__init__` (`self.triggers['TOUCH_INT'] = [self.detectedLick]`) | `trigger_assignments` in FDA JSON with a fixed `handler` enum (`default`/`log_only`/`touch_detector`/`digital_input`) | Plan 03 (pre-dates this phase; already shipped, never exercised end-to-end per CONTEXT.md) | Two hard-coded handlers cover exactly two hardware shapes; anything else (like the reference case) still requires a Python method |
| Fixed handler enum | UI-assembled `actions` list using the same vocabulary as `entry_actions` | This phase (24) | Any hardware/flag/timer/method/if combination expressible in a state body becomes expressible in a trigger, with zero Python |
| Legacy list-of-lambdas idiom, still present in non-`mics_task` tasks (`gonogo.py:161-196`: `self.triggers['C'] = [lambda: self.respond(True), self.hardware['PORTS']['C'].open]`) | N/A — out of scope | N/A | Confirms the *shape* (`self.triggers[pin]` = list of zero-arg-or-`level`/`tick`-aware callables) predates and is independent of the JSON-driven mechanism; this phase's callables must fit that same shape, nothing more |

**Deprecated/outdated:** None yet — `handler` enum values are being kept (Open Decision 2, additive), not deprecated, for backward compatibility.

## Open Questions

### 1. Dynamic target naming (TRIGA-05) — **Recommendation: Option (a)**
Return-value capture (`output`, string or list form) + new `view` action type + `{name}` key templating.
**Why not (b):** A per-channel hardware API (`read_channel(i)`) would require N assignments instead of
one and would have to poll every channel per interrupt instead of reading only the channel that
changed — a behavior change from the interrupt-driven original, and still a Pi hardware-driver change.
**Why not (c):** `_build_touch_detector_callback` — the existing "keep it built-in" option — is
demonstrably built on a return-shape assumption (`changed[i]` for a per-channel array) that does not
match the real `MPR121.detect_change()` (`hardware/i2c.py:831-842`, a single `(index, value)` tuple);
adopting it as the reference-case path would mean shipping a second latent bug rather than removing
the first. Option (a) is also the only one of the three that does not leave the reference case's core
logic still expressed in Python.

### 2. Additive or replacement (TRIGA-06) — **Recommendation: Additive**
`trigger_assignments[*]` gains an optional `actions` field; the existing `handler` enum
(`default`/`log_only`/`touch_detector`/`digital_input`) is untouched and continues to work exactly as
`apply_trigger_assignments`'s current `if/elif` chain implements it. When `actions` is present (and
non-empty) for an assignment, build the callback via `_build_trigger_action_list` instead of the
handler branch; `handler` becomes advisory/unused for that entry (front-end can leave it at `default`).
**Why:** the "absent/empty leaves `self.triggers` unchanged" contract is a locked backward-compat
requirement, and there is no way to enumerate how many stored `task_definitions` rows use
`touch_detector`/`digital_input` without querying the live database (out of scope for static research);
additive costs nothing and forecloses no future replacement/migration decision.

### 3. `level`/`tick` wiring (TRIGA-02) — **Recommendation: named-param composed callable + instance-attribute handoff**
See Architecture Patterns §2. This is the only design compatible with `execute_trigger`'s
`inspect.signature`-based dispatch (`task.py:285-296`), which this phase is explicitly barred from
modifying (CONTEXT.md: "Out of scope... Rewriting `execute_trigger` dispatch semantics").

### 4. Where validation lives / value-capture shape (TRIGA-04, TRIGA-07) — **Recommendation: build `variables` now; validate with a new hard-422 function in a new `api/fda_validation.py`**
Phase 23's design (`23-01-PLAN.md`, not yet executed) already fully specifies the `variables` registry:
a top-level `"variables": {"<name>": {}}` dict, each instantiated as a generic `Tracker` shared between
`self.flags` and `self.view.view`. Since the stabilization plan sequences **24 before 23**
(`STATE.md`: "Execution order agreed 2026-07-26: 24 → 23 → review → 18 → Open Ephys"), Phase 24 is the
first phase that actually needs this infrastructure — so Phase 24 should build it (Pi-side: the
`variables`-instantiation loop; load-time collision check against `FLAGS`), and Phase 23's later
`compute` action will simply find it already there. This directly satisfies CONTEXT.md's instruction
that the value-capture decision be made "deliberately, in this phase, and written down": the decision is
*build the registry now, add `output` to hardware/method actions, let Phase 23 add `compute` on top of
the same registry later.*

For validation: create `api/fda_validation.py` (new sibling module to `fda_utils.py`, following the
precedent Phase 23's plan already establishes for the same reason — `toolkits.py` is oversized at 925
lines). Add a `validate_trigger_assignments(fda_json, toolkit) -> list[str]` function with the hard
posture of `_validate_fda_against_toolkit` (`toolkits.py:892-925`), called from `update_task_definition`
(`:760-809`) before the DB write, raising `HTTPException(422, detail={"errors": [...]})` on any hard
error. Leave `_validate_task_definition`'s existing soft semantics (state-body hw-lib-drift badge)
completely untouched.

**On TRIGA-10 (single-sourcing) — a note of intellectual honesty:** true single-sourcing across all
four runtimes that currently know about the handler/action vocabulary (Pi runtime `_build_action_callable`
dispatch, Pi CLI tool `validate_fda.py`'s `VALID_ACTIONS`/`VALID_HANDLERS` constants, the new backend
validator, and the React `HANDLERS` array / `ActionEditor` type dropdown) is not achievable without a
cross-language schema/codegen system, which is out of scope for this phase. The two *Pi-side* copies
(`apply_trigger_assignments`'s literal string checks and `validate_fda.py`'s separately-declared
`VALID_HANDLERS`/`VALID_ACTIONS` sets) **can** be consolidated into one shared Python constant (both
files are in the same Pi codebase/venv) — recommend doing this. Across the Pi/backend/React boundary,
the realistic and honestly-scoped fix is making the new backend hard-422 validator the enforcement
point: if the React vocabulary ever drifts from what Pi/backend allow, save-time 422 catches it
immediately instead of the current failure mode (silent success at save, `ValueError` only at Pi session
start — exactly the negative case TRIGA-11 asks to be moved earlier).

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Pi framework | pytest (no `pytest.ini`/`conftest.py` found — bare `pytest` invocation); tests import `autopilot.tasks.mics_task` directly against `MagicMock`-based fake task instances (no real hardware/Pi needed) |
| Pi config file | none — see Wave 0 gap below |
| Backend framework | pytest + `fastapi.testclient.TestClient`; existing suite (`api/tests/test_toolkits_router.py`) is smoke-level only (asserts route exists / status in a tolerant set, not exact behavior) |
| Backend config file | none found (no `pytest.ini`/`conftest.py` in `api/`) |
| Quick run command (Pi, local sanity only — no hardware) | `cd ~/pi-mirror && python3 -m pytest tests/test_trigger_assignments.py tests/test_load_fda_from_json.py -q` |
| Quick run command (backend) | `cd /home/ido/mics-backend/api && python3 -m pytest tests/test_toolkits_router.py -q` |
| Full suite command (Pi) | `cd ~/pi-mirror && python3 -m pytest tests/ -q` (user-run only if Pi/autopilot import succeeds in that environment — README notes autopilot cannot be imported locally in all environments; `py_compile` is the universal fallback) |
| Full suite command (backend) | `cd /home/ido/mics-backend/api && python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| TRIGA-01 | `actions` list built via `_build_action_callable`, same validation as state bodies | unit (Pi) | `python3 -m pytest tests/test_trigger_assignments.py -k actions -q` | ❌ Wave 0 — new tests needed alongside implementation |
| TRIGA-02 | Composed callable declares `level`/`tick`; `{"trigger":...}` resolves | unit (Pi) | `python3 -m pytest tests/test_trigger_assignments.py -k trigger_context -q` | ❌ Wave 0 |
| TRIGA-03 | `view` action writes `self.view.view[key]`, accepts `pi_timestamp` kwarg | unit (Pi) | `python3 -m pytest tests/test_trigger_assignments.py -k view_action -q` | ❌ Wave 0 |
| TRIGA-04/05 | `output` capture (single + list-unpack) into `variables` registry | unit (Pi) | `python3 -m pytest tests/test_load_fda_from_json.py -k variables -q` | ❌ Wave 0 |
| TRIGA-06 | Backward compat: existing handler-based tests still pass unmodified | unit (Pi) | `python3 -m pytest tests/test_trigger_assignments.py -q` | ✅ existing (12.7 KB, must stay green) |
| TRIGA-07 | PUT with invalid `trigger_assignments.actions` returns 422 | unit (backend) | `python3 -m pytest tests/test_task_definitions_validation.py -k trigger -q` | ❌ Wave 0 — new test file |
| TRIGA-08 | `scan_fda_for_refs` includes trigger action refs | unit (backend) | `python3 -m pytest tests/test_fda_utils.py -q` | ❌ Wave 0 — new test file (no `fda_utils` tests exist today) |
| TRIGA-09 | Trigger panel renders `ActionEditor` per assignment action | manual (no frontend test runner detected in `web_ui/react-src`) | visual check in `/react/task-editor/:id` | n/a — manual-only, justified: no Vitest/Jest config found in `react-src/package.json` at research time |
| TRIGA-10 | Backend 422 fires when React sends an unsupported handler/action type | unit (backend) | covered by TRIGA-07's test file | ❌ Wave 0 |
| TRIGA-11 | Rig proof: lick detection via UI action list, no `detectedLick` method; invalid config rejected at save | manual-only (Pi hardware) | user-run session start on real rig | n/a — Pi hard rule: agent never runs Python on the Pi |

### Sampling Rate
- **Per task commit:** Pi — `py_compile` the touched file(s) (agent can run this locally per the
  established Pi workflow: "Local syntax check: `python -m py_compile <file>` from `~/pi-mirror/`");
  backend — the relevant `pytest -k` slice above.
- **Per wave merge:** Pi — full `tests/test_trigger_assignments.py` + `tests/test_load_fda_from_json.py`
  (user-run, since these import `autopilot` which may not be importable off-Pi in all dev setups —
  confirm locally first with `py_compile`, defer full pytest run to the user if import fails); backend —
  full `api/tests/` suite (agent-run, docker-compose stack is agent-driven).
- **Phase gate:** Full backend suite green + Pi `py_compile` clean before `/gsd:verify-work`; the Pi
  rig-proof checkpoint (TRIGA-11) is a mandatory **human-verify** gate per the project's Pi hard rules —
  the agent cannot execute it itself.

### Wave 0 Gaps
- [ ] `~/pi-mirror/tests/test_trigger_assignments.py` — extend with new test functions for the
      `actions`-based branch (`_build_trigger_action_list`, `view` action, `output` capture,
      `{"trigger": ...}` resolution) — do not modify or remove any existing test in this file (TRIGA-06).
- [ ] `~/pi-mirror/tests/test_load_fda_from_json.py` — extend with `variables` registry instantiation
      tests (collision-with-FLAGS raises; shared-Tracker-object assertion).
- [ ] `/home/ido/mics-backend/api/tests/test_fda_utils.py` — new file; no tests exist today for
      `scan_fda_for_refs` at all (state-body or trigger).
- [ ] `/home/ido/mics-backend/api/tests/test_task_definitions_validation.py` (or extend
      `test_toolkits_router.py`) — new hard-422 trigger-validation tests; existing file's tests are
      route-existence smoke checks only, not a suitable home for behavioral assertions without significant
      extension.
- [ ] No `conftest.py`/`pytest.ini` exists in either `~/pi-mirror/tests/` or `api/tests/` — not a blocker
      (bare `pytest` / `pytest -q` works against the existing files) but worth noting if the planner wants
      shared fixtures for the new `MockToolkit`-style task instances (the pattern in
      `test_trigger_assignments.py:34-75` is copy-pasted per test file today, not centralized).

---

## Sources

### Primary (HIGH confidence — direct code read, this session)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — full read of lines 1-45, 241-576, 599-873, 915-1225 (imports, `_COMPARE`, `check_for_detectors`, `init_flags`, `_resolve_arg`, `_build_condition_operand`, `_build_if_action`, `_build_action_callable`, `_build_state_method`, `load_fda_from_json`, `_resolve_renamed_hw_refs`, `apply_trigger_assignments`, `_build_touch_detector_callback`, `_build_digital_input_callback`, `hot_update_fda`)
- `~/pi-mirror/autopilot/autopilot/tasks/task.py` — `process_queue`, `execute_trigger`, `handle_trigger` (lines 220-320)
- `~/pi-mirror/autopilot/autopilot/tasks/learning_cage.py` — full `HARDWARE` dict, `__init__`, `detectedLick` (lines 1-172)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_cage_task.py` — trigger assignment lines 180-214
- `~/pi-mirror/autopilot/autopilot/tasks/RecordingBox.py` — `self.triggers['TOUCH_INT']` line 75
- `~/pi-mirror/autopilot/autopilot/tasks/gonogo.py` — legacy list-of-lambdas trigger idiom, lines 150-204
- `~/pi-mirror/autopilot/autopilot/hardware/i2c.py` — `MPR121`/`Touch_Detector` classes, `detect_change`/`read` (lines 799-975)
- `~/pi-mirror/autopilot/autopilot/utils/Tracker.py` — `Tracker`/`Boolean_Tracker`/`Counter_Tracker`/`Trial_Tracker` (lines 1-70)
- `~/pi-mirror/autopilot/autopilot/utils/logging_utils.py` — `log_action` decorator behavior on `.set()` (lines 14-39)
- `~/pi-mirror/autopilot/autopilot/core/View.py` — full file (`View`, `add_Tracker`, `get_value`)
- `~/pi-mirror/tests/test_trigger_assignments.py` — full file (346 lines) — existing contract that must keep passing
- `~/pi-mirror/tools/validate_fda.py` — lines 33-36 (`VALID_OPS`/`VALID_HANDLERS`/`VALID_ACTIONS`/`VALID_SPECIALS`), 100-289, 290-456 (full `validate()`, `_validate_actions_list`, trigger-assignment validation block)
- `/home/ido/mics-backend/web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` — lines 1-30 (imports), 80-360 (normalise/save wiring), 700-790 (panel hosting, trigger panel always-visible)
- `/home/ido/mics-backend/web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` — full file (161 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/StateBodyPanel.tsx` — full file (174 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/ActionEditor.tsx` — full file (533 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/ConditionBuilder.tsx` — full file (180 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/IfActionEditor.tsx` — lines 1-60
- `/home/ido/mics-backend/web_ui/react-src/src/components/ArgInput.tsx` — lines 1-60
- `/home/ido/mics-backend/web_ui/react-src/src/types/index.ts` — lines 200-320 (`FdaAction`, `FdaTriggerAssignment`, `ToolkitRead`, `FdaJson`)
- `/home/ido/mics-backend/api/routers/toolkits.py` — lines 640-926 (`_validate_task_definition`, `update_task_definition`, `push_task_definition`, `_validate_fda_against_toolkit`)
- `/home/ido/mics-backend/api/fda_utils.py` — full file (38 lines)
- `/home/ido/mics-backend/api/tests/test_toolkits_router.py` — full file (38 lines)
- `.planning/phases/23-compute-primitives-variables/23-CONTEXT.md` and `23-01-PLAN.md` — Phase 23's `variables`/`compute`/`output` design, in full

### Secondary (MEDIUM confidence)
- None — all findings in this document trace to a direct code read listed above; no web search was needed since this is an internal-architecture phase with no external library to evaluate.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new external library; internal DSL extension only (HIGH confidence this framing is correct, since every action type already exists in `_build_action_callable`)
- Architecture (action vocabulary extension design): HIGH — every code snippet in this document is either a direct quote of existing, running code or a minimal, additive extension following an existing pattern in the same file
- Pitfalls: HIGH — Pitfall 1 (touch_detector/`detect_change` mismatch) and Pitfall 3 (`learning_cage` missing `SEMANTIC_HARDWARE`) are both confirmed by reading the actual hardware/toolkit source, not inferred
- Open Decisions: MEDIUM-HIGH — recommendations are well-justified from code evidence, but each is a genuine design choice the planner/user could reasonably weigh differently; flagged as recommendations with justification, not settled fact

**Research date:** 2026-07-26
**Valid until:** Until Phase 24 is planned and executed, or until `~/pi-mirror/autopilot/` or this repo's `api/routers/toolkits.py` / `web_ui/react-src/src/components/` change materially (internal architecture research — no external-library staleness clock applies; re-verify line numbers if Phase 23 or other Pi-side plans land first, since they touch the same files)
