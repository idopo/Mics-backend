# Phase 23: Compute Operations (Compute Libs) — Context

**Gathered:** 2026-06-01
**Revised:** 2026-08-03 — reframed after Phase 24/25 landed; supersedes the original
compute-primitives design.
**Status:** Ready for re-planning (23-01/02/03 need rewriting against this shape)
**Source:** design spec `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`,
revised in discussion 2026-08-03.

<domain>
## Phase Boundary

Let researchers **compute a value inside a state, store it in a variable, and transition on
it** — without a developer editing locked toolkit source, and with every computation recorded
in the event log.

**Why now:** Phases 09–13 moved task logic off the Pi into GUI-assembled FDA-JSON-v2. That
removed the old source tasks' ability to do `self.target = random.choice([...])` in a state
body and branch on it. The action vocabulary (`hardware`/`flag`/`timer`/`special`/`method`)
has no value-producing member; the only door, `type:"method"`, requires editing centralized
locked source. Randomized trial type, jittered ITIs, randomized reward magnitude, counters,
and "every Nth trial" are all currently unexpressible.

**Scope correction — the variables half is already built.** Phase 24 landed the `variables`
registry in `mics_task.py` (`load_fda_from_json`, ~line 1017): each declared variable is ONE
`Tracker` registered in both `self.flags` and `self.view.view`, with optional `initial_value`,
readable as `{"flag": name}` or `{"view": name}`. `_validate_output_spec` and `_capture_output`
already write any action's return value into a declared variable. **Do not re-plan this.**

Phase 23's remaining delta is: **the operations, their extensibility mechanism, backend
validation, and the GUI.**

</domain>

<decisions>
## Implementation Decisions (LOCKED — confirmed with user 2026-08-03)

### The core reframe: a compute lib IS a hardware lib

Compute operations are delivered as **hardware libs that happen to have no pins**. Same
substrate, deliberately different surface.

**Substrate — reuse `hardware_libs` wholesale.** A compute lib is a row in `hardware_libs` /
`hardware_lib_versions`, which already provides everything required: `version_number`,
`source_code`, `sha256_hash`, `state` (unvalidated | beta | stable), `ast_metadata` for GUI
signatures, `validation_error`, and the promotion trail (`stable_at`, `stable_reason`,
`stable_pilot`). Shipped to the Pi by the existing `LOAD_HARDWARE_LIBS` path
(`pilot.py:670`), which writes source to disk and can `test_import` before a run.
**One new column: `kind: 'hardware' | 'compute'`.** No new table, no new transport, no new
versioning system.

**Runtime — must be an object, not a module of pure functions.** `log_action`
(`logging_utils.py:24,56`) only dispatches for `Mics_Tracker` or `Hardware` instances. A
module of free functions logs *nothing*. So a compute lib defines a class subclassing
`Hardware` (the base is pure metadata — `pin = None`, no GPIO required) and is instantiated
like any other device. Its methods carry `@log_action`, producing a `Hardware_Event` per call.

**Logging — op-level is a MUST, and result-level is already free.** Variables are Trackers,
so `Tracker.set()` already logs `{"id": "target", "value": true, "func_name": "set"}`. That
records the *result* but not the *operation* — `target = True` does not say
`random_bool(0.5) → True`, and the draw parameters are scientifically material (needed to
analyse a sequence, and to detect that p changed mid-experiment). The `Hardware` subclass +
`@log_action` closes that gap. Both events must appear.

### Surface — `type: "compute"` stays distinct

In FDA-JSON-v2 and the GUI, a compute op is `type: "compute"`, implemented as a **thin alias
over the same internal call-a-method-and-capture-`output` helper the `hardware` branch uses**.
Runtime cost is near zero. Kept distinct because:
- Validation can require `output` on compute (hardware may legitimately omit it).
- Preflight / `check_determinism()` may treat compute as pure and hardware as side-effecting.
- The state body stays readable — `compute: target = random_bool(0.5)` reads as intent;
  burying a coin-flip and a valve-open in one list does not.

### Authoring — lib editor, NOT a code box in the state

Python is written in the **hardware-lib editor**. The state body only *selects and wires*:
`output = op(args)`. Explicitly rejected: typing Python inline in a state body — it forfeits
versioning, sha, reuse, AST-driven GUI help, and (critically) has no object for `@log_action`
to attach to. User's words: *"not a code box in state cause we still want to create trackers
and @log_action it and have order in place."*

### Scoping — toolkit-scoped, same as hardware libs

Compute libs link to toolkits via `toolkit_hardware_libs`, exactly like hardware libs. Only
the active toolkit's libs reach the Pi. (Supersedes the original "one shared compute library
for all toolkits.")

