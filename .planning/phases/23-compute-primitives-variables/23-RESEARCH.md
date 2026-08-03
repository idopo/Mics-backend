# Phase 23: Compute Operations (Compute Libs) - Research

**Researched:** 2026-08-03
**Domain:** Pi task-runtime hardware dispatch (autopilot/mics_task.py), FastAPI hardware-lib
registry (api/routers/hardware_libs.py, hardware_modules.py, toolkit_dispatch.py), React FDA
editor (ActionEditor/StateBodyPanel/HardwareLibs)
**Confidence:** HIGH (all findings verified against current code, not the superseded plans)

## Summary

The CONTEXT.md reframe — "a compute lib IS a hardware lib, distinguished by a new `kind`
column" — is architecturally sound for the **storage/versioning** layer, and the codebase
already has almost every extension point pre-built for it (a `_build_action_callable` dispatch
table, an `api/fda_validation.py` module whose own docstring says "Phase 23 appends its compute
checks here", an `ActionEditor.tsx` with a live `handleTypeChange` switch and a
`HardwareActionFields.tsx` component that is a near-literal template for a compute op picker).

The one place the CONTEXT undersells the work is **Pi-side instantiation**. A `Hardware`
subclass is not reachable from `_build_action_callable` (`self.hardware[group][ref]` /
`self._semantic_hw[ref]`) unless it went through `init_hardware()`, and `init_hardware()`
unconditionally looks up `pin_numbers[type][pin]` — i.e. a `pilot_hardware_config` row — before
it will instantiate anything, silently skipping (logged, not raised) any module that has none.
**A compute lib therefore needs the exact same three-part registration a hardware module needs:
a `hardware_modules` row (name + class_name + hardware_lib_id), inclusion in the toolkit's
`hardware_module_ids`, and a `pilot_hardware_config` row per pilot** — even though that config
row will typically contain nothing but `{"class_name": "..."}`. This is not optional plumbing
the planner can skip; it is the only path that makes `type:"compute"` actions resolve on the
Pi, and it is also the only path `api/fda_validation.py`'s existing `module_methods` machinery
already knows how to validate op names against. Two direct consequences: (1) an empty-but-valid
compute config row will trip `preflight_validate`'s existing `incomplete_config` check (a false
positive that must be fixed or special-cased), and (2) every `Hardware` subclass — including the
seed compute lib — must override `release()` with a no-op, or `Task.end()` raises on every run
(`raise Exception('The release method was not overridden by the subclass!')`).

**Primary recommendation:** Reuse the hardware-module/pilot-config path wholesale for compute
(no new instantiation mechanism); add exactly one DB column (`hardware_libs.kind`), one join
column on the hardware-modules list endpoint (`lib_kind`), one new `_build_action_callable`
branch that is a byte-for-byte copy of the `hardware` branch's call-and-capture pattern with
`output` made mandatory, one new small React component modeled on `HardwareActionFields.tsx`,
and extend the version-resolution chain and `VALID_ACTION_TYPES` in the four places that already
enumerate action types. Budget real effort for the two genuinely new pieces that have no
precedent in the codebase: the `variable_never_written` reachability check (CMP-15) and fixing
the `incomplete_config` preflight false-positive for zero-param compute modules.

<user_constraints>
## User Constraints (from CONTEXT.md, revised 2026-08-03)

### Locked Decisions

- **Core reframe:** compute libs are hardware libs (rows in `hardware_libs`/
  `hardware_lib_versions`) with one new column `kind: 'hardware' | 'compute'`. No new table, no
  new transport, no new versioning system. Shipped via the existing `LOAD_HARDWARE_LIBS` path.
- **Runtime must be an object, not free functions** — a class subclassing `Hardware` (pure
  metadata, `pin = None`, no GPIO), instantiated like any device, methods carry `@log_action`.
  `log_action` only dispatches for `Mics_Tracker`/`Hardware` instances.
- **Both events must log per compute call:** a `Hardware_Event` (op + args, from `@log_action`)
  AND the `Tracker.set()` result event (value). Neither alone is sufficient — CMP-16.
- **`type: "compute"` stays a distinct FDA action type** — a thin alias over the same
  call-a-method-and-capture-`output` helper the `hardware` branch uses. Distinct so validation
  can require `output` on compute (hardware may omit it), and so preflight/`check_determinism()`
  can treat compute as pure vs hardware as side-effecting.
- **Authoring happens in the hardware-lib editor, not a code box in the state body.** Explicitly
  rejected: typing Python inline in a state. State body only selects and wires
  `output = op(args)`.
- **Scoping:** compute libs link to toolkits via `toolkit_hardware_libs`, exactly like hardware
  libs. Only the active toolkit's libs reach the Pi.
- **Version resolution (BOTH lib kinds, corrects existing behaviour):** (1) task-definition pin
  `hw_lib_versions`, (2) toolkit link `default_version_id`, (3) **latest stable**
  (`hardware_libs.stable_version_id` — currently never consulted), (4) nothing deployable →
  preflight issue, not a silent skip. No separate approval gate — compute libs inherit the
  existing unvalidated→beta→stable flow as-is.
- **Discoverability:** `variable_never_written` preflight issue (a transition reads a variable
  no reachable upstream state writes) rides Phase 25's existing preflight issue renderer
  (`view_key_unresolved` path, including the skip-save loop). Promoted to load-bearing. Plus a
  read-only variables inspector (writers/readers) in the task editor — not an authoring surface.
- **UI — one addition per surface, no new pages:** Hardware Libraries page gets a `kind` filter
  chip; StateBodyPanel action-type list gets exactly one new entry "Compute" rendering
  `[output var] = [op ▾] ( [args] )`, ops grouped by lib; typing a new `output` name auto-declares
  it into `variables`.
