# Phase 30: Pi Repo Cleanup - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove from `/home/ido/pi-mirror` everything the current architecture superseded but never
reclaimed — the replaced Terminal tree, the 27 legacy task plugins and the base classes that
exist only to serve them, hardware drivers no code path reaches, ~190 MB of vendored installers
and build output, and 244 lines of dead commented-out code — then publish the result as a new
repository in the same git account.

**Removal is judged by runtime reachability under the current architecture, never by file age
or git history.** That is the phase's whole premise: the residue was left by phases 9–25, each
of which shipped a capability without reclaiming the ground it superseded, so "old" and
"unused" are uncorrelated here.

**This phase does not touch the Pi.** No deploy, no branch, no device reconciliation. It
produces a cleaned tree and a new repo; everything downstream of that is the user's.

</domain>

<decisions>
## Implementation Decisions

### Rollout topology — two targets, two lifecycles

Settled in discussion 2026-08-10. This is not a migration, and framing it as one produced the
wrong plan initially.

- **The cleanup happens only in `pi-mirror`.** The Pi at `132.77.72.28` is untouched by this
  phase.
- **A new repo is created in the same git account** from the cleaned tree, as a **fresh
  `git init`** — never a clone, never a filtered history (see HYG-01: the leaked credential is
  in `.git`, where a later `git rm` would not remove it).
- **Pi `.28` (the current rig) is never migrated.** It stays on the old repo and receives the
  cleaned code as a **separate branch**. That branch lives **on the user's machine**, not on
  the device.
- **New units** get a fresh OS image and the new repo. **The user handles imaging — explicitly
  out of scope, do not plan provisioning work.**
- **Eventually** (explicitly *"not for now"*) the old rig will have its git and users stripped
  and the new repo enforced in place, because the OS configuration on that unit is worth
  preserving and reimaging would lose it. Recorded in Deferred.

**Consequence that changes a criterion's weight:** because `.28` will eventually receive the
new repo onto a *preserved* OS rather than a fresh image, the cleaned tree must run against an
environment it did not create. HYG-02's live-session proof therefore carries more weight than
it would if every target were a clean image.

**Consequence that dissolves an earlier concern:** `tools/sync_pi.sh` syncs only `autopilot/`
and passes no `--delete`, so an rsync-based rollout could never remove the deleted files from
the device. This topology sidesteps that entirely — a branch checkout removes them on `.28`,
and a fresh image never had them. **Do not plan an rsync-based device reconciliation step.**

### The four held toggles — all resolved

Each was commented-out code that disabled a *behaviour* rather than superseding an
implementation, so none could be deleted on reachability grounds alone.

- **Touch constant `0x3f` — DELETE.** `set_cdc_manual(0x3f)` at `elastic_test.py:138` and
  `learning_cage.py:193`, against the live `0x08` default at `i2c.py:817` (~8× difference in
  MPR121 charge-discharge current, i.e. lick sensitivity). Both host files are being deleted
  with the plugin cluster regardless; the decision was whether to preserve `0x3f` as a
  documented alternative first. It is not needed.
- **IR1–IR7 trigger registrations — DELETE.** `learning_cage.py:141-147`. **User's rationale,
  captured because it is the load-bearing part:** the IR beam-breaks no longer need their own
  trigger registration — a `Digital_In` level change is reported automatically by `@auto_log` /
  `@log_action` (`utils/logging_utils.py`) as a `Hardware_Event`, and that is sufficient. The
  dedicated `detectedIR` callback is redundant, not merely unused.
- **`OG_TRIGGER` opto pulse — DELETE.** `mics_cage_task.py:437-438`. Optogenetic stimulation is
  driven through the BlueBerry/BLE path now, not this GPIO pulse. Note `OG_TRIGGER` remains
  declared in the live `HARDWARE` dict at `mics_cage_task.py:97` and `learning_cage.py:82` —
  both files are deleted by HYG-03, so no orphan declaration survives.
- **Handshake watchdog — RESTORE, do not delete.** `station.py:1333-1346`: the ">21s no PING
  from orchestrator" and "handshake retry failed" warnings are commented out and replaced by a
  live bare `print("")`. Uncomment the logger calls and drop the bare print. Unlike the other
  three, **`station.py` survives the cleanup**, so this is a live improvement to a surviving
  file. Rationale: a silent handshake failure on a running rig is invisible — the same class of
  defect as the missing `TASK_ERROR` emitter.

