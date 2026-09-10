---
phase: 38-live-camera-source-and-annotated-live-view-for-dlc-driven-mi
plan: 01
subsystem: dlc_link (DeepLabCut sender, `dlc-link-live`)
tags: [dlc, opencv-headless, threading, cli, argparse, pacing]

requires:
  - phase: 35-deeplabcut-keypoint-likelihood-integration
    provides: proven file-driven sender (run_video_loop, DLCProcessor, Pacer) and the
      --probe-pose/corner-geometry validation tooling this plan never touches
provides:
  - classify_source/pacing_for/read_failure_is_terminal/fps_refusal (dlc_link.source):
    one pure classification that decides device/stream/file addressing and every
    downstream policy difference between a file and a camera
  - LatestSlot (dlc_link.latest) and FrameReader (dlc_link.capture): a drop-oldest
    single-slot holder with an honest overwrite count, and the reader thread that
    fills it with bounded retry for a camera and first-failure stop for a file
  - dlc-link-live --source (device index / stream URL / file, --video kept as an
    alias), --max-seconds, --min-rate (no default), --read-retries, --capture-only
  - run_video_loop(pacer=None, should_stop, observer, max_seconds): the unpaced-camera
    loop shape plan 38-03's notebook viewer will hang its observer hook off
affects: [38-02, 38-03, 38-04, 38-05, 38-06]

tech-stack:
  added: []
  patterns:
    - "module split to stay under 300 lines: live.py (pure loop) / live_cli.py
      (orchestration) / live_cli_args.py (argparse) / live_sources.py (capture open +
      summary print) -- same precedent as generate.py/generate_cli.py, extended one
      level further because the camera behaviour did not fit in two files"
    - "source-kind classification (source.py) centralizes every file-vs-camera policy
      difference (pacing, termination, --fps refusal) so nothing downstream re-derives it"
    - "single-slot drop-oldest holder (latest.py) + reader thread (capture.py) as the
      camera-analogue of decimate.py's counts-only DecimateStats (DLC-10 rule)"

key-files:
  created:
    - dlc_link/src/dlc_link/source.py
    - dlc_link/src/dlc_link/latest.py
    - dlc_link/src/dlc_link/capture.py
    - dlc_link/src/dlc_link/live_cli.py
    - dlc_link/src/dlc_link/live_cli_args.py
    - dlc_link/src/dlc_link/live_sources.py
    - dlc_link/tests/test_source.py
    - dlc_link/tests/test_latest.py
    - dlc_link/tests/test_capture.py
  modified:
    - dlc_link/src/dlc_link/live.py
    - dlc_link/tests/test_live.py

key-decisions:
  - "D-49: --source is canonical, --video stays a working alias; both given is exit 2"
  - "D-51: pacing is a property of the source kind (file=paced, device/stream=unpaced),
    never a flag default; --fps on a camera is refused, not silently honoured"
  - "D-52/D-53: a reader thread fills a LatestSlot; overwrites IS the keep-up count;
    behind_count prints n/a (unpaced source), never a structural 0"
  - "D-54: --min-rate has no default -- the threshold comes from the researcher's own
    --capture-only baseline, never invented by this tool"
  - "D-55: four deliberate stops (max-frames, max-seconds, should_stop, Ctrl-C) plus
    bounded retry for a camera vs first-failure stop for a file"
  - "Extended the plan's two-file CLI split (live_cli.py + live_sources.py) to three
    (added live_cli_args.py) to keep every production file under CLAUDE.md's 300-line
    target -- the plan only mandated live.py stay under 300, but the coding-standards
    rule applies repo-wide"

requirements-completed: [CAM-01, CAM-02, CAM-03, CAM-04]

duration: ~75min
completed: 2026-09-10
---

# Phase 38 Plan 01: Live camera source for dlc-link-live Summary

**`dlc-link-live` now opens a device index, an RTSP/HTTP stream, or a file through one
pure classifier, runs a camera unpaced on a reader-thread-fed LatestSlot counting every
skipped frame, and exits non-zero on a researcher-supplied `--min-rate` shortfall --
while `--video <file> --fps 30` behaves byte-for-byte as it did in Phase 35.**

## Performance

- **Duration:** ~75 min
- **Tasks:** 3
- **Files created:** 9
- **Files modified:** 2 (`live.py` split down to 172 lines; `test_live.py` extended)

## Accomplishments
- Fixed the `--video 0` "opened a file named 0" defect: `classify_source` decides
  device/stream/file in one pure, tested function, printed before the capture opens.
- Built the camera-side honest keep-up instrument: `LatestSlot.overwrites` plus
  `FrameReader`'s bounded-retry-vs-first-failure policy, so a camera hiccup no longer
  looks like end-of-file and a slow model no longer silently serves stale frames.
- Split `live.py`'s `run_video_loop` to support `pacer=None` (unpaced, `behind_count`
  is `None` not `0`), `should_stop`, `observer` (never breaks the run) and
  `max_seconds` -- the hooks plan 38-03's notebook viewer will use.
- Rebuilt the CLI around the new `--source`/`--min-rate`/`--capture-only`/
  `--read-retries`/`--max-seconds` flags while keeping `--video`, `--fps`, `--dry-run`,
  `--probe-pose` and every Phase 35 behaviour unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: Source classification and the policy that follows from it** - `d619bc1` (feat)
2. **Task 2: LatestSlot and the camera reader thread** - `ef680ff` (feat)
3. **Task 3: The loop, the CLI split, and the four deliberate stops** - `9eec7bf` (feat)

**Plan metadata:** (this commit, below)

## Files Created/Modified

- `dlc_link/src/dlc_link/source.py` - `classify_source`/`SourceSpec`/`pacing_for`/
  `read_failure_is_terminal`/`fps_refusal`; pure, no cv2/dlclive import
