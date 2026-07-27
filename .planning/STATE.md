---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-07-27T13:33:34.000Z"
progress:
  total_phases: 19
  completed_phases: 5
  total_plans: 33
  completed_plans: 22
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
**Phase:** 24 — Trigger Assignment Action Lists — **waves 1–2 done (5/8 plans), waves 3–4 blocked on re-plan**
**Progress:** [███████░░░] 66%

### Phase 24 status (2026-07-27)

Plans 01–05 executed, deployed, and **proven on the real rig** (run 475: 47 `TOUCH_INT`
firings with alternating `level` 0/1, action list assembled in the UI, no `learning_cage`,
no `handler` enum). TRIGA-01/02/06 demonstrated on hardware.

**Read these two files first when resuming:**
- `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md` — what is
  proven, the 7 post-execution defects and their commits, infrastructure incidents, and the
  exact deployed/registry/DB state.
- `.planning/phases/24-trigger-assignment-action-lists/24-REPLAN-BRIEF.md` — what changes in
  plans 06/07/08 for the sourceless-only decision, requirement by requirement.

**Outstanding:**
1. 41 Pi tests have never run anywhere (`autopilot` unimportable on dev host) — USER-RUN:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`
2. Re-plan 06/07/08 via `/gsd:discuss-phase 24` (**not** `--gaps` — requirement-level drift).
3. Optional: clear legacy `trigger_assignments` rows in task defs 181 and 185 (185 is Gili's).

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

1. **Run the 41 Pi tests** (USER-RUN — `autopilot` unimportable on the dev host). These have
   never executed anywhere; waves 1–2 are runtime-proven but not unit-test-proven:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`
2. `/gsd:discuss-phase 24` — re-plan 06/07/08 for the sourceless-only decision. Read
   `24-REPLAN-BRIEF.md` first. **Not** `--gaps`: TRIGA-11 is dropped, TRIGA-13 needs a new
   home, and two new requirements are proposed (hardware-`method` validation; the
   `Modules`-only constraint). `--gaps` assumes requirements still hold.
3. Execute waves 3–4, then the rewritten rig proof.
4. Then Phase 23 (Compute Primitives + Variables) — **its 3 plans are stale.** They were
   written before the 24→23 resequencing and still claim to build the `variables` registry
   (CMP-01/02) and create `api/fda_validation.py`, both of which phase 24 already delivered.
   Re-plan rather than execute as-is.
5. `/gsd:plan-phase 25` — Detector-Derived View Keys. Depends on TRIGA-12 landing, and may
   absorb TRIGA-13 (see re-plan brief).

---
*Last updated: 2026-07-27 — phase 24 waves 1–2 executed + rig-validated (run 475); sourceless-only
scope change recorded; Pi workflow section corrected to match the `pi-deploy` skill.*
