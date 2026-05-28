---
phase: 14-bug-backlog
plan: "01"
subsystem: ui
tags: [react, react-query, sessions, api, ordering]

# Dependency graph
requires: []
provides:
  - PilotSessions page always fetches fresh session list on mount
  - SubjectSessions session ordering is deterministic regardless of DB storage order
affects: [pilot-sessions, subject-sessions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use refetchOnMount: 'always' for queries that must reflect server state on navigation"
    - "Add ORDER BY to API endpoints whose callers depend on ordered results"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/pages/pilot-sessions/PilotSessions.tsx
    - api/main.py

key-decisions:
  - "refetchOnMount: 'always' preferred over cache invalidation — simpler, no cross-page coordination needed"
  - "ORDER BY session_id ASC in API to make SubjectSessions .reverse() deterministic at DB level"

patterns-established: []

requirements-completed: [BUG-02]

# Metrics
duration: 1min
completed: 2026-05-28
---

# Phase 14 Plan 1: Small Bug Fixes Backlog (Batch 1) Summary

**PilotSessions now always fetches fresh session list on mount via `refetchOnMount: 'always'`; SubjectSessions ordering made deterministic via `ORDER BY session_id ASC` in the API**

## Performance

- **Duration:** 1 min
- **Started:** 2026-05-28T08:52:10Z
- **Completed:** 2026-05-28T08:52:51Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Fixed stale React Query cache causing PilotSessions to skip the newest session on re-navigation
- Fixed non-deterministic ordering in `/subjects/{name}/runs` API endpoint so `.reverse()` in SubjectSessions always yields newest-first

## Task Commits

Each task was committed atomically:

1. **BUG-02: PilotSessions stale cache + API ordering fix** - `90c8d77` (fix)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `web_ui/react-src/src/pages/pilot-sessions/PilotSessions.tsx` - Added `refetchOnMount: 'always'` to sessions query
- `api/main.py` - Added `.order_by(SubjectProtocolRun.session_id.asc())` to `/subjects/{name}/runs` endpoint

## Decisions Made
- Used `refetchOnMount: 'always'` rather than cache invalidation from other pages — simpler, no cross-page coordination, and PilotSessions is a full navigation destination where fresh data is always desired
- ORDER BY added at DB level so the sort is deterministic regardless of VACUUM/replica behavior

## Deviations from Plan

None - plan executed exactly as written. Applied both Step 2A (React cache fix) and Step 2B (API ordering fix) as specified.

## Issues Encountered
None - both changes were straightforward and the build succeeded immediately.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BUG-02 fully resolved; PilotSessions will always show the latest session
- Phase 14 batch ready for any additional bug entries (see plan template at bottom of 14-01-PLAN.md)

---
*Phase: 14-bug-backlog*
*Completed: 2026-05-28*
