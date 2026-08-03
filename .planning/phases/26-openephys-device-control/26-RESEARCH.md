# Phase 26: OpenEphys Device Control — Research

**Researched:** 2026-08-03
**Domain:** Open Ephys REST control API integration; seeded first-party hardware-lib pattern; backend-side device REST logic; project/experiment/subject path resolution
**Confidence:** HIGH for in-repo patterns (seeded-lib precedent, migration pattern, preflight extension point, egress/lifecycle reuse — all verified by direct code read); MEDIUM for the Open Ephys REST API surface (verified against official docs via WebFetch, not Context7 — no Context7 library exists for Open Ephys; field names could drift by GUI version, flagged for rig confirmation); LOW/flagged explicitly for anything that depends on Phase 18 code that does not exist yet (it is fully planned, unexecuted) or on live behavior of the actual rig's OE instance.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward from Phase 18 — LOCKED, do not re-litigate** (see `18-CONTEXT.md`):
- `OpenEphys` is an `ExternalHardware` subclass → a versioned hardware lib flowing through
  hw_libs → hw_modules → `pilot_hardware_config` → toolkit dispatch → preflight.
- Control-only modules with **zero declared signals** are legal (EXTLINK-18). OE's control side is
  exactly this.
- Egress: FIFO one worker per device, **fire-and-forget, never retried**, bounded queue dropping the
  newest with the loss recorded, N consecutive failures flip `alive`.
- `on_run_start(run_ctx)` fires async after `.bind()` and is **retried inside the wait window**; the
  readiness gate keys on **ready** (lib-defined), not merely `alive`.
- `on_run_stop()` runs on all Pi paths + a backend safety net. **Verify stop by effect (device idle,
  lease released) — never by asserting a CONTINUOUS event reached ES**; `event_dispatcher.stop()`
  provably races ahead of `task.end()`.
- Device lease keyed on normalized `host`, hard-blocking as a preflight issue naming the holder.
- Markers ride Phase 24's existing `hardware` action type. **No new action type in the editor.**
- `required` defaults true; `wait_timeout_s` default 60, range [5, 600].
- Pi rules: never git on the Pi, never start/stop the pilot, never run Python on the Pi.

**Save-folder naming:**
- **Layout: project / experiment hierarchy** — built from the project → experiment → subject
  hierarchy MICS already models. *(User chose this over mirroring the ES run key.)*
- **Template lives as a lib default, overridable per pilot** in `pilot_hardware_config.config` —
  the same class-defaults + per-pilot-override split Phase 18 locked for every other setting.
- **Collision → refuse to start.** If the target folder already exists, fail the readiness gate with
  a message naming the path. Because `run_id` is unique, a collision means something is genuinely
  wrong (re-used run, clock problem, stale folder). Never write into or over an existing recording.
  Rejected: numeric suffixes (silently produces two folders for one run) and letting OE auto-increment
  (hands naming authority to OE precisely where MICS must be authoritative).
- **Researchers may edit the template** in the pilot hardware config UI, but **the save endpoint
  rejects unknown tokens.** Folder layout is an experimental-workflow concern, not a code concern —
  requiring a developer would just push researchers into out-of-band manual renaming. Token
  validation is what stops a typo from silently yielding an unanalysable path.

> **Risk this choice carries, and its mitigation.** A project/experiment hierarchy embeds mutable
> metadata in the path: renaming an experiment later would orphan already-written paths. **This is
> fully mitigated by persisting the RESOLVED path (below) rather than re-deriving it from current
> metadata**, plus snapshotting the names used. The two decisions are coupled — do not implement the
> hierarchy without the resolved-path persistence.

**What MICS records about each recording:**
- **Fields:** the **resolved absolute path** as computed at run start, OE record-start and
  record-stop timestamps, and which OE host wrote it.
- **Storage: a small dedicated table keyed on `(run_id, device_name)`.** Chosen over new columns on
  `session_runs` because DeepLabCut — already on the roadmap — will need to record video paths the
  same way; columns don't scale past the first device. Chosen over stuffing it in
  `session_runs.overrides` because that column means *session parameter overrides*; output artifacts
  there would be semantically wrong and unqueryable without JSON operators.
- **Snapshot the project and experiment names** used to build the path, alongside the path. Two
  extra fields; closes the rename risk completely.
- **Coverage flag:** mark the recording **incomplete** when OE was not recording for the run's full
  duration, so analysis can filter partial sessions with a query instead of discovering them by eye.
- **Visibility: API + surfaced on the existing React session/run view.**

**Event markers:**
- **MICS always emits run-start and run-stop markers**, bracketing the recording. Everything else is
  explicit — placed by the FDA author in a state body or trigger action.
  - **Rejected: automatic trial markers.** Would couple the ephys path to `INC_TRIAL_COUNTER`, which
    this project requires tasks to send explicitly.
- **Labels are free text, with autocomplete** offering labels already used in the same toolkit.
- **Marker payload carries run/trial context**, e.g. `reward|run=123|trial=45`.
- **Every marker send is dual-logged to ES.** This yields a positive record of what MICS *sent*,
  which diffs against what actually landed in the recording — precisely Phase 28's measurement.

**Bad-state handling:**
- **OE already RECORDING at run start → fail the readiness gate. Never take over.** The lease only
  knows about MICS-initiated runs; it cannot see someone using the OE GUI by hand.
- **Disk-space precheck: yes, if the OE REST API exposes free space** — block below a configurable
  threshold during the readiness gate. **Research must confirm the API actually reports it**; if it
  does not, drop the check rather than inventing one.
- **Recording stops mid-run → log, flip `alive`, and surface prominently in pilot status.**

**Lib delivery and opt-out:**
- **The `OpenEphys` lib ships as a seeded first-party lib** — `api/seed_libs/openephys.py`, seeded
  idempotently at API startup as a stable `hardware_libs` row plus an `OPENEPHYS` hardware module,
  following the pattern Phase 23 established for `compute_ops.py`.
- **A researcher can run a session without ephys via a per-run override**, without editing the
  toolkit.
  > **Scope note for the planner:** this is the one decision that grows the phase beyond the
  > roadmap's original wording. Keep it minimal — prefer reusing the existing start-on-pilot
  > `overrides` path or the already-locked `required` flag over building a new mechanism.

**Orphaned-recording cleanup — ADDED TO SCOPE 2026-08-03:**
Phase 18 closes only half of the pilot-crash case: its backend safety net releases the lease and
marks the run errored, but **cannot command the device to stop**, because the backend has no channel
to one. Phase 26 builds exactly that channel:
- When backend reconciliation detects a run that ended without a clean stop, it **also issues the
  REST call returning OE to IDLE**, not just the lease release.
- The backend reads the OE host and connection settings from `pilot_hardware_config` — the same row
  the Pi uses. No second source of truth.
- **Consequence the planner must account for:** this puts device-specific REST logic in the backend,
  which today has none. Keep it in a small dedicated module (not `api/main.py`, not
  `toolkit_dispatch.py` — both are near their size limits) and share the client shape with the
  Pi-side lib where practical rather than writing the OE REST calls twice.

### Claude's Discretion
- Exact REST call sequence and endpoint shapes against the OE API.
- Table and column names for the recording record.
- Retry cadence for `on_run_start` inside the wait window.
- The token set for the folder template (must at minimum cover project, experiment, subject,
  session, run, date).
- How autocomplete sources prior marker labels (query vs cached).
- Disk-space threshold default.

### Deferred Ideas (OUT OF SCOPE)
- **Firing rate / any neural data into the task** — Phase 27.
- **TTL-vs-network jitter measurement and any TTL removal** — Phase 28. Phase 26 only makes the
  measurement possible by dual-logging markers.