- `dlc_link/src/dlc_link/latest.py` - `LatestSlot`: single-slot drop-oldest holder,
  counts only (DLC-10)
- `dlc_link/src/dlc_link/capture.py` - `FrameReader`: threading.Thread wrapper around
  an injected `read()` callable, never calls `release()`
- `dlc_link/src/dlc_link/live.py` - `run_video_loop` (pacer=None/should_stop/observer/
  max_seconds), `compare_pose_order`, `check_corner_geometry`, `_CORNERS`, delegating
  `main()`; 172 lines
- `dlc_link/src/dlc_link/live_cli.py` - orchestration: `main()`, `_build_processor_and_infer`,
  `_run_and_close`; re-exports `build_parser`/`validate_connection_args`
- `dlc_link/src/dlc_link/live_cli_args.py` - `build_parser`, `validate_connection_args`,
  `resolve_source`
- `dlc_link/src/dlc_link/live_sources.py` - `open_file_source`, `open_camera_source`,
  `print_summary`, `_DiscardingLink`, `_NoOpProcessor`, `_no_op_infer`
- `dlc_link/tests/test_source.py` - 25 tests
- `dlc_link/tests/test_latest.py` - 8 tests
- `dlc_link/tests/test_capture.py` - 10 tests
- `dlc_link/tests/test_live.py` - 53 tests (pre-existing 29 + 24 new for Task 3's
  `pacer=None`/`should_stop`/`observer`/`max_seconds`/camera-CLI behaviour)

## Decisions Made

See `key-decisions` in frontmatter (D-49, D-51, D-52/D-53, D-54, D-55 from
`38-DECISIONS.md`, implemented as specified). One decision made during execution,
not pre-recorded in `38-DECISIONS.md`: the CLI split that the plan specified as two
files (`live_cli.py` + `live_sources.py`) grew a third (`live_cli_args.py`) because the
combined argparse definition plus orchestration logic exceeded 300 lines in one file --
this repo's coding-standards rule applies repo-wide, not just to the file the plan
named explicitly (`live.py`). `build_parser`/`validate_connection_args` remain
importable from `dlc_link.live_cli` exactly as the plan's artifact contract requires;
the third module is purely an internal implementation detail.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical / CLAUDE.md enforcement] Split the CLI into three
files instead of two to honor the repo-wide 300-line production-file rule**
- **Found during:** Task 3
- **Issue:** The plan's own artifact contract names only `live.py` (under 300) and
  `live_cli.py` as the split target; building `live_cli.py` per the plan's Step A/B
  action text alone produced a 393-line file, over this repo's CLAUDE.md/
  coding-standards 300-line target (hard limit is 500, not breached, but the target is
  the rule to follow).
- **Fix:** Extracted `open_file_source`/`open_camera_source`/`print_summary`/the
  `--dry-run`/`--capture-only` stand-ins into `dlc_link/src/dlc_link/live_sources.py`,
  then extracted `build_parser`/`validate_connection_args`/`resolve_source` into
  `dlc_link/src/dlc_link/live_cli_args.py`, re-exported from `live_cli.py` so the
  plan's `exports: ["main", "build_parser", "validate_connection_args"]` contract for
  `dlc_link.live_cli` still holds.
- **Files modified:** `dlc_link/src/dlc_link/live_cli.py`, `live_cli_args.py` (new),
  `live_sources.py` (new)
- **Verification:** `sed -n '$=' ` on every touched production file confirms all are
  under 300 lines (`live.py` 172, `live_cli.py` 207, `live_cli_args.py` 121,
  `live_sources.py` 123); full test suite green; the plan's own `--source`/`--help`
  verification commands pass unchanged against the new layout.
- **Committed in:** `9eec7bf` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 CLAUDE.md-driven structural split)
**Impact on plan:** No behaviour change; purely an internal module boundary. The
plan's artifact/export contract for `live_cli.py` is satisfied by re-export.

## Issues Encountered

- The module docstring for `latest.py` originally named "latency, jitter or drift"
  in prose while describing the DLC-10 rule it follows; the plan's own verify command
  greps for those words with only `#`-comment lines excluded (not docstrings), so the
  literal mention tripped the check it was trying to document. Reworded to "per-frame
  timing figure of any kind" -- same rule, no forbidden vocabulary in the source file.
  Same fix applied to `live_sources.py`'s `print_summary` docstring during Task 3.

## User Setup Required

None - no external service configuration required. This plan installs nothing new;
`pyproject.toml` is unmodified (verified via `git status --porcelain`).

## Next Phase Readiness

- `dlc-link-live --source 0` (device), `--source rtsp://...` (stream) and
  `--source <file>`/`--video <file>` (unchanged) are all ready for the rig session
  (plan 38-04) once a real camera is available to test against -- everything here was
  proven against fakes on the dev host (no cv2, no dlclive, no camera, no GPU).
- `run_video_loop`'s `observer`/`should_stop` hooks exist and are tested, ready for
  plan 38-03's notebook viewer to hang an annotated-frame callback off without risking
  the experiment (an observer that raises is counted, never breaks the run).
- `--min-rate`'s threshold is still unmeasured against a real camera (D-54 says the
  runbook must say "not yet measured" until 38-04 supplies a number) -- this plan only
  builds the mechanism, not the number.
- No blockers. `live_probe.py` and `pyproject.toml` are untouched; every Phase 35 test
  still passes.

---
*Phase: 38-live-camera-source-and-annotated-live-view-for-dlc-driven-mi*
*Completed: 2026-09-10*

## Self-Check: PASSED

All 12 created/modified files confirmed present on disk; all 3 task commits
(`d619bc1`, `ef680ff`, `9eec7bf`) confirmed present in `git log`.
