---
phase: 14-bug-backlog
plan: 14-01
verified: 2026-05-28T00:00:00Z
status: passed
score: 2/2 must-haves verified
requirements: [BUG-02]
---

# Phase 14 Plan 1: BUG-02 Verification Report

**Phase Goal:** Fix missing latest session in PilotSessions UI (BUG-02)
**Plan:** 14-01 (Small Bug Fixes Backlog, Batch 1)
**Verified:** 2026-05-28
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PilotSessions page always fetches a fresh session list when the component mounts | VERIFIED | `PilotSessions.tsx` line 33: `refetchOnMount: 'always'` present in the `useQuery` call for `['sessions']`. Stale cache from prior navigations is bypassed on every mount. |
| 2 | The `/subjects/{name}/runs` API endpoint returns runs in deterministic ascending session_id order so that SubjectSessions `.reverse()` always yields newest-first | VERIFIED | `api/main.py` lines 191–195: `select(SubjectProtocolRun).where(...).order_by(SubjectProtocolRun.session_id.asc())` — ORDER BY clause is present and correct. |

**Score:** 2/2 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `web_ui/react-src/src/pages/pilot-sessions/PilotSessions.tsx` | Contains `refetchOnMount: 'always'` on sessions query | VERIFIED | Line 33 confirms it. The query also uses `queryKey: ['sessions']` and `queryFn: getSessions`. No stubs or placeholders in the implementation. |
| `api/main.py` (subjects/runs endpoint, ~line 191) | `.order_by(SubjectProtocolRun.session_id.asc())` | VERIFIED | Lines 191–195 show the full `session.exec(select(...).where(...).order_by(...)).all()` chain. ORDER BY was not present before this fix; it is now. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `PilotSessions.tsx` mount | fresh `GET /api/sessions` request | `refetchOnMount: 'always'` in `useQuery` | WIRED | React Query will issue a fresh fetch on every mount, bypassing the stale cache. The response is bound to `sessions` and drives the rendered card list. |
| `GET /subjects/{name}/runs` | ordered `SubjectProtocolRun` rows | `.order_by(SubjectProtocolRun.session_id.asc())` | WIRED | The SQLModel `select` adds ORDER BY at query time. `SubjectSessions.tsx` calls `.reverse()` on the returned array, yielding newest-first regardless of DB storage or vacuum order. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BUG-02 | 14-01 | PilotSessions list does not show the most recently created session | SATISFIED | Both root causes fixed: React cache bypassed via `refetchOnMount: 'always'`; API ordering made deterministic via `ORDER BY session_id ASC`. REQUIREMENTS.md line 241 marks BUG-01 through BUG-02 as Complete. |

---

### Anti-Patterns Found

None. The only string "placeholder" in `PilotSessions.tsx` appears on line 137 as an HTML `<input placeholder="Filter by subject…">` attribute — a legitimate UI label, not an implementation stub. No TODOs, FIXMEs, or empty handlers in either modified file.

---

### Human Verification Required

#### 1. End-to-end session visibility after navigation

**Test:** Open PilotSessions for any pilot. Note the topmost session ID. Navigate away (e.g., to the pilot grid). Create a new session from the subject-sessions page. Navigate back to PilotSessions.
**Expected:** The newly created session (higher session_id) appears at the top of the list immediately on mount — no manual refresh needed.
**Why human:** Verifying React Query cache bypass behavior requires a live browser session; static analysis can only confirm the option is set.

---

### Gaps Summary

No gaps. Both fixes are substantive and wired:

- `refetchOnMount: 'always'` is correctly placed on the `['sessions']` query in `PilotSessions.tsx` line 33.
- `ORDER BY session_id ASC` is correctly added at `api/main.py` lines 191–195 in the `/subjects/{name}/runs` endpoint.

BUG-02 is fully resolved at the code level.

---

_Verified: 2026-05-28_
_Verifier: Claude (gsd-verifier)_