### Version resolution — latest stable, user override wins

Resolution order for BOTH lib kinds:
1. Task-definition pin (`hw_lib_versions`) — an explicit user choice, wins.
2. Toolkit link `default_version_id` — also a user choice.
3. **Latest stable** (`hardware_libs.stable_version_id`).
4. Nothing deployable → surface as a preflight issue, not a silent skip.

**This is a behaviour change to existing code, at TWO sites — not one.** Today the chain is
pin → `active_version_id`; `stable_version_id` is never consulted, and an unvalidated active
version is silently dropped with only a log warning. Both sites must be fixed:
1. `orchestrator_station.py:~868` (`_send_hardware_libs_if_needed`) — which source is shipped.
2. **`api/routers/toolkit_dispatch.py::get_dispatch_spec`** — found by research, and the more
   consequential of the two: it decides which `source_code` is actually exec'd and run.

Apply the corrected chain to **both** lib kinds — diverging compute from hardware would be worse
than fixing both. Also unify `hw_introspect.toolkit_hw_capabilities`, which uses
`active_version_id` directly: a third divergent resolution site is a latent bug, and CMP-17
already touches the other two.

No separate approval gate: compute libs inherit the existing unvalidated → beta → stable
promotion flow as-is.

### Pi-side registration — auto-provisioned (LOCKED 2026-08-03, post-research)

**Research correction:** `toolkit_hardware_libs` governs version pinning and the
`LOAD_HARDWARE_LIBS` file-write/test-import path **only**. It has no effect on whether a class
becomes reachable as `self.hardware[group][ref]` on the Pi. Reachability is governed exclusively
by `hardware_modules` + `toolkit.hardware_module_ids` + a per-pilot `pilot_hardware_config` row.
Without that row, `init_hardware()` (`task.py:162-217`) hits a `KeyError`, **silently logs and
skips**, and any `compute` action referencing the module dies later at FDA-load with a bare
`KeyError` on `self._semantic_hw[ref]`.

**Decision: a compute lib needs BOTH links, and the pilot-config row is auto-provisioned.**
Register the compute class as a `hardware_modules` row + `hardware_module_ids` membership (so the
existing instantiation *and* the existing op-name validation via
`hw_introspect.toolkit_hw_capabilities` both work unchanged — building a bypass path would mean
building a parallel validation path too). The per-pilot `pilot_hardware_config` row, which for a
compute module is trivially `{"class_name": "..."}` and nothing else, is **created automatically
by the backend** for `kind='compute'` modules. **No Pi-side change** — the row is real and
inspectable in the UI, the Pi path is untouched.

Rationale: requiring a manual per-rig step for something with no hardware would reintroduce
exactly the per-rig fragility Phases 09–13 removed. A researcher adds a compute lib once and it
works on every rig.

Consequences the plan must handle:
- `preflight_validate`'s existing `incomplete_config` check **will false-positive** on a
  legitimate zero-param compute module config — needs a special case.
- Every `Hardware` subclass **must override `release()`** or `Task.end()` raises on every run.

### Discoverability

- `variable_never_written` preflight issue — a transition reads a variable no reachable
  upstream state writes. Rides **Phase 25's existing preflight issue renderer** (the
  `view_key_unresolved` path, incl. the skip-save loop). Promoted from the original plan's
  "nice-to-have" to load-bearing: a silently-`None` variable reads as a mysterious dead
  branch on the rig.
- Read-only variables inspector inside the task editor (variable → writers, readers). Not an
  authoring surface, not a page.

### UI — one addition per surface, no new pages

- **Hardware Libraries page**: compute libs listed there with a `kind` filter chip.
- **State body**: action-type list gains exactly **one** entry, "Compute" (not N primitives).
  It renders a single compact row `[output var] = [op ▾] ( [args] )`, ops grouped by lib,
  same visual weight as a hardware action.
- **Variables**: read-only inspector; declaration stays inline in the compute `output` field
  (typing a new name auto-declares it into `variables` and makes it immediately selectable as
  a transition operand).

### Backend validation

`_validate_task_definition()` rejects (422, hard — distinct from the soft hardware-drift path):
a `compute` `output` not declared in `variables`; a variable name colliding with toolkit
`FLAGS` / `SEMANTIC_HARDWARE` / view keys; a transition/condition referencing an undeclared
variable. `api/fda_utils.py` ref scanner extended to cover `compute` `output` names.

**Research correction:** `api/fda_validation.py` **already exists** — built in plan 24-02, and
its own docstring says *"Phase 23 appends its compute checks here."* **Extend it; do not create
it.** Taking this document's earlier "new sibling module" wording literally would produce
duplicate and conflicting validation logic.

