---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-07-27T13:28:10.000Z"
progress:
  total_phases: 19
  completed_phases: 5
  total_plans: 33
  completed_plans: 21
  percent: 66
---

# STATE: MICS Backend

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-15)

**Core value:** Researchers can define, modify, and deploy behavioral task logic without writing Python or restarting the Pi.
**Current focus:** Planning complete — ready to begin Phase 1

---

## Current Position

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor
**Phase:** Not started (Phase 1 next)
**Progress:** [███████░░░] 66%

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

## Accumulated Context

### Roadmap Evolution

- Phases 1–4 archived (2026-07-26): moved to `.planning/archive/`. Superseded and re-planned inside phases 9–17 — the system is well past them. **Ignore when reviewing GSD phases.** Phases 5–8 (Pi Code Editor) marked Deferred: never started, not in the current plan.
- Phase 24 added (2026-07-26): Trigger Assignment Action Lists — triggers run the same action vocabulary as state `entry_actions`, assigned from the UI. Sequenced **before** Phase 23 per stabilization plan.
- Execution order agreed 2026-07-26: **24 → 23 → review → 18 → Open Ephys**. Rationale and full scope in `.planning/STABILIZATION_PLAN.md`.
- Phases 12–17 were validated manually on the live system; the "Human Verification Required" lists in their VERIFICATION.md files are stale bookkeeping, not open work.
- Phase 25 added (2026-07-27): Detector-Derived View Keys (DVK-01–08) — backend derives `LICKER0…LICKER3` from `device_name` × `num_detectors` and the FDA editor offers them as view operands / `key_template` values; per-pilot resolution lands in Phase 13's `preflight_validate`. Runs **after** Phase 24, which it depends on.
- TRIGA-12 added to Phase 24 (2026-07-27) and folded into plan 24-06: `check_for_detectors` matches detectors by capability instead of `isinstance(v, Touch_Detector)`. Identity matching silently yields zero `LICKER` trackers for a detector declared through the hardware-module registry, because `_resolve_hardware_classes` `exec`s the class from `source_code` into a fresh class object. `hardware/i2c.py` stays off-limits, so the fix lives in `check_for_detectors`. Plan 06's "do not touch `mics_task.py`" constraint is now scoped to that one method — safe because 06 is the only wave-3 plan and runs after 01 and 04.

## Blockers

None currently.

---

## Open Questions

- OR conditions between FDA transitions — deferred to v2; AND-only is sufficient
- Multi-Pi Pi editor support — deferred to v2; single Pi host for now
- Audit log for Pi exec actions — deferred to v2

---

## Pi Development Workflow

All Pi code changes follow this sequence:
1. **Edit** in `~/pi-mirror/autopilot/` (local mirror — never edit on Pi directly)
2. **Local syntax check**: `python -m py_compile <file>` from `~/pi-mirror/`
3. **Deploy to Pi**: `~/pi-mirror/tools/deploy_pi.sh` (rsync + pilot restart)
4. **Test on Pi**: verify behavior via session start or SSH inspection

Plan 06 (deploy scripts) must be completed before Pi testing of any other plan.
Plan 01 depends on Plan 06 (`depends_on: [06]`, wave 2).

## Next Actions

1. `/gsd:discuss-phase 24` — settle the open design decisions for trigger action lists
   (dynamic tracker naming from a returned channel index; additive `actions` vs replacing
   the `handler` enum) before planning.
2. `/gsd:plan-phase 24`
3. Then Phase 23 (Compute Primitives + Variables) — already planned, 3 plans, not executed.
4. `/gsd:plan-phase 25` — Detector-Derived View Keys. Depends on 24 landing first (the derived
   keys are only worth surfacing once `check_for_detectors` reliably creates them, TRIGA-12).

---
*Last updated: 2026-03-15 — corrections: hot-reload scope, SEMANTIC_HARDWARE naming source, FDA JSON persistence*
