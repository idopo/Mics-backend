# Phase 24: Trigger Assignment Action Lists — Context

**Gathered:** 2026-07-26
**Amended:** 2026-07-27 — re-plan of plans 06/07/08 after the sourceless-only scope change
**Status:** Waves 1–2 executed and rig-proven; plans 06/07/08 ready for re-planning
**Source:** Direct user direction in session + orchestrator code reading of the visual editor and Pi.

> **Read the amendment first.** Section `<replan_2026_07_27>` below supersedes parts of the
> original decisions. Where they disagree, the amendment wins. Supporting evidence:
> `24-HARDWARE-VALIDATION.md` (what is proven on hardware, the 7 post-execution defects) and
> `24-REPLAN-BRIEF.md` (requirement-by-requirement disposition).

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
- **(added 2026-07-27)** Backend derivation of detector view keys for the editor's pickers —
  Phase 25 (DVK), scheduled to run immediately after this phase. See the amendment.
- Phase 23 `variables` / `compute` primitives — separate phase, but any value-capture mechanism introduced here MUST be design-compatible with it (see Decisions).
- New trigger *sources*. This phase changes what a trigger **does**, not what fires it.
- Rewriting `execute_trigger` dispatch semantics in `task.py`.

</domain>

<replan_2026_07_27>
## Amendment — Re-plan of Plans 06 / 07 / 08 (2026-07-27)

**Why:** user decision — *"we are only working with sourceless toolkits from now on"*, with the
clarification that `check_for_detectors` / `detect_change` functionality **must still exist**, just
via the sourceless (backend-authored) path rather than the `learning_cage` Python class.

**Plans 01–05 are unaffected** and are proven on hardware (run 475). This amendment governs 06/07/08.

### The target, in the user's words (2026-07-27)

> *"I want to emulate what happens today where num of detectors will derive the pins numbering and
> create dedicated trackers for them, they will reside in the view so the user in UI can make
> transitions and actions for trigger so it can set the appropriate tracker based on the pin the
> trigger was calling in detect lick. So we need 1st action to be detect lick — this one returns a
> value that will set the correct tracker. If it is too much for UI we can also leave less for the
> user so it does not have the ability to take one pin and accidentally change another tracker in
> the process. Basically I want the legacy functionality to be handled in the back end as all
> things are according to our architecture."*

### R1 — TRIGA-11 is DROPPED

*"No Python callback registered for `TOUCH_INT`"* is vacuous on a sourceless toolkit — it dispatches
to `mics_task` and never had a Python callback to unregister. The grep-based proof tests a property
that cannot exist. Its rig-proof half is already superseded by run 475.

**Consequence:** the `learning_cage.py` edits deployed by plan 24-01 (`SEMANTIC_HARDWARE`) are inert
on this path and are left alone. `learning_cage` is not touched by plans 06/07/08.

### R2 — The level comes from `detect_change`, NEVER from the trigger

Reaffirmed with new evidence, because it was nearly reversed in discussion.

`Touch_Detector.detect_change()` (`i2c.py:831-843`) returns `changes[0] if changes else (None, None)`
— `(pin_number, level)` where `level` is **that electrode's new state** (1 on 0→1, 0 on 1→0).

`execute_trigger`'s `level` is the **GPIO edge on the `TOUCH_INT` IRQ line**. The MPR121 holds IRQ
asserted until its touch-status register is read — the documented cause of runs 473/474 firing only
once. With `EITHER_EDGE` that yields **two** edges per real event: assert, then deassert when
`detect_change` performs the read. Run 475's tidy alternating 0/1 is therefore the assert/deassert
handshake, not touch/release — consistent with 140 `Mid_LED` calls for 47 firings.

With one LED this looked plausible. With four electrodes, `{trigger: "level"}` would write IRQ
polarity into whichever `LICKER` changed: **wrong data that looks correct in ES.**

**Locked:** `pin_number` *and* `level` both come from action[0]'s captured `output`. Only
`pi_timestamp` comes from the trigger context, injected silently (already locked, unchanged).

### R3 — The editor gets a CONSTRAINED detector write, not free-hand wiring

User chose *"leave less for the user"*. The editor offers the detector device as a **single pick**;
the target key and the written value are both derived from that call's own return. The researcher
**cannot** cross the wires — read electrode 2, write `LICKER0`.

```
Trigger: TOUCH_INT
  [1] Read detector:  [ MPR121 ▾ ]
      → writes LICKER0..3 from the changed electrode
```

