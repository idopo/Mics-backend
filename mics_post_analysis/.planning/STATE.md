---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: offline-analysis-toolkit
status: planning_complete
last_updated: "2026-06-15"
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 40
---

# STATE: MICS Offline Analysis Toolkit

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-15)

**Core value:** One unified, clock-aligned events+spikes DataFrame per session — ES events always work alone; ephys/spike layers attach only when a recording exists.
**Current focus:** Phases 1 & 2 complete (events layer live, 12 tests pass). Phase 3 (Open Ephys) next — needs planning.

---

## Current Position

**Milestone:** v1.0 — Offline Analysis Toolkit
**Phase:** Phase 2 complete — Phase 3 next (not yet planned)
**Progress:** [████░░░░░░] 40%

---

## Decisions Made

| Decision | Made | Rationale |
|---|---|---|
| Clean-slate architecture; legacy = reference only | 2026-06-15 | Legacy is patchy/data-coupled; capture intent, not code |
| ES events always-present base; ephys/spikes optional layers | 2026-06-15 | Not all ES sessions have ephys/spikes; pipeline must degrade gracefully |
| New-portal schema primary, legacy read-compat (one path) | 2026-06-15 | Must read old m74 data and current portal runs |
| `SESSIONS` entry carries explicit `es_subject` (+ optional host/index) | 2026-06-15 | Key can't derive descriptive ES subject; data spans two ES hosts |
| Single-session end-to-end first; multi-subject batch deferred to v2 | 2026-06-15 | Prove the path on m74s4 before generalizing |
| Fixture = m74s4 (`m74_cue_reward` s4), a legacy session | 2026-06-15 | Complete across all three legs; exercises legacy read path |
| DLC alignment deferred to v2 | 2026-06-15 | Legacy flaky; video not guaranteed present |
| Code in mics-backend/mics_post_analysis/; dedicated .planning/ | 2026-06-15 | Keeps backend skills/context; native /gsd:* pinned to backend root |

---

## Open Risks / To Verify During Execution

- ES field names confirmed from live sample: `subject`, `session`, `event.event_type`, `event.event_data`, `pilot`, `timestamp`, `continuous`. Confirm `relative_time`/trigger-reference derivation against legacy `_get_relative_reference_time` logic during Phase 2.
- Secondary ES host `132.77.73.125:9200` holds `restored-event_log_v2` — confirm which subjects require it.
- Large `.xls` spike exports (~192 MB) are slow to parse — pickle is the fast path; validate `.xls`/`.plx` fallback only if a session lacks a pickle.
- Open Ephys reader library choice (e.g. `open-ephys-python-tools`) to be selected in Phase 3.
- **Phase 4 must decide the alignment clock: ingest (`raw_time`) vs precise GPIO (`pi_time`).** Both are kept as independent columns in the events DF (no merged clock — per user direction). `pi_time` is generic (any event reporting `event_data.pi_timestamp`), ~23 ms ahead of ingest; matters for lick/IR-locked PSTHs.

---

## Next Action

Plan + execute Phase 3 (Open Ephys Layer): `EphysRecording` TTL/trigger rising-edge
extraction + visualizer, lazily imported and skippable. Independent of Phase 2.

Env note: real venv at `.venv/` is now the environment (ipykernel registered as the
"MICS Analysis (.venv)" Jupyter kernel). Run tests with `.venv/bin/python -m pytest`.
`elasticsearch` is pinned `<9` (server is 8.10.2). `.pylibs/` is the old --target
hack — safe to delete now that `.venv` exists.
