---
phase: 38-live-camera-source-and-annotated-live-view-for-dlc-driven-mi
plan: 07
subsystem: infra
tags: [ffmpeg, dshow, tee-muxer, powershell, mjpeg, directshow, dlc-link-relay]

# Dependency graph
requires:
  - phase: 38-01
    provides: "camera source classification (source.py) and the LatestSlot/FrameReader capture seam that the delivery leg's consumer (dlc-link-live) already uses"
  - phase: 38-05
    provides: "the 713-line RUNBOOK.md TOPOLOGY section (corrected here) and the -listen trap's original documentation"
provides:
  - "acquire.py: pure ffmpeg-argv + tee-spec builder (AcquireSpec, build_ffmpeg_argv, build_tee_spec) -- segmented file leg (no onfail), pushed delivery leg (onfail=ignore), -fps_mode passthrough mandatory, no -v/-loglevel ever, tee-unsafe segment_pattern refused structurally"
  - "acquire_supervisor.py: pure PowerShell-text builder (build_supervisor_ps1, render_argv_lines) -- bounded restart loop, per-attempt log files, paste-safe under-100-char lines including for single tokens (the tee spec) longer than one line on their own"
  - "dlc-link-relay console script (acquire_cli.py): prints argv + PS block by default, writes only via --out, refuses writing inside a DLC project directory via the shared guard dlc-link-generate already uses"
  - "scripts/mics-acquire.ps1: checked-in reference supervisor, byte-identical to the generator for a declared placeholder set"
  - "RUNBOOK.md ACQUISITION section: why/precondition/shape/fps_mode/quality-escalation/supervisor/completeness-procedure/auto-exposure-caveat/non-goals/rollback"
  - "RUNBOOK.md TOPOLOGY section corrected: the -listen 1 prescriptions plan 38-05 wrote (D-88 postdates and forbids them) are replaced with pushed-form pointers to ACQUISITION"
affects: [38-ACQUISITION-VALIDATION, dlc-link-relay-pypi-release]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure argv/text builders with a dedicated AcquireSpecError/validation layer, mirroring source.py's precedent (no cv2/subprocess/network, fully unit-testable on Linux)"
    - "A CLI's DLC-project write-guard composes an existing sibling module's guard function (generate_cli._check_out_dir_not_in_project) with another sibling's project-root walk-up (convert_cli._find_dlc_project_root), rather than writing a third copy of the commonpath check"
    - "Long single PowerShell array tokens are pre-declared as $tN variables built from multiple under-budget string-literal concatenation lines, because a per-token line chunker cannot split inside one token"

key-files:
  created:
    - dlc_link/src/dlc_link/acquire.py
    - dlc_link/src/dlc_link/acquire_supervisor.py
    - dlc_link/src/dlc_link/acquire_cli.py
    - dlc_link/scripts/mics-acquire.ps1
    - dlc_link/tests/test_acquire.py
    - dlc_link/tests/test_acquire_supervisor.py
    - dlc_link/tests/test_acquire_cli.py
  modified:
    - dlc_link/pyproject.toml
    - dlc_link/RUNBOOK.md

key-decisions:
  - "File-leg quality is a first-class requirement, not a tuning knob: the recorded footage IS this camera's DeepLabCut training set, so the builder exposes --delivery-codec as an explicit escalation to the two-stream select= form rather than ever letting the archival file silently inherit the delivery leg's cheap MJPEG quality."
  - "dlc-link-relay's DLC-project write guard reuses dlc_link.generate_cli._check_out_dir_not_in_project verbatim (composed with convert_cli._find_dlc_project_root), per the plan's explicit 'not a second copy of it' instruction -- the first time this codebase's write-guard has actually been imported across CLI modules instead of re-implemented."
  - "--transport has no default, matching --min-rate's precedent: the measured answer belongs in 38-ACQUISITION-VALIDATION.md Sec3, never invented here."
  - "-listen is now named exactly once in RUNBOOK.md (the ACQUISITION section's trap paragraph), worded without the literal '-listen 1' substring so the plan's own grep gate and the trap explanation coexist."

