---
phase: 14-bug-backlog
plan: "03"
subsystem: ui
tags: [react, typescript, fastapi, proxy, wizard, ux]

requires:
  - phase: 11-06-toolkit-creation-modal
    provides: CreationModal.tsx wizard with hw-lib step and proxy routes in app.py

provides:
  - Streamlined toolkit creation wizard (5 steps with file, 4 without)
  - Automatic hw-lib linking on toolkit creation (stable version fallback to active)
  - Proxy routes for POST/GET /api/toolkits/{id}/hardware-libs (BUG-07 fixed)

affects: [toolkits, hardware-libs, creation-workflow]

tech-stack:
  added: []
  patterns:
    - "Step-skip navigation: handleNext/handleBack check state to jump over irrelevant steps"
    - "Auto-link pattern: onSuccess loops over all items and links them with default version"

key-files:
  created: []
  modified:
    - web_ui/app.py
    - web_ui/react-src/src/pages/toolkits/CreationModal.tsx

key-decisions:
  - "BUG-07: add explicit proxy routes with /api/ prefix — catch-all strips prefix when forwarding, causing 404 on toolkit/{id}/hardware-libs"
  - "BUG-06: auto-link all libs unconditionally in onSuccess rather than letting user pick — version pinning is per task-definition, not per toolkit"
  - "BUG-05: skip step 2 (locked-states) entirely when no file selected, jump 1→3 on Next and 3→1 on Back"

requirements-completed: [BUG-05, BUG-06, BUG-07]

duration: 12min
completed: 2026-05-27
---

# Phase 14, Plan 3: Toolkit Creation Modal UX Fixes Summary

**Removed dead hw-lib selection step, auto-skip locked-states when no file, and fixed proxy 404 for toolkit/hardware-libs routes**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-27T08:30:00Z
- **Completed:** 2026-05-27T08:42:00Z
- **Tasks:** 2 (BUG-07 proxy fix; BUG-05 + BUG-06 modal rewrite)
- **Files modified:** 2

## Accomplishments

- Fixed 404 on `POST /api/toolkits/{id}/hardware-libs` by adding explicit proxy routes with the `/api/` prefix that the catch-all drops
- Removed step 3 (manual hw-lib selection) from the creation wizard; all libs auto-linked in `onSuccess` using stable_version_id falling back to active_version_id
- Eliminated the dead "no file selected" step 2 screen: Next from step 1 with no file jumps directly to step 3 (hw-modules); Back from step 3 returns to step 1
- Step counter header now shows correct visible step and total (4 when no file, 5 when file selected)

## Task Commits

1. **BUG-07: proxy routes for toolkit hw-libs** - `fc1451f` (fix)
2. **BUG-05 + BUG-06: modal step removal and auto-link** - `7d80ff6` (fix)

## Files Created/Modified

- `web_ui/app.py` — added `proxy_toolkit_hw_libs` (GET/POST) and `proxy_toolkit_hw_lib_item` (GET/DELETE) routes before the catch-all
- `web_ui/react-src/src/pages/toolkits/CreationModal.tsx` — removed step 3, renumbered steps 4→3/5→4/6→5, added handleNext/handleBack skip logic, replaced selectedLibVersions loop with auto-link in onSuccess, removed listVersions import and HardwareLibVersion type

## Decisions Made

- The catch-all proxy in `app.py` (`/api/{path:path}`) forwards to `{API_URL}/{path}` — it strips the `/api/` prefix, so any toolkit sub-resource route that doesn't have an explicit proxy entry gets forwarded to the wrong URL. Adding explicit routes is the right fix rather than changing the catch-all behavior (that would break everything else).
- Step 2 content when `!selectedFile` was a dead screen (just an info message, nothing interactive). Removing the entire branch when no file is selected is cleaner than keeping the dead path.
- Auto-linking all libs is correct: version pinning granularity is per-task-definition (done in the FDA editor), not per-toolkit. Having the user manually pick libs at creation time adds friction with no benefit.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — build passed on first attempt.

## Next Phase Readiness

- Toolkit creation flow is cleaner and the proxy gap is closed
- Hardware lib auto-linking on toolkit creation is wired end-to-end
- BUG-05, BUG-06, BUG-07 requirements fulfilled

---
*Phase: 14-bug-backlog*
*Completed: 2026-05-27*