- **DeepLabCut** — reserved; will reuse the recording-record table and the `sub_connect` role.
- **Device scheduling** (queue, notify-when-free) — explicitly rejected; the lease hard-blocks only.
- **Multi-OE-host support** (more than one ephys machine per install) — the lease is keyed on host
  so the model allows it, but nothing in this phase exercises it.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| EPHYS-01 | `OpenEphys` subclasses `ExternalHardware`, drives IDLE→RECORD/RECORD→IDLE via `on_run_start`/`on_run_stop`; readiness gate keys on `on_run_start` succeeding | Exact REST calls confirmed (`PUT /api/status`); "already recording" detection confirmed (`GET /api/status`); readiness-gate wiring is Phase 18's `LifecycleRunner`/`ready_gate_decision` (18-06/18-10/18-11), reused not rebuilt |
| EPHYS-02 | Save folder resolved per run from `run_ctx`, unambiguous across rigs | REST fields for folder config confirmed (`PUT /api/recording`); OE's OWN subdirectory nesting beneath that folder confirmed (Architecture Patterns); **the project/experiment resolution chain from a `run_id` is NOT already unambiguous in the data model — see Open Question 1, the single most load-bearing finding in this document** |
| EPHYS-03 | Resolved path persisted in MICS, readable via API | New table pattern confirmed (`run_hardware_lib_kind_migration`-style idempotent migration); OE does not hand back a ready-made absolute path — MICS must construct it from `GET /api/recording`'s echoed fields (Architecture Patterns) |
| EPHYS-04 | Labelled markers via ordinary Phase-24 `hardware` action, egress-queued, dual-logged to ES | Phase 24's action dispatch + Phase 23's `@log_action` precedent together give an exact, already-proven blueprint (Architecture Patterns → "Marker send blueprint") |
| EPHYS-05 | Preflight reports OE-unreachable and device-held, both block | `PREFLIGHT_ISSUE_KINDS` registry read in full (current, post-Phase-23 state) — two new issue kinds join it and mirror into `HardwareCheckModal.tsx`'s `PreflightIssue` union, exact precedent already used twice this session (Phase 18's `device_held`, Phase 23's compute issues) |
</phase_requirements>

## Summary

Phase 26 has two genuinely separate research surfaces: an **external one** (what does the Open Ephys
HTTP Server plugin actually expose on port 37497) and an **internal one** (how does this codebase's
own data model connect a `session_runs` row to a project/experiment/subject triple, and how does the
established seeded-lib + migration + preflight-extension pattern apply to a REST-controlled device
instead of a compute op). The internal surface turned out to hide the harder problem.

**External finding, MEDIUM-HIGH confidence (official docs, not Context7 — none exists for Open
Ephys):** the documented API is small and matches the source doc's framing closely. `PUT
/api/status {"mode": "IDLE"|"ACQUIRE"|"RECORD"}` drives acquisition; `GET /api/status` returns the
current mode and is the only way to detect "already recording" before a run starts. `GET`/`PUT
/api/recording` reads/writes `parent_directory`, `base_text`, `prepend_text`, `append_text`,
`default_record_engine`, and (PUT-only) `start_new_directory`; the GET response additionally nests a
`record_nodes` array with `node_id`, `experiment_number`, `recording_number` per node. `PUT
/api/message {"text": "..."}` broadcasts a marker into every active Record Node. **No endpoint
anywhere in the documented API reports free disk space** — per the user's own locked instruction,
this means the disk-space precheck should be **dropped**, not invented. Critically, **OE does not
hand back a ready-made absolute path** for a recording — it imposes its own subdirectory nesting
(`.../Record Node <id>/experiment<N>/recording<M>/...`) beneath whatever `parent_directory` you set,
where `experiment_number` increments on an acquisition stop/restart and `recording_number` increments
on each RECORD start/stop within one acquisition run. Because EPHYS-01 already locks an IDLE→RECORD
/ RECORD→IDLE cycle per run (i.e., acquisition itself stops between runs), **every MICS run likely
lands in a fresh `experiment1` unless OE's counters persist across the directory change** — this is
not settled by the docs and must be confirmed on the rig (Open Question 2).

**Internal finding, HIGH confidence (direct code read), and the most load-bearing discovery of this
research session:** the React session/run UI (`SessionCard.tsx` → `getSessionDetail` →
`GET /api/sessions/{session_id}`) and the orchestrator's actual pilot dispatch
(`orchestrator_station.py` → `session_runs` SQLAlchemy table) are **two different identity chains
that share integers by convention, not by foreign key.** `GET /api/sessions/{id}` reads from the
SQLModel `SubjectProtocolRun` table (which has a real `subject_id` FK, hence a real subject name, and
via `Subject`→`SubjectProject`→`Project` a real project) — but the orchestrator's `run_ctx` (what
Phase 18's `on_run_start` will actually receive) is built from the SQLAlchemy `session_runs` row,
whose only subject-shaped field is a synthetic `subject_key = f"bp_s{session_id}_r{run_id}"` string
with **no FK to `Subject` at all**. The two tables are bridged only by both carrying the *same
integer value* in a field each calls `session_id` — a bridge the codebase already leans on
(`preflight_validate`'s step 2: `SELECT protocol_id FROM subject_protocol_runs WHERE session_id =
:sid LIMIT 1`, an explicit "just pick one" shortcut, not a guaranteed-unique join). Resolving
project/experiment names for the folder template requires walking through this exact bridge, and the
schema is many-to-many on **both** ends of the walk (`Subject`↔`Project` via `subject_projects`,
`Experiment`↔`ProtocolTemplate` via `experiment_protocols`) — there is no built-in guarantee of a
single project or a single experiment per run. See Open Question 1.

**Primary recommendation:** copy the Phase 23 `compute_ops.py` / `seed_compute.py` /
`compute_provisioning.py` triad almost verbatim for the seeding half of this phase (kind stays
`'hardware'`, not `'compute'`); resolve project/experiment names using the SAME pragmatic
"session_id bridge, pick one, document the limitation" pattern `preflight_validate` already uses
rather than inventing new disambiguation machinery; and treat the OE REST client as two
near-identical-but-unshared implementations (Pi-side using `requests`, already pinned at
`requests==2.27.1` in `~/pi-mirror/environment.yml` — **no new Pi dependency**, unlike Phase 18's
msgpack gap — and backend-side using `httpx`, already an `api/` dependency).

## Architecture Patterns

### The seeded-first-party-lib pattern (verified precedent — copy this shape)

Read in full: `api/seed_libs/compute_ops.py`, `api/seed_compute.py`, `api/compute_provisioning.py`,
and their wiring in `api/main.py`.

- **The op/method class** (`api/seed_libs/compute_ops.py::ComputeOps`) subclasses `Hardware`
  directly today because compute has no transport. **`OpenEphys` will instead subclass
  `ExternalHardware`** (Phase 18, not yet built) — the shape below still applies for everything
  except the base class:
  - No `__init__` override — `init_hardware()` splats `pilot_hardware_config.config` in as kwargs.
  - `release()` is a **mandatory** override (the `Hardware` base raises if not overridden;
    `Task.end()` calls it unconditionally on every hardware object, on every run — see
    `18-RESEARCH.md` Pitfall 7 for the exact same trap already documented for Phase 18).
  - Methods that must be dispatchable from an FDA `hardware` action (e.g. `send_marker`) are ordinary
    instance methods; Phase 24's `_build_action_callable` calls them by name via
    `self.hardware[group][ref]` / `self._semantic_hw[ref]` exactly like any GPIO device.
- **`api/seed_compute.py::seed_compute_ops_lib(engine)`** — idempotent, raw-SQL, one
  `engine.begin()` transaction, called at API startup alongside the migration block. Checks
  `SELECT id FROM hardware_libs WHERE filename = :f` first and no-ops if found. Inserts a
  `hardware_libs` row (`kind='hardware'` for OpenEphys — **not** `'compute'**), a
  `hardware_lib_versions` row with `state='stable'` set directly (skips the normal
  unvalidated→beta→stable promotion flow for the seed content, exactly as compute ops does), sets
  both `active_version_id` and `stable_version_id` to it, and a `hardware_modules` row
  (`class_name='OpenEphys'`). Wrapped in `try/except`: a seeding failure must never stop the API
  from booting (documented rule, followed by the compute seeder).
