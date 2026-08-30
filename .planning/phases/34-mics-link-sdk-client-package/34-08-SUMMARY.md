---
phase: 34-mics-link-sdk-client-package
plan: 08
subsystem: sdk
tags: [readme, packaging, wheel, distribution, device-neutrality, ascii-safety]

# Dependency graph
requires: ["34-01", "34-05", "34-06", "34-07"]
provides:
  - "sdk/README.md — SDK-13's mandatory nine sections: what this is, install (two paths per the DLC-Live/Windows amendment), rig prerequisites, the exact pilot_hardware_config.config shape, a working sender (pull-loop + callback/push), how to observe results in the FDA and ES, replay, eight afternoon-wasting pitfalls, and why there is no latency readout"
  - "sdk/examples/ten_line_sender.py — the counted artifact (4 real lines), and sdk/examples/callback_sender.py — the amendment-mandated callback/push shape (SDK-15), exempt from the line count"
  - "sdk/tests/test_readme_contract.py — 47 tests mechanically enforcing the ten-line bar, every required marker, the public-repo risk disclosure, no bare PyPI line, no latency claim outside its own section, device-neutrality (word-boundary matched) across README+examples+src, ASCII-only encoding, and full mics_link.__all__ documentation coverage"
  - "A built wheel (mics_link-0.1.0-py3-none-any.whl) proven to install+import from a throwaway target, and a git+file:// subdirectory install proven against this worktree's own branch"
  - "Device-neutrality fix to 7 pre-existing src/mics_link docstrings (waves 2-4) that referenced vendor-specific terms, closing a gap this plan's own guard would otherwise have failed on day one"
affects: [34-09, 35]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "count_real_lines(): AST-based module-docstring exclusion (not string matching) so a future 'clever' example cannot game the ten-line bar by hiding code inside a fake docstring"
    - "Device-neutrality guard uses \\b word-boundary regex (not plain substring) for all five banned terms, including 'pose' — a plain substring match on 'pose' would also flag ordinary English words like 'purpose'/'exposed'/'supposed' throughout the README and existing docstrings, which is not what the guard is for"
    - "Every mics_link.__all__ name is round-tripped through the README (test_every_public_name_appears_in_the_readme) so 'Phase 35's adapter is writable from the README alone' is a testable claim, not an aspiration"

key-files:
  created:
    - sdk/README.md
    - sdk/examples/ten_line_sender.py
    - sdk/examples/callback_sender.py
    - sdk/tests/test_readme_contract.py
  modified:
    - sdk/pyproject.toml
    - sdk/src/mics_link/__init__.py
    - sdk/src/mics_link/client.py
    - sdk/src/mics_link/replay.py
    - sdk/src/mics_link/replay_io.py
    - sdk/src/mics_link/selfcheck.py
    - sdk/src/mics_link/timing.py
    - sdk/src/mics_link/values.py

