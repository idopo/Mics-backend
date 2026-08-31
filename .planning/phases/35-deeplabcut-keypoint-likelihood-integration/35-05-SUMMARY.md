---
phase: 35-deeplabcut-keypoint-likelihood-integration
plan: 05
subsystem: infra
tags: [python, deeplabcut, pandas, pytables, csv, replay]

# Dependency graph
requires:
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 03)
    provides: "dlc_link.generate/generate_cli, dlc_link.config_read (BodypartSource, read_dlc_config)"
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 04)
    provides: "dlc_link.signal_map.load_signal_map (the loaded record convert.py's flatten_columns indexes)"
provides:
  - "dlc_link.convert: flatten_columns/rows_to_wide/write_wide_csv (pure) and read_h5 (pandas.read_hdf on the PyTables backend, never h5py)"
  - "dlc_link.convert_cli: the dlc-link-convert CLI, D-44's write-location refusal (own directory or any ancestor DLC project root detected by a sibling config.yaml), and the atomic same-directory temp-file write"
  - "dlc_link/tests/test_replay_roundtrip.py: proof the converter's output is consumable by sdk/src/mics_link/replay_io.py's real reader and drivable by mics_link.replay.replay, with zero skips"
affects: [35-06, 35-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Suffix-convention grouping, not identifier re-derivation: _likelihood_groups groups already-emitted signal NAMES by the <ident>_likelihood/<ident>_x/<ident>_y suffix convention dlc_link.names.signal_names_for documents, to know which x/y cells to blank on a below-threshold likelihood -- this parses the convention of already-safe identifiers, it does not re-derive an identifier from a bodypart string (the D-12/T-35-01 boundary stays in dlc_link.names alone)"
    - "convert.py split into convert.py (pure core + read_h5) plus convert_cli.py (argparse + D-44 + atomic write), mirroring plan 35-03's generate.py/generate_cli.py split, to satisfy the 300-line production-file standard"
    - "pandas imported inside read_h5 only, never at module scope; every pandas/numpy-typed value converted to a plain Python scalar via _to_plain (.item()) at that one boundary so nothing pandas-typed crosses back into the pure core"

key-files:
  created:
    - dlc_link/src/dlc_link/convert.py
    - dlc_link/src/dlc_link/convert_cli.py
    - dlc_link/tests/test_convert.py
    - dlc_link/tests/test_replay_roundtrip.py
  modified: []

key-decisions:
  - "convert.py split into convert.py + convert_cli.py (same shape as generate.py/generate_cli.py and live.py/live_probe.py from plans 35-03/35-04): the pure core plus read_h5 alone is 296 lines, and adding the full argparse CLI + D-44 refusal + atomic-write mechanics would have pushed it well past 300. dlc_link.convert.main is a thin lazy-import re-export so the declared console script (dlc-link-convert = dlc_link.convert:main, pyproject.toml, from plan 35-01) needs no change."
  - "D-44's write-location refusal for convert.py is stricter than generate_cli.py's: it checks two boundaries (the .h5's own directory, AND any ancestor of it that is a DLC project root, detected by walking up looking for a sibling config.yaml) rather than one, because a real DLC .h5 export commonly lives in a videos/ subdirectory nested well below the project root that itself is read-only."
  - "_likelihood_groups groups signal names by suffix (_likelihood/_x/_y) rather than by re-deriving the bodypart identifier -- documented explicitly in-code as a deliberate distinction from the D-12/T-35-01 boundary (dlc_link.names remains the sole bodypart-string-to-identifier declaration site)."
  - "Cells-emptied-by-likelihood counted in the CLI by comparing len(header_names) to len(values) per row as the wide-row generator is consumed, rather than adding a stats parameter to the pure rows_to_wide signature -- keeps rows_to_wide's signature exactly as the plan specifies (rows, position_to_name, fps, likelihood_threshold, start_t) with no stats/counter parameter."

requirements-completed: [DLC-09, DLC-03]

duration: ~55min
completed: 2026-08-31
---

# Phase 35 Plan 05: DeepLabCut Export-to-Replay Converter Summary

**Built `dlc-link-convert`: a DeepLabCut `.h5` export (3-level single-animal or 4-level single-animal-only multi-animal MultiIndex) becomes a wide replay CSV that the SDK's own reader and replay driver play back with zero malformed rows, occlusion surviving as genuinely empty cells, and the whole path exercised with no camera, GPU or trained model.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3/3 completed
- **Files modified:** 4 created, 0 modified

## Accomplishments
- `flatten_columns` turns a DeepLabCut export's 3-level `(scorer, bodypart, coord)` or 4-level `(scorer, individual, bodypart, coord)` column labels into an ordered `{position: signal_name}` mapping using only names present in the loaded signal map — never re-deriving the bodypart-to-identifier transform. A four-level export whose only individual is `single` flattens identically to the equivalent three-level export (the `LED_on`/`LED_off` unique-bodypart demo case); two or more real individuals raise `ConvertError` naming `single_animal=True` and listing every individual found.
- `rows_to_wide` reconstructs `t` from the frame index and the video's fps (a DLC export carries no time column) and blanks a bodypart's `x`/`y` cells — never a zero, never a hold — when that bodypart's likelihood for the row is below `--likelihood-threshold`, while the likelihood cell itself is always emitted with its real value.
- `write_wide_csv` emits the SDK's documented wide contract exactly: header `t` first, no header field literally `signal`, absent values as zero-length fields, `encoding="utf-8"`/`newline=""` for Windows correctness.
- `read_h5` imports `pandas` inside the function only and reads via `pandas.read_hdf` on the PyTables backend — `h5py` appears nowhere in `convert.py` or `convert_cli.py` (`grep -c h5py` returns 0 for both). Every value crossing back is converted to a plain Python scalar via `.item()`, so nothing pandas-typed reaches the pure core. A multi-key store without `--key` raises `ConvertError` listing the available keys; an absent `pandas` raises `ConvertError` naming the `convert` extra.
- `dlc-link-convert`'s D-44 refusal covers two boundaries: the `.h5`'s own directory, and any ancestor of it that is a DLC project root (detected by walking up for a sibling `config.yaml`) — since a real export commonly sits in a nested `videos/` subdirectory below the project root. The write itself goes through a temp file in `--out`'s own directory, renamed into place, proven never to touch an empty cwd.
- `dlc_link/tests/test_replay_roundtrip.py` drives the REAL `mics_link.replay_io.read_rows` and `mics_link.replay.replay` (no reimplementation) against a real generated-and-loaded signal map and a hand-built 6-frame confident/occluded/confident export: `stats.rows_malformed == 0`, the occluded stretch yields likelihood tuples with zero x/y tuples at those timestamps, and the written file's line count is exactly frame-count + 1 (D-31's wide-vs-long arithmetic) — zero skips, all four tests run for real on this dev host.
- 172 tests total in `dlc_link` (141 from plans 01/03/04 + 27 pure-core/CLI `test_convert.py` + 4 `test_replay_roundtrip.py`), 3 skipped (the `pandas`/`tables`-dependent `read_h5` tests, correctly, since neither is installed on this dev host), everything else green.