- **`api/compute_provisioning.py::provision_compute_configs`** auto-creates the trivial
  `pilot_hardware_config` row (`{"class_name": "..."}`) a module needs before `init_hardware()` will
  instantiate it on the Pi — **this genuinely does NOT transfer to OpenEphys as-is**: unlike a
  compute op, `OpenEphys` needs real per-pilot config (`host`, port(s), the folder template
  override, disk threshold if kept) from day one, so an auto-provisioned trivial row would still
  fail preflight's `incomplete_config` check (correctly — there is real config to supply). The
  closer precedent is Phase 18's own `EXTLINK-10` config schema (`class_name`, `role`, `host`,
  `connect_port`/`listen_port`, `source_id`, `stale_ms`, `required`, `wait_timeout_s`,
  `egress_fail_threshold`), not the compute module's zero-config case. **Recommend NOT
  auto-provisioning a working OE config row** — seed the lib/module only, and let the existing
  `missing`/`incomplete_config` preflight issues (already in `PREFLIGHT_ISSUE_KINDS`) do their job
  the first time a researcher wires an OE-equipped toolkit to a pilot.
- **Startup wiring** (`api/main.py`): `run_hardware_lib_kind_migration(engine)` then
  `seed_compute_ops_lib(engine)`, both called unconditionally after `create_all()`. A
  `seed_openephys_lib(engine)` call belongs in the same place, same ordering rule (migrations before
  seeding, since seeding reads `kind`).

### Migration pattern (verified precedent — `api/db.py`)

Every migration function in `api/db.py` (12 of them, read in full) follows one shape:
`def run_<name>_migration(eng): with eng.begin() as conn: conn.execute(text("ALTER TABLE ... ADD
COLUMN IF NOT EXISTS ... / CREATE TABLE IF NOT EXISTS ..."))`. `run_hardware_lib_kind_migration`
(the most recent, Phase 23) is the closest template for a brand-new table:
```python
def run_openephys_recording_migration(eng):
    """Phase 26: device_recordings table (run_id, device_name) — idempotent."""
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS device_recordings (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES session_runs(id),
                device_name VARCHAR NOT NULL,
                resolved_path TEXT NOT NULL,
                device_host VARCHAR,
                project_name_snapshot VARCHAR,
                experiment_name_snapshot VARCHAR,
                record_started_at TIMESTAMP,
                record_stopped_at TIMESTAMP,
                is_incomplete BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (run_id, device_name)
            )
        """))
```
`session_runs` is the SQLAlchemy-owned table (`api/models.py:431`) — this new table must therefore
be queried/written with a SQLAlchemy `Session` (`SA_SessionLocal`/`_SA_SessionLocal` pattern already
used by `toolkit_dispatch.py` and `pilot_hardware_config.py`), never a SQLModel session (CLAUDE.md's
dual-ORM rule, and the exact mixing hazard `18-RESEARCH.md`/CONTEXT already flag generally).
`device_name` (not `oe`-specific naming) is deliberate — it is the CONTEXT-locked reason this table
exists at all (DeepLabCut reuse).

### The project/experiment/subject resolution chain (verified, and genuinely unresolved — read carefully)

Traced end-to-end this session (`api/models.py`, `api/main.py`, `web_ui/app.py`,
`web_ui/react-src/src/api/sessions.ts`):

1. The React session UI's `sessionId` (what `SessionCard`/`PilotSessions` operate on) is the
   `session_id` field shared — **by convention, not FK** — between two independent tables:
   - `subject_protocol_runs` (SQLModel: `subject_id`, `protocol_id`, `session_id`, `current_step`) —
     created by `POST /sessions/start` (`_start_session_for_pending_subjects`), one row **per
     subject** in that session.
   - `session_runs` (SQLAlchemy: `session_id`, `pilot_id`, `subject_key`, ...) — created by
     `POST /session-runs` (`web_ui/app.py::start_session_on_pilot` passes the SAME `session_id`
     value straight through), one row **per pilot** the session is started on.
   - `session_runs.subject_key` is **synthetic** (`f"bp_s{session_id}_r{run_id}"`), not a subject
     name and not an FK to `Subject`.
2. **The only existing code that bridges the two tables is `toolkit_dispatch.py::preflight_validate`
   step 2**: `SELECT protocol_id FROM subject_protocol_runs WHERE session_id = :sid LIMIT 1` —
   explicitly takes the first match, with no attempt to disambiguate a multi-subject session. This
   is the ONLY established precedent for "given a session_runs-flavoured session_id, find the
   protocol/subject it's about." Phase 26 needs the mirror image of this query (subject NAME +
   project NAME + experiment NAME, not just protocol_id), and should follow the same pragmatic
   shape rather than inventing stricter semantics preflight itself doesn't have.
3. From there: `subject_protocol_runs.subject_id` → `Subject.name` (real name) →
   `subject_projects` → `Project.name` — **many-to-many** (a subject can belong to 0, 1, or many
   projects; `SubjectProject` has no notion of "the current one").
4. `subject_protocol_runs.protocol_id` → `experiment_protocols` → `Experiment.name` — **also
   many-to-many** (`ExperimentProtocol` is a plain join table; a protocol can be attached to more
   than one experiment).

**There is currently no schema guarantee of a single project or a single experiment per run.** This
is not a Phase-26-specific problem to solve from scratch (Phases 1-25 never needed this resolution),
but Phase 26 is the first phase for which it becomes load-bearing, since the folder path must be
deterministic. See Open Question 1 for the concrete recommendation.

### Marker send blueprint (composes two already-proven precedents — HIGH confidence)

EPHYS-04 wants: an ordinary Phase-24 `hardware` action, non-blocking (egress-queued), and dual-logged
to ES (a positive record of what MICS *sent*, independent of whether it arrived). This composes two
things already verified working in this exact codebase:

1. **Phase 23's `@log_action` precedent** (`api/seed_libs/compute_ops.py`) — a `Hardware`-subclass
   method decorated `@log_action` gets its call (name + args) auto-dispatched to ES the instant it
   runs on the calling thread — this is what "dual-logged" needs for the **send** half.
2. **Phase 18's egress worker** (`external_hardware_runtime.py::EgressWorker`, 18-06/18-10) — a
   thread-per-device FIFO queue; the calling method enqueues and returns immediately.