patterns-established:
  - "acquire_supervisor.render_argv_lines(argv, array_var) returns (decl_lines, array_lines): callers needing a paste-ready PowerShell block (the CLI's default print mode, and the supervisor itself) share one length-aware renderer instead of two independently-chunked ones."

requirements-completed: []  # CAM-18 is NOT complete -- Task 3 (the rig measurement) is still pending; do not mark the requirement done on this plan alone.

# Metrics
duration: ~50min
completed: 2026-09-10
---

# Phase 38 Plan 07: Acquisition recorder builder, dlc-link-relay CLI, and runbook (Tasks 1-2 of 3)

**Pure ffmpeg-argv/PowerShell-supervisor builder plus the `dlc-link-relay` console script that prints them — D-88's tee-fan-out recorder, with the measurement checkpoint (Task 3) still awaiting the researcher's rig session.**

## Performance

- **Duration:** ~50 min (not precisely tracked — no start timestamp captured at spawn)
- **Completed:** 2026-09-10 (Tasks 1-2 only; Task 3 is a blocking checkpoint, not yet run)
- **Tasks:** 2 of 3 completed (Task 3 is `checkpoint:human-verify`, `gate="blocking"` — USER-RUN, not attempted)
- **Files modified:** 9 (3 created source modules, 1 created CLI, 1 created reference script, 3 created/modified test files, 2 modified: pyproject.toml, RUNBOOK.md)

## Accomplishments

- `acquire.py`: `AcquireSpec`/`build_ffmpeg_argv`/`build_tee_spec`/`AcquireSpecError` — a pure builder that cannot emit `-listen`, cannot emit `-v`/`-loglevel`, cannot mangle a tee slave with a Windows path, and defaults to one cheap MJPEG encode while exposing `delivery_codec` as an explicit escalation to a two-stream `select=` form for when the file leg is training footage that needs real quality.
- `acquire_supervisor.py`: `build_supervisor_ps1`/`render_argv_lines` — a bounded-restart PowerShell generator with per-attempt log files and a length-aware renderer that keeps every line under 100 characters, including the tee spec itself (a single token that can exceed that budget alone — see Deviations).
- `dlc-link-relay` (`acquire_cli.py`): the console script a researcher actually runs on a different machine. Writes nothing by default; `--out` is the only write path and is refused inside a DeepLabCut project directory via the SAME guard `dlc-link-generate` already applies.
- `scripts/mics-acquire.ps1`: a checked-in reference supervisor, held byte-identical to the generator's own output by a test, using RFC 5737 addresses and a generic device name.
- `RUNBOOK.md`: corrected the TOPOLOGY section's `-listen 1` prescriptions (D-88 postdates and forbids them) and added a full ACQUISITION section covering the precondition, the tee shape, the mandatory `-fps_mode passthrough`, the quality-escalation reasoning, the supervisor, the four-witness completeness procedure with its decision table, the auto-exposure caveat, and the explicit non-goal (no simultaneous IC Capture access).
- Test suite: 406 baseline → 532 passed, 3 skipped (126 new tests across three new/modified test files).

## Task Commits

1. **Task 1: A pure ffmpeg-argv and PowerShell-supervisor builder that cannot emit a silent recorder** - `5f87f9e` (feat)
2. **Task 2: The `dlc-link-relay` surface, the reference supervisor, and the runbook's acquisition section** - `7819ad5` (feat)

**Task 3: CHECKPOINT (USER-RUN)** — NOT started. See "Checkpoint State" below.

_Note: no separate plan-metadata commit yet — this SUMMARY's own commit is that commit, since the plan is not complete._

## Files Created/Modified

