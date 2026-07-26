# Phase 24: Trigger Assignment Action Lists — Context

**Gathered:** 2026-07-26
**Status:** Ready for planning
**Source:** Direct user direction in session + orchestrator code reading of the visual editor and Pi.

<domain>
## Phase Boundary

**The ask, in the user's words:** *"have a trigger perform a code segment identical to an action within a state (so flag or hardware or what not). In legacy we would just add a function and assign it to the triggers list in the class. The best example is the detect lick function, and that is something I would like to test this whole thing with now — with UI assignment instead of code."*

A hardware trigger must be able to run the **same action vocabulary a state's `entry_actions` uses** — `hardware`, `flag`, `timer`, `special`, `method`, `if` — assembled in the task-editor UI instead of hard-coded as a Python method on the task class.

**In scope:**
- Pi: trigger assignments carry an ordered **action list** built through the existing `_build_action_callable` path.
- Pi: whatever new action/arg plumbing the `detectedLick` reference case requires (see Open Decisions).
- Backend: **validation of `trigger_assignments`** — currently zero. This is the only FDA-JSON section the API never validates.
- Backend: `api/fda_utils.py` reference scanner must see trigger hardware refs.
- UI: reuse the state-body action editor inside the trigger panel rather than a parallel implementation.
- Rig proof: lick detection driven entirely by a UI-assigned action list.

**Out of scope:**
- Phase 23 `variables` / `compute` primitives — separate phase, but any value-capture mechanism introduced here MUST be design-compatible with it (see Decisions).
- New trigger *sources*. This phase changes what a trigger **does**, not what fires it.
- Rewriting `execute_trigger` dispatch semantics in `task.py`.

</domain>

<decisions>
## Locked Decisions

### The reference case defines "done"
`learning_cage.py:162 detectedLick` is the acceptance target, not an example:
```python
pin_number, level = self.hardware['I2C']['MPR121'].detect_change()
if pin_number is None: return
device_str = f"{self.hardware['I2C']['MPR121'].device_name}{pin_number}"
self.view.view[device_str].set(level, pi_timestamp=tick)
```
**Success gate:** this behaviour runs on the rig from a UI-assigned action list, with **no `detectedLick` method in the task class.**

### Backward compatibility is required
Task definitions already stored in the DB must keep loading and running. `apply_trigger_assignments` already documents the contract that an absent/empty `trigger_assignments` leaves `self.triggers` untouched — that must survive.

### Existing Pi unit tests must keep passing
`~/pi-mirror/tests/test_trigger_assignments.py` (12 KB) covers the current handler behaviour.

### Value-capture must be consistent with Phase 23
If this phase introduces a way to capture a method's return value into a named slot, it must use the same shape Phase 23 will use for `variables` / `compute` `output`. Two competing mechanisms for "put a value somewhere and read it back" is the outcome to avoid. Phase 23 is planned but not executed, so it can still be aligned to whatever this phase lands on — but the decision must be made deliberately, in this phase, and written down.

### HARD CONSTRAINT — `~/pi-mirror/autopilot/autopilot/hardware/i2c.py` is OFF-LIMITS
**Do not change anything in `i2c.py`.** Not `detect_change()`, not `Touch_Detector`, not any signature.
User instruction, 2026-07-26. Any design that requires editing that file is disqualified.

### The touch architecture is intentional — understand it before designing around it
User explanation, 2026-07-26, confirmed against `pilot/prefs.json` and `learning_cage.py`:

> *"Touch detector is there because there is not an actual hardware for the 4 electrodes. The GPIO touch interrupt is triggering, and then we communicate in I2C and check the electrode number. We did that to standardize things."*

Declared in `pilot/prefs.json` `HARDWARE`:
```json
"I2C":  { "MPR121":    { "group":"TOUCH", "name":"mpr121", "num_detectors":4,
                          "device_name":"LICKER", "type":"i2c.Touch_Detector" } }
"GPIO": { "TOUCH_INT": { "group":"touch_int", "pin":8, "polarity":1,
                          "type":"gpio.Digital_In" } }
```