Concretely, `OpenEphys.send_marker(label: str, run: int = None, trial: int = None)` should be
`@log_action`-decorated (captures "marker X was requested" synchronously, on the FDA thread, the
instant `_build_action_callable`'s `hardware` branch calls it) and its BODY should only build the
payload string and call `self._egress.enqueue(...)` (returns immediately; the actual `PUT
/api/message` HTTP call happens later, off-thread, fire-and-forget per Phase 18's locked egress
semantics). This exactly matches EPHYS-04's three requirements in one method, using nothing that
doesn't already exist once Phase 18 lands. **Dependency note:** this cannot be smoke-tested for real
until Phase 18's `ExternalHardware`/`EgressWorker` exist — Phase 26 planning should write the
Pi-mirror test against a **fake** `_egress`/`event_dispatcher` (per Phase 18's own Validation
Architecture pattern), not assume the real classes are importable at Phase 26 plan time.

### Backend-side REST-to-a-device (new territory for this codebase — confirmed feasible, no gaps)

- `httpx` is already an `api/` dependency (`api/requirements.txt:8`) — no new backend dependency.
- The Pi already has `requests==2.27.1` pinned in `~/pi-mirror/environment.yml:49` and it is already
  imported elsewhere in the same codebase (`autopilot/setup/request_helpers.py`,
  `autopilot/utils/wiki.py`, `autopilot/utils/plugins.py`) — **no new Pi-side dependency**, unlike
  Phase 18's msgpack gap. This materially de-risks Phase 26 relative to Phase 18: there is no
  Wave-0 "resolve a version pin on the rig" step needed for the REST client itself.
- The orchestrator already makes synchronous HTTP calls to the api container via
  `orchestrator/orchestrator/mics/mics_api_client.py` (uses stdlib `requests`, pinned
  `requests==2.32.3` in `orchestrator/requirements.txt`) — this is the existing pattern any
  orchestrator-side reconciliation trigger would use to reach a new backend endpoint.
- **Recommended shape, given the CONTEXT's explicit constraint** ("not `api/main.py`, not
  `toolkit_dispatch.py`"): a new `api/openephys_client.py` module exposing small, pure-ish functions
  (`set_mode(host, port, mode) -> httpx.Response`, `get_status(host, port) -> dict`,
  `set_recording_config(host, port, **fields)`, `send_message(host, port, text)`), imported by
  whatever endpoint Phase 18's device-lease force-release/reconciliation path ends up calling.
  "Share the client shape with the Pi-side lib" (CONTEXT's own wording) cannot mean literal code
  sharing — `api/` (httpx, Python 3.11 in docker) and `~/pi-mirror/` (requests, Python 3.7.3) are
  separate repos/processes with no shared package — it should be read as: **keep the same function
  names/URL-building logic conceptually identical in both places**, so a future OE API change is a
  symmetric two-file edit, not a rediscovery.
- **Orchestrator vs backend split, confirmed by reading `orchestrator_station.py` in full**: the
  reconciliation loop Phase 18 must build (`_redis_touch`'s `updated_at` staleness, replacing the
  dead `_run_watchdog`) lives in the **orchestrator** process (per Phase 18's own file list:
  `orchestrator/orchestrator/orchestrator_station.py`). But `pilot_hardware_config` — the row the
  OE host/port config lives in — is api/Postgres data, not something the orchestrator process reads
  directly today (it always goes through `self.api.*` HTTP calls, per `mics_api_client.py`).
  **Recommended flow:** the orchestrator's reconciliation loop detects the stale heartbeat (as
  Phase 18 already plans) and calls a NEW api endpoint (e.g., extending whatever Phase 18's
  device-lease force-release endpoint turns out to be) that, backend-side, reads
  `pilot_hardware_config`, calls `openephys_client.set_mode(..., "IDLE")`, and releases the lease —
  all in one api-side transaction. This keeps the "no second source of truth" constraint the CONTEXT
  locks (backend reads the SAME row the Pi uses) while keeping orchestrator-to-OE communication
  indirect (orchestrator → api → OE), consistent with everything else the orchestrator already does.
  **This exact endpoint shape is Claude's Discretion at plan time, gated on what Phase 18's 18-08/18-09
  actually ship** — flagged as a cross-phase dependency, not something Phase 26 can finalize today.

### Control-only module and the transport-role question (open — depends on unbuilt Phase 18 code)

EXTLINK-18 states a zero-signal control-only module "must instantiate, bind, participate in the
readiness gate, and use the egress path" — but Phase 18's `socket_plan` (18-05-PLAN.md, read in
full) always produces a `router_bind` or `sub_connect` plan; there is no documented third "no
socket" mode in the plans read this session. **Whether Phase 26's `OpenEphys` control class must
still declare a `role`/port pair in `pilot_hardware_config.config` (e.g. a `router_bind` on an unused
port, purely so `.bind()`/egress/lifecycle machinery runs uniformly) or whether Phase 18 will grow a
"no transport" mode is not yet decided in any plan read this session.** Recommend the Phase 26 plan
treat this as a dependency check against Phase 18's actual shipped code (not this document) at
execution time, defaulting defensively to declaring `role: "router_bind"` with a dedicated,
never-connected port if no better option exists once Phase 18 lands.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-blocking device control from the FDA thread | A new async/thread mechanism for HTTP PUT | Phase 18's `EgressWorker` (`external_hardware_runtime.py`) | Already designed for exactly "one FIFO worker per device, fire-and-forget" — EPHYS-04's marker requirement is this mechanism verbatim |
| Op-level audit logging | A custom "log what I sent" table/event | `@log_action` (`logging_utils.py`) on the `OpenEphys` method | Already dispatches a `Hardware_Event` per call, verified working for Phase 23's compute ops; zero new logging code needed |
| First-party lib bootstrap | A manual upload step / admin doc | The `seed_compute_ops_lib`-shaped idempotent seeder | Exact precedent exists, verified twice-idempotent in Phase 23; copy the shape |
| New table migration mechanism | An ORM migration framework (alembic etc.) | The existing `run_*_migration(eng)` raw-SQL idempotent function pattern in `api/db.py` | This project has never used a migration framework; introducing one for one table would be inconsistent with 12 existing precedents |
| New preflight issue surfacing | A new validation framework or endpoint | `PREFLIGHT_ISSUE_KINDS` frozenset + `HardwareCheckModal.tsx`'s mirrored union | Verified current (post-Phase-23) shape; the exact extension point two prior phases already used for their own new issue kinds |
| Subject/project/experiment resolution | A brand-new normalized "current project" concept bolted onto `session_runs` | The existing `subject_protocol_runs`-via-`session_id` bridge `preflight_validate` already uses | Introducing a stricter model is a real, valuable improvement but is bigger than this phase's stated scope — CONTEXT.md never asked for it; flag as Open Question, don't silently redesign the subject/project data model inside a device-control phase |

**Key insight:** almost everything genuinely new in this phase is Open-Ephys-specific glue over
already-proven MICS mechanisms (seeded lib, migration, preflight, egress, `@log_action`). The one
piece of real, novel backend work is the httpx-based OE REST client module — and even that has no
new dependency to add.

## Common Pitfalls

### Pitfall 1: Assuming a resolved absolute path can be read back from one API call
**What goes wrong:** Code that expects `GET /api/recording` (or the `PUT` response) to hand back a
single ready-made path string will have nothing to persist as EPHYS-03's "resolved path."
**Why it happens:** The OE HTTP API documents `parent_directory`/`base_text`/`prepend_text`/
`append_text` and, separately, per-record-node `experiment_number`/`recording_number` — but no
endpoint composes them into one path (confirmed via WebFetch against the official Remote-control
docs page this session; no endpoint returning a full path was found).
**How to avoid:** After `PUT /api/status {"mode": "RECORD"}` succeeds, immediately `GET
/api/recording` again, read `record_nodes[].node_id` / `.experiment_number` / `.recording_number` for
the node(s) in the chain, and construct the resolved path in MICS's own code from those parts plus
the directory-name fields already sent. **The exact on-disk naming convention (e.g. `Record Node
102` vs `Record_Node_102`, and how `prepend_text`/`base_text`/`append_text` compose into one
directory name) is NOT stated in the official docs fetched this session** — confirm the literal
string format against the real rig before hardcoding it (see Open Question 3).
**Warning signs:** A plan task that treats path construction as "just read a field" instead of "read
three-plus fields and assemble them, then confirm against the rig."

