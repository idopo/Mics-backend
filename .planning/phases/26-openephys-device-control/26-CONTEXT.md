# Phase 26: OpenEphys Device Control — Context

**Gathered:** 2026-08-03
**Status:** Ready for planning
**Source doc:** `docs/open_ephys_integration.pdf` (+ `.md` twin)

<domain>
## Phase Boundary

A MICS session starts and stops an Open Ephys recording by itself, names the save folder per
project/experiment/subject, writes labelled event markers into the recording mid-task, and records
the resulting path back into MICS — so a researcher never touches the Open Ephys GUI and the system
knows where its own ephys data landed.

**Control only.** No neural data reaches the task in this phase — firing rate over ZMQ is Phase 27,
TTL-vs-network validation is Phase 28.

**This phase is the first consumer of the Phase 18 `ExternalHardware` substrate.** It adds no new
transport, no new dispatch shape, and no new action vocabulary.

</domain>

<decisions>
## Implementation Decisions

### Carried forward from Phase 18 — LOCKED, do not re-litigate
See `18-CONTEXT.md`. Restated here only because this phase depends on them:
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

### Save-folder naming
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

### What MICS records about each recording
- **Fields:** the **resolved absolute path** as computed at run start, OE record-start and
  record-stop timestamps, and which OE host wrote it.
- **Storage: a small dedicated table keyed on `(run_id, device_name)`.** Chosen over new columns on
  `session_runs` because DeepLabCut — already on the roadmap — will need to record video paths the
  same way; columns don't scale past the first device. Chosen over stuffing it in
  `session_runs.overrides` because that column means *session parameter overrides*; output artifacts
  there would be semantically wrong and unqueryable without JSON operators.
- **Snapshot the project and experiment names** used to build the path, alongside the path. Two
  extra fields; closes the rename risk completely. Without it a folder name that disagrees with
  current metadata is unexplainable — nobody can tell a rename from a bug.
- **Coverage flag:** mark the recording **incomplete** when OE was not recording for the run's full
  duration, so analysis can filter partial sessions with a query instead of discovering them by eye.
- **Visibility: API + surfaced on the existing React session/run view.** A path that lives only in
  the database is a path someone ends up asking a human to look up — which is the manual step this
  phase exists to remove.

### Event markers
- **MICS always emits run-start and run-stop markers**, bracketing the recording. Everything else is
  explicit — placed by the FDA author in a state body or trigger action.
  - **Rejected: automatic trial markers.** They would couple the ephys path to `INC_TRIAL_COUNTER`,
    which this project requires tasks to send explicitly — so a task that doesn't send it would
    silently produce no trial markers, presenting as an ephys bug rather than a task bug.
- **Labels are free text, with autocomplete** offering labels already used in the same toolkit.
  Keeps authoring frictionless while stopping `reward` / `Reward` / `rewrd` drift, which is what
  silently fragments an analysis. Not a constrained per-toolkit declared list — that adds a
  maintenance surface and blocks a researcher mid-experiment.
- **Marker payload carries run/trial context**, e.g. `reward|run=123|trial=45`. Costs nothing (the
  REST call takes a string regardless) and makes each marker self-describing inside the recording —
  the exact advantage the integration doc claims over anonymous TTL pulses. It also keeps a
  recording interpretable if separated from MICS.
- **Every marker send is dual-logged to ES.** This yields a positive record of what MICS *sent*,
  which diffs against what actually landed in the recording. **That diff is precisely Phase 28's
  TTL-vs-network measurement**, so this makes the validation phase nearly free — and it is the only
  way to distinguish "marker never sent" from "marker sent but never arrived".