**Four electrodes → ONE I2C device object → ONE GPIO interrupt line. There is deliberately no
per-electrode Hardware object.** The per-electrode abstraction is created later, in the **view**, by
`check_for_detectors` (`mics_task.py:241-266`) — it reads `num_detectors` + `device_name` off the
device and calls `view.add_Tracker("LICKER0".."LICKER3")`. That is the standardization layer.

Runtime flow:
1. GPIO `TOUCH_INT` edge → `handle_trigger` → `execute_trigger("TOUCH_INT", level, tick)`
2. Callback queries I2C: `detect_change()` → `(electrode_index, new_level)`
3. Write `view.view[f"LICKER{electrode_index}"].set(new_level, pi_timestamp=tick)`

**Therefore `detect_change()` returning a `(index, value)` 2-tuple is CORRECT and intentional** —
one interrupt, then a query to discover *which* electrode moved. It is not a defect and must not be
"fixed".

### Consequences for the Open Decisions
- **Open Decision 1 option (b) — "per-channel hardware API with fixed keys" — is RULED OUT.** It would
  require inventing per-electrode hardware objects, inverting the standardization above, and editing
  `i2c.py`. Do not propose it.
- **Option (a) is the direction the hardware design implies:** capture the returned `(index, level)`
  and write `LICKER{index}` through a `view` action with key templating. This is precisely what
  `detectedLick` does by hand.
- **The existing `_build_touch_detector_callback` (`mics_task.py:1089-1137`) is genuinely wrong** — it
  loops `for i in range(hw.num_detectors)` and does `changed[i]`, so with the real 2-tuple return it
  writes the *electrode index* into `LICKER0` and the *level* into `LICKER1`, then swallows `IndexError`
  for the rest; its `changed is not None` guard also never fires because the no-change sentinel is
  `(None, None)`. Its unit test (`test_trigger_assignments.py:317-345`) passes only because it mocks
  `detect_change.return_value = [1, 0]`, encoding a contract the hardware never had. **Latent, not
  currently corrupting data** — this path only runs for a task definition that uses `trigger_assignments`,
  and the feature has never been exercised end-to-end. Fix the handler and its test; never `i2c.py`.

### Verification posture (project hard rule)
Backend and React are agent-driven inside the docker compose stack. **Pi-side work is edit-in-mirror only** (`~/pi-mirror/`). Every Pi `<verify>` block returns commands for the **user** to run. The agent never runs git on the Pi, never starts/stops the pilot process, and never runs Python on the Pi.

</decisions>

<specifics>
## Ground Truth from Code Reading (2026-07-26)

Verified by the orchestrator against the actual files — planning must not contradict these without re-checking.

### Current state of the three layers
| Layer | File | Status |
|---|---|---|
| UI | `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` (161 lines), wired at `TaskEditor.tsx:739`, state at `:108` / `:359` | Exists — fixed `handler` enum dropdown |
| Backend | `api/` | **Nothing.** `grep -rn "trigger" api/` returns zero hits |
| Pi | `mics_task.py:1037 apply_trigger_assignments`, `:1089 _build_touch_detector_callback`, `_build_digital_input_callback` | Exists — two hard-coded handlers |

The feature has **never been exercised end-to-end.**

### `execute_trigger` — the dispatch contract (`task.py:270-300`)
- Normalises `self.triggers[pin]` to a list, iterates.
- For each callback: `inspect.signature(trig)` — passes `level=` and/or `tick=` **only if the callback declares those parameter names**, else calls with no args.
- Wrapped in `try/except KeyError` → unknown pin logs at debug and is swallowed.
- The unconditional `Hardware_Event` dispatch happens **before** callbacks and is independent of them.

### `_build_action_callable` — the vocabulary to reuse (`mics_task.py:524`)
Returns a **zero-arg** callable. Handles `if` (recursive, via `_build_if_action`), `hardware`/`timer` (direct-ref `group` key or legacy `_semantic_hw`), `flag`, `special` (`INC_TRIAL_COUNTER` only), `method` (gated on `CALLABLE_METHODS`). Raises `ValueError` at **load time** for unknown types/refs.