- `dlc_link/src/dlc_link/acquire.py` - pure ffmpeg argv + tee-spec builder (D-88)
- `dlc_link/src/dlc_link/acquire_supervisor.py` - pure PowerShell supervisor-text builder
- `dlc_link/src/dlc_link/acquire_cli.py` - `dlc-link-relay` console script
- `dlc_link/scripts/mics-acquire.ps1` - checked-in reference supervisor (RFC 5737 placeholders)
- `dlc_link/pyproject.toml` - added `dlc-link-relay = "dlc_link.acquire_cli:main"`
- `dlc_link/RUNBOOK.md` - added ACQUISITION section; corrected TOPOLOGY's `-listen` prescriptions
- `dlc_link/tests/test_acquire.py` - builder invariant/shape/refusal tests (57 cases)
- `dlc_link/tests/test_acquire_supervisor.py` - supervisor-text tests incl. long-token reconstruction
- `dlc_link/tests/test_acquire_cli.py` - CLI behavior, write-guard, byte-identity tests

## Decisions Made

- **File-leg quality is a first-class requirement, not a tuning knob.** The orchestrator's brief explained this recording IS the DeepLabCut training set for this camera — no model exists yet to be forgiving of compression artifacts. The builder's default stays the cheap single-MJPEG-encode form (matches D-88's stated default), but `--delivery-codec`/`delivery_codec` is the explicit, always-available escalation to the two-stream `select=` form, and this reasoning is recorded in `acquire.py`'s module docstring, `acquire_cli.py`'s `--delivery-codec` help text, and RUNBOOK.md ACQUISITION §5 — wherever the plan said to record it.
- **Reused, not duplicated, the DLC-project write guard.** `acquire_cli._check_out_not_in_dlc_project` imports `generate_cli._check_out_dir_not_in_project` and `convert_cli._find_dlc_project_root` directly rather than adding a third independent commonpath implementation — the plan asked for this explicitly ("not a second copy of it").
- **`--transport` has no default**, matching the `--min-rate` precedent already in this codebase: an unmeasured default is exactly the mistake that flag exists to prevent, so the CLI's help text points at `38-ACQUISITION-VALIDATION.md` §3 instead of guessing.
- **`-listen` is named exactly once in the runbook** (the new ACQUISITION section's trap paragraph), and never with the literal substring `-listen 1` — satisfying both the plan's "named once" instruction and its `grep -c -- '-listen 1'` gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The tee spec (one token) could exceed the 100-character paste-safety budget on its own**
- **Found during:** Task 2, while testing the generated supervisor against a realistic `--delivery` invocation (the Part 6-style rig command from the plan itself).
- **Issue:** `acquire_supervisor.py`'s original chunker grouped WHOLE tokens per line, length-aware across tokens but not WITHIN a token. The tee spec (`[f=segment:...]<pattern>|[f=mpjpeg:onfail=ignore]<url>`) is a single ffmpeg argv element that is routinely 130-150+ characters once a real URL is substituted — one token, and the chunker always emits at least one token per line even if that token alone busts the budget. This is exactly the paste-safety defect the plan's rule exists to prevent, just one level deeper (inside a token, not across tokens).
- **Fix:** `acquire_supervisor.py` now pre-declares any token too long to fit one line as a short `$tN` variable, built from multiple `$tN = '...'` / `$tN += '...'` string-literal-concatenation lines (each itself under budget), and references `$tN` (not the literal) at that position in the `$a=@(...)` array. `render_argv_lines` (renamed from the former private `_argv_array_lines`/`_chunk_argv` pair) returns `(decl_lines, array_lines)` so both the supervisor and the CLI's `--print argv` mode share the identical, correct rendering.
- **Files modified:** `dlc_link/src/dlc_link/acquire_supervisor.py`, `dlc_link/src/dlc_link/acquire_cli.py` (consumer), `dlc_link/tests/test_acquire_supervisor.py` (added `test_long_token_reconstructs_exactly_across_declaration_lines` and `test_render_argv_lines_long_token_reconstructs_to_the_exact_original_value`, which verifies exact byte reconstruction including an embedded single quote).
- **Verification:** regenerated the Part-6-style rig invocation by hand after the fix; longest line dropped from 150 to 90 characters. Full suite re-run, 0 regressions.
- **Committed in:** `7819ad5` (Task 2 commit — the fix was needed to make Task 2's own CLI output correct, so it rides that commit rather than a separate one).

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Necessary for correctness of the paste-safety requirement the plan itself states as a `must_haves.truth`. No scope creep — the fix stayed inside the two files Task 1/2 already owned.

## Issues Encountered

None beyond the deviation above.

## Checkpoint State — Task 3 is USER-RUN and has NOT been attempted

Per this plan's `autonomous: false` and Task 3's `type="checkpoint:human-verify" gate="blocking"`:
this executor did **not** run any command on the lab computer or the vision box, did **not**
touch a camera, did **not** start or stop anything on a Pi, and did **not** create or write into
`.planning/phases/38-live-camera-source-and-annotated-live-view-for-dlc-driven-mi/38-ACQUISITION-VALIDATION.md`.
That file does not exist yet.

**What Task 3 needs from the researcher** (full detail in `38-07-PLAN.md` Task 3's
`<how-to-verify>`, Parts 1-7): a rig session on the LAB computer (`132.77.73.214`) and the
VISION box (`132.77.73.217`) that —

1. Confirms IC Capture is not mid-recording someone else's data (`D:\Inbar\Data\MethodsCourse\...`)
   and asks first if it is; records exposure/gain/ROI before touching anything.
2. Proves the file leg alone records (`dlc-link-relay`'s plain-segment form, no delivery).
3. Measures which transport (`mpjpeg-tcp` vs `mpegts-udp`) survives a SLOW consumer, not just a
   dead one, and adopts accordingly.
4. Measures which encoder drops zero frames while the model is actually loaded and running
   (`--dry-run`, so nothing reaches a Pi).
5. Runs the four-witness completeness test twice — auto-exposure as found, then with exposure
   pinned — and applies the decision table exactly as written.
6. Runs the kill test (supervisor restart) and the consumer-death test.
7. Writes all of the above into `38-ACQUISITION-VALIDATION.md`, in the shape of
   `38-HARDWARE-VALIDATION.md`.

**Exact commands to run:** every command block in `38-07-PLAN.md` Task 3 `<how-to-verify>` is
already fully written out by the plan (PowerShell, short `$var=` assignments, argument arrays —
no line wraps on paste). The generator commands in that section (`dlc-link-relay ... --print
supervisor --out ...`) now work exactly as documented, since Tasks 1-2 are complete.

**Resume signal:** one of `approved — complete`, `approved — complete with defects`, or
`blocked — <reason>` (see Task 3's `<resume-signal>` in the plan for the exact distinguishing
criteria). Until one of those is given, `dlc-link-relay`/`mics-acquire.ps1` exist and are tested,
but **no footage has been recorded anywhere, and CAM-18 is not complete.**

## User Setup Required

None from Tasks 1-2 — they only produce text. Task 3 itself requires the researcher to run
PowerShell commands on the lab computer and the vision box (detailed above); this executor
cannot and did not run them.

## Next Phase Readiness

- `dlc-link-relay` is ready to be dogfooded on the real rig the moment the researcher starts
  Task 3 — no further code changes are anticipated before the measurement.
- `38-ACQUISITION-VALIDATION.md` does not exist; Task 3 creates it.
- If the adopted transport or encoder (once measured) differs from this plan's documented
  defaults, Task 3 itself updates `RUNBOOK.md`'s ACQUISITION section to quote the adopted values
  — that update is explicitly Task 3's responsibility, not deferred to a later plan.
- `requirements-completed` is deliberately empty in this summary's frontmatter: CAM-18 only
  completes once Task 3's measurement closes the loop.

---
*Phase: 38-live-camera-source-and-annotated-live-view-for-dlc-driven-mi*
*Plan 07: Tasks 1-2 of 3 complete; Task 3 checkpoint awaiting the researcher*

## Self-Check: PASSED

All 7 created files confirmed present on disk; both task commit hashes (`5f87f9e`, `7819ad5`)
confirmed present in `git log --oneline --all`. No missing items.