### Bad-state handling
- **OE already RECORDING at run start → fail the readiness gate. Never take over.** The lease only
  knows about MICS-initiated runs; it cannot see someone using the OE GUI by hand, so "already
  recording" may be a colleague's session. Refusing is recoverable; taking over destroys data with
  no warning. Rejected: force-to-IDLE-and-restart, and attach-to-existing (the latter breaks the
  path-persistence guarantee — data lands somewhere MICS didn't choose or record).
- **Disk-space precheck: yes, if the OE REST API exposes free space** — block below a configurable
  threshold during the readiness gate. **Research must confirm the API actually reports it**; if it
  does not, drop the check rather than inventing one. Rationale: a session dying 40 minutes in
  because the disk filled is the most expensive failure mode here — the animal's time is
  unrecoverable.
- **Recording stops mid-run → log, flip `alive`, and surface prominently in pilot status.**
  Consistent with the Phase 18 mid-run policy (don't kill a behavioural session over an accessory),
  but loud rather than log-only, so a mid-run failure isn't discovered at analysis time. The
  behavioural data stays valid and the researcher decides whether to stop.

### Lib delivery and opt-out
- **The `OpenEphys` lib ships as a seeded first-party lib** — `api/seed_libs/openephys.py`, seeded
  idempotently at API startup as a stable `hardware_libs` row plus an `OPENEPHYS` hardware module,
  following the pattern Phase 23 established for `compute_ops.py`. Ephys works after a deploy with
  no manual upload, while still living in the normal versioning/promotion system so a researcher can
  fork or override it.
- **A researcher can run a session without ephys via a per-run override**, without editing the
  toolkit. Rigs get used for quick behavioural checks and pilot runs where ephys is irrelevant;
  without an escape hatch the readiness gate turns each into a toolkit edit or a forced skip.
  > **Scope note for the planner:** this is the one decision that grows the phase beyond the
  > roadmap's original wording. Keep it minimal — prefer reusing the existing start-on-pilot
  > `overrides` path or the already-locked `required` flag over building a new mechanism.

### Claude's Discretion
- Exact REST call sequence and endpoint shapes against the OE API.
- Table and column names for the recording record.
- Retry cadence for `on_run_start` inside the wait window.
- The token set for the folder template (must at minimum cover project, experiment, subject,
  session, run, date).
- How autocomplete sources prior marker labels (query vs cached).
- Disk-space threshold default.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/seed_libs/compute_ops.py` + `api/seed_compute.py::seed_compute_ops_lib` (Phase 23) — the
  exact precedent for shipping a first-party lib as an idempotently-seeded `hardware_libs` row plus
  a `hardware_modules` row, with auto-provisioned pilot config. Copy this shape for `openephys.py`.
- `api/routers/toolkit_dispatch.py` — `PREFLIGHT_ISSUE_KINDS` frozenset (added by Phase 23 plan 07)
  is now the single registry of preflight issue kinds, with `compute_lib_import_failed_issue()` as
  the reserved-issue-shape precedent. Any new issue kind here (already-recording, disk-low,
  folder-collision) registers there **and** mirrors into `HardwareCheckModal.tsx`'s `PreflightIssue`
  union.
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` — existing preflight issue renderer with
  an inline-fix precedent; where new issues surface.
- Phase 18's `external_hardware.py` / `external_hardware_wire.py` / `external_hardware_runtime.py` —
  the base class, egress worker, and lifecycle runner this phase subclasses. **Do not reimplement
  any of it.**

### Established Patterns
- **Dual ORM:** `session_runs` is SQLAlchemy-owned. The new recording table must use a SQLAlchemy
  session, not SQLModel — mixing causes silent failures (CLAUDE.md).
- **Free-form per-pilot config:** `api/routers/pilot_hardware_config.py:41` stores config as-is and
  delegates validation to the caller — so new keys (folder template, disk threshold) need **no**
  endpoint or schema change. Validation belongs in preflight.
- **Seeded-lib provisioning:** `api/compute_provisioning.py::provision_compute_configs` auto-creates
  the trivial pilot config row a seeded module needs. Same need here.

### Integration Points
- `api/models.py:431` `SessionRun` — `subject_key`, `started_at`, `ended_at`, `session_run_index`,
  `mode`, `overrides` (JSON). The new recording table FKs to `session_runs.id`.
- `api/main.py:1524` `POST /session-runs/{run_id}/stop` — the API-side run-stop chokepoint.
- `orchestrator/orchestrator/orchestrator_station.py:255,401` `start_run` / `stop_run` — orchestrator
  lifecycle, and where the Phase 18 backend safety net hangs.
- `api/routers/toolkit_dispatch.py::preflight_validate` — where reachability, already-recording,
  disk-low, and folder-collision issues are emitted. **Note: 500-line hard limit is close; put logic
  in a new module and call it from here.**
- `web_ui/react-src/src/pages/pilot-sessions/` and `subject-sessions/` — the session views where the
  recording path surfaces.

</code_context>

<specifics>
## Specific Ideas

- Source doc confirms: HTTP REST control on **37497**; `PUT /api/status {"mode":"RECORD"}`; a
  message endpoint for injecting markers into the recording. ZMQ data on **5556** is Phase 27.
- The doc's framing — *"treat Open Ephys as just another piece of hardware in a MICS task"* — is
  exactly the Phase 18 mental model, which is why no new dispatch path is warranted.
- The OE machine is **shared across rigs but never used simultaneously**; the lease is a safety net,
  not a scheduler. No queue/notify UX.
- **The TTL cable stays.** Network markers run alongside it; Phase 28 measures the two and any
  cutover is a later decision on that evidence.

</specifics>

<deferred>
## Deferred Ideas

- **Firing rate / any neural data into the task** — Phase 27 (`sub_connect` + `@decoder`, declared
  units, windowed estimator, `(ts_pi_recv, oe_sample)` sync pairs).
- **TTL-vs-network jitter measurement and any TTL removal** — Phase 28. Phase 26 only makes the
  measurement possible by dual-logging markers.
- **DeepLabCut** — reserved; will reuse the recording-record table and the `sub_connect` role.
- **Device scheduling** (queue, notify-when-free) — explicitly rejected; the lease hard-blocks only.
- **Commanding the foreign device to stop from the backend safety net** — Phase 18 documents this
  residual risk: a crashed pilot can leave OE recording, because the backend has no channel to the
  device. **Phase 26 owns the OE control channel, so closing this is possible here** — but it was
  not discussed and is not in the roadmap's success criteria. Flag to the user before planning it in.
- **Multi-OE-host support** (more than one ephys machine per install) — the lease is keyed on host
  so the model allows it, but nothing in this phase exercises it.

</deferred>

---

*Phase: 26-openephys-device-control*
*Context gathered: 2026-08-03*
