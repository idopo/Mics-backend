---
phase: 35-deeplabcut-keypoint-likelihood-integration
plan: 04
subsystem: infra
tags: [python, dlclive, mics-link, adapter, cli]

# Dependency graph
requires:
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 01)
    provides: "dlc_link package skeleton, dlc_link.decimate.RECOMMENDED_DEFAULTS (deadband + Hz cap)"
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 03)
    provides: "dlc_link.generate/templates (render_signal_map's exact constant set) and dlc_link.config_read"
provides:
  - "dlc_link.signal_map: load_signal_map / assert_pairs_with / SignalMapError -- the one way to read a generated <source_id>_signals.py"
  - "dlc_link.processor.DLCProcessor: a dlclive-compatible Processor sending declared, normalised, as_scalar-converted signals"
  - "dlc_link.live: run_video_loop / main / compare_pose_order / check_corner_geometry -- the paced video-file loop and dlc-link-live CLI"
  - "dlc_link.live_probe: the D-42 --probe-pose implementation (split out to hold live.py under 300 lines)"
affects: [35-06, 35-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Base-class resolution as a testability seam: `from dlclive import Processor as _Base` falls back to `object` on ImportError, with DLCLIVE_AVAILABLE recording which happened, so the whole adapter unit-tests with no dlclive/cv2/torch/GPU installed"
    - "Heavy imports (cv2, dlclive) deferred inside main()/a lazily-imported companion module, never at module scope, so pure logic (run_video_loop, compare_pose_order, check_corner_geometry) stays testable with fakes"
    - "Split a >300-line CLI module into the required-exports file plus a companion module for one large sub-feature, imported lazily to avoid a circular import -- same shape as plan 35-03's generate.py/generate_cli.py split"

key-files:
  created:
    - dlc_link/src/dlc_link/signal_map.py
    - dlc_link/src/dlc_link/processor.py
    - dlc_link/src/dlc_link/live.py
    - dlc_link/src/dlc_link/live_probe.py
    - dlc_link/tests/test_signal_map.py
    - dlc_link/tests/test_processor.py
    - dlc_link/tests/test_live.py
  modified: []

key-decisions:
  - "signal_map.py cross-checks SIGNAL_NAMES against the names SIGNALS itself declares using dlc_link.names.flat_signal_names (the generator's own flattening helper) rather than re-deriving anything -- this is data-consistency checking, not a bodypart-to-identifier re-derivation, and the file still contains zero occurrences of to_identifier/build_name_map"
  - "live.py split into live.py (run_video_loop/main/compare_pose_order/check_corner_geometry, the plan's required exports) plus live_probe.py (the D-42 --probe-pose implementation) to satisfy the plan's own 300-line cap for live.py; live_probe imports compare_pose_order/check_corner_geometry FROM live.py, and live.py imports live_probe lazily inside main() to avoid a circular import at module-load time"
  - "DLCProcessor computes len(signal_map.POSE_ORDER) exactly once, in __init__, rather than re-invoking len() per frame in process() -- satisfies the row-count guard's 'once per instance, cached' requirement by construction rather than by an explicit flag check on every access"

requirements-completed: [DLC-03, DLC-04, DLC-07, DLC-12, DLC-13]

duration: 70min
completed: 2026-08-31
---

# Phase 35 Plan 04: DeepLabCut Sender-Side Adapter (Processor + Paced Video Loop) Summary

**Built the sender-side adapter DLC-07 requires: a dlclive-compatible `DLCProcessor` that turns a pose array into declared, normalised mics-link signals, and a paced video-file loop (`dlc-link-live`) that IS the live camera pipeline with a file substituted in — including the D-42 corner-geometry probe that catches a same-length pose-row reordering no count check can see.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-08-31T12:00Z (approx)
- **Completed:** 2026-08-31T13:10Z
- **Tasks:** 3/3 completed
- **Files modified:** 7 created, 0 modified

## Accomplishments
- `dlc_link.signal_map.load_signal_map` imports a generated `<source_id>_signals.py` by filesystem path, validating every required constant, `SIGNALS` shape, index uniqueness/type, and `SIGNAL_NAMES` consistency — refusing a hand-edited or corrupted map loudly, never partially trusting it. `assert_pairs_with` proves a map and a deployed lib came from the same generator invocation.
- `dlc_link.processor.DLCProcessor` is a real `dlclive.Processor` subclass (or a plain `object` when `dlclive` is absent) that sends every declared bodypart's likelihood first, then its normalised x/y coordinates, through `mics_link.values.as_scalar` — never a bare numeric coercion. It refuses a 3-D pose (naming `single_animal=True` and `stitch_tracklets` explicitly) and a POSE_ORDER length mismatch (naming both numbers, plus plan 35-07's probe when the order is unverified), both checked once per instance rather than per frame.
- `dlc_link.live.run_video_loop` paces inference at the video's native fps via `mics_link.timing.Pacer`, never touches `link` directly, and returns a counts-only record — the docstring/comment states verbatim that dropping the `pacer.wait_until(...)` line is the entire swap to a live camera (D-29).
- `dlc_link.live.check_corner_geometry` is a pure function asserting the four arena corners (`NW`/`NE`/`SE`/`SW`) land in their own quadrants with a confidence floor — a low-likelihood corner returns `UNRELIABLE`, never a false `PASS` — catching the "worst failure available" (a same-length pose-row reordering) that no count check can see. `dlc_link.live_probe.run_probe_pose` (D-42's `--probe-pose`) drives it against a real `DLCLive` construction without ever connecting to the Pi.
- `dlc-link-live` writes NOTHING by default (D-47): `DLCLive(..., display=False)` is pinned explicitly at every call site with a comment naming D-47; two tests drive `--dry-run` and `--probe-pose` with an empty temporary directory as the current working directory and assert it stays empty, using fake `cv2`/`dlclive` modules injected via `sys.modules` so the assertion holds with neither library installed.
- 141 tests total in `dlc_link` (90 from plans 01/03 + 8 signal_map + 16 processor + 27 live/live_probe), all green, `dlclive`/`torch`/`cv2`/`pandas` all absent from the dev host (verified: all three raise `ModuleNotFoundError` when imported directly).

## Task Commits

Each task was committed atomically:

1. **Task 1: Load the generated signal map and prove it pairs with the deployed lib** - `4835db8` (feat)
2. **Task 2: DLCProcessor, the dlclive-compatible callback** - `4c03e21` (feat)
3. **Task 3: The paced video-file loop and the dlc-link-live CLI** - `f86475b` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `dlc_link/src/dlc_link/signal_map.py` - `load_signal_map`, `assert_pairs_with`, `SignalMapError`, `SignalMapRecord`
- `dlc_link/src/dlc_link/processor.py` - `DLCProcessor`, `PoseShapeError`, `DLCLIVE_AVAILABLE`
- `dlc_link/src/dlc_link/live.py` - `run_video_loop`, `main`, `compare_pose_order`, `check_corner_geometry`, `_build_parser`, `_DiscardingLink`
- `dlc_link/src/dlc_link/live_probe.py` - `run_probe_pose`, `_discover_pose_order`, `_median_corner_measurements` (the D-42 `--probe-pose` implementation, split out of `live.py`)
- `dlc_link/tests/test_signal_map.py` - 8 tests: round-trip, corrupted `SIGNAL_NAMES`, duplicated index, missing constant, non-dict `SIGNALS`, unparseable file, `assert_pairs_with` pass/raise, no-re-derivation check
- `dlc_link/tests/test_processor.py` - 16 tests: likelihood-first order, resolution-independent normalisation, `as_scalar` type proof (numpy + plain list), 3-D guard, row-count guard (both messages, cached-once proof), identity-preserving return, drop/suppress/reject counting, out-of-frame unclamped, `save()` no-op, snapshot vocabulary
- `dlc_link/tests/test_live.py` - 27 tests: `run_video_loop` pacing/ordering/max_frames/never-closes, `compare_pose_order`'s three outcomes, `check_corner_geometry`'s four verdicts plus the sub-margin boundary, median-not-mean-or-last aggregation, static source assertions (`model_type`, no `tensorrt`/`lite`, no write sites, no latency vocabulary, D-47 `display=False` pin), D-47 empty-directory proof for `--dry-run` and `--probe-pose` via faked `cv2`/`dlclive` modules

## Decisions Made
- **`signal_map.py` reuses `dlc_link.names.flat_signal_names` for the `SIGNAL_NAMES`-vs-`SIGNALS` consistency check** rather than hand-rolling a second flattening: this is comparing two data structures the generator already produced, not deriving a name from a bodypart string, so it does not violate the "one declaration site" rule the task's own automated grep (`to_identifier|build_name_map` count 0) enforces — verified.
- **`live.py` split into `live.py` + `live_probe.py`**: the full `--probe-pose` implementation (corner-geometry orchestration, pose-order discovery, per-frame collection) would have pushed `live.py` to ~407 lines, over the plan's own stated "under 300 lines" acceptance criterion. Split the D-42 probe into `dlc_link/live_probe.py`, which imports `compare_pose_order`/`check_corner_geometry` FROM `live.py` (the pure verdict logic keeps exactly one home); `live.py`'s `main()` imports `live_probe` lazily, inside the `--probe-pose` branch, to avoid a circular import at module-load time. This mirrors plan 35-03's `generate.py`/`generate_cli.py` split, documented there for the identical reason (Rule 1/3 — the plan's own acceptance criteria would otherwise conflict with its own required content). `live.py` is 289 lines; `live_probe.py` is 134.
- **`DLCProcessor` caches `len(signal_map.POSE_ORDER)` at construction**, not behind a per-call length check with a separate flag re-derivation — `self._expected_row_count = len(signal_map.POSE_ORDER)` runs exactly once in `__init__`, and `process()` compares the cached int on its first call only. A test wraps `POSE_ORDER` in a length-counting list subclass and asserts `len()` was invoked exactly once across five `process()` calls, proving the cache rather than merely asserting no exception was raised.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The `live camera` literal-comment requirement was defeated by a mid-word line wrap**
- **Found during:** Task 3, writing the swap-comment test
- **Issue:** The plan requires `live.py` to carry, verbatim, a comment stating that dropping the `wait_until` line is the one-line swap to a live camera. My first draft wrapped the comment across two lines such that the words `live` and `camera` landed on different lines (`...swap in a live\n    # camera later...`), so the contiguous substring `"live camera"` never appeared in the module source despite the sentence reading correctly to a human.
- **Fix:** Rewrapped the comment so `live camera` appears together on one line.
- **Files modified:** `dlc_link/src/dlc_link/live.py`
- **Verification:** `grep "live camera" src/dlc_link/live.py` matches; `test_wait_until_swap_comment_present` passes.
- **Committed in:** `f86475b` (Task 3 commit)