### Restorations and set-removals (carried in from the audit, already decided)

- **Restore** the NTP enable / clock-freeze call sites at `pilot.py:1137-1148`. Confirmed a
  **regression, not a decision** — the methods stay live at `:498`/`:514` and the comment reads
  "Freeze wall clock so it never jumps during the task." Material on a rig that timestamps
  behavioural events to the millisecond. **Do not delete these commented lines.**
- **Remove as one set:** `open_file()` (55 lines), the `self.h5f` cleanup at `pilot.py:640-641`,
  and the ~23 commented lines at `:1174-1261`. ES is the sole data path, so the half-disabled
  subsystem goes whole rather than leaving a live method nobody calls.
- **`pilot/plugins/` is deleted entirely** — all live work is backend-authored and sourceless.

### Removal criteria — how the sweep decides

The sweep must be reproducible from stated criteria, not from a hand-list (HYG-07). A file is
removable when it satisfies **all** of:

1. Not in the static import closure of `python3 -m autopilot.core.pilot`.
2. Not reachable through a dynamic path — the `PLUGINDIR` sweep, the `autopilot/tasks/` AST
   sweep, `importlib`, or a string-keyed dispatch table.
3. Not named by the backend — no literal filename, module path or class-name string in
   `mics-backend`, and no row in `hardware_libs`, `hardware_modules`, `task_toolkits` or
   `available_locked_states` that resolves to it.
4. Not reserved by a pending phase (see Integration Points).

**Ordering is a hard constraint, not a preference.** Subclasses before base classes, always —
`api/main.py:1059-1070` raises 400 on an unresolvable `base_class`, and because the commit is
at `:1117` inside `orchestrator_station.py:85-183`'s single `try`, that 400 discards the tasks
upsert, the toolkit upsert, the hardware-config seed and the locked-states upsert together.

### Claude's Discretion

- Commit granularity and sweep sequencing within the ordering constraint above. Not discussed;
  the planner should choose staged commits per category over one atomic sweep, because the
  rollback unit matters more than commit tidiness here.
- The exact form of the post-sweep survival manifest (HYG-13).
- The `prefs.json` template's placeholder values and structure (HYG-10).
- Where the root pytest config lands and what it contains (HYG-09).
- How the `30-HARDWARE-VALIDATION.md` evidence log is organised, following the house format
  established by phases 18/23/24/25.

</decisions>

<code_context>
## Existing Code Insights

### The audit is the phase's primary reusable asset

Completed 2026-08-10 by five independent agents — runtime reachability, legacy assets, backend
contract, GSD phase history, commented-out code — cross-checked against the live Postgres DB
and against which `.cpython-37` bytecode the Pi itself wrote. **The planner should not re-derive
reachability.** Full findings are in the audit artifact; the load-bearing conclusions are
reproduced here and in REQUIREMENTS.md HYG-01–14.

**Three agent conflicts were resolved by direct verification. Do not re-open them:**

- **`cameras.py`** — one agent called it a hard requirement, another called it sweep collateral.
  Both were wrong about *why*, and so was this file's first draft. `hardware/i2c.py:8` does
  `from autopilot.hardware.cameras import Camera` and `i2c.py` is imported by `mics_task.py:4`,
  so deleting the file alone stops the pilot at import time.

  > **CORRECTION, 2026-08-10 (planning).** The original text here read *"`Camera` is **never
  > used** in `i2c.py`; the only other matches are docstring prose. It is a dead import."*
  > **That is false.** `Camera` is the **base class of `MLX90640`** — `i2c.py:580
  > class MLX90640(Camera):`, body spanning `:580`–`:798`, directly above `MPR121` at `:799`.
  > The claim came from misreading filtered grep output that rendered line 580 as blank. Acting
  > on it — removing the import but keeping the class — leaves an undefined name evaluated at
  > module-import time, killing the pilot silently. Root cause worth remembering: on this host
  > `grep` output passes through a compressing proxy, so **any load-bearing "symbol X is
  > unused" claim must be re-checked with unfiltered output** before it is written down.

  The correct edit is **three-part**: drop the import, drop the `MLX90640` class, drop
  `cameras.py` — applied **in both the Pi copy and `hardware_libs` version 26**, whose
  `source_code` is `exec()`'d on the Pi. `MLX90640` independently satisfies all four removal
  criteria (no backend hits, no `hardware_libs`/`hardware_modules` row, no `MLX` key in any
  pilot's prefs, and `i2c.py:33`'s `import MLX90640 as mlx_cam` guard already sets
  `MLX90640_LIB = False` on this rig).