No `key_template` text box, no operand wiring, on this path.

**This is an editor-side affordance only.** It is a deliberate, contained exception to the
separation principle — the Pi runtime stays fully generic and hardware-agnostic.

### R4 — The widget is a UI MACRO over the general vocabulary

The widget emits ordinary FDA JSON. Nothing new reaches the Pi as a concept, and Phase 23's
`compute` keeps working inside triggers with zero rework (the TRIGA-10 / separation-principle test).

```json
[
  {"type": "hardware", "ref": "MPR121", "method": "detect_change",
   "output": ["pin_number", "level"]},
  {"type": "view", "key_template": "{device_name}{pin_number}", "source_ref": "MPR121",
   "value": {"flag": "level"}, "if": {"pin_number": "!= null"}}
]
```

Rejected alternatives:
- **New `detector` action type expanded on the Pi** — puts detector-specific code back into the
  trigger runtime, precisely what TRIGA-06 deleted and run 475 proved unnecessary.
- **Backend expands a compact stored form** — stored JSON ≠ dispatched JSON, and `validate_fda.py`
  on the Pi would only ever see the expanded form.

**Accepted cost:** the widget renders by *recognising* this shape. A hand-edited variant that no
longer matches falls back to the raw action editor. That is graceful degradation, not failure, and
the raw editor must stay reachable.

### R5 — NEW Pi capability: a `{device_name}` token in `key_template`

`LICKER` is `device_name` from `pilot_hardware_config` — **per-pilot data**, while task definitions
are pilot-agnostic (TRIGA-07, DVK-02). Baking the literal `"LICKER{pin_number}"` in at save time
would make the definition pilot-specific: on a pilot whose MPR121 is named `TONGUE` it writes into a
view key that does not exist — a silent no-op, no exception, no data.

**Locked:** the `view` action gains a `source_ref`, and `resolve_key_template` gains a
`{device_name}` token resolved at runtime from that hardware object's own `device_name` attribute.

- Generic, **not** detector-specific — any hardware has a name.
- `resolve_key_template` (`fda_vocabulary.py`) substitutes only from the captured-values dict today,
  so the resolver must be handed `device_name` alongside the captured variables.
- Keeps the task definition pilot-agnostic, and means **Phase 25 never has to solve `device_name`
  for the trigger path** — only for the editor's operand pickers.

### R6 — TRIGA-12 is the load-bearing change

Unchanged as written in REQUIREMENTS.md (capability-based discovery: `num_detectors` +
`device_name` + `read()`), but its status changes from robustness fix to **the single thing standing
between the current state and working lick detection.**

Verified this session:
- `check_for_detectors` (`mics_task.py:261`) filters with `isinstance(v, Touch_Detector)` against the
  class imported at `mics_task.py:17`.
- `_resolve_hardware_classes` (`mics_task.py:149`) `exec`s the registry's `source_code` into a fresh
  namespace → a **different class object** → zero matches.
- Result: no `add_Tracker`, no `LICKER0..3` in the view, and a `view` action writes a missing key
  with **no exception and no data**.
- `init_hardware` (`task.py:178-204`) stores instances at `self.hardware[group][id]`, so
  `check_for_detectors`' two-level iteration **does** reach a `Modules`-group MPR121. The `isinstance`
  identity check is the only breakage. This is a one-predicate fix.

### R7 — Detector key derivation for the editor stays in PHASE 25

Phase 25 (DVK-01…08) already specifies backend derivation, operand pickers, preflight resolution
against a specific pilot, per-pilot disagreement, and unknown-key degradation.

- Phase 24 does **not** derive keys. R3 removes the need on the trigger path; R5 removes the need
  for `device_name`.
- **Transitions on `LICKER2` are Phase 25**, which is scheduled to run **immediately after 24**.
- Rationale: DVK-01 mandates *one derivation, one key format*. A minimal second derivation in 24
  is the outcome to avoid.
- TRIGA-13 as written (derive at HANDSHAKE from `prefs.HARDWARE`) is **void** — a registry-declared
  detector never appears in `prefs.HARDWARE`; its config arrives per-run via `PREFS_HARDWARE` in the
  START payload. The Pi structurally cannot do it. Reword or retire TRIGA-13 in favour of DVK.

### R8 — TRIGA-15: dropdown over ALL `is_trigger` hardware, grouped

