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
**Success gate:** this behaviour runs on the rig from a UI-assigned action list, with **no Python
callback registered for `TOUCH_INT`** — `learning_cage` no longer assigns `self.triggers['TOUCH_INT']`.

**The `detectedLick` METHOD IS RETAINED** (user, 2026-07-26). Removing the *registration* is necessary
and sufficient. Deleting the method proves nothing extra: unregistered it is unreachable — `learning_cage`
has no `CALLABLE_METHODS`, so FDA JSON cannot invoke it either. It stays as the reference implementation
and as a one-line rollback if the rig proof fails. Note also that `RecordingBox.py:80` and
`mics_cage_task.py:286` each keep their own `detectedLick` + `self.triggers['TOUCH_INT']` registration
and are **out of scope** — so any "no `detectedLick` anywhere in the mirror" check is unsatisfiable by
construction and must not be used as a gate.

### Focus is the `mics_task` BASE CLASS (user, 2026-07-26)
> *"We are currently working on the mics_task base class, since all other flags and FDA are received
> from the backend — so this should be where we are focusing our intention and understanding."*

The mechanism lives in `mics_task.py`. Concrete task classes (`learning_cage`, `RecordingBox`,
`mics_cage_task`) are hardware declarations plus legacy helpers; flags, FDA and trigger assignments all
arrive from the backend. Consequences for planning:
- The separation-principle gates belong on `mics_task.py` (Plan 04 already asserts zero
  `touch_detector`/`digital_input` identifiers there).
- `learning_cage`'s change is a **single line** — unregister `TOUCH_INT`. It is not where the work is.
- Anything that would push task-specific behaviour back into a concrete class is going the wrong way.

### THE SEPARATION PRINCIPLE (user, 2026-07-26) — the organising idea of this phase
> *"I want to make the separation between the touch detector turning into a tracker, and the actual
> assign-trigger which is a broader thing. Obviously I chose to implement the lick as a test for the
> trigger, so we need both. I want to be able to declare the trigger — what triggers, and what are the
> actions done in the trigger… and the part of constructing the actual callback function should not be
> any more different than adding actions to states. So when primitives come we will be able to use this
> once implemented."*

Three consequences, all binding:

1. **The mechanism is: declare a trigger = (what fires, what actions run).** Hardware-agnostic. Nothing
   about touch, licks or MPR121 belongs in the trigger runtime.
2. **Callback construction MUST go through the same `_build_action_callable` a state body uses.** Not
   an equivalent implementation — the same one. The test of this: when Phase 23's `compute` action
   lands, it must work inside a trigger with **zero** Phase 24 rework.
3. **The licker is a test case, not part of the mechanism.** For it to be usable it must appear in the
   toolbox — hence the `learning_cage.SEMANTIC_HARDWARE` prerequisite — so the researcher picks MPR121
   as an ordinary hardware action, exactly like a valve or an LED. "Touch detector → tracker" is then
   just an action list, expressed in the UI, with no runtime special case.

### DECISION REVERSED 2026-07-26 — the `handler` enum is DROPPED, not kept alongside `actions`
Supersedes the earlier "additive" decision. `trigger_assignments` entries carry **`actions` only**.

**Evidence that made this safe** (orchestrator, live DB query, 2026-07-26): exactly ONE
`task_definitions` row has a non-empty `trigger_assignments` — id **185**, three entries, all
`handler: "touch_detector"`, two with an empty `trigger_name`, and **none with a `config` key**. It is
referenced by **no** `protocol_step_templates` row — an orphan scratch record. It would also crash the
Pi if ever started (`config["hardware_ref"]` → `KeyError` inside `load_fda_from_json`). There is no real
handler usage to preserve.

Consequences:
- **Delete** `_build_touch_detector_callback` and `_build_digital_input_callback` rather than correcting
  them. The buggy code goes away instead of being fixed.
- `digital_input` is redundant — copying `hardware_state` into a view key is
  `{"type":"view", …, "args":[{"hardware": …}]}` in the general vocabulary.
- One vocabulary instead of two, so TRIGA-10's divergence risk largely evaporates.
- Legacy Python tasks that assign `self.triggers[...]` directly are unaffected — `apply_trigger_assignments`
  only ever *adds* callbacks and still no-ops when `trigger_assignments` is absent/empty.
- Clean up the three junk entries in task definition 185.

### Detector keys are derived and shown in the GUI — inside this phase (user, 2026-07-27)
> *"I want to be able to have the LICKER{pin} tracker derived from the MPR num of detectors within
> phase 24 so I can add to the trigger tracker LICKER{num}.set(level) … make sure it is visible in
> the GUI as well."*

Plan **08** delivers it (TRIGA-13/14). Locked choices:
- **Derive on the Pi, at HANDSHAKE, from `prefs.HARDWARE`.** The Pi is the only party that already
  knows `device_name` × `num_detectors` at that moment, and HANDSHAKE is the existing channel for
  exactly this class of metadata (`flags`, `semantic_hardware`, `callable_methods`). The keys travel
  as finished strings; `api/` and React never compute a key and never learn what a detector is.