- **`jackclient.py` / `pyoserver.py`** — **not loaded.** `pilot.py:75` gates on
  `prefs['AUDIOSERVER']` (false) or `'AUDIO' in CONFIG` (empty). But **`sounds.py` and `base.py`
  *are* loaded**, because `stim/managers.py:17` tests `AUDIOSERVER is not None` and
  `False is not None` is True. Corroborated by which pycs exist.
- **`unreal.py`** — nothing in `autopilot/` imports it; **15 plugin files do**. It is orphaned
  by HYG-03 and goes with them, along with the stale `UNREAL` block in `prefs.json`.

### Established patterns this phase must respect

- **The Pi rules are absolute** (`STATE.md:1723-1744`): no git in `/home/ido/pi-mirror`, not
  even `status`; never `rsync --delete`; never start or stop the pilot; never run Python on the
  Pi; Pi tests are USER-RUN. The agent edits the mirror and runs `python3 -m py_compile` —
  **`autopilot` cannot be imported on this host** (`npyscreen` absent), so `py_compile` is the
  ceiling for agent-run verification.
- **Hardware-validation log**: phases 18/23/24/25 each produced `NN-HARDWARE-VALIDATION.md` with
  a per-requirement PROVEN/UNPROVEN table, md5 manifests and run numbers. Phase 30 produces one.
- **Guarded vs unguarded sweeps — a real asymmetry.** `pilot/plugins/` is imported with a
  per-file `try/except` (`plugins.py:64-66`), so one bad plugin is skipped. `autopilot/tasks/`
  is **not** — `common.py:47-67`'s `list_classes` has no per-file guard, so one syntactically
  broken file there makes `discover_tasks_metadata`'s blanket handler ship `tasks: []` in every
  handshake. `py_compile` over the surviving `tasks/` directory is therefore a gate, not a nicety.

### Integration points

- **HANDSHAKE** — with no plugins, `discover_tasks_metadata()` reports `tasks: []`. This must be
  **verified against the live API, not assumed** (HYG-04): the orchestrator skips its upserts,
  the API returns `tasks_received: 0`, nothing is deleted. The backend **never prunes** — there
  is no delete path on the handshake — so existing toolkit rows persist in the UI with no signal
  the Pi stopped reporting them. That staleness is accepted, not fixed here.
- **`hardware_libs`** — the DB stores hardware driver source that is `exec()`'d on the Pi and
  imports back into `autopilot.hardware.*`. Any Pi-side edit to a versioned lib needs the
  matching DB edit. `i2c.py` has **already drifted 6 bytes** (35,934 on disk vs 35,928 in the
  DB), with no process keeping them in sync.
- **Files a naive sweep destroys** (HYG-13): `external_hardware_ingress.py` and
  `external_hardware_binding.py` appear in **no plan's `files_modified`** — they emerged during
  Phase 18 execution. `external_hardware.py` imports both, and `_binding.py` is the single
  writer of the `alive` tracker Phase 19 depends on entirely. `fda_vocabulary.py` has zero
  top-level classes so the AST sweep would never find it; it survives on one import at
  `mics_task.py:18`, and it is the hand-maintained twin of `api/detector_keys.py` where drift is
  silent.
- **Reserved names, not strays**: `hardware/openephys_client.py`, `tests/test_openephys_client.py`,
  `tests/test_openephys_markers.py` (Phase 26). Note the `OpenEphys` `ExternalHardware` subclass
  ships as a **backend** seeded lib (`api/seed_libs/openephys.py`), not a Pi file — a
  research-stage doc that puts it on the Pi is superseded.
- **Uncommitted state**: every pi-mirror edit from Phase 25 is an uncommitted working-tree
  change, and debug prints from that phase are deployed on the live Pi. The
  `Event_Dispatcher.py` change is **not only prints** — it carries a guarded tick read and the
  `_dropped_no_clock` / `_dropped_on_send` counters, which are real fixes and must survive
  (HYG-12).