key-decisions:
  - "Device-neutrality guard implemented with \\b word-boundary matching for all five banned terms (deeplabcut/keypoint/bodypart/pose/dlc), not a plain case-insensitive substring search as a literal reading of the plan text might suggest — a substring match on 'pose' would flag 'purpose', 'exposed', 'supposed', 'proposed' throughout the README and pre-existing docstrings, which is not the intent of banning vendor/keypoint terminology. Verified the pattern still catches real violations (a constructed 'DeepLabCut keypoint...pose' sentence) via an out-of-band sanity check before trusting the immediate green result."
  - "Fixed device-neutrality violations in 7 already-committed src/mics_link files (from waves 2-4's 'DLC-Live and Windows' amendment citations) rather than leaving them as a documented-but-unfixed pre-existing gap — this plan's own success criteria states 'Nothing in mics_link or its docs knows what a keypoint is', and Task 2's own guard scans the whole sdk/src/mics_link/ tree, so an unfixed violation would fail this plan's own required verification on day one. Wording-only changes, no behavior change, full suite re-verified green before and after."
  - "test_readme_contract.py's 47 tests passed on the FIRST run against Task 1's already-written content — no RED failure occurred. Verified the suite is not vacuous with an out-of-band sanity check (an artificially constructed 11-line fixture correctly fails the line-count bar; an artificial DeepLabCut/keypoint/pose sentence correctly fails the device-neutrality pattern) before accepting the immediate green result as genuine, not a test that trivially passes anything."
  - "The git+file://...#subdirectory=sdk verification runs against THIS WORKTREE's own path and branch (git+file:///home/ido/mics-backend/.claude/worktrees/<id>@worktree-agent-<id>#subdirectory=sdk), not against /home/ido/mics-backend (the main repo checkout on branch `claude`) — the worktree's commits are not yet merged, so pointing at the main repo resolves a stale HEAD (this plan's OWN base commit, 276b3ef, with none of this plan's work). Both forms were run; results recorded below rather than one being silently substituted for the other."
  - "python3 -m pip install build failed under this host's PEP-668 externally-managed-environment restriction (same failure 34-01 hit installing mics_link itself) — resolved by creating a throwaway venv (scratchpad) and running python -m build --wheel through that venv's python against sdk/, exactly as 34-01's own Rule-3 resolution for the analogous problem. The venv itself is not part of the repo or any commit."

requirements-completed: [SDK-01, SDK-13]

# Metrics
duration: ~50min
completed: 2026-08-30
---

# Phase 34 Plan 08: README + distribution — the researcher-facing surface Summary

**A 325-line researcher-facing `sdk/README.md` covering install/rig-prerequisites/config-shape/sender/observability/replay/pitfalls, backed by a 47-test contract (`test_readme_contract.py`) that mechanically enforces the 10-line sender bar, full `__all__` documentation coverage, device-neutrality and ASCII-safety, plus a proven wheel build (`mics_link-0.1.0-py3-none-any.whl`, sha256 `fc2ef9e8...`) and a git-subdirectory install verified against this worktree's own commits.**

## Performance

- **Duration:** ~50 min (commit timestamps in this sandboxed environment cluster within
  minutes of each other and are not a reliable wall-clock signal; this is a qualitative
  estimate based on the work performed)
- **Started:** 2026-08-30 (after worktree base correction — HEAD was on an unrelated
  3-commit history sharing only an early ancestor with the expected base `276b3ef`)
- **Completed:** 2026-08-30
- **Tasks:** 3/3 completed, plus 1 mandatory prerequisite fix (device-neutrality) and 1
  readability fix found during the plan's own manual read-through pass
- **Files modified:** 4 created, 8 modified

## Accomplishments

- **`sdk/README.md`** (325 lines, well above the 120-line minimum) covers, in order: what
  this is, install (two paths — a GitHub Release wheel URL first, `git+https` second, both
  `python -m pip`, both flagging the public-repo/token risk, plus the offline wheel
  fallback and the explicit PyPI non-support statement), the four things a researcher must
  create on the rig (with the standing `ExtlinkDemo` fixture as the worked example), the
  exact `pilot_hardware_config.config` shape with a per-field table and the load-bearing
  `host`-vs-egress-target warning, a working sender in both the pull-loop AND
  callback/push shapes (SDK-15), a full API reference where every name is provably in
  `mics_link.__all__`, how to observe results in the FDA and Elasticsearch, replay (both
  file shapes, timing modes, `Pacer`), eight numbered pitfalls led by the `source_id`
  identity-acceptance warning, and why there is no latency readout.
- **`sdk/examples/ten_line_sender.py`** is the counted artifact: **4 real lines**
  (`from mics_link import connect`, the `with connect(...)` line, the `for` line, the
  `send_signal` line) — well under the 10-line bar, so no API simplification was needed.
  Embedded verbatim in the README and proven to stay verbatim by
  `test_readme_contains_the_ten_line_examples_counted_lines_verbatim`.