- **Scope limits accepted, not overlooked:** prefs-declared hardware only (a registry-declared
  detector's config is merged at task start, after HANDSHAKE) and last-handshake-wins per toolkit
  row across pilots. Both go to Phase 25 (DVK-01/02/06).
- **Variables join the operand pickers** (TRIGA-14, CMP-14 pulled forward from Phase 23) — without it
  the canonical payload's `pin_number != null` guard and its `{"flag": "level"}` value are not
  selectable, since both dropdowns are closed sets built from `toolkit.flags` alone.

### A trigger source must be trigger-capable hardware, picked from a dropdown (user, 2026-07-27)
> *"we need the assigned trigger to be a gpio class since this is the mechanism of the handle trigger
> in the code with the assign_cb … in the ui there should be a dropdown from the available gpio that
> are in the toolbox."*

Verified against the runtime, and the rule is slightly tighter than "GPIO": the predicate is
`hw.is_trigger`. `init_hardware` (`task.py`) calls
`hw.assign_cb(partial(self.handle_trigger, hardware=hw))` for exactly those objects, and
`handle_trigger` maps the firing BCM pin → board → `self.pin_id` back to the `HARDWARE[group][id]`
key — which is what `self.triggers` is keyed by, and why `learning_cage` wrote
`self.triggers['TOUCH_INT']`. `Hardware.is_trigger` is False by default and only `gpio.Digital_In`
(gpio.py:843) and `gpio.Digital_Out` (gpio.py:343) set it True, so an i2c device — MPR121 included —
can never be a trigger source, only the *target of an action inside one*.

Consequences (TRIGA-15, plan 08):
- The Pi reports `trigger_sources` in HANDSHAKE using that same `is_trigger` predicate, so the UI's
  list and the runtime's wiring cannot drift.
- `trigger_name` becomes a dropdown, with the usual unknown-value preservation and a free-text
  fallback only when the list is absent (un-redeployed Pi).
- The backend 422s a name outside the set when the set is known. This is not pedantry: an unknown
  name is a **silent no-op** today — the assignment saves, `self.triggers["TOCH_INT"]` is created,
  and nothing ever fires it.
- `Digital_Out` carrying `is_trigger = True` looks like a wart, but it is reported truthfully rather
  than filtered, because `init_hardware` really does wire it. Flagged in the plan for a later look.

### `pi_timestamp` is passed silently by Python — no UI control (user, 2026-07-27)
> *"the handle trigger passes onward the tick which is the pi timestamp — this should also be done
> silently in the python code (no need in the UI)."*

The `view` action injects `pi_timestamp` from the trigger's tick, read off the THREAD-LOCAL
`self._trigger_ctx` published for the duration of one action list and cleared in a `finally`
(Plan 04 `<trigger_context_lifetime>` — a plain attribute would leak a fired trigger's tick into
later state-body writes and is read across two threads). Outside a trigger no kwarg is passed at
all; an explicit `kwargs.pi_timestamp` still wins. The checkbox planned in 24-03 is removed and the canonical payload loses its `kwargs` block.
Rationale: timestamp fidelity is not a per-action editorial choice, and `{"trigger": "tick"}` remains
in the vocabulary for anything that genuinely needs the tick as a value.

### The licker level comes from I2C, NOT from the trigger's `level`
`execute_trigger(self, pin, level, tick, hardware)` (`task.py:286`) passes the **GPIO edge level of
the `TOUCH_INT` interrupt line**. That is not the electrode's state: the interrupt says *something*
changed, and only `detect_change()` says *which electrode* and *to what*. `detectedLick` accordingly
takes `tick` only and reads the level from the I2C return. So the canonical payload's view value is
`{"flag": "level"}` — the **captured** second element of `output: ["pin_number", "level"]` — and
never `{"trigger": "level"}`. Wiring the trigger level here would record interrupt polarity and look
plausible while being wrong. `{"trigger": "level"}` stays correct for GPIO inputs (beam-break, IR)
where the edge level IS the payload.

### Detector trackers stay in the view; `variables` are the flags (2026-07-27)
Asked whether the write should go "via the flags dict" instead of `self.view.view[key].set(...)`:
no, and the two halves of the design already sit on opposite sides of that line.
- `init_flags` writes **both** `self.flags` and `self.view.view`; `check_for_detectors` →
  `view.add_Tracker` writes **only** `self.view.view` (`View.py:18`). So `self.view.view` is the
  superset and the only namespace that can address a detector channel at all — `self.flags["LICKER0"]`
  does not exist and injecting it there would break the "flags = the declared `FLAGS` contract the
  backend validates against" invariant, on top of the Boolean/Counter typing mismatch.
- `variables` (`pin_number`, `level`) ARE created in `self.flags` (Plan 01), which is why they are
  addressed as `{"flag": …}`. So the user's instinct is satisfied where it applies: the *captured
  values* live in the flags dict; the *detector channel* is a view tracker. One `view` action with a
  key template covers the dynamic-name requirement that a static `flag` ref cannot express.

### No legacy non-FDA protocols remain (user, 2026-07-26)
> *"No legacy, just FDA now."*

This closes the Plan 06 risk: removing `self.triggers['TOUCH_INT'] = [self.detectedLick]` cannot strand
a non-FDA `learning_cage` session, because every session now carries an FDA task definition. Plan 07's
rig-proof checkpoint no longer needs to block on confirming legacy usage.

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