</code_context>

<specifics>
## Specific Ideas

- **The phase deliberately departs from the plan of record, and this is the justification.**
  No phase document in 1–29 authorizes deleting a single Pi *file*; every authorized deletion is
  of a method, constant or import inside a surviving file. The corpus explicitly retains
  `pilot/plugins/*.py` (they feed `available_locked_states`) and `learning_cage.detectedLick`
  ("the reference implementation and a one-line rollback if the rig proof fails"). **That
  posture was correct while source-authored toolkits were still dispatched. It no longer holds:**
  all live work is backend-authored and sourceless — user-confirmed 2026-08-10 and corroborated
  by the DB, where protocols 56/57/58 all run `source_less_toolkit`, whose NULL
  `locked_state_source` dispatches to `mics_task` rather than to any plugin file. The 43 protocol
  steps naming `elastic_test` and 15 naming `AppetitveTaskReal` are legacy rows that are not run.
  Recorded so a future reader does not mistake the departure for an oversight.

- **The acceptance test is a live session, not an import check** — deliberately. The Pi has **no
  `TASK_ERROR` emitter at all**: `pilot.py:609` catches a failed START, sets state IDLE and
  reports nothing, so the backend marks the run `running` indefinitely. Every removal failure
  mode in this phase is silent by default, and only a real session surfaces it.

- **Clear pilot 1 before the rig checkpoint.** The Phase 18 demo fixture `ExtlinkDemo` (module
  62, `role: router_bind`, `required: true`) is still assigned to toolkit 100 and configured on
  pilot 1, so every real session there preflight-fails or hangs the full 30 s timeout; a TCP echo
  listener on the dev host at `132.77.73.125:5597` is a second standing dependency. Teardown is
  in `18-HARDWARE-VALIDATION.md` §3. HYG-02 cannot pass until this is cleared.

- **Revoke the credential at Google.** A human action outside the repo, recorded as done before
  publication. Deleting the file is not sufficient — hence fresh-init publication.

</specifics>

<deferred>
## Deferred Ideas

- **Converting `.28` to the new repo in place** — strip git and users from the old rig and
  enforce the new repo there, preserving the OS configuration that a reimage would lose.
  Explicitly *"not for now"* (user, 2026-08-10). Captured so nobody later assumes a fresh image
  was the plan for that unit — it deliberately is not.
- **Provisioning / imaging a new unit** — venv creation, `pigpio`/`jackd` setup, a systemd unit
  or launcher, a per-cage prefs template someone fills in. The user handles imaging; explicitly
  out of scope. If it ever becomes a phase, it is a *provisioning* capability, not a cleanup one.
- **`LOAD_HARDWARE_LIBS` fails silently during a run** — `mics_task.py:1589` imports
  `autopilot.autopilot.core.pilot`, a path that does not resolve, so `receive_hardware_libs()`
  raises `ModuleNotFoundError` and the exception dies unhandled in the `Net_Node` listen thread.
  Only the no-task-running path works. **This undercuts the mechanism the whole
  hardware-centralization arc rests on** and deserves its own fix.
- **No `TASK_ERROR` emitter on the Pi** — restoring it would convert the single largest
  silent-failure mode into a reported one.
- **`i2c.py:819`** — `except(e):` on an undefined name, so MPR121 init failures raise
  `NameError`. `i2c.py` is off-limits under TRIGA-12, so this needs its own decision.
- **`pilot.py:887`** — calls the undefined `get_hardware_class`; `STREAM_VIDEO` raises.
- **`hardware_libs` ↔ disk drift** — no process keeps the exec'd DB copy in sync with the Pi
  file. Already 6 bytes apart for `i2c.py`.
- **Backend dead code found during the audit** — `orchestrator_station._run_watchdog` (kept dead
  deliberately), the `task_files` handshake branch (the Pi never sends it), `on_task_error` (no
  emitter). Not this phase.
- **Roadmap bookkeeping** — the phase-summary table's column-shift corruption affects rows
  11–14, 16 and 18, and the Phase 18 row still reads "Pending — must be re-planned" although
  `STATE.md:276` records it complete (15/15 plans, 2026-08-09). A Phase 29 row was missing and
  was added 2026-08-10.

</deferred>

---

*Phase: 30-pi-repo-cleanup*
*Context gathered: 2026-08-10*