`variable_never_written` (CMP-15) has **no existing backend precedent** — "rides Phase 25's
renderer" is true of the frontend issue shape and rendering convention only. The write/read
analysis is genuinely new code. **v1 semantics: existence check** (a variable read by any
transition/condition that no `compute` action anywhere writes), not full graph reachability —
reachability analysis would imply a confidence the FDA's guard semantics can't support.

### Seed content

Ship a starter compute lib covering the known needs — random/copy (`random_choice`,
`random_int`, `random_float`, `random_bool`, `assign`) and numeric
(`add`, `subtract`, `multiply`, `divide`, `modulo`, `minimum`, `maximum`, `clamp`;
raise on divide/modulo by zero). Stdlib `random`/`math`/builtins only. This is now **seed
content in an extensible system**, not a closed curated set — the point of the phase is that
a researcher can add sampling-without-replacement or weighted choice themselves.

No comparison/boolean-logic ops: branching stays in transitions, and Phase 15 DNF conditions
already compose booleans. A variable read back as its own arg (`add(counter,1)→counter`) is
the supported counter/tally pattern.

### Branching

Branching stays in **FDA transitions (idiomatic)** — the pair of guarded transitions *is* the
if/else. Compute ops only produce values. **No `if`-action type.**

### Determinism

Compute runs **at state entry**, so transition guards only read the stored result and
`check_determinism()` never re-runs randomness.

### Operand-namespace consistency (LOCKED 2026-08-05 — plan 23-11, CMP-20–25)

Added after rig use of plans 01–10. Not new compute capability — a consistency pass over the
operand pickers. **The governing rule: write by name (flag/tracker actions); read anything
through `view`.**

**The trigger.** Declared variables work in transition conditions and appear in the flags
dropdown, but are invisible inside `if`/`else` conditions in the state builder. Cause is a
single React call site — `IfActionEditor.tsx:82-87` renders `<ConditionBuilder>` with
`condition/toolkit/detectorChannels/onChange` and drops `variableNames` **and**
`hwModuleNames`, even though the same component forwards `variableNames` into its then/else
`ActionEditor`s (lines 108, 183). Everything below the GUI already works: `fda_utils.py::
_scan_action_conditions` walks `if`-action conditions, `fda_validation.py::
validate_compute_variables` accepts the operands, and `_build_condition_operand` is the *same*
builder transitions use. Not a design decision — a wiring bug.