## Task Commits

Each task was committed atomically:

1. **Task 1: The pure flatten-and-write core, with the wide contract asserted** - `ac9076f` (feat)
2. **Task 2: The pandas.read_hdf reader and the dlc-link-convert CLI** - `8d4bcaa` (feat)
3. **Task 3: Round-trip the converter output through the SDK's own replay reader** - `9faf34a` (test)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `dlc_link/src/dlc_link/convert.py` - `ConvertError`, `flatten_columns`, `rows_to_wide`, `write_wide_csv` (pure), `read_h5` (pandas-inside-function), thin `main()` re-export
- `dlc_link/src/dlc_link/convert_cli.py` - argparse CLI, `_check_out_not_in_dlc_project` (D-44, two boundaries), `_write_atomically` (temp file beside `--out`), summary printing
- `dlc_link/tests/test_convert.py` - 27 tests: column-shape variants, skip/raise rules, occlusion suppression, CSV writing, pandas-guarded `read_h5` tests (3 skip here), CLI `--help`/argparse-required/D-44/atomic-write tests
- `dlc_link/tests/test_replay_roundtrip.py` - 4 tests: real reader/replay round trip, wide-shape detection, `FakeLink`-driven send counts, D-31 line-count arithmetic

## Decisions Made
- **`convert.py` split into `convert.py` + `convert_cli.py`:** same reasoning and shape as plan 35-03's `generate.py`/`generate_cli.py` split and plan 35-04's `live.py`/`live_probe.py` split — the pure core plus `read_h5` alone reached 296 lines, and the full CLI (argparse, D-44's two-boundary check, atomic write, summary) would have pushed the file well past the 300-line production standard. `dlc_link.convert.main` stays a thin lazy-import wrapper so `dlc-link-convert = dlc_link.convert:main` (pyproject.toml, unchanged from plan 35-01) needs no edit.
- **D-44 check covers two boundaries, not one:** `generate_cli.py`'s `_check_out_dir_not_in_project` only checks the config's own directory. `convert_cli.py`'s `_check_out_not_in_dlc_project` additionally walks up from the `.h5`'s directory looking for a sibling `config.yaml`, because a real DLC `.h5` export lives in a `videos/` subdirectory nested below the project root — checking only the `.h5`'s own directory would miss an `--out` placed in a *different* subdirectory of the same read-only project.
- **`_likelihood_groups` groups signal names by suffix convention, not by re-deriving an identifier:** `rows_to_wide`'s fixed signature (`rows, position_to_name, fps, likelihood_threshold, start_t`) carries no bodypart-grouping structure, so grouping which `x`/`y` cells belong to which likelihood must happen from `position_to_name`'s own signal-name strings. Stripping the `_likelihood`/`_x`/`_y` suffix that `dlc_link.names.signal_names_for` already documents as its output convention is parsing an already-safe identifier's known shape, not re-deriving an identifier from a researcher-authored bodypart string — the actual D-12/T-35-01 boundary, which stays exclusively in `dlc_link.names`. Documented as such in-code so a future reader does not conflate the two.
- **Cells-emptied-by-likelihood counted by the CLI, not by `rows_to_wide` itself:** rather than add a stats/counter parameter to `rows_to_wide` (which the plan's literal signature does not include), `convert_cli.main` wraps the generator and computes `len(header_names) - len(values)` per row as it consumes them for the summary print. `rows_to_wide`'s signature matches the plan exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The module's own docstring/comments tripped the plan's own `grep -c h5py` verify check**
- **Found during:** Task 1, first draft of `convert.py`
- **Issue:** The module docstring and `read_h5`'s docstring both explained the D-09c constraint using the literal word `h5py` in prose (e.g., "`h5py` is ABSENT from the target env"), which is exactly the substring the plan's own automated verify command (`grep -c "h5py" src/dlc_link/convert.py`) checks is zero — the same self-defeating-comment pattern plan 35-03's summary documented for `@command` and plan 35-04's for `cv2`.
- **Fix:** Reworded every occurrence to "the HDF5 binding that `pandas.read_hdf` would otherwise prefer" / "the other common HDF5 binding," preserving the same documented rationale (D-09c) without the literal substring.
- **Files modified:** `dlc_link/src/dlc_link/convert.py`
- **Verification:** `grep -c h5py src/dlc_link/convert.py src/dlc_link/convert_cli.py` returns 0 for both files; the negative-assertion test `test_convert_module_has_no_h5py_reference` passes.
- **Committed in:** `ac9076f` (Task 1 commit) and `8d4bcaa` (Task 2 commit, `read_h5`'s own docstring)

**2. [Rule 3 - Blocking issue, pre-existing, out of scope] `dlc_link/pyproject.toml` already contains the literal string `h5py`**
- **Found during:** final verification (`grep -rc h5py dlc_link/`)
- **Issue:** The plan's own `<verification>` block states `grep -rc h5py dlc_link/` should return 0 for every file, but `dlc_link/pyproject.toml` line 30 (`# h5py is deliberately absent from every extra above...`) already contains the substring — this line was added in plan 35-01 (`e62de85`), before this plan started, and is itself a correct, deliberate statement of D-09c (h5py is not a dependency; the comment documents its absence).
- **Fix:** None applied — this is a pre-existing file this plan's `files_modified` list does not include (only `convert.py`, `test_convert.py`, `test_replay_roundtrip.py` are declared), and the mention is documentation of the correct behavior (h5py genuinely absent from every dependency list), not a defect. Per the scope boundary rule, pre-existing conditions in files outside this plan's declared scope are logged, not fixed.
- **Files modified:** none
- **Verification:** `grep -c h5py dlc_link/pyproject.toml` returns 1 (the comment); `grep -c h5py dlc_link/src/dlc_link/convert.py dlc_link/src/dlc_link/convert_cli.py` returns 0 for both — h5py is not declared as a dependency anywhere and is not imported anywhere in the module this plan owns.
- **Committed in:** not applicable (no change made)

---

**Total deviations:** 2 (1 Rule 1 — a literal-text requirement and the plan's own automated grep check interacted the same way plans 35-03/35-04 already documented; 1 pre-existing, out-of-scope, no fix applied)
**Impact on plan:** No scope creep. The Rule 1 fix is a narrow rewording with no logic change. The pre-existing pyproject.toml comment is correct as written and outside this plan's declared files.

## Issues Encountered
- Worktree HEAD was initially on `b4831f7a4...` (behind the required base `1bf41b06d38be64d0bce3903976f7850efa3fbfb`, which contains plans 35-01 through 35-04 merged plus the phase-tracking update after wave 3). Working tree was clean, so `git reset --hard 1bf41b06d38be64d0bce3903976f7850efa3fbfb` was run per the mandatory worktree-branch-check before any plan work began; branch remained `worktree-agent-a3a0d99b0de6d3bf9` throughout.
- `docker compose exec -T api python -m pytest -q tests/` (the backend 452-pass baseline) was not run in this isolated worktree — no docker services are running under this worktree's own compose project, consistent with plans 35-01/35-03/35-04's summaries noting the same limitation. This plan makes zero changes to `api/` or `sdk/` (`git status --porcelain sdk/ api/` confirmed empty), so the baseline is not expected to be affected.

## User Setup Required

None — no external service configuration required. This plan installs nothing; `pandas`/`tables` are already declared as the `convert` extra (plan 35-01) and their absence on this dev host correctly SKIPs the three `read_h5` tests that need them, without affecting any other test.

## Next Phase Readiness

- `dlc_link.convert`/`convert_cli` are ready for plan 35-06 (generating and uploading the real demo lib against the target project, and exercising the converter against a real DeepLabCut `.h5` export produced by `analyze_videos` against the copied project) and plan 35-07 (the likelihood-distribution measurement that supplies `--likelihood-threshold`'s value, per D-41).
- `sdk/` and `api/` are both untouched by this plan (`git status --porcelain sdk/ api/` is empty).
- The full `dlc_link` test suite (172 tests: 168 passed here plus the 4 round-trip tests, 3 skipped) is green on the dev host with `dlclive`/`torch`/`cv2`/`pandas` all absent, confirming the plan's core objective end-to-end: the whole DLC path is replayable with no camera, no GPU and no trained model.
- The `--likelihood-threshold` flag intentionally has no default and will not produce a usable conversion until plan 35-07 measures the real value; this is stated in the CLI's own `--help` text (naming `pcutoff` and D-41).

## Self-Check: PASSED

All 4 created files verified present on disk (`convert.py`, `convert_cli.py`, `test_convert.py`, `test_replay_roundtrip.py`); all 3 task commit hashes (`ac9076f`, `8d4bcaa`, `9faf34a`) verified present in git history.