`Digital_Out.is_trigger = True` (`gpio.py:343`), not only `Digital_In`, so every LED qualifies.
**Report truthfully, grouped inputs vs outputs** — `init_hardware` really does call
`assign_cb` on them, and filtering would make the UI understate what the runtime wires. The
`Digital_Out` flag remains flagged as a probable wart for a later look, not silently hidden here.

Justification for the requirement at all: a typo'd `trigger_name` is a **silent no-op** today —
the assignment saves, `self.triggers["TOCH_INT"]` is created, and nothing ever fires it.

### R9 — NEW requirement: validate a hardware action's `method`

`fda_validation` checks `CALLABLE_METHODS` only for `type: "method"`. So
`{"type":"hardware","ref":"MPR121","method":""}` returns **200** and is a silent no-op on the Pi —
the exact failure class TRIGA-07 exists to prevent. The UI is currently the only guard, and three of
the seven post-execution defects lived in that seam. AST metadata for hardware libs already exists,
so the data is available. **In scope for this phase.** Needs a new TRIGA id.

### R10 — Rig proof (plan 07′)

- **Checkpoint 1 (UI round-trip) runs FIRST**, not last. Five of the seven post-execution defects
  were in the UI↔API seam and surfaced only by using the editor. Evidence-backed, not preference.
- **Checkpoint 2** (422 negative cases) survives; 8 live cases already pass.
- **Checkpoint 3 replaces the old grep-based one:** build the detector write on toolkit 100, run,
  touch **each of the four electrodes**, confirm the matching `LICKER{n}` updates with a
  `pi_timestamp` — **and that touching electrode 2 never moves `LICKER0/1/3`.** The cross-talk
  negative is the point of R3 and must be asserted, not assumed.

Two stale mechanics to fix while rewriting 07:
1. It specifies `git -C /home/ido/pi-mirror status --porcelain …/i2c.py`. **All git operations in
   `pi-mirror` are forbidden.** Use:
   `diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/.../i2c.py') /home/ido/pi-mirror/.../i2c.py`
2. It says `cd ~/pi-mirror && python3 -m pytest` — that is the **dev host**, where `autopilot`
   cannot import (`npyscreen` missing). Correct path is `cd ~/Apps/mice_interactive_home_cage`
   **on the Pi**, user-run.

### R11 — Sourceless tasks receive ONLY the `Modules` group (recorded, not scoped)

`mics_task.py:94` does `self.HARDWARE = self._resolve_hardware_classes(kwargs["HARDWARE"])` — a
**wholesale replace** — and `get_dispatch_spec` only ever emits `hardware["Modules"]`. A
backend-authored task therefore has **no `GPIO`, `I2C`, `Timers` or `UNREAL` groups at all**.

**Everything a sourceless task touches must be a registered hardware module.** This also makes
`SEMANTIC_HARDWARE` on Pi classes irrelevant for this path.

User decided **not** to make replace-vs-merge a work item in this phase. Recorded here as
load-bearing ground truth; revisiting the semantic is deferred.

</replan_2026_07_27>

<decisions>
## Locked Decisions

### The reference case defines "done"

> **SUPERSEDED 2026-07-27 by amendment R1.** The `learning_cage` *implementation* is no longer the
> acceptance target — the same **pattern** must be reproduced on a backend-authored toolkit via
> registered hardware modules. The "no Python callback registered for `TOUCH_INT`" gate (TRIGA-11)
> is dropped as vacuous. The code reading below remains accurate and is still the behavioural spec.

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
## Open Decisions — ALL RESOLVED

| # | Question | Resolution |
|---|---|---|
| 1 | Dynamic tracker naming | **(a)** — return-value capture + `view` action + key templating. Executed in waves 1–2. Amended by **R3/R4/R5**: the researcher reaches it through a constrained one-pick widget that emits this JSON, and the key uses a runtime-resolved `{device_name}` token. |
| 2 | Additive or replacement? | **Replacement** — the `handler` enum was dropped (TRIGA-06), delivered in plan 24-04, proven on the rig. |
| 3 | How do `level` / `tick` reach the actions? | Composed callable declares them; thread-local `_trigger_ctx` for the duration of one action list. Delivered in plan 24-04. **See R2** — for the licker specifically, `level` must NOT come from here. |
| 4 | Where does validation live? | New `api/fda_validation.py`, hard 422 on save. Delivered in plan 24-02. **Extended by R9** — it must also validate a hardware action's `method`. |

*Original text retained below for the reasoning that produced these answers.*

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