- **Backend validation:** `_validate_task_definition()` (soft path, `api/routers/toolkits.py`)
  rejects nothing new; the HARD 422s (compute `output` not declared, name collisions with
  FLAGS/SEMANTIC_HARDWARE/view keys, transition referencing an undeclared variable) live in
  `api/fda_validation.py` — **this file already exists (built in Phase 24-02), its own
  `collect_hard_errors()` docstring says "Phase 23 appends its compute checks here" — Phase 23
  EXTENDS it, does not create a new sibling module** (CONTEXT.md's "new
  api/fda_validation.py sibling module" phrasing predates this discovery; see Common Pitfalls).
  `api/fda_utils.py` ref scanner extended to cover `compute` `output` names.
- **Seed content:** stdlib `random`/`math`/builtins only — `random_choice`, `random_int`,
  `random_float`, `random_bool`, `assign`, `add`, `subtract`, `multiply`, `divide` (raise on /0),
  `modulo` (raise on /0), `minimum`, `maximum`, `clamp`. Extensible, not closed. No
  comparison/boolean-logic ops (branching stays in transitions).
- **Branching stays in FDA transitions.** No `if`-action type for compute.
- **Determinism:** compute runs at state entry; transition guards read stored results only;
  `check_determinism()` never re-runs randomness.
- **Last-write-wins on re-entry.** No reset between trials.
- **Hot-reload:** `variables`/`compute` flow through the existing `UPDATE_FDA` →
  `hot_update_fda()` → `load_fda_from_json()` path; variables are re-created and reset on
  hot-reload — intended.

### Claude's Discretion

- Internal structure of the compute device class / method dispatch.
- React component decomposition within the existing StateBodyPanel/ActionEditor/ConditionBuilder.
- Test harness shapes (negative-test cases, the gonogo-translation verification task).

### Deferred Ideas (OUT OF SCOPE)

- `expr` escape-hatch / inline Python in a state — forfeits versioning and op logging.
- `if`-action / nested then-else action branching — transitions handle branching.
- Typed variables — untyped generic scratch for v1.
- Sandboxing user compute code — a compute lib runs arbitrary Python in the task thread,
  mitigated by the stable-version promotion flow, not a sandbox.
- Third-party PyPI packages + per-Pi package management — CMP-19 reserves three cheap hooks
  (declared-dependencies field, `test_import` wiring, `compute_lib_import_failed` preflight
  issue class) so the deferral is not rework later.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| CMP-01 | `variables` registry in FDA-JSON-v2 | Already built (Phase 24, `mics_task.py:1023-1033`). Verified in place — see Architecture Patterns. No new work; a task in the plan should assert this still holds, not build it. |
| CMP-02 | Variables as Trackers in `self.flags` + `self.view.view`; `_validate_output_spec`/`_capture_output` write any output | Already built (`mics_task.py:521-539`, confirmed read). No new work. |
| CMP-03 | `type:"compute"` entry-action, thin alias over call-and-capture | `_build_action_callable` dispatch table documented line-by-line (Architecture Patterns, Code Examples). Exact insertion point and pattern to copy identified (the `hardware`/`atype in ("hardware","timer")` branch, `mics_task.py:697-711`). |
| CMP-04 | Compute lib = `Hardware` subclass, seed ops, no comparison ops | `Hardware.__init__` signature and the mandatory `release()` override documented (Architecture Patterns, Common Pitfalls). `log_action`'s Hardware branch traced (`logging_utils.py:56-90`). |
| CMP-05 | Last-write-wins on re-entry | No new mechanism needed — `_capture_output`/`Tracker.set` already overwrite; state re-entry re-runs `entry_actions` unconditionally today. Verified by reading `_build_state_method` call pattern. |
| CMP-06 | Hot-reload flows `variables`/`compute` through `UPDATE_FDA` | Already true structurally — `hot_update_fda()` calls `load_fda_from_json()` (verified via `l_update_fda` in `pilot.py:646-668`), which rebuilds variables (step 2b) before transitions (step 5). No new work once CMP-03 lands. |
| CMP-10 | Hard 422s in `api/fda_validation.py`, incl. output-declared / collision / undeclared-var-reference | File already exists (Phase 24-02) with `VALID_ACTION_TYPES`, `_validate_action`, `collect_hard_errors` explicitly reserving a Phase-23 slot — full read included in Code Examples. Output-collision check (`_valid_flag_names`) already generalizes. |
| CMP-11 | `fda_utils.py` ref scanner covers `compute` output | `scan_fda_for_refs`/`_scan_actions` read in full (`fda_utils.py:5-50`) — exact one-line change identified (`action_type in (...)` tuple). Also flags that the SOFT drift-badge path (`_validate_task_definition`) needs the same tuple extended, for the same reason hardware/method are in it. |
| CMP-12 | `kind` column on `hardware_libs`, no new table | Full `HardwareLib`/`HardwareLibVersion`/`ToolkitHardwareLib`/`HardwareModule`/`PilotHardwareConfig` schema read (`api/models.py:639-713`). Migration pattern for `ADD COLUMN IF NOT EXISTS` located and quoted (`api/db.py`). |
| CMP-13 | GUI "Compute" action row, ops grouped by lib | `ActionEditor.tsx` and `HardwareActionFields.tsx` read in full — exact clone-and-adapt pattern documented (Code Examples), including why `OutputCapture.tsx`'s toggle-based reuse does NOT satisfy "output is mandatory". |
| CMP-14 | Variables in condition-operand dropdown | Already built (Phase 24, plan 08 / TRIGA-14). No new work — verify only. |
| CMP-15 | `variable_never_written` preflight issue via Phase 25's renderer | Phase 25's `preflight_validate` (`toolkit_dispatch.py:144-372`) and `HardwareCheckModal.tsx` issue-rendering convention read in full. Flags precisely: NO existing reachability/graph-walk code exists anywhere in the codebase — this is genuinely new logic, only the issue-shape/rendering *convention* is reused, not a function body (Common Pitfalls). |
| CMP-16 | Op-level `Hardware_Event` + result-level `Tracker` event, both must log | `log_action` read in full (`logging_utils.py`) — confirms both paths fire independently and unconditionally once the class hierarchy is right; no gap once CMP-03/04 land correctly. |
| CMP-17 | Version resolution pin→toolkit-default→stable→issue, for BOTH kinds | The CURRENT wrong chain located and quoted verbatim in two places: `orchestrator_station.py:852-900` (`_send_hardware_libs_if_needed`, used for `LOAD_HARDWARE_LIBS`) and `toolkit_dispatch.py:29-113` (`get_dispatch_spec`, used for actual Pi instantiation — this second site was NOT named in CONTEXT.md and must also be fixed, since it is what determines which version's `source_code` actually runs). |
| CMP-18 | Hardware Libraries page `kind` filter chip | `HardwareLibs.tsx` read in full (116 lines) — trivial addition point identified. |
| CMP-19 | Declared deps field, `test_import` wiring, `compute_lib_import_failed` reservation | `l_load_hardware_libs`/`receive_hardware_libs` read (`pilot.py:670-691`) — confirmed `test_import` is a real, already-implemented flag that is simply never set to `True` by the current orchestrator caller. Wiring it is an orchestrator-side one-line change, not new Pi protocol. |
</phase_requirements>

## Architecture Patterns

### The five places "action type" is enumerated — all must learn about `compute`

Every one of these currently lists exactly `{hardware, flag, timer, special, method, if, view}`
and must gain `compute`. Missing any one produces a subtly different failure mode (silent
no-op vs. 422 vs. TypeScript compile error vs. save-time acceptance of something the Pi rejects
at session start):

1. **`autopilot/autopilot/tasks/mics_task.py::_build_action_callable`** (line 684-811) — the Pi
   dispatch table. Raises `ValueError` at FDA-load time for an unknown type.
2. **`autopilot/autopilot/tasks/fda_vocabulary.py::VALID_ACTION_TYPES`** (line 9-11) — single-sourced
   with `tools/validate_fda.py`, the Pi-side CLI validator.
3. **`api/fda_validation.py::VALID_ACTION_TYPES`** (line 42) — the hard-422 save-time gate. Its own
   module docstring/`collect_hard_errors` docstring literally reserves this: *"Phase 23 appends
   its compute checks here."*
4. **`api/fda_utils.py::_scan_actions`** (line 39: `if action_type in ("hardware", "flag", "timer", "method")`)
   — feeds BOTH `scan_fda_for_refs` (soft drift-badge path in `routers/toolkits.py::_validate_task_definition`)
   and the hw-lib-update impact scan (`hardware_libs.py::_flag_broken_task_defs`). Compute ops must be
   added here too, not just to the `output`-name scanner (CMP-11), or a compute lib rename/removal
   will never flag affected task definitions.
5. **`web_ui/react-src/src/components/ActionEditor.tsx`** — `TYPE_COLORS`, `TYPE_LABELS`, the `<select>`
   options list (line 243-249), and `handleTypeChange`'s `else if` chain (line 165-190).

### The Pi dispatch chain a `compute` action reuses (verified read, `mics_task.py`)

```
type:"hardware"/"timer" branch (697-711) — the pattern to copy verbatim for "compute":

    if "group" in action:
        group = action["group"]
        hw = self.hardware[group][ref]
    else:
        hw = self._semantic_hw[ref]
    self._validate_output_spec(action)
    def _hw_call(_hw=hw, _method=method, _action=action):
        args   = [self._resolve_arg(a) for a in _action.get("args", [])]
        kwargs = {k: self._resolve_arg(v) for k, v in _action.get("kwargs", {}).items()}
        result = getattr(_hw, _method)(*args, **kwargs)
        self._capture_output(_action, result)
    return _hw_call
```

For `compute`, the only substantive difference is that `_validate_output_spec` must be made
**mandatory** (raise if `action.get("output")` is `None`), since CMP-03 requires `output` to be
present on every compute action — `hardware`/`method` treat it as optional today.

`self._semantic_hw` and `self.hardware["Modules"]` are populated identically for hardware and
compute modules — see next section. A compute action can therefore use either `{"ref": name}`
(resolves via `_semantic_hw`) or `{"ref": name, "group": "Modules"}` (direct-ref form) exactly
like a hardware action.

### THE HIGH-RISK FINDING: Pi-side instantiation requires the full hardware-module ceremony

This was flagged in the task prompt as the highest-risk unknown. Traced end-to-end through
`init_hardware()` (`autopilot/autopilot/tasks/task.py:162-217`):

```python
def init_hardware(self):
    self.hardware = {}
    pin_numbers = prefs.get('HARDWARE')          # = _merge_prefs_hardware(kwargs["PREFS_HARDWARE"])
    for type, values in self.HARDWARE.items():   # = _resolve_hardware_classes(kwargs["HARDWARE"])
        self.hardware[type] = {}
        for pin, handler in values.items():
            try:
                hw_args = pin_numbers[type][pin]      # <-- KeyError if no pilot_hardware_config row
                ...
                hw = handler[hw_args['name']](**hw_args, event_dispatcher=..., pi=..., run_id=...)
                self.hardware[type][pin] = hw
                self.view.view[pin] = hw
            except Exception as e:
                self.logger.exception(...)            # <-- SILENTLY SKIPPED, not raised
```

`self.HARDWARE["Modules"]` comes from the START payload's `HARDWARE` key
(`orchestrator_station.py::_inject_backend_toolkit_spec`, line 822-850), which in turn comes
from `GET /toolkits/{id}/dispatch-spec` (`api/routers/toolkit_dispatch.py::get_dispatch_spec`,
line 29-113). That endpoint builds `hardware["Modules"][module.name]` **only from
`toolkit.hardware_module_ids` joined to `hardware_modules`** — it does **not** read
`toolkit_hardware_libs` at all. `pin_numbers["Modules"][module.name]` (i.e. `prefs_hardware`) is
populated **only if a `pilot_hardware_config` row exists** for that `(pilot_id, name)` — if none
exists, `cfg` is `None` and the module never enters `prefs_hardware["Modules"]` at all, meaning
`init_hardware()`'s `pin_numbers[type][pin]` lookup raises `KeyError`, is caught, logged, and
the module is silently absent from `self.hardware["Modules"]`. Any later `type:"compute"` action
referencing that module then fails **at FDA-load time** with a plain `KeyError` on
`self._semantic_hw[ref]` — a load-time failure, not silent, but with no context pointing at "you
forgot to configure this compute module on this pilot."

**Conclusion — verified, not inferred:** `toolkit_hardware_libs` (what CONTEXT.md calls the
compute-lib-to-toolkit link) governs **version pinning and the `LOAD_HARDWARE_LIBS` file-write/
test-import path only** (`hardware_libs.py::list_toolkit_hardware_libs`,
`orchestrator_station.py::_send_hardware_libs_if_needed`). It has **no effect whatsoever** on
whether a class becomes reachable as `self.hardware[group][ref]` on the Pi. That reachability is
governed exclusively by `hardware_modules` + `toolkit.hardware_module_ids` +
`pilot_hardware_config`. **A compute lib therefore needs BOTH links**: `toolkit_hardware_libs`
(for versioning/`LOAD_HARDWARE_LIBS`) AND a `hardware_modules` row + `hardware_module_ids`
membership + a `pilot_hardware_config` row per pilot (for actual instantiation). This doubles
the registration ceremony CONTEXT.md's prose implies, and is corroborated independently by
`api/fda_validation.py`'s existing hard-422 machinery: `_validate_action_method`'s
`module_methods` lookup (used to validate a hardware action's `method` is real) is populated by
`hw_introspect.toolkit_hw_capabilities(db, toolkit.hardware_module_ids)` — i.e. **the exact same
validation infrastructure CMP-10 needs for compute op names already only works for things
registered as `hardware_modules`.** Building a parallel/bypass instantiation path for compute
would also mean building parallel validation, which contradicts "reuse the substrate wholesale."

**Recommendation (Claude's Discretion per CONTEXT.md):** do not invent a new instantiation
mechanism. Register a compute lib exactly like a hardware module (a `hardware_modules` row whose
`class_name` is the compute class, added to `toolkit.hardware_module_ids`). Since a compute
module's `pilot_hardware_config` row will almost always be `{"class_name": "..."}` and nothing
else, the plan should make that a one-click affordance in `PilotHardwareConfig.tsx`'s existing
"module registry picker" flow (Phase 17 UI, already supports pre-filling `class_name` +
constructor args from AST — a compute class typically has zero extra `__init__` params, so the
picker already produces the right minimal row). This still requires **a manual per-pilot step
before a compute-using toolkit will run on that pilot** — flag as an open question below on
whether to auto-provision it.

### `Hardware` base class contract a compute lib class MUST satisfy

Verified in `autopilot/autopilot/hardware/__init__.py:105-164`:

```python
class Hardware(object):
    is_trigger = False
    pin = None
    type = ""
    input = False
    output = False

    def __init__(self, name=None, group=None, init_hardware_state=HardwareState.CLOSED,
                 event_dispatcher=None, **kwargs):
        ...
        self.hardware_type = kwargs['type']   # KeyError if 'type' absent — but init_hardware()
                                               # always injects it (via _merge_prefs_hardware,
                                               # which sets config["type"] = group when absent)
        self.event_dispatcher = event_dispatcher

    def release(self):
        raise Exception('The release method was not overridden by the subclass!')
```

`release()` is called unconditionally for **every** object in `self.hardware` when a task ends
(`autopilot/autopilot/tasks/task.py:434-441`, `Task.end()`):

```python
def end(self):
    for k, v in self.hardware.items():
        for pin, obj in v.items():
            obj.release()   # <-- raises if the compute class doesn't override this
```

**Every compute lib class — including the seed lib — MUST define `def release(self): pass`** (or
equivalent no-op). This is not documented anywhere in CONTEXT.md and is a hard requirement for
any task using a compute lib to end cleanly. Recommend this be enforced at AST-validation time
(reject upload of a compute-kind lib class with no `release` method) or at minimum documented
prominently in the compute-lib authoring UI/seed template.

`is_trigger = False` (class default) means `init_hardware()`'s `if hw.is_trigger:
hw.assign_cb(...)` branch is skipped — no `assign_cb` override needed. `hardware_state` defaults
to `HardwareState.CLOSED` (0); `log_action`'s Hardware branch logs `level=int(self.hardware_state)`
unconditionally — for a compute class this will always log `level=0`, which is semantically
meaningless but harmless (no compute op sets `hardware_state`). Not a bug to fix, just an
expected artifact worth noting in the seed lib's docstring.

### The variables registry (CMP-01/02 — already built, verify only)

`load_fda_from_json()`, step 2b, `mics_task.py:1018-1033`:

```python
for var_name, var_def in (definition.get("variables") or {}).items():
    if var_name in self.flags:
        raise ValueError(f"... variable '{var_name}' collides with an existing flag ...")
    initial = (var_def or {}).get("initial_value", None)
    tracker = Tracker(info_type=var_name, initial_value=initial,
                      event_dispatcher=self.event_dispatcher)
    self.flags[var_name]     = tracker
    self.view.view[var_name] = tracker
```

Runs AFTER `_semantic_hw` construction and BEFORE state methods are built (step 3) and BEFORE
transitions are registered (step 5) — so a compute action's `output` into a variable, and a
transition condition reading that variable, both resolve correctly regardless of declaration
order in the FDA JSON. `_validate_output_spec`/`_capture_output` (lines 521-539) are fully
generic over `self.flags`, so they need zero changes for `compute` to write into them.

### Version-resolution chain — TWO sites need the CMP-17 fix, not one

CONTEXT.md names only `orchestrator_station.py:868` / `hardware_libs.py:541`. Verified reading
found a **second, more consequential site**:

1. **`orchestrator_station.py::_send_hardware_libs_if_needed`** (line 852-900) — governs
   `LOAD_HARDWARE_LIBS` (file-write + optional `test_import`). Chain today: task-def pin →
   `lib.get("active_state")`. `stable_version_id` never read. Matches CONTEXT.md's description.

2. **`api/routers/toolkit_dispatch.py::get_dispatch_spec`** (line 29-113) — governs what
   `source_code` actually gets exec'd into the running class via `_resolve_hardware_classes`
   (i.e. what code truly runs, independent of what `LOAD_HARDWARE_LIBS` merely writes to disk for
   test-import). Chain today (line 62-81):
   ```python
   pinned_version_id = hw_versions.get(str(module.hardware_lib_id))  # task-def pin
   if pinned_version_id:
       version_id = pinned_version_id
   else:
       lib = ... SELECT active_version_id FROM hardware_libs ...
       version_id = lib.active_version_id     # <-- stable_version_id never consulted here either
   ```
   This site was not named in CONTEXT.md/CMP-17 and **must also be fixed** — it is the dispatch
   path that actually matters for backend-authored (sourceless) toolkits, which per
   `STATE.md`'s 2026-07-27 scope change is now the only toolkit shape being developed against.

Also note `hw_introspect.py::toolkit_hw_capabilities` (line 156, `LEFT JOIN hardware_lib_versions
hlv ON hlv.id = hl.active_version_id`) uses `active_version_id` only, for AST-introspection
purposes (deriving `module_methods` for hard-422 validation). This is a third site touching
version resolution, though arguably acceptable to leave as "active version" since it answers "is
this ref/method valid against what's currently being edited," not "what will actually run" —
flag as a judgment call for the planner rather than a definite bug.

### Where `kind` needs to surface, end to end

| Layer | File | Current state | What CMP-12/13/18 need |
|---|---|---|---|
| DB | `api/models.py::HardwareLib` (line 656-674) | No `kind` column | `kind = Column(String, default="hardware")`; migration via `api/db.py`'s established `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pattern (see e.g. `run_toolkit_hw_lib_version_migration`) |
| API | `hardware_libs.py::_lib_dict` (line 156-169) | No `kind` key | Add `"kind": lib.kind` |
| API | `hardware_modules.py::_module_row` (line 53-63) | Joins `HardwareLib` already, exposes `lib_filename` | Add `"lib_kind": lib.kind if lib else None` — same join, one more field, exact precedent already exists |
| Types | `web_ui/react-src/src/types/index.ts` (`HardwareLib` line 435, `HardwareModule` line 477) | No `kind`/`lib_kind` field | Add both |
| GUI | `HardwareLibs.tsx` (116 lines) | Flat list, no filter | Add a filter-chip row (`All / Hardware / Compute`) filtering `libs` by `lib.kind` — trivial, page is small |
| GUI | `ActionEditor.tsx::isTimerModule` (line 69-71) precedent: `mod.lib_filename === 'timer.py'` | — | Same pattern: `isComputeModule(mod) => mod.lib_kind === 'compute'`, exported the same way `isTimerModule` is |

### GUI: the compute action row (CMP-13) — clone `HardwareActionFields.tsx`, not `OutputCapture.tsx`

`HardwareActionFields.tsx` (220 lines, read in full) is the near-exact template: it already does
`toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))`, fetches
methods per module via `getHardwareModuleMethods(moduleId, taskDefId)` (AST-derived, cached), and
renders a module dropdown + a method dropdown + per-arg `ArgInput`s driven by AST arg metadata.
A new `ComputeActionFields.tsx` should:
- Filter `toolkitModules` to `isComputeModule(m)` (new `lib_kind === 'compute'` predicate).
- Present ONE flattened "op" dropdown grouped by lib name (`<optgroup label={lib.name}>`), not a
  two-step module→method picker — CMP-13 says "ops grouped by lib" as a single control, matching
  a compute lib's typical shape (many small ops in one class) rather than hardware's typical
  shape (one module = one device = a handful of methods).
- Under the hood this still resolves to the same `{ref: moduleName, method: opName}` shape a
  hardware action uses — `_build_action_callable`'s new `compute` branch and `_validate_action`'s
  new compute branch can both reuse the ref/method vocabulary verbatim.

**`OutputCapture.tsx` (92 lines, read in full) is NOT reusable as-is for compute.** It is an
opt-in checkbox — `output` starts `undefined` and the user must explicitly turn "Capture return
value" on, then pick from already-declared `variableNames`. CONTEXT.md requires output to be
**mandatory** on a compute action AND to support **typing a brand-new name that auto-declares
into `variables`** — neither behavior exists in `OutputCapture`. Build a small dedicated
always-visible output field for the compute row (a combobox: select an existing variable name OR
type a new one, which on blur/change patches `fdaJson.variables[name] = {}` alongside
`action.output = name`). This is genuinely new UI, not a clone of existing code — flag it as such
in the plan so it isn't underestimated.

### Backend hard-422 validation (CMP-10) — extend the existing file precisely

`api/fda_validation.py` (370 lines, read in full) already has every seam Phase 23 needs:

- `VALID_ACTION_TYPES` (line 42) — add `"compute"`.
- `_validate_action` (line 290-370) — add a `compute` branch mirroring the `hardware`/`timer`
  branch (line 320-326: unknown-ref check against `known_hw`/`module_names`, plus
  `_validate_action_method`'s ref/method-known check reused verbatim since `module_methods` is
  populated identically for any `hardware_modules` row regardless of `kind`) PLUS a new
  unconditional check: `if action_type == "compute" and not action.get("output"): errors.append(...)`
  (output is optional for hardware/method today via the generic check at line 354-359, but
  MANDATORY for compute — CMP-03's stated reason for keeping the type distinct).
- The existing output-collision check (line 354-359, `if output is not None: ... if name not in
  valid_names: errors.append(...)`) **already generalizes to compute** with zero changes, since
  `valid_names` (`_valid_flag_names`, line 262-268) already unions toolkit flags + `variables` +
  `trial_counter`.
- `collect_hard_errors` (line 207-223) — its own comment says `# Phase 23 appends its compute
  checks here`. No structural change needed; `validate_variables`/`validate_state_actions` already
  run generically over any `type` present via `_validate_action`.

**Correction to CONTEXT.md/CMP-10's wording:** the phrase "a new `api/fda_validation.py` sibling
module" is stale — this file already exists (built in Phase 24-02, confirmed by its own docstring
referencing Phase 23). The plan must frame this as **extending** an existing, actively-maintained
422-enforcement module, not creating one. Getting this wrong risks either a duplicate/conflicting
validation module or accidentally recreating logic (`VALID_ACTION_TYPES`, `_valid_flag_names`,
`module_methods` plumbing) that already exists and is exercised by Phase 24's test suite.

### `LOAD_HARDWARE_LIBS` / `test_import` (CMP-19b) — the flag exists, the caller never sets it

`autopilot/autopilot/core/pilot.py::l_load_hardware_libs` (line 670-691, read in full):

```python
def l_load_hardware_libs(self, value):
    libs = value.get("libs", [])
    test_import = value.get("test_import", False)   # <-- always False today
    version_id = value.get("version_id")
    ...
    if test_import:
        for lib in libs:
            importlib.import_module(lib["filename"].replace(".py", ""))
        self.node.send(self.parentid, "HARDWARE_LIB_TEST_RESULT", {...})
```

`orchestrator_station.py::_send_hardware_libs_if_needed` (the only current caller) sends
`self.gateway.send(pilot_key, "LOAD_HARDWARE_LIBS", {"libs": deployable})` — no `test_import` key,
no `version_id` key. The Pi-side round-trip (`HARDWARE_LIB_TEST_RESULT` →
`orchestrator_station.py::handle_hardware_lib_test_result` → `PATCH
/hardware-libs/versions/{id}/validate`) is fully implemented and already wired to
`hardware_libs.py::validate_version`, but **is dead code today** because nothing ever sets
`test_import=True`. CMP-19b ("wire compute libs into the existing test_import round-trip") is
therefore not purely a Pi-side no-op — it requires an orchestrator-side change too: pass
`test_import=True` and `version_id=<the version being sent>` for at least compute-kind libs (or
all libs, which would also finally activate this dormant validation path for hardware libs).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Compute op signature discovery for the GUI picker | A new AST walker for compute classes | `extract_ast_metadata`/`hw_introspect.class_capabilities`/`resolve_class_methods` (already generic over any class, already handle in-file-ancestor resolution) | These already power the hardware-module method picker and the hard-422 method-known check; a compute lib class is just another class in the same source file format |
| Version pin resolution | A parallel compute-specific resolver | Fix the ONE shared chain (pin → toolkit default → stable) in the two sites identified above, applied to both kinds via a shared helper | CMP-17 explicitly says "diverging compute from hardware would be worse than fixing both" |
| Op-level logging | A custom event-dispatch call inside each compute op | `@log_action` on the `Hardware` subclass's methods (already does exactly this for every existing hardware class) | This is the entire point of CONTEXT's reframe — free logging in exchange for using the `Hardware` base |
| "Is this hardware module a compute lib" check anywhere Pi-side | A parallel `self._compute` registry | `self.hardware["Modules"][name]` / `self._semantic_hw[name]` — already populated identically regardless of kind | The Pi has no reason to know or care about `kind` — it is a pure GUI/validation-time distinction; the running class is just a `Hardware` instance like any other |

**Key insight:** almost nothing about the Pi runtime needs to know a hardware object is "a
compute lib" rather than "a hardware lib" — `kind` is purely a backend/GUI-time distinction for
storage, validation, and the editor's op picker. The Pi already treats every `Modules`-group
object uniformly.

## Common Pitfalls

### Pitfall 1: Registering a compute lib and stopping at `toolkit_hardware_libs`

**What goes wrong:** A researcher (or a plan that follows CONTEXT.md's prose literally) links a
compute lib to a toolkit via `POST /toolkits/{id}/hardware-libs` and expects `type:"compute"`
actions referencing it to work. They will not — `get_dispatch_spec` never reads
`toolkit_hardware_libs`; only `hardware_module_ids` feeds `self.HARDWARE`.
**Why it happens:** CONTEXT.md's "Compute libs link to toolkits via `toolkit_hardware_libs`,
exactly like hardware libs" is true for versioning but silently omits the second, load-bearing
registration (`hardware_modules` + `hardware_module_ids` + `pilot_hardware_config`).
**How to avoid:** Plan must include a task that registers the seed compute lib as a
`hardware_modules` row and adds it to the test toolkit's `hardware_module_ids`, exactly as any
hardware module would be, before wiring up `type:"compute"` actions.
**Warning signs:** FDA load-time `KeyError` on `self._semantic_hw[ref]` even though the lib shows
up correctly on the Hardware Libraries page.

### Pitfall 2: `incomplete_config` preflight false-positive on a legitimate zero-param compute module

**What goes wrong:** `preflight_validate` step 6 (`toolkit_dispatch.py:288-298`) flags ANY
`pilot_hardware_config` row whose config has no keys besides `class_name` as `"incomplete_config"`.
A compute module's config is *supposed* to be just `{"class_name": "..."}"` — this will always
false-positive once compute modules exist.
**Why it happens:** The check was written assuming every hardware module needs at least one real
param (a pin, an address, a duration). Compute modules are the first case that legitimately needs
zero.
**How to avoid:** Either special-case `kind == 'compute'` modules to skip this check, or accept
`{"class_name": ...}` alone as complete when the class's AST-derived `__init__` has no other
required params (reusing `hw_introspect`'s method/arg introspection). Flag as an explicit task in
the plan — do not let it surface as a surprise preflight warning during the phase's rig proof.
**Warning signs:** Every pilot running a compute-using toolkit shows a spurious "incomplete
config" warning for the compute module on the pre-run check modal.

### Pitfall 3: Forgetting `release()` on the compute base/seed class

**What goes wrong:** `Task.end()` calls `.release()` unconditionally on every object in
`self.hardware`. Any compute class (including a researcher's own future extension) that doesn't
override it raises `Exception('The release method was not overridden by the subclass!')` — every
single run ends with an unhandled exception if this is missed.
**Why it happens:** Not mentioned anywhere in CONTEXT.md; only visible by reading `Hardware.release()`
and `Task.end()` together.
**How to avoid:** Seed compute lib class must define `def release(self): pass`. Consider
validating this at compute-lib upload time (AST check: does the class define `release`?) since a
researcher writing their own compute lib will hit this immediately and non-obviously.
**Warning signs:** Task crashes on stop/end with a `release` exception; nothing else in the run
looks wrong up to that point.

### Pitfall 4: Treating `api/fda_validation.py` as new work

**What goes wrong:** A plan that creates a brand-new module (as CONTEXT.md's literal wording
suggests) either duplicates `VALID_ACTION_TYPES`/`_valid_flag_names`/the `module_methods`
plumbing, or worse, creates two competing 422-enforcement paths, one of which Phase 24's existing
test suite doesn't know about.
**Why it happens:** CONTEXT.md predates the discovery that Phase 24-02 already built this file.
**How to avoid:** Read `api/fda_validation.py` (370 lines) before writing this plan's tasks; the
file's own docstring says exactly where Phase 23 hooks in.
**Warning signs:** `grep -c "compute"` on a freshly-planned `fda_validation.py` task showing "new
file" language, or a second file with overlapping `VALID_ACTION_TYPES`.

### Pitfall 5: `variable_never_written` treated as "reuse the Phase 25 function"

**What goes wrong:** CONTEXT.md says this "rides Phase 25's existing preflight issue renderer
(the `view_key_unresolved` path, incl. the skip-save loop)." Read literally, a planner might
expect `resolve_view_key_issues`/`detector_keys_scan.py` to already contain something adaptable.
It does not — that code resolves detector CHANNEL RANGES against a specific pilot's wiring, an
entirely different problem from "is there any FDA state, reachable from `initial_state` via
`transitions`, that writes variable X before some other state reads it in a condition." No
reachability/graph-walk code exists anywhere in this codebase today.
**Why it happens:** "Rides the same renderer" is true for the FRONTEND convention (the
`PreflightIssue` union type in `HardwareCheckModal.tsx`, the "exclude this issue kind from the
PUT/save loop" pattern) but not for the backend resolver function.
**How to avoid:** Plan a genuinely new backend function (likely its own module, given
`detector_keys_scan.py`'s docstring already notes the combined file would exceed the 300-line
budget). Decide up front on the simplest tractable semantics — e.g. "no state anywhere in the FDA
JSON writes this variable via a `compute`/`method`/`hardware` `output` spec" (existence check,
not full graph reachability) is likely the right MVP scope; true "reachable from every path to the
read" analysis is a much larger undertaking than the rest of this phase and is not implied by the
bug this issue is meant to catch (a silently-`None` variable).
**Warning signs:** A task in the plan that says "wire CMP-15 into `resolve_view_key_issues`"
without a separate task actually implementing the write/read scan.

### Pitfall 6: File-size limits on already-oversized files

**What goes wrong:** `api/routers/toolkits.py` is **990 lines** (nearly 2x the 500-line hard
limit already) and `api/main.py` is **2233 lines**. `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx`
is **844 lines** (also over the 500-line hard limit). Any plan task that adds more than a couple
lines to these files without extracting will make an existing violation worse.
**Why it happens:** These are the natural places new wiring calls would go (toolkits.py already
hosts `_validate_task_definition`; TaskEditor.tsx already threads props to every panel).
**How to avoid:** Follow the established pattern from Phase 24-02 (`reject_if_hard_errors`
helper — toolkits.py net growth capped at "<=15 lines" per that plan's own budget note) and
Phase 11-05/11-06 (extracted `EditModal`/`CreationModal` into separate files specifically to stay
under the line budget). New compute-specific UI logic belongs in new small files
(`ComputeActionFields.tsx` etc.), imported and called, not inlined.
**Warning signs:** A diff to `toolkits.py`, `main.py`, or `TaskEditor.tsx` larger than ~20 lines.

### Pitfall 7: `hardware_type` KeyError if a compute module is ever instantiated outside the normal `init_hardware()` path

**What goes wrong:** `Hardware.__init__` does `self.hardware_type = kwargs['type']`, a bare
`KeyError` if `type` is absent. In the normal path this is always populated by
`_merge_prefs_hardware` (`config["type"] = group` when absent). Any test harness or manual
instantiation of a compute class that skips `_merge_prefs_hardware`/`init_hardware()` (e.g. a
Pi-side unit test that instantiates the class directly) must pass `type=` explicitly.
**How to avoid:** Document this constructor requirement in the seed lib / test harness guidance.

## Code Examples

### Pi: the `compute` branch to add to `_build_action_callable` (pattern, not literal diff)

```python
# Source: pattern derived from mics_task.py:697-711 (the existing "hardware"/"timer" branch)
elif atype == "compute":
    if "group" in action:
        hw = self.hardware[action["group"]][ref]
    else:
        hw = self._semantic_hw[ref]
    if not action.get("output"):
        raise ValueError(
            f"_build_action_callable: compute action '{ref}.{method}' requires 'output' "
            f"(compute ops must write a declared variable)."
        )
    self._validate_output_spec(action)
    def _compute_call(_hw=hw, _method=method, _action=action):
        args   = [self._resolve_arg(a) for a in _action.get("args", [])]
        kwargs = {k: self._resolve_arg(v) for k, v in _action.get("kwargs", {}).items()}
        result = getattr(_hw, _method)(*args, **kwargs)
        self._capture_output(_action, result)
    return _compute_call
```

### Pi: minimal seed compute op class shape

```python
# Source: pattern derived from Hardware.__init__ (hardware/__init__.py:105-164) +
# logging_utils.log_action's Hardware branch (utils/logging_utils.py:56-90)
from autopilot.hardware import Hardware
from autopilot.utils.logging_utils import log_action
import random

class ComputeOps(Hardware):
    def release(self):
        pass  # no system resources — MANDATORY override, see Common Pitfalls #3

    @log_action
    def random_bool(self, p: float = 0.5):
        return random.random() < p

    @log_action
    def add(self, a, b):
        return a + b

    @log_action
    def divide(self, a, b):
        if b == 0:
            raise ZeroDivisionError("divide: b must not be 0")
        return a / b
```

### `api/fda_validation.py`: existing hooks Phase 23 extends (verbatim, current code)

```python
# api/fda_validation.py:42 — add "compute"
VALID_ACTION_TYPES = {"hardware", "flag", "timer", "special", "method", "if", "view"}

# api/fda_validation.py:207-223 — no structural change needed, comment already anticipates this:
def collect_hard_errors(fda_json, toolkit, module_names=None, module_methods=None,
                         trigger_sources=None, detector_refs=None) -> list[str]:
    """Every hard (422-worthy) error for this FDA. Phase 23 appends its compute checks here."""
```

### React: the module→ops filter pattern to copy (`ActionEditor.tsx:149`, `HardwareActionFields.tsx:32`)

```typescript
// Source: web_ui/react-src/src/components/ActionEditor.tsx:149 (existing, verbatim)
const toolkitModules = hwModules.filter(m => toolkit?.hardware_module_ids?.includes(m.id))
// New for CMP-13:
const computeModules = toolkitModules.filter(m => m.lib_kind === 'compute')
```

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework (backend) | pytest, run inside the `api` docker container or via `DATABASE_URL` env var against the compose Postgres |
| Framework (Pi) | pytest, but `autopilot` is **unimportable on the dev host** (`npyscreen` missing) — only stdlib-only test files (e.g. `tests/test_fda_vocabulary.py`) are agent-runnable; the rest are USER-RUN on the Pi from `~/Apps/mice_interactive_home_cage` |
| Framework (React) | `tsc --noEmit`, `npm run build`, plus any `node --test` pure-function tests (precedent: `detectorOptions.mts` in Phase 25 plan 04) |
| Config file | none dedicated — existing `docker compose exec api pytest`, `~/pi-mirror`'s `tests/` dir, `web_ui/react-src`'s `package.json` scripts |
| Quick run command (backend) | `docker compose exec api python -m pytest -q api/tests/test_fda_validation.py` (or the relevant new test file) |
| Quick run command (Pi, stdlib-only) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_fda_vocabulary.py` (agent-runnable) |
| Full suite command (backend) | `docker compose exec api python -m pytest -q` |
| Full suite command (Pi) | **USER-RUN**: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |
| Full suite command (React) | `cd web_ui/react-src && npx tsc --noEmit && npm run build` |

### Split verification posture (per `CLAUDE.md` / `pi-deploy` skill hard rules)

- **Pi-side work is spec/edit-in-mirror only.** All Pi-side `<verify>` steps in the plan must be
  commands handed to the **user** to run (deploy via targeted `rsync` of only session-edited
  files per the pi-deploy skill, restart the pilot, run the Pi-side pytest suite, run the
  gonogo-translation task on the rig). The agent NEVER runs git on the Pi, never starts/stops the
  pilot process, never runs Python directly on the Pi.
- **Backend (`api/`) and GUI (`web_ui/`) work is agent-driven** inside the docker compose stack —
  `docker compose up --build api`, direct `curl`/httpx calls against `localhost:8000`, Postgres
  verification via the project's DB access pattern, `npm run build` for the React bundle.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| CMP-03/04 | `type:"compute"` action calls an op, captures `output` | unit (Pi) | `cd ~/pi-mirror && python3 -m py_compile autopilot/autopilot/tasks/mics_task.py` (syntax only — full unit test is USER-RUN) | ❌ Wave 0 |
| CMP-10 | Save-time 422 on undeclared compute output | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_fda_validation.py -k compute` | ❌ Wave 0 |
| CMP-11 | Removed compute op flags dependent task defs `broken` | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_hardware_libs.py -k compute` | ❌ Wave 0 (extend existing hw-lib impact-scan tests) |
| CMP-12 | `kind` column migration idempotent | integration (backend) | `docker compose exec api python -m pytest -q api/tests/test_db_migrations.py -k hardware_lib_kind` (or run migration twice manually and diff) | ❌ Wave 0 (check for an existing migration test file first — `grep -rl migration api/tests/`) |
| CMP-16 | Both `Hardware_Event` and `Tracker` events reach ES per compute call | manual + rig | Rig proof only — verify via ES query (see project's `es-query` skill) after the gonogo-translation task run | N/A — manual-only, justified: requires live ES + real hardware/task run |
| CMP-17 | Version resolution pin→default→stable→issue | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k version_resolution` | ❌ Wave 0 (new test target, no existing file found for `toolkit_dispatch.py`) |
| CMP-13/18 | GUI compute row + kind filter chip | manual + `tsc`/build | `cd web_ui/react-src && npx tsc --noEmit && npm run build` | ✅ (scripts exist) — manual click-through is the acceptance step |
| CMP-15 | `variable_never_written` preflight issue | unit (backend) | new test file, e.g. `api/tests/test_variable_reachability.py` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `docker compose exec api python -m pytest -q <touched test file>` (backend);
  `cd ~/pi-mirror && python3 -m py_compile <touched file>` (Pi, syntax-only, agent-runnable);
  `npx tsc --noEmit` (React).
- **Per wave merge:** `docker compose exec api python -m pytest -q` (full backend suite);
  `npm run build` (React); Pi full suite is **USER-RUN**, requested explicitly at each Pi-touching
  wave boundary, not run silently by the agent.
- **Phase gate:** Full backend + React suites green, PLUS the user has confirmed the Pi suite
  passed and the gonogo-translation task fired both branches on the rig with both event types
  (`Hardware_Event` op+args, `Tracker` result) visible in ES, before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] No existing test file targets `api/routers/toolkit_dispatch.py` (`grep` found none) —
      version-resolution fix (CMP-17) and the `incomplete_config` fix (Pitfall 2) both need a new
      `api/tests/test_toolkit_dispatch.py`.
- [ ] No existing test file for `api/fda_validation.py`'s compute branch — confirm exact filename
      convention by checking what Phase 24-02 used for `trigger_assignments`/`variables` tests
      (likely `api/tests/test_fda_validation.py` — verify before creating a duplicate).
- [ ] No reachability/graph-walk test scaffolding exists anywhere — CMP-15 needs both the
      implementation module and its test file from scratch.
- [ ] Pi-side: no existing test file for a `compute` action type (naturally, since it doesn't
      exist yet) — new `tests/test_compute_actions.py` on the Pi side, USER-RUN.
- [ ] Framework install: none needed — pytest and the React toolchain are already present project-wide.

## Open Questions

1. **Should a compute module's `pilot_hardware_config` row be auto-provisioned, or remain a
   manual per-pilot step?**
   - What we know: today, ANY hardware module (including a zero-param compute module) requires a
     manual `pilot_hardware_config` row per pilot before it will instantiate; missing it is a
     silent (logged-only) skip that surfaces later as a load-time `KeyError` in an unrelated place.
   - What's unclear: whether the phase should invest in auto-provisioning a trivial
     `{"class_name": ...}` row for every existing pilot when a compute module is linked to a
     toolkit (a genuinely new mechanism, arguably out of scope), versus documenting the manual step
     and relying on `preflight_validate`'s existing `"missing"` issue to catch it before a session
     start (already works today with zero new code, once Pitfall 2's false-positive is fixed).
   - Recommendation: rely on the existing preflight `"missing"` issue (already correct for this
     case, no new code) and make the manual-add path a one-click affordance in
     `PilotHardwareConfig.tsx`'s existing module-registry picker, rather than building
     auto-provisioning. Revisit only if the manual step proves to be a recurring friction point.

2. **Exact semantics of `variable_never_written` (CMP-15).**
   - What we know: it must catch "a transition reads a variable no reachable upstream state
     writes" and must be cheap enough to run inside `preflight_validate`'s existing try/except
     envelope (which already treats a broken check as non-blocking).
   - What's unclear: full graph reachability (does every path from `initial_state` to the reading
     state pass through a writing state?) vs. a simpler existence check (does ANY state in the FDA
     JSON write this variable, anywhere?). The former is meaningfully more complex to implement
     and test correctly against arbitrary transition graphs (including cycles); the latter is a
     same-day task.
   - Recommendation: implement the existence check for v1 (matches the bug it's meant to catch —
     a variable that is read but genuinely never written anywhere), and note in the plan that true
     reachability is a possible future refinement, not required by any CMP requirement's literal
     text.

3. **Does `hw_introspect.toolkit_hw_capabilities`'s use of `active_version_id` (rather than the
   corrected pin→default→stable chain) need to change too?**
   - What we know: this function feeds the hard-422 `module_methods` check (is this op name
     real?), which conceptually should validate against "what's currently being edited," which
     arguably IS the active version, not necessarily the stable one that will actually deploy.
   - What's unclear: whether leaving this asymmetric (validation against active, deployment
     against pin→default→stable) will confuse researchers when a save succeeds against one
     version's op names but the toolkit actually ships a different version.
   - Recommendation: leave as `active_version_id` for validation-time introspection (matches its
     existing, working purpose for hardware modules today) unless a plan task specifically wants
     to unify it — flag to the planner as a judgment call, not a defect to silently fix.

## Sources

### Primary (HIGH confidence — direct code reads, this session)

- `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — `_build_action_callable`
  (684-811), `_resolve_arg`/`_validate_output_spec`/`_capture_output` (461-539), `load_fda_from_json`
  variables block (960-1123), `_resolve_hardware_classes`/`_merge_prefs_hardware` (167-232),
  `check_for_detectors` (262-326), class-level docstrings and imports (1-160)
- `/home/ido/pi-mirror/autopilot/autopilot/tasks/task.py` — `init_hardware` (162-217), `end`
  (434-448), `process_queue`/`execute_trigger`/`_report_trigger_error` (258-333)
- `/home/ido/pi-mirror/autopilot/autopilot/hardware/__init__.py` — `Hardware` base class (105-217)
- `/home/ido/pi-mirror/autopilot/autopilot/utils/logging_utils.py` — `log_action` (full file)
- `/home/ido/pi-mirror/autopilot/autopilot/core/pilot.py` — `l_update_fda`/`l_load_hardware_libs`
  (646-691)
- `/home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py` — `VALID_ACTION_TYPES`,
  `unpack_output`, `resolve_key_template` (1-60, 175-195)
- `/home/ido/mics-backend/api/models.py` — `TaskToolkit`/`HardwareLibVersion`/`HardwareLib`/
  `ToolkitHardwareLib`/`HardwareModule`/`PilotHardwareConfig` (592-714)
- `/home/ido/mics-backend/api/routers/hardware_libs.py` — full file (774 lines)
- `/home/ido/mics-backend/api/routers/hardware_modules.py` — CRUD + `_module_row` (1-90)
- `/home/ido/mics-backend/api/routers/toolkit_dispatch.py` — full file (373 lines)
- `/home/ido/mics-backend/api/fda_validation.py` — full file (370 lines)
- `/home/ido/mics-backend/api/fda_utils.py` — full file (162 lines)
- `/home/ido/mics-backend/api/hw_introspect.py` — full file (194 lines)
- `/home/ido/mics-backend/api/routers/toolkits.py` — `create_backend_toolkit` (323-393),
  `_validate_task_definition` (731-819)
- `/home/ido/mics-backend/api/db.py` — migration function patterns (180-260)
- `/home/ido/mics-backend/orchestrator/orchestrator/orchestrator_station.py` —
  `start_run`/`_inject_backend_toolkit_spec`/`_send_hardware_libs_if_needed`/
  `handle_hardware_lib_test_result` (300-400, 790-912)
- `/home/ido/mics-backend/web_ui/react-src/src/components/ActionEditor.tsx` — full file (423 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/HardwareActionFields.tsx` — full file (221 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/components/OutputCapture.tsx` — full file (93 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/pages/toolkits/CreationModal.tsx` — full file (219 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/pages/hardware-libs/HardwareLibs.tsx` — full file (117 lines)
- `/home/ido/mics-backend/web_ui/react-src/src/types/index.ts` — `HardwareLib`/`HardwareLibVersion`/
  `HardwareModule`/`AstMethod` (433-492)
- `/home/ido/mics-backend/.claude/skills/pi-deploy/SKILL.md` — full file (hard rules for Pi work)
- `/home/ido/mics-backend/.planning/phases/23-compute-primitives-variables/23-CONTEXT.md`,
  `.planning/REQUIREMENTS.md` (CMP section), `.planning/ROADMAP.md` (Phase 23/24/25 sections),
  `.planning/STATE.md`, `.planning/config.json`

### Secondary / Tertiary

None — every substantive claim in this document is grounded in a direct read of current
repository code performed in this research session, not training-data recall or web search. This
is a monorepo-internal architecture question; no external library research applies.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — this phase reuses only in-repo infrastructure, no external library choice
- Architecture: HIGH — every claim traced to a specific file:line read this session, including
  the two version-resolution sites and the instantiation-ceremony finding that CONTEXT.md's prose
  understates
- Pitfalls: HIGH — all seven are derived from actual code paths (Hardware.release, log_action,
  preflight's incomplete_config check, existing file sizes), not speculation
- Validation architecture: MEDIUM — test file paths for NEW test targets (toolkit_dispatch,
  compute validation, reachability) are proposed conventions, not verified against an existing
  naming scheme, since those specific test files don't exist yet; verify against
  `api/tests/test_fda_validation.py`'s actual name before the planner commits to a filename

**Research date:** 2026-08-03
**Valid until:** ~2026-08-17 (fast-moving internal codebase; re-verify file:line references if
Phase 18 or other in-flight work lands first and touches any of the files above)