### The four gaps between that vocabulary and `detectedLick`
1. **No `view` action type.** `flag` actions write `self.flags[ref]`. Touch-channel trackers are created by `check_for_detectors` (`mics_task.py:241-266`) via `self.view.add_Tracker(device_str, ...)` and live **only** in `self.view.view` — contrast `init_flags` (`:268-280`) which writes **both** `self.flags[name]` and `self.view.view[name]`. No existing action type can write a licker tracker.
2. **Return values are discarded.** `_hw_call` does `getattr(_hw, _method)(*args, **kwargs)` and drops the result. `detect_change()`'s return value *is* the payload.
3. **No trigger context in `_resolve_arg`** (`mics_task.py:401`). Supports `{param}`, `{flag}`, `{now}` only. Needs a `{"trigger": "level"|"tick"}` form — and the composed callable must **declare** `level`/`tick` parameters or `execute_trigger` will never pass them.
4. **Dynamic target naming.** `device_str` is built from the channel index **returned** by `detect_change()`. A flat declarative action list cannot express "index into the return value to choose the target tracker."

### UI assets to reuse rather than reimplement
`components/StateBodyPanel.tsx`, `components/ActionEditor.tsx` (per-action forms + `ArgInput`), `components/ConditionBuilder.tsx` (operand pickers), `types/index.ts` (`FdaTriggerAssignment`, action types). The trigger panel should host the same action editor the state body panel uses.

### Handler-list divergence
The allowed handlers are hard-coded **twice** — `HANDLERS` array in `TriggerAssignmentPanel.tsx` and the `if/elif` chain in `apply_trigger_assignments`. Nothing keeps them in sync.

</specifics>

<open_decisions>
## Open Decisions — the plan MUST resolve these explicitly

### 1. How does an action list express `detectedLick`'s dynamic tracker naming?
Candidate approaches (planner should pick one and justify, not enumerate):
- **(a)** Add return-value capture (`output`) + a new `view` action type + key templating (e.g. `"TOUCH{ch}"`). Most faithful to `detectedLick`; the `output` slot is the mechanism Phase 23 also needs.
- **(b)** Per-channel hardware API so each licker is a fixed tracker key and the researcher adds one assignment per channel. Simpler action vocabulary; requires an MPR121 API change and N assignments instead of 1.
- **(c)** Keep `touch_detector` as a built-in handler for the multi-channel fan-out and offer generic `actions` for everything else. Least Pi change — but leaves the reference case hard-coded in Python, which is the thing this phase exists to remove.

### 2. Additive or replacement?
Do `trigger_assignments` entries accept `actions` **alongside** the existing `handler` enum (`default` / `log_only` / `touch_detector` / `digital_input`), or does `actions` replace it with a migration for stored definitions? Backward compatibility for stored task definitions is non-negotiable either way.

### 3. How do `level` / `tick` reach the actions?
The composed trigger callable must declare those parameter names for `execute_trigger`'s `inspect.signature` check to pass them, while the underlying action callables from `_build_action_callable` remain zero-arg. Needs an explicit wiring design.

### 4. Where does validation live?
`api/routers/toolkits.py::_validate_task_definition` is the existing hook (it already does hardware-ref and action validation for states). Trigger validation should join it and return **422 on save**, not `ValueError` at session start. Decide whether the allowed-handler / allowed-action-type list becomes backend-served to kill the divergence in the Specifics section.

</open_decisions>

<deferred>
## Deferred

- Phase 23 `compute` primitives and the `variables` registry — separate phase; only the *shape* of value capture is coordinated here.
- New trigger sources / trigger creation from the UI.
- Any change to the unconditional `Hardware_Event` logging path.

</deferred>

---

*Phase: 24-trigger-assignment-action-lists*
*Context captured: 2026-07-26 from session direction + orchestrator code reading*
