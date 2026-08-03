---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-08-03T09:27:56.154Z"
progress:
  total_phases: 19
  completed_phases: 6
  total_plans: 46
  completed_plans: 32
  percent: 73
---

# STATE: MICS Backend

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-15)

**Core value:** Researchers can define, modify, and deploy behavioral task logic without writing Python or restarting the Pi.
**Current focus:** Planning complete — ready to begin Phase 1

---

## Current Position

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor
**Phase:** 23 — Compute Primitives + Variables — **2/10 plans done** (Wave 0 + Wave 2 plan 04)
**Also outstanding:** Phase 25 plan 06 (last plan in that phase, not yet executed)
**Progress:** [███████░░░] 73%

### Phase 23 status (2026-08-03)

**Plan 01 executed:** Wave 0 — the three ❌ contract-test targets from `23-VALIDATION.md` now
exist on disk, all failing/skipping/xfailing today for the right reason (missing feature, not a
typo), per the phase's re-scoped compute-as-hardware-lib plan (see the four `docs(23):` commits
immediately preceding this one — re-scope, re-plan as 10 plans/6 waves, defer-and-gate the
trigger-assignment compute option). `api/tests/test_hardware_lib_kind.py` (9 tests: 2 real-DB
migration-idempotency + 2 real-DB `seed_compute_ops_lib`/allowlist tests, 5 xfail route tests)
pins CMP-12/19 — the `hardware_libs.kind`/`hardware_lib_versions.declared_imports` columns,
`run_hardware_lib_kind_migration`'s idempotency, and `POST /api/hardware-libs`'s
`kind='compute'`/`declared_imports=[...]` validation, none of which exist until plan 23-02.
`api/tests/test_toolkit_dispatch.py` (11 tests, module-level `pytest.importorskip` since
`api/lib_version_resolution.py` doesn't exist until plan 23-05) pins CMP-17's
`resolve_lib_version_id` pin → toolkit_default → stable → active → none chain (every reason
string covered) plus the `get_dispatch_spec` stable-over-active regression and the
`resolved_version_id`/`resolved_state`/`resolution_reason` fields `list_toolkit_hardware_libs`
must gain. `/home/ido/pi-mirror/tests/test_compute_ops.py` (8 tests, USER-RUN, not deployed)
pins CMP-03/04/05 — a `Hardware` subclass needs `type=` supplied explicitly (Pitfall 7) and must
override `release()` or `Task.end()` raises on every run (Pitfall 3), plus the compute action's
build-time-required `output`, its `group`-present/absent dual resolution form, and last-write-
wins re-invocation. Full backend suite green throughout: **231 passed, 5 skipped, 5 xfailed**
(verified before AND after `docker compose up --build api`, since that service has no bind mount
— new test files are invisible to a running, un-rebuilt container). No pi-mirror files other
than the one new test file touched; no git commands run there. See `23-01-SUMMARY.md`.

**Plan 04 executed (2026-08-03):** CMP-03/04/05/06 delivered on the Pi runtime, in
`/home/ido/pi-mirror`. `fda_vocabulary.py` gained `"compute"` in `VALID_ACTION_TYPES` (single-
sourced comment pointing at `api/fda_validation.py`'s backend twin). `mics_task.py`'s
`_build_action_callable` gained the `compute` branch — byte-for-byte the `hardware`/`timer`
branch's dual ref-resolution (`group` present → `self.hardware[group][ref]`, absent →
`self._semantic_hw[ref]`), with `output` made mandatory at BUILD time (`ValueError` naming
`ref.method`). `tools/validate_fda.py` gained the matching CLI-side `compute` branch, message-
worded identically to the runtime's. `tests/test_compute_ops.py` (plan 23-01's pre-written Wave 0
tests, unchanged) plus 4 new Task 3 regression tests for CMP-01/02/05/06 (verify-only — pinning
that Phase 24's variables registry holds for compute-written variables). `tests/test_fda_vocabulary.py`
extended with a `compute`-membership assertion: **23 passed** (agent-verified). **One bug found
and fixed in-task (Rule 3 — blocking):** `_build_state_method`'s separate entry_actions
pre-validation loop had no branch for `compute` and would have raised "unknown action type"
before ever reaching the new `_build_action_callable` branch — widened its existing `hardware`
check to `("hardware", "compute")`. **One bug found and NOT fixed, per the plan's explicit
instruction:** `load_fda_from_json`'s variables-collision guard (`if var_name in self.flags:
raise`) does not exempt a variable name the mechanism itself declared on a prior load, so
`hot_update_fda` re-declaring the SAME variable name (the normal hot-reload case) appears, by
code inspection, to raise instead of recreating the tracker — CMP-06's "hot-reload re-creates
variables" promise. Not confirmed by execution (autopilot unimportable here); flagged as a
predicted Phase-24 defect for plan 23-10 to confirm via `test_hot_update_fda_recreates_variables_
before_rebuilding_transitions`. No pi-mirror git commits (pi-mirror is user-owned git, same as
plan 25-02). See `23-04-SUMMARY.md` and its "Next Phase Readiness" for the exact rsync file list.

### Phase 25 status (2026-07-29)

**Plan 01 executed:** DVK-01/02/07/09/11 delivered on the backend. `api/detector_keys.py`
single-sources `derive_channels`/`derive_view_keys` (the `f"{device_name}{i}"` format, now
declarable via `first_channel` for DVK-09's channel-1-4 wiring) and `module_detector_channels`
(the advisory cross-pilot union with surfaced `conflict` + `by_pilot` provenance — verified
live: `MPR121` → `channels [0,1,2,3]`, `keys LICKER0…LICKER3`, `conflict: false`). New
`scan_fda_condition_operands` in `api/fda_utils.py` is the ONE condition-operand walker shared
by this plan's save-time gate and plan 03's preflight resolver. New
`validate_condition_operands` in `api/fda_validation.py` is the DVK-11 save-time 422: a
`view_detector` operand must name a real detector and carry a non-negative int `channel` — range
checking stays with preflight (plan 03). DVK-07 pinned by 4 regression tests verified passing
against pre-plan code first. Full backend suite: 163 passed. No route changes yet (plan 03).
See `25-01-SUMMARY.md`.

**Plan 02 executed (2026-07-29):** DVK-09/10/11 delivered on the Pi runtime, in
`/home/ido/pi-mirror`. `fda_vocabulary.py` gained `detector_channel_range` /
`detector_view_keys` / `detector_channel_key` (the Pi's half of plan 01's shared golden-table
derivation) and `parse_view_detector_operand` (DVK-11's shape parser). `check_for_detectors`
now honours `first_channel` read from `prefs.HARDWARE[group][module_name]` — the exact fix for
the channel-4 data loss in runs 480/481 (`LICKER1..LICKER4` correctly seeded from
`curr_vals[1..4]`, never shifted). `execute_trigger`'s `except KeyError` is narrowed to the
`self.triggers[pin]` lookup alone; a raising callback now reports via a new
`_report_trigger_error` helper (error log naming the exception + `TRIGGER_ACTION_ERROR` event)
whose entire body is exception-contained so a dead `event_dispatcher` can't kill the worker
thread. `_build_condition_operand` gained a `view_detector` branch resolving
`{"ref": ..., "channel": ...}` to a pilot's real view key ONCE at build time — the same stored
JSON reads `LICKER2` on one pilot and `TONGUE2` on another. Mirror-Pi identity proved via diff
before any edit (all four target files byte-identical); diff re-confirmed after editing that
only the intended methods/import lines changed and `i2c.py` stayed untouched. Dev-host
agent-runnable suite: 64 passed (`test_detector_view_keys.py` + `test_fda_vocabulary.py`).
Three new/extended test files (`test_check_for_detectors.py` DVK-09 cases,
`test_execute_trigger_guard.py`, `test_view_detector_operand.py`) are USER-RUN on the Pi —
plan 06 owns running them plus the deploy and rig proof. **No pi-mirror git commits made**
(pi-mirror is its own user-owned git repo; pi_rules forbid any git command there). See
`25-02-SUMMARY.md`.

**Plan 03 executed (2026-07-29):** DVK-02/06/11 wired into the two routes the rest of the
system reads from. `scan_fda_view_keys` + `resolve_view_key_issues` (new
`api/detector_keys_scan.py`, re-exported from `detector_keys.py` — the combined file would
have exceeded its 300-line budget) compose plan 01's `scan_fda_condition_operands` with a new
`key_template` action walker, then classify every scanned entry against ONE pilot's declared
`pilot_hardware_config` wiring. `preflight_validate` gained step 8 — nested inside step 7's
`fda_json` guard (not after it, to avoid a swallowed `NameError` on a fda_json-less task def)
and wrapped in its own `try/except` + `logger.warning` — resolving detector channels (DVK-11
range check) and literal/`key_template` view keys (DVK-06) against the target pilot, emitting
`view_key_unresolved` issues with an optional `detector`/`available_channels` field pair (R1).
`detector_channels` now rides every toolkit read route including
`GET /api/toolkits/by-name/{name}` (the route `TaskEditor.tsx` actually calls) — required
fixing `toolkit_hw_capabilities` to return `module_names` on its early-return path too, since
98 of 112 `task_toolkits` rows are module-less and previously would have 500'd
`GET /api/toolkits` once a caller relied on that key. `is_detector` added to
`GET /api/hardware-modules/{id}/methods`. Full backend suite: 219 passed. Live-verified from
`mics_web_ui`: both toolkit routes carry the MPR121 `detector_channels` group,
`GET /api/toolkits` 200s across all 112 rows, module 7 `is_detector: true` / module 8
`is_detector: false`. `api/main.py` and `api/fda_validation.py` diffs both empty. See
`25-03-SUMMARY.md`.

**Plan 04 executed (2026-07-29):** DVK-03/04/05/07/11 delivered on the FDA editor. New
`web_ui/react-src/src/components/detectorOptions.mts` (pure, tested via `node --test`, zero
new npm dependencies) is the single option-assembly + operand-encoding module behind every
view-operand picker: `buildViewOptions` groups options into Hardware / one-group-per-detector
labelled by `device_name` / Flags & variables; `viewOperandToOptionValue` /
`optionValueToViewOperand` round-trip a `view_detector` operand through an opaque
`"@detector/MPR121#2"` select token, resolved by scanning the backend's own
`detector_channels`, never by parsing the token. `ConditionBuilder.tsx`'s `OperandEditor` now
renders that grouped `<optgroup>` picker and emits `{"view_detector": {"ref","channel"}}` for a
picked channel — never a resolved per-pilot key (DVK-11). The keep-current-value escape
survives verbatim, now flagged `(unknown)` (DVK-05, scoped to keys the backend cannot model,
per 25-CONTEXT S6 — there is no legacy detector key to migrate). `detectorChannels` threaded
end to end (`TaskEditor` → `StateBodyPanel`/`TriggerAssignmentPanel`/`ConditionGroupsEditor` →
`ActionEditor` → `IfActionEditor` → `ConditionRow`/`ViewActionFields`). `ViewActionFields`'
`key_template` field now offers `{device_name}` + variable + derived-key completions from the
same builder while staying free text (DVK-04/DVK-05); `DetectorWriteWidget.tsx` (trigger `view`
action, 25-CONTEXT D5) untouched. 24 unit tests green, `tsc --noEmit` clean, `vite build`
succeeds — bundle `dist/TaskEditor-B6-dKcPk.js`. Two Rule-3 ordering deviations (types added a
task early; `ViewActionFields` wiring deferred a task late) documented in `25-04-SUMMARY.md`,
both to keep each task's own `tsc` green — no scope change from the plan. Behavioural
verification of the rendered pickers is manual, deferred to plan 06's checkpoint. See
`25-04-SUMMARY.md`.

**Plan 05 executed (2026-07-29):** DVK-06/09/11 delivered on the FDA editor's two preflight-facing
surfaces. `HardwareCheckModal.tsx`'s `PreflightIssue` union gained `view_key_unresolved` plus the
optional `location`/`key`/`available_keys`/`detector`/`available_channels` fields from plan 03's
two issue shapes; a new `ViewKeyIssueDetail` read-only component renders both (leading with
`MPR121 — channel 5` + an `available_channels` pill row for the DVK-11 shape, the offending `key`
for the literal shape, `detail` alone when only that field is present) — the issue that previously
rendered as `null` and left the researcher unable to tell why start was gated. `handleStart` and
the `pendingEdits` initialiser both skip `view_key_unresolved` — it names no config row, so it can
no longer trigger a destructive PUT (overwriting a good config with `{}`, or hitting an empty path
segment). The `issues.map` React key, previously `module_name` alone, is now
`${issue.issue}:${issue.module_name}:${issue.location ?? i}` — fixes a real duplicate-key
collision (two bad channels on one MPR121 previously shared a key). No start gate added; preflight
stays advisory per Phase 13. Separately, `PilotHardwareConfig.tsx` now offers a `first_channel`
number input (empty = key absent, via new `setJsonKey` helper) plus a live derived-key preview
(new `DetectorChannelFields.tsx`, comment-pinned to `api/detector_keys.py::derive_view_keys` as the
real authority) on a detector module's **edit** row — resolved by module **name** against
`listHardwareModules` since `PilotHardwareConfigRow` carries no `module_id` (Phase 17).
`handleModulePick`'s existing template fetch was rerouted through `qc.fetchQuery` on the same
`['hardware-module-methods', id]` key the new `is_detector` `useQuery` hooks use, so the add and
edit flows share one fetch, not two. `HardwareModuleMethods` gained `is_detector: boolean`
(already shipped on the backend response by plan 03). `tsc --noEmit` clean; `npm run build`
succeeds (bundles `dist/HardwareCheckModal-DKJUfoGY.js`, `dist/PilotHardwareConfig-B09He_Dl.js` —
`npx vite build` itself failed in this environment with `npm error Missing script: "vite"`,
apparently the rtk command-rewriting hook misinterpreting `npx <bin>`; `npm run build`, the
project's own script, produced the identical build unaffected). No deviations from plan. No
hardcoded `LICKER` in any rendered string — verified by grep. Behavioural verification (both issue
shapes against the rig pilot, the edit-flow `first_channel` round-trip) is plan 06's, per this
plan's own note not to claim DVK-06/09/11 proven here. See `25-05-SUMMARY.md`.

### Phase 24 status (2026-07-27)

Plans 01–05 executed, deployed, and **proven on the real rig** (run 475: 47 `TOUCH_INT`
firings with alternating `level` 0/1, action list assembled in the UI, no `learning_cage`,
no `handler` enum). TRIGA-01/02/06 demonstrated on hardware.

**Plan 06 executed (2026-07-27):** TRIGA-12/18/19 delivered — capability-based
`check_for_detectors` (fixes the isinstance-identity bug that made sourceless lick detection
silently produce zero trackers), `source_ref` + runtime-resolved `{device_name}` on the `view`
action (task definitions stay pilot-agnostic), and the value-source lock (level always from
`detect_change()`'s own capture, never the trigger's IRQ-edge level). Deployed to the Pi,
md5-verified. **Not yet USER-verified** — awaiting pilot restart + full test-suite run (below).
See `24-06-SUMMARY.md`.

**Plan 08 executed (2026-07-27):** TRIGA-14/15/16/17 delivered — `api/hw_introspect.py` derives
`trigger_sources`/`detector_refs` from the lib AST (verified live on toolkit 100/module 7); a
hardware/timer action with no `method` is now a hard 422 in triggers AND state `entry_actions`;
the `view` action accepts the runtime `{device_name}` token when paired with a resolvable
`source_ref`; `trigger_name` is a grouped dropdown; declared `variables` join the condition
operand pickers; new `DetectorWriteWidget.tsx` is the constrained one-pick detector write UI
macro (emits ordinary FDA JSON, no Pi-side change). `api`/`web_ui` rebuilt and verified live.
Blast-radius re-confirmed unchanged: task defs 181/185(Gili's)/187 blocked from re-save by the
method rule, none edited. See `24-08-SUMMARY.md`.

**Read these two files first when resuming:**
- `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md` — what is
  proven, the 7 post-execution defects and their commits, infrastructure incidents, and the
  exact deployed/registry/DB state.
- `.planning/phases/24-trigger-assignment-action-lists/24-REPLAN-BRIEF.md` — what changes in
  plans 06/07/08 for the sourceless-only decision, requirement by requirement.

**Re-plan discussion COMPLETE (2026-07-27).** Decisions R1–R11 are in `24-CONTEXT.md`
§ `<replan_2026_07_27>`; REQUIREMENTS.md and ROADMAP.md are updated to match. Headlines:
- **Constrained one-pick detector write** in the editor, emitting ordinary FDA JSON (UI macro).
  The researcher cannot read electrode 2 and write `LICKER0`. No detector code on the Pi.
- **`{device_name}` token** in `key_template` + `source_ref` on the `view` action, resolved at
  runtime — task definitions stay pilot-agnostic.
- **Level comes from `detect_change`'s return, never `{"trigger":"level"}`** — the trigger's level
  is IRQ assert/deassert, not electrode state. Run 475's alternating 0/1 was that handshake.
- **TRIGA-11 dropped** (vacuous on a sourceless toolkit) → **TRIGA-11a** rig proof.
- **TRIGA-13 moved to Phase 25**, which now runs **immediately after 24, before 23**.
- **New: TRIGA-16** (validate hardware action `method` — `method:""` currently 200s and silently
  no-ops), **TRIGA-17/18/19**.

**Plan 07 executed (2026-07-27) — PHASE 24 IS FUNCTIONALLY COMPLETE, 8/8 plans.**
TRIGA-11a proven on hardware across runs 478/480/481: **144 trigger firings, 63 licker writes,
zero correctness errors** — every write hit the tracker matching the electrode `detect_change`
reported, carried that call's own level (never the IRQ edge), and carried the triggering
`TOUCH_INT` tick as `pi_timestamp`. The `pin_number != null` guard blocked all 72 no-change
edges. Save-time negative suite: **8/8** (canonical 201, seven invalid payloads 422 with
specific messages, including TRIGA-16's method gate). See `24-07-SUMMARY.md` and
`24-HARDWARE-VALIDATION.md` §2b.

**Outstanding:**
1. **Pi tests STILL never run anywhere** (`autopilot` unimportable on dev host) — the one real
   gap in phase 24. ~60 tests now, including `test_check_for_detectors.py`,
   `test_log_action_values.py` and additions to three existing files. USER-RUN:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`
2. **Phase 25 is next** (agreed order: 24 → 25 → 23). It now carries **DVK-09**, added from rig
   evidence: the rig's four spouts sit on MPR121 channels **1–4**, so `range(0, num_detectors)`
   builds a dead `LICKER0` and **silently discards channel 4** (9 real events lost in runs
   480/481). Names cannot be offset — the key is `{device_name}{pin_number}` where `pin_number`
   is the raw hardware index — so the channel range itself must become declarable.
   **Decided 2026-07-29 (user):** `first_channel` (default `0`) + existing `num_detectors`, i.e.
   `range(first_channel, first_channel + num_detectors)`. **Not** an explicit channel list — the
   extra editor UI is not justified by contiguous 1–4 wiring. Non-contiguous channels are
   consciously out of scope.
3. **DVK-10 (new, 2026-07-29)** — traced *why* DVK-09 was silent: `mics_task.py:717-721` **does**
   raise `KeyError` for the unknown `LICKER4`, `_run_trigger_actions` (`mics_task.py:1323-1328`)
   has no `except`, and `execute_trigger`'s `except KeyError` (`task.py:285-298`) — intended for a
   missing `self.triggers[pin]` lookup — swallows it and logs `"No valid trigger for {pin}"` at
   DEBUG. Wrong handler, wrong message, no mention of the key. Narrow that guard to the lookup
   alone. Hides every action-list key error DVK-06 preflight does not catch first.
4. `process_queue` (`task.py:262-266`) has no exception handler: any trigger-callback exception
   permanently disables all trigger processing with no operator-visible signal. Found via defect
   8. User deferred it; not scoped. Distinct from DVK-10 — the LICKER4 `KeyError` never reached
   `process_queue`, which is why the worker survived and the other 63 writes succeeded.
5. Optional: clear legacy `trigger_assignments` rows in task defs 181 and 185 (185 is Gili's).
   Note task defs 181/185/187 also hold state-body hardware actions with an empty `method` and
   cannot be re-saved until fixed (TRIGA-16 blast radius).
6. `detect_change` reports only `changes[0]`, so simultaneous multi-electrode transitions are
   lost unrecoverably (`i2c.py`, off-limits, pre-existing). Bounds what concurrent multi-spout
   licking can measure.

---

## Decisions Made

| Decision | Made | Rationale |
|---|---|---|
| Hardware_Event logging is unconditional | 2026-03-15 | execute_trigger() always dispatches Hardware_Event; trigger_assignments only adds semantic layer |
| FDA v2 JSON with entry_actions | 2026-03-15 | Declarative state bodies; no exec() or pickle needed |
| SEMANTIC_HARDWARE defined in code by developer | 2026-03-15 | Friendly names are toolkit public API; developer writes them in Python, HANDSHAKE ships them to DB, GUI consumes them as read-only dropdowns; researchers cannot rename hardware from UI |
| Three-layer abstraction: prefs.json → HARDWARE dict → SEMANTIC_HARDWARE → FDA JSON | 2026-03-15 | prefs.json changes (pins) never reach FDA JSON; HARDWARE key renames require one SEMANTIC_HARDWARE update; semantic name renames require DB migration — avoid |
| Hot-reload scope: between task runs, not mid-execution | 2026-03-15 | Orchestrator includes latest fda_json from DB in every START payload; Pi calls load_fda_from_json() at task start; pilot process never restarts; mid-execution UPDATE_FDA deferred to v2 |
| Three state modes: passthrough / GUI-built / hybrid | 2026-03-15 | Passthrough = existing Python method used as-is (no entry_actions); GUI-built = full entry_actions in JSON; hybrid = GUI-built state calling CALLABLE_METHODS as building blocks |
| CALLABLE_METHODS is developer-defined, not UI-created | 2026-03-15 | Developer marks Python methods as callable from JSON by listing in CALLABLE_METHODS; GUI consumes from task_toolkits.callable_methods; researchers cannot create callable methods from UI |
| Monaco + asyncssh for Pi editor | 2026-03-15 | Jupyter/code-server too heavy for Pi |
| Phase 5 independent of Phases 1-4 | 2026-03-15 | Pi editor viewer has no dependency on toolkit/FDA work |

---
- [Phase 01-pi-foundation]: nohup launch uses < /dev/null to prevent SSH stdin hang (required for pilot restart)
- [Phase 01-pi-foundation]: Deploy scripts in ~/pi-mirror/tools/ (not mics-backend repo) — operational tools outside codebase
- [Phase 01-pi-foundation]: serialize_flags and _serialize_semantic_hardware added as private Pilot helpers for testability; all six enriched fields default to empty collections for backward compat
- [Phase 01-pi-foundation]: validate() takes (definition, cls) order — definition first, class second — consistent with test signatures
- [Phase 01-pi-foundation]: if-action recursion shares _validate_actions_list() for state loop and then/else branches
- [Phase 02-db-api]: Toolkit schema in task_toolkits separate from task_definitions — multiple FDAs per toolkit possible
- [Phase 02-db-api]: fda_json stored as JSONB in task_definitions, toolkit_name as FK ref by name
- [Phase 02-db-api]: hw_hash pre-computed by orchestrator as SHA256(json.dumps(sem_hw, sort_keys=True)); API trusts caller hash
- [Phase 02-db-api]: Enriched HANDSHAKE detected by key presence (SEMANTIC_HARDWARE or FLAGS), not schema version field
- [Phase 02-db-api]: All new API endpoints go in api/routers/ package — api/main.py change is only include_router call
- [Phase 02-db-api]: Migrated columns (toolkit_name, display_name, fda_json) not in ORM class — use raw sa_text SQL for all queries touching them
- [Phase 02-db-api]: Used stdlib urllib.request instead of requests in api push endpoint — requests not in api/requirements.txt
- [Phase 02-db-api]: state_machine injection in _build_step_task is non-fatal — failure logs and continues without state_machine key
- [Phase 04-protocol-integration]: task_definition_id uses bare Optional[int] (no SQLModel FK) in ProtocolStepTemplate — task_definitions is SQLAlchemy-owned; SQLModel FK resolution fails at startup. DB constraint enforced by run_protocol_migrations().
- [Phase 04-protocol-integration]: ProtocolStep type extended with task_definition_id; palette filtered to fda_json != null definitions; getLeafTasks kept as fallback in OverridesModal for legacy protocol backward compat
- [Phase 04-protocol-integration]: set-canonical conservatively flags all task_definitions for toolkit name as needs_migration=True — no toolkit_id FK on task_definitions so cannot distinguish per-variant
- [Phase 11]: Legacy HANDSHAKE filename reconstructed from task class name (AppetitiveTaskReal.py) with is_legacy_filename=True; detected by uppercase in stem
- [Phase 11]: HwLibVersionModal scans all hw/timer FDA refs (not filtered per-lib) since module→lib resolution would need extra API calls
- [Phase 11-02]: class_name stored in available_locked_states; new HANDSHAKE format carries it per-entry, legacy format derives it from task_type
- [Phase 11-02]: Dispatch endpoint in api/routers/toolkit_dispatch.py (toolkits.py already >500 lines — router-per-domain split)
- [Phase 11-02]: task_type override placed after _build_*_task in start_run and _advance_run_step to respect re-assertion at lines 686/745
- [Phase 11-03]: task_type left to dispatch-class override — _inject_backend_toolkit_spec does not set task_type
- [Phase 11-03]: pilot_hardware_config table name is singular (plan had wrong plural name)
- [Phase 11-04]: _resolve_flags() reads 'tracker_type' key (DB format) with 'type' fallback; pops key and sets 'type' = Tracker class for init_flags() compatibility
- [Phase 11-05]: EditModal extracted to separate file to keep Toolkits.tsx under 500-line limit
- [Phase 12-hardware-fda-builder]: Direct-ref format uses 'group' key as discriminator for hardware actions in Pi — backward compat, no version bump
- [Phase 12-hardware-fda-builder]: GUI-built states unconditionally call wait_for_condition() — entry_actions present is sufficient signal, blocking field ignored
- [Phase 12-hardware-fda-builder]: Trial_Tracker.increment() dispatches INC_TRIAL_COUNTER (was DATA) — orchestrator now counts trials from flag-based actions
- [Phase 12-hardware-fda-builder]: trial_counter injection is server-side in _normalize_flags() — every toolkit GET response always has it, UI never needs to handle 0-trial-flags case
- [Phase 12-hardware-fda-builder]: auto-save depends on fdaJson only (not editName) — name changes excluded from debounce since user may still be typing
- [Phase 12]: Context menu renders as fixed-positioned div outside ReactFlow canvas — avoids transform coordinate issues
- [Phase 11-06]: CreationModal extracted to separate file to keep Toolkits.tsx under 300-line limit
- [Phase 12-hardware-fda-builder]: scan_fda_for_refs in api/fda_utils.py shared between hardware_libs and toolkits routers
- [Phase 12-hardware-fda-builder]: Pinned task definitions insulated from active-version lib changes (skip in impact scan); classic toolkits skip hardware ref validation (no hardware_module_ids)
- [Phase 12-hardware-fda-builder]: Lazy import _validate_task_definition in _revalidate_task_def to avoid circular import between router modules
- [Phase 12-hardware-fda-builder]: Auto-pin uses stable_version_id falling back to active_version_id at task def creation
- [Phase 14]: CSS :hover tooltip chosen over React state tooltip to survive ReactFlow re-renders without JS overhead
- [Phase 14-bug-backlog]: BUG-07: explicit proxy routes for toolkit/{id}/hardware-libs needed — catch-all strips /api/ prefix when forwarding
- [Phase 14-bug-backlog]: BUG-06: auto-link all hw-libs at toolkit creation; per-lib version pinning is task-definition concern, not toolkit concern
- [Phase 14-bug-backlog]: BUG-05: skip step 2 (locked-states) when no file selected by jumping step 1→3→1 in handleNext/handleBack
- [Phase 15-compound-transition-conditions]: Pi DNF uses single _dnf callable with default arg capture to avoid late-binding closures in loop
- [Phase 15-compound-transition-conditions]: normaliseTransition drops legacy conditions field from in-memory state; Pi still reads it from stored JSON via legacy fallback
- [Phase 15-compound-transition-conditions]: Empty condition_groups [] = unconditional (not [{conditions:[]}]) so ConditionGroupsEditor shows hint instead of empty group card
- [Phase 15-compound-transition-conditions]: ConditionRow delete button placed inline alongside Right operand to avoid layout shifts
- [Phase 15-compound-transition-conditions]: ConditionGroupsEditor is fully controlled (no internal state); mutations go through onChange prop
- [Phase 16-recursive-condition-tree]: Leaf node detection in _build_tree_lambda uses op not in (AND,OR) — handles both unified and legacy leaf formats transparently
- [Phase 16-recursive-condition-tree]: Three-way fallback chain in transition registration: condition_tree (Phase 16+) → condition_groups (Phase 15 DNF) → conditions[] (legacy)
- [Phase 16-recursive-condition-tree]: TaskEditor callsite bridged with groupsToTree/treeToGroups adapters — full migration is Plan 02 scope
- [Phase 16-recursive-condition-tree]: ConditionNode leaf = raw FdaCondition discriminated by absence of children key; branch = op AND|OR plus children array
- [Phase 16-recursive-condition-tree]: normaliseTransition accepts Record<string,unknown>; callsite casts FdaTransition via 'as unknown as' to handle legacy stored data
- [Phase 14-bug-backlog]: refetchOnMount: 'always' for PilotSessions sessions query — no cross-page cache coordination needed
- [Phase 14-bug-backlog]: ORDER BY session_id ASC in /subjects/{name}/runs — deterministic sort at DB level for SubjectSessions .reverse()
- [Phase 13]: class_name injected by PUT endpoint from DB record (authoritative) — class_mismatch check skipped for legacy rows without class_name
- [Phase 13]: preflight network failure is non-blocking — error caught silently so broken preflight endpoint never blocks session start
- [Phase 13]: stable promotion fires after graduation check and wrapped in try/except — trial increment never fails due to promotion error
- [Phase 17]: PilotHardwareConfig row identity switched from (pilot_id, hardware_module_id) to (pilot_id, name) — hardware_module_id retained as nullable FK for backward compat
- [Phase 17]: Seed maps Pi 'class' key -> config['class_name'] without module registry lookup — free-form naming mirrors Pi prefs.json HARDWARE dict
- [Phase 17-free-form-pilot-hardware-config]: HardwareCheckModal pendingEdits keyed by module_name (string) — was module_id (number); class_name not stripped before PUT
- [Phase 17-free-form-pilot-hardware-config]: PilotHardwareConfig rewritten to show pilot_hardware_config rows directly; cascade delete removed from hardware modules router
- [Phase 24-02]: New api/fda_validation.py is the hard-422 enforcement point for trigger_assignments/variables, kept fully separate from the soft _validate_task_definition drift-badge path; wired into POST/PUT /api/task-definitions via a 2-line reject_if_hard_errors(db, fda, toolkit_id) helper (routers/toolkits.py net growth 6 lines, budget 15)
- [Phase 24-02]: known_hw for hardware/timer trigger-action refs is semantic_hardware keys only; actions carrying an explicit "group" key (direct-ref/GUI-built) skip the ref check since fda_validation.py has no DB access to join hardware_module_ids to friendly names
- [Phase 24-02]: unknown trigger_name is enforced against toolkit.trigger_sources only via getattr(toolkit, "trigger_sources", None) or [] — a no-op on toolkits predating Plan 08's column
- [Phase 24-02]: view action key_template validated for shape only (non-empty string, every {token} names a declared variable/flag); key resolution deferred to Phase 13 preflight per 24-CONTEXT.md
- [Phase 24-03]: TriggerAssignmentPanel.add() patched with actions:[] to keep the codebase compiling after FdaTriggerAssignment.actions became required — Plan 05 fully rewrites this file
- [Phase 24-03]: isTimerModule/TrackerMethod exported from ActionEditor (not threaded as props) into HardwareActionFields, matching the labelStyle precedent — pure render-time reads, safe under a circular value export
- [Phase 24]: Plan 24-01: variables registry built now (shared with Phase 23); thread-local _trigger_ctx (not plain attrs); pi_timestamp injected implicitly by view action
- [Phase 24-05]: TriggerAssignmentPanel rewritten — handler enum and all config fields deleted; an assignment is now exactly (trigger_name, actions), with each action list hosted by the SAME ActionEditor StateBodyPanel uses (allowTriggerContext passed only here). add() seeds non-colliding trigger1/trigger2/... placeholders instead of an empty trigger_name, matching VariablesPanel's variable1/variable2 pattern — a required field is never produced empty by construction
- [Phase 24-05]: VariablesPanel rename commits onBlur (uncontrolled defaultValue input), not per-keystroke, to avoid remounting the row when its React key (the variable name) changes mid-edit; collision-checked against both existing variable names and toolkit.flags
- [Phase 24-04]: apply_trigger_assignments is handler-free — (trigger_name, actions) only; both hard-coded handler builders (_build_touch_detector_callback, _build_digital_input_callback) deleted outright, not corrected, along with the mock-only test that encoded detect_change()'s wrong per-channel-array contract
- [Phase 24-04]: _build_trigger_action_list is a thin composition over _build_action_callable with zero action-dispatch logic of its own — the trigger mechanism and the hardware-specific action list (licker) are now provably separate, verified by a detectedLick-equivalence test with no lick-specific runtime code
- [Phase 24-04]: Idempotent hot-reload tracked via self._fda_trigger_callbacks (trigger_name -> callbacks appended by the last apply_trigger_assignments call), diffed/removed at the top of every call, placed after the absent/empty backward-compat guard
- [Phase 24-04]: tools/validate_fda.py single-sourced against autopilot.tasks.fda_vocabulary (VALID_ACTION_TYPES/VALID_SPECIALS/VALID_TRIGGER_CONTEXT_KEYS); VALID_HANDLERS deleted outright; _validate_actions_list gained context_kind/allow_trigger_context params so ONE helper validates both state entry_actions and trigger actions
- [Phase 24-04]: _resolve_renamed_trigger_refs left as a harmless legacy no-op (docstring corrected) rather than deleted — trigger_assignments no longer carry a config key for it to rewrite, but deleting it was out of this plan's scope
- [Phase 24-04]: cmd_rename_hw_ref's TRIGGER_ASSIGNMENTS_SQL is now a no-op against current-format rows (no config.hardware_ref) — logged in deferred-items.md, not fixed (separate code path from validate(), out of Task 3 scope)
- [Phase 24-06]: check_for_detectors matches by capability (num_detectors:int-not-bool>0, device_name:non-empty-str, callable read()), not isinstance(v, Touch_Detector) — a hardware-module-registry detector's class is exec'd fresh by _resolve_hardware_classes and can never satisfy the identity check, so detection silently found zero LICKER trackers before this fix
- [Phase 24-06]: view action gains source_ref + runtime-resolved {device_name} key_template token (RUNTIME_KEY_TEMPLATE_TOKENS, single-sourced in fda_vocabulary.py) — resolved from the source hardware object's own device_name attribute at call time, so one task definition writes LICKER2 on one pilot and TONGUE2 on another without hard-coding either name
- [Phase 24-06]: the sourceless-lick canonical payload captures both pin_number and level from detect_change()'s own output — never {"trigger": "level"} — since execute_trigger's level is the TOUCH_INT IRQ edge (assert/deassert), not electrode state; wiring the trigger level would write interrupt polarity into whichever LICKER changed
- [Phase 24]: Plan 08: trigger_sources/detector_refs derived from lib AST; hard-422 on method-less hardware/timer actions in triggers and state bodies; constrained one-pick DetectorWriteWidget UI macro
- [Phase 25]: Plan 25-01: derive_channels/derive_view_keys single-source the detector key format; module_detector_channels surfaces cross-pilot conflict instead of merging
- [Phase 25]: Plan 02: Pi-side DVK-09/10/11 fixes (check_for_detectors first_channel, execute_trigger error containment, view_detector build-time resolution) landed in pi-mirror; no git commits made there per pi_rules
- [Phase 25]: Plan 25-03: preflight step 8 nested inside step 7's fda_json guard (not after) to reuse already_flagged as skip_modules without risking a swallowed NameError; key_template device_name resolution does not consult skip_modules per the plan's literal resolution-rules table
- [Phase 25]: Plan 25-05: view_key_unresolved is excluded from HardwareCheckModal's PUT loop and pendingEdits initialiser (it names no config row); is_detector resolved by module NAME (not module_id, which pilot_hardware_config rows don't carry) at both the PilotHardwareConfig add and edit entry points, sharing one ['hardware-module-methods', id] query key so no second fetch is introduced
- [Phase 23]: Wave 0 contract tests use per-test skip/xfail guards (not module-level) when a file mixes already-real integration tests with not-yet-real route tests; module-level importorskip only when every test shares one dependency

## Accumulated Context

### Roadmap Evolution

- Phases 1–4 archived (2026-07-26): moved to `.planning/archive/`. Superseded and re-planned inside phases 9–17 — the system is well past them. **Ignore when reviewing GSD phases.** Phases 5–8 (Pi Code Editor) marked Deferred: never started, not in the current plan.
- Phase 24 added (2026-07-26): Trigger Assignment Action Lists — triggers run the same action vocabulary as state `entry_actions`, assigned from the UI. Sequenced **before** Phase 23 per stabilization plan.
- Execution order agreed 2026-07-26: **24 → 23 → review → 18 → Open Ephys**. Rationale and full scope in `.planning/STABILIZATION_PLAN.md`.
- Phases 12–17 were validated manually on the live system; the "Human Verification Required" lists in their VERIFICATION.md files are stale bookkeeping, not open work.
- Phase 25 added (2026-07-27): Detector-Derived View Keys (DVK-01–08) — backend derives `LICKER0…LICKER3` from `device_name` × `num_detectors` and the FDA editor offers them as view operands / `key_template` values; per-pilot resolution lands in Phase 13's `preflight_validate`. Runs **after** Phase 24, which it depends on.
- TRIGA-12 added to Phase 24 (2026-07-27) and folded into plan 24-06: `check_for_detectors` matches detectors by capability instead of `isinstance(v, Touch_Detector)`. Identity matching silently yields zero `LICKER` trackers for a detector declared through the hardware-module registry, because `_resolve_hardware_classes` `exec`s the class from `source_code` into a fresh class object. `hardware/i2c.py` stays off-limits, so the fix lives in `check_for_detectors`. Plan 06's "do not touch `mics_task.py`" constraint is now scoped to that one method — safe because 06 is the only wave-3 plan and runs after 01 and 04.

- **Scope change (2026-07-27): sourceless toolkits only.** All future work targets
  backend-authored ("sourceless") toolkits; the legacy `learning_cage`-backed toolkit is no
  longer run. Detector/lick functionality must still exist — via registered hardware modules
  on the sourceless path, not the `learning_cage` Python class. Invalidates plans 06/07/08 as
  written; see `24-REPLAN-BRIEF.md`. Plans 01–05 unaffected.
- **Constraint discovered (2026-07-27): a sourceless task receives ONLY the `Modules` group.**
  `mics_task.py:94` replaces `self.HARDWARE` wholesale and `get_dispatch_spec` emits only
  `hardware["Modules"]`, so there is no `GPIO`/`I2C`/`Timers` group. Everything a sourceless
  task touches must be a registered hardware module. This makes Pi-class `SEMANTIC_HARDWARE`
  irrelevant on that path, including the `learning_cage` entry added by plan 24-01.
- **Correction (2026-07-27): TRIGA-06's DB claim is wrong.** It records task def 185 as the
  only row with non-empty `trigger_assignments`. Task def **181** has one too, and it caused
  three of the seven post-execution defects. Re-run the query; do not trust the recorded finding.
- **Registry additions (2026-07-27):** hardware modules 7 (`MPR121`→`Touch_Detector`, i2c.py)
  and 8 (`TOUCH_INT`→`Digital_In`, gpio.py) created with pilot-1 configs and attached to
  toolkit 100. These were prerequisites for any sourceless detector work.

## Blockers

None currently.

---

## Open Questions

- OR conditions between FDA transitions — deferred to v2; AND-only is sufficient
- Multi-Pi Pi editor support — deferred to v2; single Pi host for now
- Audit log for Pi exec actions — deferred to v2

---

## Pi Development Workflow

Authoritative rules live in `.claude/skills/pi-deploy/SKILL.md`. They **override** any
conflicting instruction inside a PLAN file.

1. **Verify sync first** (Pi is source of truth). Read-only:
   `rsync -avzi --dry-run --exclude='__pycache__' --exclude='.git' -e "ssh -i ~/.ssh/pi_mics" pi@132.77.72.28:~/Apps/mice_interactive_home_cage/ /home/ido/pi-mirror/`
   Do **not** pull while an agent is mid-edit — it clobbers in-flight work.
2. **Edit** in `/home/ido/pi-mirror/` only. Never edit on the Pi.
3. **Syntax check**: `cd /home/ido/pi-mirror && python3 -m py_compile <file>`.
   `autopilot` **cannot be imported** on this host (`npyscreen` missing), so only
   stdlib-only tests (`tests/test_fda_vocabulary.py`) are agent-runnable.
4. **Deploy only session-edited files**, never the whole mirror, never `--delete`:
   `rsync -avz --relative -e "ssh -i ~/.ssh/pi_mics" /home/ido/pi-mirror/./<path> … pi@132.77.72.28:~/Apps/mice_interactive_home_cage/`
5. **NO git in `/home/ido/pi-mirror`** — not even `status`. To prove a file is untouched:
   `diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/.../f.py') /home/ido/pi-mirror/.../f.py`
6. **Never start/stop the pilot; never run Python on the Pi.** Hand the user the command.
7. Pi tests are USER-RUN, from `~/Apps/mice_interactive_home_cage` **on the Pi** — not from
   `~/pi-mirror`, which is the dev host.

> Plans 06/07/08 still contain the forbidden `git -C /home/ido/pi-mirror status` check and a
> `cd ~/pi-mirror && pytest` step. Fix both during the re-plan.

## Next Actions

1. **Execute Phase 23 Plan 02** (kind-column migration + `seed_compute.py` + declared-imports
   allowlist) — turns `api/tests/test_hardware_lib_kind.py`'s 4 skipped + 5 xfailed tests into
   real passes. See `23-02-PLAN.md` and `23-01-SUMMARY.md` "Next Phase Readiness".
   (Plan 04, Wave 2, is now also done — see "Phase 23 status" above and `23-04-SUMMARY.md`. Its
   4 pi-mirror files are staged for deploy at plan 23-10, uncommitted in the pi-mirror working
   tree, same as plan 02's Phase 25 files below.)
2. **Execute Phase 25 Plan 06** (last plan in phase 25, still outstanding — deferred while phase
   23 Wave 0 was picked up) — **deploy** plan 02's seven pi-mirror files (`fda_vocabulary.py`,
   `mics_task.py`, `task.py`, and four `tests/` files — see `25-02-SUMMARY.md` "Next Phase
   Readiness" for the exact rsync list) AND the plan 04/05 React rebuild (confirm the deployed
   bundles are `dist/TaskEditor-B6-dKcPk.js`, `dist/HardwareCheckModal-DKJUfoGY.js`,
   `dist/PilotHardwareConfig-B09He_Dl.js` — see `25-04-SUMMARY.md` and `25-05-SUMMARY.md` "Next
   Phase Readiness" for the exact operand JSON / config round-trip to look for), run the three
   new USER-RUN Pi test files plus the pre-existing suite, and rig-prove DVK-09 (channel 4 lands
   in `LICKER4`) and DVK-11 (a transition on "MPR121 — channel 2" fires, then re-fires unchanged
   after a `device_name` rename). Also owns the manual/behavioural verification of plan 04's
   editor pickers (grouped `<optgroup>`s, the "(unknown)" flag, the S3 type-switch guard) and
   plan 05's `HardwareCheckModal`/`PilotHardwareConfig` rendering (both `view_key_unresolved`
   shapes, the edit-flow `first_channel` round-trip) — both deferred per their own
   `<verification>` notes.
3. **Run the full Pi test suite** (USER-RUN — `autopilot` unimportable on the dev host), still
   outstanding from phase 24 and now larger after plan 02's additions, plus the new
   `test_compute_ops.py` once plan 23-04 lands:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`

Note: Phase 23 was re-planned 2026-08-03 as 10 plans in 6 waves against a "compute-as-hardware-lib"
reframe (see the `docs(23):` commits immediately before `test(23-01):` in git log) — the prior
"plans are stale" note above no longer applies. Plan 01 (Wave 0 contract tests) and Plan 04
(Wave 2, Pi-runtime compute action) are done; see "Phase 23 status" above and
`23-01-SUMMARY.md`/`23-04-SUMMARY.md`.

Note: `gsd-tools requirements mark-complete` found no checkbox/traceability rows for
CMP-03/04/05/06/12/17/19 in `REQUIREMENTS.md` (same gap previously found for DVK-02/06/07/11) —
completion is tracked via the ROADMAP.md phase-23 status line instead, updated via
`gsd-tools roadmap update-plan-progress 23`. `gsd-tools state advance-plan` still errors
("Cannot parse Current Plan or Total Plans in Phase from STATE.md" — this file predates that
command's expected conventions); `state update-progress` DOES work and was used to update the
frontmatter above (51 total / 37 completed / 73%). `record-metric`/`record-session` remain no-ops
on this STATE.md; position is tracked via the prose "Phase NN status" sections above, per this
file's established pattern.

---
*Last updated: 2026-08-03 — phase 23 plan 04 executed (Wave 2): compute action type lands on the
Pi runtime (CMP-03/04/05/06) — `fda_vocabulary.py`/`mics_task.py`/`tools/validate_fda.py` gain
`type:"compute"`, single-sourced, with mandatory `output` enforced at build time in both the
runtime and the CLI validator. One blocking bug found and fixed in-task (`_build_state_method`'s
validate loop didn't recognize `compute`); one bug found and deliberately left unfixed per the
plan's own instruction (`load_fda_from_json`'s variable-collision guard likely breaks
`hot_update_fda` re-declaring the same variable — flagged as a predicted Phase-24 defect for plan
23-10 to confirm). Agent-verified: `tests/test_fda_vocabulary.py` 23 passed; all `py_compile`
clean. No pi-mirror git commits (user-owned repo). Phase 25 plan 06 (last plan in that phase)
remains outstanding. Next: phase 23 plan 02 (kind-column migration + seed_compute.py), phase 23
plan 05, or phase 25 plan 06, per Next Actions above.*