**2. [Rule 1 - Bug] `processor.py`'s own module docstring tripped its own "no image-handling identifier" grep check**
- **Found during:** Task 2 verification
- **Issue:** The docstring stated the testability seam works "with no dlclive, no cv2, no torch and no GPU installed" — but the plan's own acceptance criterion greps `processor.py` for `cv2|imread|VideoCapture|frame_buffer` (case-insensitive) and requires zero matches, to prove the Processor never touches an image. The literal word `cv2` in the docstring's own explanation tripped that check.
- **Fix:** Reworded to "no camera library, no torch and no GPU installed" — same meaning, no longer matching the grep pattern.
- **Files modified:** `dlc_link/src/dlc_link/processor.py`
- **Verification:** `grep -ciE "cv2|imread|VideoCapture|frame_buffer" src/dlc_link/processor.py` returns `0`.
- **Committed in:** `4c03e21` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — a literal-text requirement and its own automated verification check interacted in a way the first draft didn't satisfy; both are wording fixes with no logic change)
**Impact on plan:** No scope creep. Both fixes are narrow rewording changes that satisfy both the plan's required literal content and its own automated grep checks simultaneously.

## Issues Encountered
- None beyond the two auto-fixed wording issues above. The worktree's HEAD was already correctly positioned on `34aa768` (this plan's stated dependency base, containing plans 35-01/35-02/35-03 merged) at session start — no reset was required.

