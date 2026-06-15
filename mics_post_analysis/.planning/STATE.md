---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: offline-analysis-toolkit
status: planning_complete
last_updated: "2026-06-15"
progress:
  total_phases: 5
  completed_phases: 1
  total_plans: 4
  completed_plans: 2
  percent: 20
---

# STATE: MICS Offline Analysis Toolkit

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-15)

**Core value:** One unified, clock-aligned events+spikes DataFrame per session — ES events always work alone; ephys/spike layers attach only when a recording exists.
**Current focus:** Phase 1 complete (5/5 criteria). Ready to execute Phase 2 (ElasticClient).

---

## Current Position

**Milestone:** v1.0 — Offline Analysis Toolkit
**Phase:** Phase 1 complete — Phase 2 next
**Progress:** [██░░░░░░░░] 20%

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

---

## Next Action

Execute Phase 2 (Elasticsearch Events Layer):
1. `02-01` — `ElasticClient` → tidy events DataFrame (TDD against live `m74_cue_reward` s4 = ~2137 events)
2. `02-02` — notebook Section 1 (cached events display) after 02-01

Env note: deps in `.pylibs/`; run with `PYTHONPATH=.pylibs:src`. ES-py client is 9.x against ES server 8.10.2 — confirm scroll API compatibility early in 02-01.