**Added 2026-07-27:**
- **Backend derivation of detector view keys for the editor's pickers** → **Phase 25 (DVK-01…08)**,
  to run immediately after this phase. Includes transitions on `LICKER2`, `key_template` completion,
  preflight resolution per pilot, and unknown-key degradation. (R7)
- **`Digital_Out.is_trigger = True`** (`gpio.py:343`) — probable wart. Reported truthfully in this
  phase (R8); narrowing the predicate is a later question.
- **Duplicate `set` calls** — run 475 logged 140 `Mid_LED` calls for 47 trigger firings (~3×). Some
  are `Digital_Out` callback bookkeeping, but genuine duplicates appear present. User chose not to
  block the re-plan on it. **Must be understood before real data collection** — if each lick writes
  its tracker more than once, the behavioural record is inflated.
- **`HARDWARE` replace-vs-merge semantics for sourceless tasks** (R11) — recorded as ground truth,
  not scoped as work.
- **Legacy `trigger_assignments` rows** in task definitions 181 and 185 (185 is Gili's — ask before
  touching). Re-run the query rather than trusting the recorded finding; TRIGA-06's claim that 185
  was the only such row was wrong.

</deferred>

<code_context>
## Existing Code Insights (verified 2026-07-27)

### Reusable assets — waves 1–2 shipped these; 06/07/08 build on them, not beside them
- `autopilot/autopilot/tasks/fda_vocabulary.py` — `VALID_ACTION_TYPES` (now includes `view`),
  `VALID_TRIGGER_CONTEXT_KEYS`, `resolve_key_template`, `unpack_output`. Stdlib-only, shared by
  `mics_task` and `tools/validate_fda.py`. **R5's `{device_name}` token lands here.**
- `api/fda_validation.py` — hard-422 validation, 60 pytest cases. **R9 extends this.**
- `web_ui/react-src/src/components/ActionEditor.tsx` (419 lines, `view`/`output` supported),
  `ArgInput.tsx`, `ConditionBuilder.tsx`, `TriggerAssignmentPanel.tsx` (hosts the shared editor,
  `HANDLERS` removed), `VariablesPanel`. **R3's widget sits alongside these, and the raw editor
  must stay reachable as the R4 fallback.**

### Established patterns that constrain this work
- `check_for_detectors` iterates `self.hardware[group][id]` two levels deep; `init_hardware`
  (`task.py:203`) stores instances there for every group including `Modules`. Reach is fine —
  only `isinstance` identity fails (R6).
- `resolve_key_template` substitutes solely from the captured-values dict, so R5 requires passing
  `device_name` into the resolver, not just declaring a token.
- `add_Tracker` (`View.py:18`) writes `self.view.view` **only**, unlike `init_flags` which writes
  both. Detector keys are `{"view": …}`, never `{"flag": …}`.
- `@log_action` records kwargs only — `hardware.set(x)` never logs `x`, and a `set` event's
  envelope `level` is post-call hardware state. **An acceptance criterion of the form "confirm the
  action passed value N" is unverifiable from ES.** Only `Tracker.set` logs `value` — which is what
  makes R10's checkpoint 3 verifiable at all.

### Integration points
- Pi: `mics_task._build_trigger_action_list`, `_build_action_callable`, `check_for_detectors`.
- Backend: `api/fda_validation.py`; HANDSHAKE processing in `orchestrator_station.py` for R8's
  `trigger_sources`.
- UI: `TriggerAssignmentPanel` → `ActionEditor`.

### Environment facts that cost time in waves 1–2 — do not rediscover
- **`mics_api` and `mics_web_ui` have no bind mounts.** `docker exec mics_api pytest` runs the
  *image's* code. Test edits need `docker compose up --build -d api` first.
- **`orchestrator/prefs.json` is baked into the image.** `up -d` silently reuses the old image;
  credential rotation requires `--build`.
- **Vite output is code-split** — task-editor strings live in `TaskEditor-<hash>.js`, not `main.js`.
- Live ES/Kibana is **`132.77.73.217`** (`event_log_v2`). `.125` is a different cluster.
- **The editor holds the save entirely while any assignment is incomplete** (`7cd2734`/`4ac5a18`),
  reversing an earlier decision that caused data loss. Any new validation gate must account for the
  autosave/refetch interaction — do not re-litigate this from code alone.

</code_context>

---

*Phase: 24-trigger-assignment-action-lists*
*Context captured: 2026-07-26 from session direction + orchestrator code reading*
*Amended: 2026-07-27 — re-plan of 06/07/08 for sourceless-only scope (see `<replan_2026_07_27>`)*