## User Setup Required

None — no external service configuration required. This plan performs no install of `deeplabcut-live`, `cv2`, or any GPU/vision dependency; the whole adapter is proven importable and fully unit-tested with all three absent from the dev host.

## Next Phase Readiness

- `dlc_link.signal_map`, `dlc_link.processor`, and `dlc_link.live`/`live_probe` are ready for plan 35-06 (generating and uploading the real demo lib against the target project's `config.yaml`) and plan 35-07 (the `--probe-pose` D-42 measurement against the real vision box, and the corner-geometry rig proof).
- `sdk/` and `api/` are both untouched by this plan (`git status --porcelain sdk/ api/` is empty).
- The full `dlc_link` test suite (141 tests) is green on the dev host with `dlclive`/`torch`/`cv2`/`pandas` all absent, confirming the plan's core objective end-to-end.
- Not run in this worktree: `docker compose exec -T api python -m pytest -q tests/` (the backend baseline) — no docker services are running in this isolated worktree and this plan touches no backend file (`git status --porcelain api/` confirms), consistent with plans 35-01 and 35-03's summaries noting the same limitation. Should be spot-checked once merged if there is any doubt.
- `dlc-link-live --probe-pose`'s corner-geometry check is stated, in both source and printed output, to have one known limit: a permutation that leaves all four corners in place while swapping two other parts (e.g. `LED_on`/`LED_off`) still passes. Plan 35-07 Task 3's temporal check against the operator's own LED actions is the documented complement, not yet built.

## Self-Check: PASSED

All 7 created files verified present on disk; all 3 task commit hashes (`4835db8`, `4c03e21`, `f86475b`) verified present in git history.

---
*Phase: 35-deeplabcut-keypoint-likelihood-integration*
*Completed: 2026-08-31*