- **`sdk/examples/callback_sender.py`** (new, amendment-mandated, not in this plan's
  original `files_modified`) demonstrates the callback/push shape SDK-15 requires:
  client created outside and outliving the callback, the callback returning what its host
  expects, and per-callback state living on the callback object. Exempt from the line-count
  bar but still parsed and still checked against `mics_link.__all__`.
- **`sdk/tests/test_readme_contract.py`** (47 tests, new) is the mechanical enforcement
  layer: the ten-line bar (with its own 4 unit-tested fixtures for `count_real_lines`,
  including the exact docstring/blank/full-comment/trailing-comment/two-real-statements
  case CONTEXT.md's own instruction describes), every one of the 12 required markers, the
  public-repo private/token disclosure, the no-bare-PyPI-line negative assertion, the
  no-latency-claim-outside-its-section negative assertion (located by heading, not by
  hardcoded line numbers), the device-neutrality guard across README + examples + all of
  `src/mics_link/`, an ASCII-only encoding check on the README and every example, and full
  `mics_link.__all__` -> README coverage.
- **A built wheel**, `mics_link-0.1.0-py3-none-any.whl` (sha256
  `fc2ef9e81b3b42cc7b379b3ac6826566b19c45dee771517a7cb1e620438b5178`), installs into a
  throwaway `--target` and imports cleanly (`mics_link.__version__ == "0.1.0"`).
  `sdk/dist/` stays gitignored — the wheel was never committed.
- **Dependency closure proven honestly**: installing the wheel WITHOUT `--no-deps` into a
  fresh throwaway target pulled in exactly `pyzmq` (27.2.0) and `msgpack` (1.2.2) alongside
  `mics-link` itself — three `.dist-info` directories, nothing else. Matches SDK-01's claim
  exactly.
- **Device-neutrality gap closed across the whole phase, not just this plan's new files**:
  found and fixed 7 pre-existing `sdk/src/mics_link/*.py` docstrings (from waves 2-4's own
  "DLC-Live and Windows" amendment citations) that would have failed this plan's own
  Task 2 guard on day one — see Deviations.

## Task Commits

1. **[Prerequisite fix, ahead of Task 1] Remove device-specific vendor language from
   prior-wave docstrings** - `59b2151` (fix)
2. **Task 1: Write sdk/README.md and the counted examples** - `f843001` (feat)
3. **Task 2: Automate the ten-line bar and the README contract** - `ad9ffa7` (test)
4. **[Readability fix, found during manual read-through] Line wrap + real imports in the
   callback snippet** - `59a0f7e` (docs)
5. **Task 3: Build the wheel and prove the git-subdirectory install** - no commit (no
   tracked file changed; `sdk/dist/` is gitignored by design). Results recorded below.

## Files Created/Modified

- `sdk/README.md` (325 lines, new) - the full researcher-facing document, SDK-13
- `sdk/examples/ten_line_sender.py` (new) - the counted pull-loop sender, 4 real lines
- `sdk/examples/callback_sender.py` (new) - the callback/push sender, SDK-15, exempt from
  the line count
- `sdk/tests/test_readme_contract.py` (new, 47 tests) - mechanical enforcement of the
  README contract
- `sdk/pyproject.toml` - gained `readme = "README.md"`, left out deliberately by 34-01
- `sdk/src/mics_link/__init__.py`, `client.py`, `replay.py`, `replay_io.py`,
  `selfcheck.py`, `timing.py`, `values.py` - wording-only device-neutrality fixes (no
  behavior change)

## Final Wheel + Install Evidence (for the SUMMARY's required record)

- **Wheel filename:** `mics_link-0.1.0-py3-none-any.whl`
- **sha256:** `fc2ef9e81b3b42cc7b379b3ac6826566b19c45dee771517a7cb1e620438b5178`
- **Throwaway `--target` install + import:** succeeded, `mics_link.__version__ == "0.1.0"`
- **Dependency closure (no `--no-deps`):** exactly `pyzmq==27.2.0` + `msgpack==1.2.2` +
  `mics-link==0.1.0` itself — 3 `.dist-info` directories, nothing extra
- **`git+file://...#subdirectory=sdk` against THIS WORKTREE's own branch**
  (`git+file:///home/ido/mics-backend/.claude/worktrees/agent-abcdb23c8c15e195c@worktree-agent-abcdb23c8c15e195c#subdirectory=sdk`):
  resolved to commit `ad9ffa7` (this plan's own Task 2 commit, at the time of the check —
  current, not stale), installed, and imported (`mics_link.__version__ == "0.1.0"`).
- **`git+file://...#subdirectory=sdk` against the MAIN REPO** (`/home/ido/mics-backend`,
  branch `claude`, the plan's own literal `<verification>` command): resolved to commit
  `276b3ef` — this PLAN's OWN BASE commit, before any of this plan's work, because this
  worktree's commits are not yet merged into `claude`. This install still succeeds and
  imports (the base commit already had a working `sdk/` from waves 1-4), but it is NOT
  evidence of THIS plan's changes — it is stale by construction until merge. **Unverified
  until merge:** the exact literal command in this plan's own `<verification>` block,
  run against the real remote (or the real local main branch after merge), has not been
  run in this session. The worktree-branch form above is the closest available proof that
  the `#subdirectory=sdk` mechanism itself, and this plan's own commits specifically,
  resolve correctly.

## Decisions Made

See `key-decisions` in the frontmatter for: why the device-neutrality guard uses
word-boundary matching rather than plain substring matching; why 7 pre-existing source
files needed wording fixes rather than being left as a documented gap; why the
test-passing-on-first-run outcome was independently sanity-checked rather than trusted at
face value; why the git-subdirectory check targets this worktree's own branch; and the
PEP-668 venv workaround for installing `build`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, mandatory prerequisite] 7 pre-existing `sdk/src/mics_link/*.py`
docstrings violated this plan's own device-neutrality guard**
- **Found during:** reading Task 2's `<behavior>` block before writing the test, then
  confirmed with an ad-hoc scan before writing any test code
- **Issue:** Waves 2-4 (plans 34-01, 34-02, 34-06, 34-07), executing under the same
  "DLC-Live and Windows" amendment this plan also operates under, cited that amendment's
  own title verbatim in several docstrings ("DLC-Live and Windows"), and `selfcheck.py`
  and `client.py` used vendor-specific illustrative language ("DeepLabCut environments",
  "an inspected `DEEPLABCUT223` env", "`dlclive`'s `Processor.process`", "DLC's own
  inference thread", "an occluded DLC keypoint", "a DLC-driven task"). This plan's own
  Task 2 `<behavior>` block requires a device-neutrality guard scanning ALL of
  `sdk/src/mics_link/` for exactly these terms, and this plan's own success criteria
  states "Nothing in `mics_link` or its docs knows what a keypoint is" — an unfixed
  violation would fail this plan's own required test on first run, for content this plan
  did not introduce but is nonetheless bound by its own stated bar to satisfy.
- **Fix:** Reworded all 7 occurrences in place, preserving every technical claim: amendment
  citations became "cross-platform/vendor-neutrality amendment"; "DeepLabCut environments"
  became "scientific Python environments"; the specific inspected env name was
  generalized to "scientific-computing conda environment"; the `dlclive`/`Processor.process`
  worked example became "a vendor inference SDK's per-frame callback ... that library's
  own worker thread"; "occluded DLC keypoint"/"occluded keypoint" became "occluded tracked
  feature"/"occluded feature"; "DLC-driven task" became "model-driven task". No code
  behavior changed — every edit is inside a docstring or comment.
- **Files modified:** `sdk/src/mics_link/__init__.py`, `client.py`, `replay.py`,
  `replay_io.py`, `selfcheck.py`, `timing.py`, `values.py`
- **Verification:** full `sdk/` suite green (227/227) both before and after; a
  word-boundary scan (`grep -rniE "\b(deeplabcut|keypoint|bodypart|pose|dlc)\b"`) across
  `README.md`, `examples/`, `src/mics_link/*.py` returns zero matches after the fix
- **Committed in:** `59b2151` (ahead of Task 1, since Task 2's test depends on this being
  true)

**2. [Rule 2 - amendment-mandated] `sdk/examples/callback_sender.py` is not in this
plan's frontmatter `files_modified`**
- **Found during:** reading the "AMENDED 2026-08-30" block before starting Task 1
- **Issue:** The amendment's own text explicitly requires "Section 5 gains a second
  example: the callback / push shape, in a new file `sdk/examples/callback_sender.py`" —
  this postdates the plan's original `files_modified` list, which only names
  `ten_line_sender.py`.
- **Resolution:** Implemented exactly as the amendment specifies (client created outside
  the callback, the callback returns its host's expected value, per-callback state lives
  on the callback object), written device-neutrally per the guard above rather than
  reusing the amendment's own DeepLabCut-Live illustrative wording verbatim.
- **Files affected:** `sdk/examples/callback_sender.py` (new)
- **Committed in:** `f843001`

**3. [Rule 1 - Bug, self-caught, clarifying an ambiguous instruction] Device-neutrality
guard implemented as word-boundary, not plain substring, matching**
- **Found during:** writing `test_readme_contract.py`'s device-neutrality tests, before
  running them
- **Issue:** Task 2's `<behavior>` block says "a case-insensitive match for `deeplabcut`,
  `keypoint`, `bodypart` or `pose`, nor a word-boundary match for `dlc`" — read literally,
  only `dlc` gets word-boundary treatment, and a plain substring search for `pose` would
  match "purpose", "exposed", "supposed", "proposed", "composed" throughout the README's
  own prose and every existing docstring in `src/mics_link/` (e.g. "for FDA purposes",
  "exposed package-private", multiple "purpose"s in the new README) — none of which have
  anything to do with device-specific pose-estimation terminology, the guard's actual
  intent per CONTEXT.md ("nothing in mics_link may know what a keypoint is").
- **Fix:** Implemented all five banned terms with `\b` word-boundary matching, consistent
  with `dlc`'s own explicitly word-boundary treatment and with the guard's stated intent.
  Verified this doesn't silently make the guard toothless: an out-of-band check confirms
  the pattern still matches a constructed "a DeepLabCut keypoint is a pose" sentence while
  correctly ignoring "this has a purpose and exposed data".
- **Files modified:** `sdk/tests/test_readme_contract.py` (written this way from the
  start, not retrofitted)
- **Verification:** ad-hoc Python check confirming both the true-positive and
  true-negative cases; full device-neutrality test parametrization (README + all examples
  + all `src/mics_link/*.py` files) passes
- **Committed in:** `ad9ffa7`

**4. [Rule 3 - Blocking issue] Dev host Python is PEP-668 externally-managed, blocking
`python3 -m pip install build`**
- **Found during:** Task 3, first command in the plan's own `<action>` block
- **Issue:** `python3 -m pip install build` fails with `error: externally-managed-environment`
  — the same class of failure 34-01 hit installing `mics_link` itself into this host's
  system Python.
- **Fix:** Created a throwaway venv (in the session scratchpad, not the repo) and ran
  `python -m build --wheel` through that venv's own `python`, targeting `sdk/` — does not
  touch the host Python at all, mirrors 34-01's own resolution for the analogous problem.
- **Files modified:** none (venv is not part of the repo)
- **Verification:** `sdk/dist/mics_link-0.1.0-py3-none-any.whl` built successfully;
  installs and imports from a throwaway `--target`
- **Committed in:** no commit needed (no tracked file changed)

**5. [Rule 1 - Bug, self-caught] README's callback example snippet omitted its own
imports, and one intro line was awkwardly wrapped**
- **Found during:** the plan's own required manual read-through pass, after Task 2's
  tests already passed
- **Issue:** Section 5's callback/push code block showed only the `with connect(...)`
  body, omitting `from mics_link import connect` / `from mics_link.values import
  as_scalar` present in the real `sdk/examples/callback_sender.py` — a reader could
  mistakenly conclude `as_scalar` is importable from the `mics_link` package root
  (it deliberately is not, see 34-06's key-decisions).
- **Fix:** Added both import lines to the README's callback snippet, matching the real
  file exactly; also rewrapped one overlong intro line for readability.
- **Files modified:** `sdk/README.md`
- **Verification:** full suite still green (274/274) after the edit; re-ran the
  device-neutrality and ASCII scans
- **Committed in:** `59a0f7e`

---

**Total deviations:** 5 (1x Rule 1 mandatory prerequisite fix across 7 pre-existing
files, 1x Rule 2 amendment-mandated file addition, 1x Rule 1 self-caught interpretation
fix in the new test, 1x Rule 3 blocking-issue PEP-668 workaround, 1x Rule 1 self-caught
readability fix from the plan's own required manual read-through). All were necessary for
correctness or directly required by this plan's own stated success criteria and
verification bar. No scope creep beyond what the "DLC-Live and Windows" amendment or this
plan's own Task 2 `<behavior>` block already mandated.

## Issues Encountered

None beyond the deviations documented above, all found and resolved during normal
execution.

## User Setup Required

None — no external service configuration required. Decision 5's narrowing (publishing the
wheel as a GitHub Release asset) is explicitly an OUTWARD-FACING action the user runs
themselves, not something this plan executes: **no `gh release create` command was run in
this session**, and none should be inferred as having happened. If the user wants the
wheel published as `https://github.com/idopo/Mics-backend/releases/download/sdk-v0.1.0/mics_link-0.1.0-py3-none-any.whl`
(the exact URL this README's install path 1 documents), they need to run something
equivalent to:
```
gh release create sdk-v0.1.0 sdk/dist/mics_link-0.1.0-py3-none-any.whl \
  --title "mics-link SDK v0.1.0" \
  --notes "mics-link 0.1.0 -- see sdk/README.md for install and usage."
```
Until that release exists, README install path 1 (the wheel URL) will 404; path 2
(`git+https`) and the offline wheel-copy fallback both work today.

## Next Phase Readiness

SDK-13 and the distribution half of SDK-01 are complete and tested. `sdk/README.md`,
`sdk/examples/ten_line_sender.py`, and `sdk/examples/callback_sender.py` are the complete
researcher-facing surface; `sdk/tests/test_readme_contract.py` keeps it honest against
future drift. Plan 34-09's rig checkpoint can proceed using this README as the literal
instructions a researcher would follow. Two things remain genuinely unverified until
human action: (1) the GitHub Release / wheel-URL install path, since no release has been
published (User Setup Required, above); (2) the git+https install against the real merged
`main`/`claude` branch, since this worktree's commits are not yet merged — the
worktree-branch-local form of the same mechanism is proven instead, and the merge itself
is the last missing step, not a design gap. No blockers to 34-09.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*

## Self-Check: PASSED

All claimed files verified present on disk (`sdk/README.md`,
`sdk/examples/ten_line_sender.py`, `sdk/examples/callback_sender.py`,
`sdk/tests/test_readme_contract.py`, `sdk/dist/mics_link-0.1.0-py3-none-any.whl`). All 4
task commits (`59b2151`, `f843001`, `ad9ffa7`, `59a0f7e`) verified present in `git log`.
Full `sdk/` suite: 274 tests green (227 baseline + 47 new), no regressions.