**The equivalence is exact, and was verified before adoption — do not re-litigate it.**
`{flag: X}` → `self.flags[X].value`; `{view: X}` → `self.view.view[X].get_state()`, and
`Tracker.get_state()` is literally `return self.value`. `init_flags` (`mics_task.py:339-340`)
and the variables loop (`:1060-1061`) register the **same Tracker instance** in both dicts. So
retiring `flag` from the *read* pickers changes nothing at runtime. `view` is the strict
superset: flags + variables + hardware + detector-derived keys (which are view-only, which is
why Phase 25's licker comparison uses view — that choice was correct).

**`{hardware: X}` is retired because it is broken, not merely redundant.**
`_build_condition_operand` (`mics_task.py:633-634`) reads `_hw.value`; no `Hardware` class,
subclass, or seed lib defines `.value` — the base (`hardware/__init__.py:148-153`) has only
`hardware_state` / `get_state()`. That operand raises `AttributeError` whenever evaluated. The
working read path for hardware is `{view: X}` → `get_state()`.

**Backward compatibility — escape, not migration.** Stored `{flag:...}` / `{hardware:...}`
operands must round-trip untouched. Use the **keep-current escape the codebase already applies
twice** (`ArgInput.tsx:82` for the trigger pill, `ConditionBuilder.tsx:122` for unknown view
keys): render the legacy type in the `<select>` only when the stored operand already has that
shape, labelled legacy; it disappears once edited. Do **not** rewrite saved definitions and do
**not** drop the type from `getOperandType` — a `<select>` whose `value` is absent from its
options renders blank and the next `setType` silently corrupts the operand. Backend and Pi keep
both branches.

**Two invariant holes this promotes to load-bearing** (both must land with the UI change, or the
rule has live counterexamples):
- `trial_counter` auto-created at `mics_task.py:1042-1044` goes into `self.flags` only, never
  `self.view.view` — and `_valid_flag_names` whitelists the name, so `{"view":"trial_counter"}`
  saves cleanly then `KeyError`s mid-run on any toolkit whose FLAGS lacks a Trial_Tracker.
- `validate_compute_variables`'s `valid_names` (`fda_validation.py:245`) omits
  `toolkit.semantic_hardware`, while `ConditionBuilder.tsx:100` already offers it in the view
  picker — a 422 on semantic (non-backend-authored) toolkits **today**.

**Also in scope, same theme:**
- `ArgInput` gains `view` replacing `! Flag` (CMP-23) — an argument value is a read. `_resolve_arg`
  has supported `{"view": key}` since Phase 24 (`:511-518`); no picker could emit it.
- `_resolve_arg`'s view branch reads `.value`, `_build_condition_operand`'s reads `get_state()`.
  Unify on `get_state()` or "view means one thing everywhere" is false for hardware.
- `_build_state_method`'s pre-validation loop (`:901`) rejects `type:"view"` — closes the open
  item in `deferred-items.md`. A `view` action works inside an `if` branch (the loop does not
  recurse) but raises at FDA load directly in a state body.
- Variables selectable as a `type:"flag"` action ref (CMP-22, the write side), mapped to the
  `'Tracker'` method set — **not** the `?? 'Counter_Tracker'` default, whose `decrement`/`reset`
  entries do not exist in `Tracker.py` at all and `AttributeError` on the rig. Remove those two.

**Unchanged:** flags are still declared on toolkits and written with tracker methods in the state
builder. This is a read-path change only.

### Claude's Discretion

- Internal structure of the compute device class / method dispatch.
- React component decomposition within the existing StateBodyPanel/ActionEditor/ConditionBuilder.
- Test harness shapes (negative-test cases, the gonogo-translation verification task).
- Exact presentation of the legacy-operand escape (label wording, whether it is visually muted),
  so long as it round-trips and cannot silently rewrite.

</decisions>

<specifics>
## Specific Ideas

- **Canonical verification task**: translate `gonogo`'s random-target logic into FDA-JSON-v2 —
  `"variables": {"target": {}}`, a `trial_onset` state with a compute action
  `random_bool(0.5) → target`, and two guarded transitions on
  `{"view":"target","op":"==","rhs":{"literal":true}}` / `false`. Both branches must be
  reachable across trials; `target` recomputed once per entry. Verify **both** the
  `Hardware_Event` (op + args) and the `Tracker` set event (result) reach the event log.
- **Hot-reload**: `variables`/compute flow through the existing `UPDATE_FDA` store;
  `hot_update_fda()` re-runs `load_fda_from_json()`, so variables are re-created and reset —
  intended, not a bug.

</specifics>

<forward_compat>
## Deferred, but plan for it now

**Third-party packages + per-Pi package management stay deferred.** User-authored Python is
already solved (source ships from the DB and is test-imported); third-party wheels (numpy,
scipy) are not, and that is genuinely a package-management problem. Three cheap things now so
the deferral is not rework later:

1. **Declare dependencies from day one** — compute lib versions carry an explicit
   imports/requires field. Validation today accepts stdlib only and rejects the rest with a
   clear message, but the dependency is *declared*, not inferred from source. When package
   management lands it reads a field that already exists.
2. **Wire compute libs into the existing `test_import` round-trip** (`l_load_hardware_libs`
   already imports and reports back pre-run) — the natural place a missing dependency surfaces
   as a preflight failure rather than a mid-session crash.
3. **Reserve a `compute_lib_import_failed` preflight issue class** alongside
   `view_key_unresolved`, so the surfacing path exists before there is anything to surface.

</forward_compat>

<deferred>
## Deferred Ideas

- **`expr` escape-hatch / inline Python in a state** — rejected for this phase (see Authoring).
  Forfeits versioning and op logging. Full design in
  `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`.
- **Compute in trigger assignments** — deferred (user decision, 2026-08-03). `ActionEditor` is
  shared between `StateBodyPanel` and `TriggerAssignmentPanel`, and the latter already threads
  `variableNames`, so the compute option must be **actively gated off** in the trigger context
  (via the existing `allowTriggerContext` flag, mirroring `ArgInput.tsx:76`) rather than simply
  left unwired — otherwise it appears there and half-works. UI-only restriction: the Pi builds
  both action lists through the same `_build_action_callable`, so a hand-authored compute action
  in a trigger list would still run. Revisit as its own small phase.
- **`if`-action / nested then-else action branching** — transitions handle branching.
- **Typed variables** — untyped generic scratch for v1; revisit only on concrete need.
- **Sandboxing user compute code** — a compute lib runs arbitrary Python in the task thread.
  Mitigated for now by the stable-version promotion flow rather than a sandbox. Revisit if
  authoring widens beyond the current lab.

</deferred>

---

*Phase: 23-compute-primitives-variables*
*Context revised: 2026-08-03 — compute-as-hardware-lib reframe*