### Pitfall 2: Treating "collision → refuse to start" as a live filesystem check on the OE host
**What goes wrong:** There is no documented directory-listing/exists-check endpoint in the OE REST
API. A plan that assumes MICS can ask OE "does this folder already exist" before starting will have
nothing to call.
**Why it happens:** The CONTEXT's locked wording ("If the target folder already exists, fail the
readiness gate") reads naturally as a filesystem check, but the only OE-side signal available is
`GET /api/recording`'s echoed config fields, not a directory listing.
**How to avoid:** Implement the collision check as a **MICS-side DB uniqueness check** against the
new recording table — before computing/sending the folder config, `SELECT` whether a row already
exists with this exact `resolved_path` (or, more simply, whether `(run_id, device_name)` already has
a row, which the `UNIQUE` constraint already guarantees can't double-insert). Since the folder
template is deterministic given `(project, experiment, subject, session, run, date)` and `run_id` is
unique, this check will almost always be equivalent to "has MICS ever recorded to exactly this path
before" for the normal case. **Document the residual gap explicitly**: this does NOT detect a folder
a researcher created by hand via the OE GUI outside MICS — an accepted risk parallel to the
already-recording gap the CONTEXT itself accepts for manual GUI use.
**Warning signs:** A plan task naming an OE endpoint for "check if folder exists" that isn't one of
the ones confirmed in this document (`/api/status`, `/api/recording`, `/api/message`,
`/api/processors`).

### Pitfall 3: Assuming `experiment_number`/`recording_number` reset predictably across runs
**What goes wrong:** A plan that hardcodes "each MICS run always writes to `experiment1/recording1`"
(or the opposite — "OE keeps counting up forever") could be wrong either way.
**Why it happens:** Community sources (not official docs) state experiment_number increments on
acquisition stop/restart and recording_number increments on each RECORD start/stop within one
acquisition run — but whether OE resets these counters when the target directory changes (via
`start_new_directory` or a changed `base_text`/`prepend_text`/`append_text`) is not stated anywhere
found this session.
**How to avoid:** Read back `experiment_number`/`recording_number` from `GET /api/recording` after
every RECORD start (Pitfall 1's pattern) rather than assuming a fixed value — the resolved path
persisted in MICS must reflect what OE actually did, not what MICS predicted it would do. Use `PUT
/api/recording`'s `start_new_directory` field on every `on_run_start` to maximize the chance of a
fresh `experiment1/recording1`, but do not treat that as guaranteed without a rig confirmation.
**Warning signs:** A plan or test asserting a specific `experiment_number`/`recording_number` value
without having verified OE's actual reset behavior against the rig.

### Pitfall 4: Building `send_marker`/lifecycle logic against a `Hardware`/`ExternalHardware` import that raises on the dev host
**What goes wrong:** Any Pi-mirror test file that does `from autopilot.hardware.external_hardware
import ExternalHardware` (or even `from autopilot.hardware import Hardware`) triggers
`autopilot/__init__.py`'s unconditional `from autopilot.setup import setup_autopilot`, which imports
`npyscreen` — not installed on the dev host. This is Phase 18's own documented finding, reproduced
independently by Phase 23's compute-ops tests, and it applies identically here.
**How to avoid:** Follow Phase 18's own Validation Architecture split — keep anything Phase 26 wants
to unit-test agent-side (the OE REST client's URL/payload construction, the folder-template token
resolver, the marker-payload string builder) in `autopilot`-free modules, and test the
`OpenEphys`/`ExternalHardware`-coupled glue only via fakes, deferring the real-import proof to the
single rig checkpoint (per Phase 18's own precedent).
**Warning signs:** A Wave-0 test file for this phase that imports `autopilot.hardware.external_hardware`
directly and expects to run on the dev host.

### Pitfall 5: Assuming `kind='compute'` applies to the OpenEphys seed lib
**What goes wrong:** Copying `seed_compute.py` too literally (including the `kind` value) would make
`OpenEphys` subject to `_validate_compute_lib`'s stdlib-only import allowlist and CMP-19's
compute-specific version-resolution nuances — neither of which apply to a genuine hardware lib.
**Why it happens:** The seeded-lib pattern is the same shape for both; only the `kind` column
differs, and it is easy to copy-paste the wrong literal.
**How to avoid:** Seed `OpenEphys` with `kind='hardware'` (the column's existing default) — it is a
real `ExternalHardware`/`Hardware` subclass with real transport, not a pure-compute module.
**Warning signs:** `api/seed_libs/openephys.py`'s `hardware_libs` INSERT carrying `kind='compute'`,
or a `declared_imports` field being validated against `COMPUTE_STDLIB_ALLOWLIST`.

## Code Examples

### OE REST call sequence (backend module shape — pattern, endpoints verified against official docs)
```python
# api/openephys_client.py (new)
import httpx

def _base_url(host: str, port: int = 37497) -> str:
    return f"http://{host}:{port}"

def get_status(host: str, port: int = 37497) -> dict:
    return httpx.get(f"{_base_url(host, port)}/api/status", timeout=5.0).json()

def set_mode(host: str, port: int, mode: str) -> dict:
    # mode in {"IDLE", "ACQUIRE", "RECORD"} — confirmed via official Remote-control docs
    resp = httpx.put(f"{_base_url(host, port)}/api/status", json={"mode": mode}, timeout=5.0)
    resp.raise_for_status()
    return resp.json()

def set_recording_config(host: str, port: int, **fields) -> dict:
    # fields subset of: parent_directory, base_text, prepend_text, append_text,
    # default_record_engine, start_new_directory
    resp = httpx.put(f"{_base_url(host, port)}/api/recording", json=fields, timeout=5.0)
    resp.raise_for_status()
    return resp.json()

def get_recording_config(host: str, port: int) -> dict:
    return httpx.get(f"{_base_url(host, port)}/api/recording", timeout=5.0).json()

def send_message(host: str, port: int, text: str) -> None:
    httpx.put(f"{_base_url(host, port)}/api/message", json={"text": text}, timeout=5.0)
```

### Marker send on the Pi (pattern — depends on Phase 18's unbuilt `ExternalHardware`/`EgressWorker`)
```python
# ~/pi-mirror/autopilot/autopilot/hardware/openephys.py (new, Phase 26)
from autopilot.hardware.external_hardware import ExternalHardware
from autopilot.utils.logging_utils import log_action
import requests

class OpenEphys(ExternalHardware):
    # zero @signal/@event declared — control-only, legal per EXTLINK-18

    def on_run_start(self, run_ctx: dict) -> bool:
        # returns True/False for the retried-readiness contract (Phase 18's LifecycleRunner)
        resp = requests.get(f"http://{self.host}:{self.port}/api/status", timeout=5.0)
        if resp.json().get("mode") == "RECORD":
            return False  # already recording -- never take over (locked decision)
        requests.put(f"http://{self.host}:{self.port}/api/recording",
                     json=self._resolved_recording_config(run_ctx), timeout=5.0)
        requests.put(f"http://{self.host}:{self.port}/api/status",
                     json={"mode": "RECORD"}, timeout=5.0)
        return True

    def on_run_stop(self) -> None:
        requests.put(f"http://{self.host}:{self.port}/api/status",
                     json={"mode": "IDLE"}, timeout=5.0)

    @log_action
    def send_marker(self, label: str, run: int | None = None, trial: int | None = None):
        text = label if run is None else f"{label}|run={run}|trial={trial}"
        self._egress.enqueue(lambda: requests.put(
            f"http://{self.host}:{self.port}/api/message", json={"text": text}, timeout=5.0
        ))
        return text  # @log_action captures label/run/trial synchronously — the "sent" record
```

### Project/experiment/subject resolution (pattern — mirrors `preflight_validate`'s existing bridge)
```python
# Given a session_runs.id (run_id):
run = db.execute(text("SELECT session_id FROM session_runs WHERE id = :id"), {"id": run_id}).fetchone()
spr = db.execute(
    text("SELECT subject_id, protocol_id FROM subject_protocol_runs WHERE session_id = :sid LIMIT 1"),
    {"sid": run.session_id},
).fetchone()  # same "pick one" shortcut preflight_validate already uses -- see Open Question 1
subject_name = db.execute(text("SELECT name FROM subjects WHERE id = :id"), {"id": spr.subject_id}).scalar()
project_name = db.execute(text("""
    SELECT p.name FROM projects p JOIN subject_projects sp ON sp.project_id = p.id
    WHERE sp.subject_id = :sid ORDER BY p.id LIMIT 1
"""), {"sid": spr.subject_id}).scalar()
experiment_name = db.execute(text("""
    SELECT e.name FROM experiments e JOIN experiment_protocols ep ON ep.experiment_id = e.id
    WHERE ep.protocol_id = :pid ORDER BY e.id LIMIT 1
"""), {"pid": spr.protocol_id}).scalar()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — first REST-controlled external device in this codebase | `ExternalHardware` control-only subclass driving a remote device via REST from the Pi | Phase 26 (this phase, pending Phase 18) | First use of `EXTLINK-18`'s "zero-signal control-only module" allowance in production |
| Backend has zero device-specific outbound HTTP logic | A small `api/openephys_client.py` module doing device-specific REST | Phase 26 | First time backend code speaks to lab hardware directly, not just to the Pi/orchestrator |

**Deprecated/outdated:** nothing in this phase deprecates existing mechanisms — it is additive.

## Open Questions

1. **How does the folder template resolve a single project and a single experiment for a given
   run, given the schema is many-to-many on both edges?**
   - What we know: `Subject`↔`Project` is many-to-many (`subject_projects`); `Experiment`↔`Protocol`
     is many-to-many (`experiment_protocols`); the only existing bridge from a `session_runs`-style
     `session_id` to a subject/protocol at all is `preflight_validate`'s own `LIMIT 1` shortcut.
   - What's unclear: whether "pick the first match, ordered by id" is an acceptable resolution rule
     for a value that gets **written into a filesystem path and persisted as a snapshot**, versus
     `preflight_validate`'s existing use where the ambiguity is at worst a wrong preflight check.
   - Recommendation: use the same `LIMIT 1` pragmatic pattern (Code Examples above), but make the
     ambiguity **visible**: log a warning (or even a CONTINUOUS event) whenever a subject has more
     than one project or a protocol maps to more than one experiment at resolution time, and
     consider surfacing "which project/experiment was chosen" in the recording-record API response
     so a researcher can catch a wrong pick immediately rather than discovering it in an unlabelled
     folder weeks later. Do NOT attempt to redesign the Subject/Project/Experiment schema inside this
     phase — that is a bigger, separate change the CONTEXT never asked for.

2. **Does OE's `experiment_number`/`recording_number` counter reset when the target directory
   changes (via `start_new_directory` or new `base_text`/`prepend_text`/`append_text`), or does it
   persist across the GUI's whole process lifetime regardless of directory?**
   - What we know: official docs confirm the fields exist and confirm (via a secondary, non-official
     but consistent source) the general stop/restart-acquisition semantics for `experiment_number`
     and the start/stop-record semantics for `recording_number`. No source found this session states
     the directory-change reset behavior explicitly.
   - What's unclear: whether every MICS run reliably lands in `experiment1/recording1` (making the
     resolved path simple and stable) or whether the numbers can climb across runs even with a fresh
     directory (making the resolved path only knowable by reading it back after the fact, per
     Pitfall 1/3).
   - Recommendation: Phase 26's rig checkpoint (Validation Architecture, below) must include one
     explicit probe — start two MICS-driven runs back to back on the real rig, and record the
     resulting `experiment_number`/`recording_number` pairs — before finalizing the resolved-path
     construction logic. Always read back the values rather than predicting them, regardless of the
     answer.

3. **What is the literal on-disk directory-naming convention for `Record Node <id>` and for the
   composition of `parent_directory`/`base_text`/`prepend_text`/`append_text` into one directory
   name?**
   - What we know: a Record Node's own settings (`node_id`, `parent_directory`, `record_engine`,
     `experiment_number`, `recording_number`, `is_synchronized`) are confirmed field names from the
     official docs. A third-party source (not official Open Ephys docs) shows an example path
     `Record_Node_###\experiment1\recording1\continuous\...` with underscores, which may or may not
     match the exact GUI version the lab runs.
   - What's unclear: whether the real separator is a space (`"Record Node 102"`) or an underscore
     (`"Record_Node_102"`), and the exact order/joiner (`_`? no separator?) the GUI uses to combine
     `prepend_text`+`base_text`+`append_text` into the first-level directory name.
   - Recommendation: do not hardcode this string format in the plan. Either (a) confirm it on the
     rig before writing the path-construction code, or (b) construct the resolved path defensively
     by having the OE lib, after `on_run_start` succeeds, do a lightweight verification pass (e.g. if
     the OE host is reachable via the same network as the Pi, list the parent directory — though this
     likely requires a filesystem mount or SSH the Pi does not currently have, so (a) is the
     realistic option).

4. **Does a zero-signal control-only `ExternalHardware` module need to declare a `role` (and an
   unused port) in `pilot_hardware_config.config`, or will Phase 18 grow a "no transport" mode?**
   - What we know: EXTLINK-18 requires such a module to "instantiate, bind, participate in the
     readiness gate, and use the egress path." Phase 18's `socket_plan` (18-05-PLAN.md) always
     returns a `router_bind` or `sub_connect` plan in the plans read this session; no third mode was
     found.
   - What's unclear: whether this is a deliberate simplification (every module gets a socket even if
     nothing ever uses it) or an oversight Phase 18 will still resolve before it ships.
   - Recommendation: Phase 26 planning should re-check Phase 18's actual shipped
     `external_hardware.py`/`external_hardware_wire.py` at execution time (not rely on this document,
     since Phase 18 is unexecuted), and default to declaring `role: "router_bind"` on a dedicated,
     never-connected port if no better option exists.

5. **Exact endpoint/shape for the backend-side "force stop the device" hook Phase 26 attaches to
   Phase 18's device-lease reconciliation.**
   - What we know: the orchestrator's reconciliation loop (Phase 18, keyed on `_redis_touch`'s
     `updated_at`) lives in `orchestrator_station.py`; `pilot_hardware_config` is api/Postgres data;
     the orchestrator only ever reaches the api via `mics_api_client.py`'s synchronous `requests`
     calls.
   - What's unclear: the literal endpoint name/shape, since it depends on what Phase 18's 18-08/18-09
     (device-lease core + reconciliation) actually ship, and those are unexecuted.
   - Recommendation: treat this as a genuine cross-phase dependency to re-verify against Phase 18's
     actual code at Phase 26 plan/execution time, not something this document can finalize.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework (backend) | pytest, run inside the `api` docker container (`docker compose exec api pytest`) |
| Framework (Pi, agent-runnable) | pytest, but any test importing `autopilot.hardware.external_hardware` (or `autopilot.hardware`/`autopilot.tasks` at all) fails on the dev host — `ModuleNotFoundError: No module named 'npyscreen'` via `autopilot/__init__.py`'s unconditional import chain. Identical finding to Phase 18 and Phase 23, reproduced by inspection this session (same `__init__.py` still in place). Anything touching the real `OpenEphys`/`ExternalHardware` class is therefore USER-RUN unless kept behind a fake. |
| Framework (React) | vitest/`node --test` per existing precedent (`detectorOptions.mts`), if any pure-TS logic is extracted (e.g. folder-template token validation) |
| Quick run command (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k openephys` (new tests, once written) |
| Quick run command (Pi, agent-runnable, fakes only) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_openephys_client.py` (proposed — pure REST-shape logic, no `autopilot` import) |
| Full suite command (backend) | `docker compose exec api python -m pytest -q` |
| Full suite command (Pi) | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |

### Design-for-testability requirement

Following Phase 18's own established split: keep the OE REST call construction (URL building,
payload shapes, mode-transition decision logic, "already recording" detection, folder-token
resolution/validation) in **`autopilot`-free** functions/classes on the Pi side — either a sibling
module (`openephys_client.py`, mirroring the backend module's name deliberately) imported by the
`OpenEphys` class, or plain functions inside `openephys.py` that do not import `Hardware`/
`ExternalHardware` at module scope. This is what makes the REST-shape logic agent-testable at all;
the `ExternalHardware`-coupled glue (constructor, `.bind()`, egress wiring) stays USER-RUN, exactly
as Phase 18 already established for its own wire/runtime split.

### Per-subsystem validation strategy

#### 1. OE REST client (URL/payload construction, mode decisions)
- **(A) Fully agent-verifiable, no live OE needed.** Both the Pi-side (`openephys_client.py`,
  `autopilot`-free) and the backend-side (`api/openephys_client.py`) modules are pure functions over
  `httpx`/`requests` — mock the HTTP layer (a fake `requests.put`/`httpx.put`, or `responses`/
  `respx`-style interception) and assert:
  - `test_set_mode_builds_correct_url_and_payload`: `set_mode(host, port, "RECORD")` issues `PUT
    http://{host}:{port}/api/status` with body `{"mode": "RECORD"}`.
  - `test_already_recording_detected_before_start`: a faked `GET /api/status` returning
    `{"mode": "RECORD"}` causes `on_run_start`'s decision logic to return "refuse" without ever
    calling `PUT /api/status`.
  - `test_recording_config_payload_only_includes_locked_fields`: the config PUT body only ever
    contains `parent_directory`/`base_text`/`prepend_text`/`append_text`/`default_record_engine`/
    `start_new_directory` — never an invented field.
  - `test_send_marker_payload_shape`: `send_marker("reward", run=123, trial=45)` builds
    `{"text": "reward|run=123|trial=45"}` for `PUT /api/message`.
  Run via `docker compose exec api python -m pytest -q` (backend) and
  `cd ~/pi-mirror && python3 -m pytest -q tests/test_openephys_client.py` (Pi, `autopilot`-free).
- **(B) USER-RUN, single checkpoint:** every field name/endpoint path claimed in this document is
  sourced from official docs fetched via WebFetch this session, not Context7 or a live probe against
  the lab's actual OE instance/version. The single most valuable rig action for this phase is a raw
  `curl` (or the smoke script) round-trip against the real OE box confirming: `GET /api/status`
  shape, `GET`/`PUT /api/recording` field names, and the literal on-disk directory-naming convention
  (Open Questions 2 and 3) — ideally done BEFORE the plan finalizes path-construction code, not after.

#### 2. Folder-template token resolution + collision check
- **(A) Fully agent-verifiable, backend-only, no rig.** Token substitution
  (`{project}`/`{experiment}`/`{subject}`/`{session}`/`{run}`/`{date}` → literal strings) and
  unknown-token rejection are pure string/dict logic against a fixture DB:
  - `test_resolve_folder_template_all_tokens`: seed a `Subject`/`Project`/`SubjectProject`/
    `Experiment`/`ExperimentProtocol`/`SubjectProtocolRun`/`session_runs` fixture chain, assert the
    resolver produces the expected literal path.
  - `test_resolve_folder_template_rejects_unknown_token`: a template containing `{bogus}` is
    rejected at save time with a 422 naming the offending token (CONTEXT-locked behavior).
  - `test_resolve_folder_template_ambiguous_project_picks_deterministically`: a subject in two
    projects resolves to the lower-id project (or whatever rule is chosen) and does NOT raise —
    proves Open Question 1's "pick one, don't crash" resolution.
  - `test_collision_check_blocks_duplicate_resolved_path`: inserting a `device_recordings` row with
    a given `resolved_path`, then attempting to resolve the SAME path for a different `run_id`,
    surfaces the collision preflight issue rather than silently overwriting.
  Run via `docker compose exec api python -m pytest -q api/tests/test_openephys_folder_resolution.py`
  (new file).
- **(B) USER-RUN:** whether the resolved path, once sent to OE, actually avoids collision with a
  folder a human created by hand via the OE GUI (the accepted residual gap from Pitfall 2) — not
  meaningfully fakeable, and explicitly accepted as a documented limitation rather than a test target.

#### 3. Marker send (egress-queued, dual-logged)
- **(A) Agent-verifiable once Phase 18's `EgressWorker` exists, using a fake `_egress`/
  `event_dispatcher` exactly per Phase 18's own pattern** (`test_extlink_egress.py`'s shape):
  - `test_send_marker_enqueues_not_blocks`: call `send_marker()` with a `_egress.enqueue` fake that
    records calls but never executes them; assert the call returns immediately and the exact payload
    string was enqueued.
  - `test_send_marker_logged_via_log_action`: assert `@log_action`'s dispatch fires synchronously
    (label/run/trial captured) regardless of whether the enqueued HTTP call ever succeeds — proving
    the "positive record of what MICS sent" survives even a total network failure.
- **(B) USER-RUN, folded into the same Phase 18 rig checkpoint (do not schedule a second rig visit):**
  a marker sent for real actually appears inside a real OE recording, confirming the dual-log
  actually diffs against ground truth — this IS explicitly Phase 28's job, not Phase 26's, per the
  CONTEXT ("that diff is precisely Phase 28's TTL-vs-network measurement"). Phase 26 only needs to
  prove the marker was *sent and logged*, not that it landed — the landing proof is deliberately
  deferred.

#### 4. Preflight issue kinds (OE-unreachable, device-held)
- **(A) Fully agent-verifiable, no Pi, no live OE — same pattern Phase 18 already designed for its
  own `device_held` kind and Phase 23 already used for its four compute issue kinds.**
  `api/tests/test_toolkit_dispatch.py` (existing file) gains:
  - `test_openephys_unreachable_issue`: a faked/mocked `openephys_client.get_status` raising a
    connection error surfaces an `openephys_unreachable` (or similarly-named) issue, not an
    unhandled 500 — preflight's existing non-blocking `try/except` posture (steps 8-10 in the
    current file) is the precedent to follow for step 11+.
  - `test_openephys_already_recording_issue`: a faked `get_status` returning `{"mode": "RECORD"}`
    at preflight time (before any run starts) surfaces the same-shaped issue preflight would need if
    checking proactively — separate from EPHYS-01's own runtime refusal, this is the pre-run warning
    a researcher sees before the animal is in the box.
  Both new kinds must be added to `PREFLIGHT_ISSUE_KINDS` (currently 9 entries, verified this
  session) and mirrored into `HardwareCheckModal.tsx`'s `PreflightIssue` union — the exact two-file
  edit Phase 18's `device_held` and Phase 23's compute kinds already established as mandatory.
- **(B) NOT independently rig-only** — this subsystem is backend-only and fully agent-verifiable
  with a mocked OE client; no rig checkpoint is needed for the preflight issue plumbing itself (only
  for confirming the underlying `get_status` call shape, covered in subsystem 1).

### What is genuinely NOT verifiable before the rig (single consolidated checkpoint)

Consistent with Phase 18's own posture — everything below requires either a live OE HTTP server, the
real Pi process's `ExternalHardware`/egress machinery, or ground truth about a real recording:

1. The exact OE REST field names/behavior this document sourced from official docs but did not (and
   could not, from this environment) verify against a live instance — Open Questions 2 and 3.
2. Full `on_run_start`/`on_run_stop` firing through the real `pilot.py::run_task` teardown chokepoint
   with a real OE box on the other end (mirrors Phase 18's own rig-only item #4).
3. A marker actually landing inside a real OE recording (deliberately deferred to Phase 28, not a
   Phase 26 acceptance criterion).
4. Backend safety-net force-stop actually reaching a real OE box from a genuinely crashed pilot (the
   Phase 18 rig-only item #7's mirror image, now carrying an actual device command instead of just a
   lease release).
5. Whether `experiment_number`/`recording_number` reset predictably across MICS-driven runs (Open
   Question 2) — cannot be answered from documentation alone.

Fold all five into ONE consolidated `<verify>` checklist at the end of Phase 26's plan, per the Pi
operational rules and Phase 18's own established practice — do not schedule multiple separate rig
visits for this phase.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EPHYS-01 | `set_mode`/`get_status` URL+payload shape, already-recording refusal | unit (backend + Pi, agent-runnable, mocked HTTP) | `docker compose exec api python -m pytest -q api/tests/test_openephys_client.py` | ❌ new |
| EPHYS-02 | Folder-template token resolution, unknown-token rejection, ambiguous-project pick | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_openephys_folder_resolution.py` | ❌ new |
| EPHYS-03 | `device_recordings` migration idempotency, resolved-path persistence round-trip | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_db_migrations.py -k openephys` | ❌ new/extend (confirm exact migration test filename via `grep -rl run_hardware_lib_kind_migration api/tests/` first) |
| EPHYS-04 | Marker enqueue-not-block, `@log_action` fires regardless of send outcome | unit (Pi, fakes, agent-runnable once Phase 18 lands) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_openephys_markers.py` | ❌ new, depends on Phase 18 |
| EPHYS-05 | OE-unreachable / already-recording preflight issue kinds | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k openephys` | ❌ extend existing file |

### Sampling Rate
- **Per task commit:** the specific new test file touched (all backend tests run inside docker
  compose without a rebuild needed for logic-only files that ARE bind-mounted — confirm bind-mount
  status for `api/` before assuming a rebuild is unnecessary, since Phase 23's own summaries note the
  `api` service has **no bind mount** and needs `docker compose up --build api` before new test files
  are visible).
- **Per wave merge:** `docker compose exec api python -m pytest -q` (full backend suite); every new
  `autopilot`-free Pi test file as a batch.
- **Phase gate:** full backend suite green, all agent-runnable Pi-mirror tests green, PLUS the single
  consolidated rig checkpoint above confirmed by the user before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `api/tests/test_openephys_client.py` — new, covers EPHYS-01 REST shape + already-recording
      refusal, mocked HTTP.
- [ ] `api/tests/test_openephys_folder_resolution.py` — new, covers EPHYS-02 token resolution +
      collision + ambiguous-project handling.
- [ ] Extend the existing DB-migration test file (confirm exact name via
      `grep -rl run_hardware_lib_kind_migration api/tests/` before creating a duplicate) — covers
      EPHYS-03's new-table migration idempotency.
- [ ] `~/pi-mirror/tests/test_openephys_markers.py` — new, `autopilot`-free (fakes only), covers
      EPHYS-04. **Depends on Phase 18's `EgressWorker`/`ExternalHardware` existing** — if Phase 18
      has not shipped by Phase 26 plan time, this file tests the marker-payload-construction logic
      only, deferring the enqueue-integration assertions.
- [ ] Extend `api/tests/test_toolkit_dispatch.py` — two new preflight issue kinds, covers EPHYS-05.
- [ ] Extend `PREFLIGHT_ISSUE_KINDS` (`toolkit_dispatch.py`) and `HardwareCheckModal.tsx`'s
      `PreflightIssue` union — both required together, per the established two-file rule.
- [ ] Confirm whether `docker compose exec api` sees new test files without a rebuild, or whether
      `docker compose up --build api` is required first (Phase 23's own summaries suggest the latter
      — re-verify at plan time, don't assume).

## Sources

### Primary (HIGH confidence — direct code reads, this session)
- `api/seed_libs/compute_ops.py`, `api/seed_compute.py`, `api/compute_provisioning.py` — full reads,
  the seeded-lib precedent
- `api/db.py` — full read, all 13 migration functions including `run_hardware_lib_kind_migration`
- `api/main.py` (lines 1-90, 780-930, 1233-1340) — startup wiring, legacy `/sessions/*` routes,
  `POST /session-runs`
- `api/models.py` (lines 120-330, 380-510) — `Project`/`Experiment`/`ExperimentProtocol`/
  `SubjectProject`/`SessionRun` models
- `api/routers/toolkit_dispatch.py` — full read, current (post-Phase-23) `PREFLIGHT_ISSUE_KINDS` and
  `preflight_validate` including the `subject_protocol_runs` session_id bridge (step 2)
- `api/routers/pilot_hardware_config.py` — full read
- `api/requirements.txt` — confirms `httpx` already present
- `web_ui/app.py` (lines 140-270) — `assign-protocol`, `start-on-pilot` proxy handlers, confirming
  the shared-but-not-FK'd `session_id` bridge between `subject_protocol_runs` and `session_runs`
- `web_ui/react-src/src/api/sessions.ts`, `.../pages/pilot-sessions/SessionCard.tsx` — full reads,
  current React session/run display pattern
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` (lines 1-60) — current `PreflightIssue`
  union, `NON_CONFIG_ISSUES` set
- `.claude/docs/subject_project_experiment_plan.md` — original Project/Experiment design intent,
  confirms the many-to-many joins were a deliberate (if since-unresolved) choice
- `~/pi-mirror/environment.yml` — confirms `requests==2.27.1` already pinned
- `orchestrator/requirements.txt`, `orchestrator/orchestrator/mics/mics_api_client.py` (lines 1-80) —
  confirms orchestrator's existing synchronous-HTTP-to-api pattern
- `orchestrator/orchestrator/orchestrator_station.py` (lines 355-490, 920-995) — `start_run`/
  `stop_run`/`_run_watchdog`/`_redis_touch`, re-confirming Phase 18's own findings hold unchanged
- `.planning/phases/18-extlink-pi-transport/18-CONTEXT.md`, `18-RESEARCH.md` (full), `18-05-PLAN.md`,
  `18-10-PLAN.md` — the substrate this phase consumes; `18-RESEARCH.md`'s Validation Architecture is
  the direct template for this document's own
- `.planning/REQUIREMENTS.md` (EPHYS-01–12, EXTLINK-01–18), `.planning/ROADMAP.md` (Phase 26-28
  entries + "MICS-Link consumers" preamble), `.planning/STATE.md` (Phase 18/23/26 status sections)
- `docs/open_ephys_integration.md` — the source doc for this arc

### Secondary (MEDIUM confidence)
- Open Ephys official docs, `https://open-ephys.github.io/gui-docs/User-Manual/Remote-control.html`
  — fetched via WebFetch this session (no Context7 library exists for Open Ephys). Gives the
  `/api/status`, `/api/recording`, `/api/message` shapes quoted in this document. No GUI version
  number was surfaced by the fetch; field names should be reconfirmed against the lab's actual OE
  version at the rig checkpoint.
- Community/third-party sources (DataJoint docs, Moser lab pipeline docs) on `experiment_number`/
  `recording_number` semantics and the `Record_Node_###/experiment1/recording1` directory shape —
  cross-referenced across two independent sources, consistent with each other, but NOT official Open
  Ephys documentation. Flagged explicitly wherever used (Open Questions 2, 3).

### Tertiary (LOW confidence)
- WebSearch summaries that could not locate a documented disk-space/free-space endpoint — this is a
  negative claim; treated per this project's verification protocol as "not found after a real search
  across official docs and GitHub," not as a training-data assumption, but it remains unverifiable
  from this environment. Recommend a direct rig confirmation before finalizing the "drop the disk
  check" decision, even though the current evidence supports dropping it.

## Metadata

**Confidence breakdown:**
- Standard stack (httpx/requests already present, no new deps): HIGH — verified by reading
  `requirements.txt`/`environment.yml` directly.
- OE REST API surface: MEDIUM — official docs fetched and cross-checked internally for consistency,
  but no Context7 source exists and no live probe against the lab's actual instance was possible from
  this environment; several fields (directory-naming convention, counter-reset behavior) are
  genuinely undocumented and flagged as Open Questions requiring a rig check.
- Internal data-model resolution (project/experiment/subject from a run_id): HIGH confidence that the
  ambiguity is real (verified by reading every relevant model and the one existing bridge query) —
  MEDIUM confidence on the recommended resolution rule itself, since it is a new design choice this
  document proposes rather than one already locked by CONTEXT.md.
- Seeded-lib/migration/preflight patterns: HIGH — all read in full, directly copyable.
- Validation Architecture: HIGH for the agent-verifiable split (mirrors Phase 18's own proven split);
  the marker/egress subsystem's (A) tier is contingent on Phase 18 actually shipping the classes it
  fakes against, flagged explicitly.

**Research date:** 2026-08-03
**Valid until:** 30 days for the internal-codebase findings (stable until Phase 18 lands and changes
the ground truth this document assumes); re-verify the OE REST API findings at plan time regardless
of elapsed time, since they were never confirmed against a live instance from this environment.
