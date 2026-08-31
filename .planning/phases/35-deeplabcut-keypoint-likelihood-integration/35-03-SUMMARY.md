---
phase: 35-deeplabcut-keypoint-likelihood-integration
plan: 03
subsystem: infra
tags: [python, ast, codegen, deeplabcut, security]

# Dependency graph
requires:
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 01)
    provides: "dlc_link.names.build_name_map (the single name/index transform), dlc_link.decimate.RECOMMENDED_DEFAULTS (the 10Hz/60msg-s budget)"
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 02)
    provides: "the canonical clock-consistent liveness_hook snippet (D-49..D-51 workaround)"
provides:
  - "dlc_link.config_read: config.yaml/pose_cfg.yaml readers resolving all three bodypart sources (flat/multianimal/unique), the MULTI! sentinel trap, provenance, and the identity/D-37 warning"
  - "dlc_link.templates: render_lib_source / render_signal_map, pure string rendering with whole-block repr() docstring safety (T-35-09)"
  - "dlc_link.generate / dlc_link.generate_cli: the dlc-link-generate CLI plus the D-15 generation-time validation gate re-parsing the RENDERED text"
  - "dlc_link/tests/test_generate_ast_contract.py: proof the emitted source is consumable by the real api/extlink_ast.py extractor"
affects: [35-04, 35-06, 35-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Whole-block repr() for any docstring embedding researcher-controlled text: build the full text as a plain runtime string, then emit repr(that_text) as the single literal token, so a stray triple-quote/backslash can never corrupt the enclosing source (T-35-09)"
    - "Re-parse-and-validate: the D-15 gate runs ast.parse on the RENDERED text and re-extracts signal specs, never trusting that the template did the right thing"
    - "Split a >300-line CLI module into a thin re-exported main() plus a _cli module, to satisfy the 300-line production-file standard without breaking the pyproject.toml console-script target"

key-files:
  created:
    - dlc_link/src/dlc_link/config_read.py
    - dlc_link/src/dlc_link/templates.py
    - dlc_link/src/dlc_link/generate.py
    - dlc_link/src/dlc_link/generate_cli.py
    - dlc_link/tests/test_config_read.py
    - dlc_link/tests/test_generate.py
    - dlc_link/tests/test_generate_ast_contract.py
    - dlc_link/tests/fixtures/dlc3_multianimal_config.yaml
    - dlc_link/tests/fixtures/dlc3_singleanimal_config.yaml
    - dlc_link/tests/fixtures/tf_pose_cfg.yaml
    - dlc_link/tests/fixtures/pose_order_declared.txt
  modified: []

key-decisions:
  - "Added an `identity: Optional[bool]` field to BodypartSource beyond the plan's literal field list, because warn_multianimal_identity(source) has no other way to read the config's identity key without it (Rule 2 - missing critical functionality)"
  - "Docstring safety uses ONE whole-block repr() per docstring rather than per-value repr() embedded in hand-written triple-quoted text: per-value repr() alone cannot prevent a researcher-controlled value from containing an unescaped triple-quote (Python's repr() only escapes the delimiter it chooses, and a string containing BOTH quote types forces single-quote delimiting, leaving embedded triple-double-quotes unescaped). Building the full text as a runtime string first and repr()-ing the whole thing guarantees valid Python source regardless of content."
  - "generate.py split into generate.py (core: GenerationError, generate(), the D-15 gate) and generate_cli.py (argparse + the D-44/D-46 refusal), to satisfy the 300-line production-file limit (generate.py alone would have been ~513 lines). dlc_link.generate.main is a thin lazy-import wrapper so pyproject.toml's `dlc-link-generate = dlc_link.generate:main` console script target is unaffected."
  - "The D-39 'must not select every candidate' gate is skipped when source.source_format == 'explicit-list': in that mode the source's own candidate list IS --bodyparts by construction (there is no larger config-declared universe to narrow from), so applying the gate there would make D-10's documented escape hatch permanently unusable."
  - "api/extlink_keys.py (and api/lib_version_resolution.py, which it imports) pull in sqlalchemy at module scope for functions the AST-contract test never calls. Rather than installing sqlalchemy (excluded from auto-fix; package installs need human legitimacy verification) or vendoring derive_extlink_keys's logic (explicitly forbidden), the test injects a minimal sys.modules stub satisfying that unrelated import. The real, unmodified derive_extlink_keys still executes."

requirements-completed: [DLC-02, DLC-03, DLC-05, DLC-13]

duration: 55min
completed: 2026-08-31
---

# Phase 35 Plan 03: DeepLabCut Config Reader and Hardware-Lib Generator Summary

**Built `dlc-link-generate`: one CLI that reads a DeepLabCut config.yaml (handling the MULTI! multi-animal sentinel and all three bodypart sources), and turns an explicit bodypart selection into a paired ExternalHardware lib source and signal map, refusing every D-15 declaration that would fail late and lethally on the rig, proven consumable by the real backend AST extractor.**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-31T11:05Z (approx)
- **Completed:** 2026-08-31T11:52Z
- **Tasks:** 3/3 completed
- **Files modified:** 11 created, 0 modified

## Accomplishments
- `config_read.py` resolves all three DLC bodypart sources (flat `bodyparts`, `multianimalbodyparts`+`individuals`, `uniquebodyparts`) from either `config.yaml` (pytorch) or `pose_cfg.yaml` (tensorflow), never iterates the `MULTI!` sentinel, counts 72 declarable candidates on the real transcribed project config, and warns when post-hoc identity (`stitch_tracklets`) makes per-individual signals unsafe.
- `dlc-link-generate` emits a paired `ExternalHardware` lib source and machine-readable signal map from one command; the lib source has zero egress path (verified by scanning the RENDERED text for `self.send(`/`_egress_probe`/`on_run_start`/`on_run_stop`), no `release()` override, and no `@command`/`@event` methods.
- Every D-15 failure mode (`stale_after_ms==0`, illegal/`return_none` `stale_policy`, missing `-> float`/`default=0.0`) is refused by re-parsing the rendered source with `ast`, never by trusting the template.
- D-39's message budget (default 6 signals = 60 msg/s at the 10Hz decimator cap) and the "no emit-everything" refusal are enforced with the arithmetic shown in the error message.
- D-44/D-46: `--out-dir` is required (no default of `.`), and a `commonpath`-based, case/symlink-resolved check refuses to write into the config's own directory or any descendant of it, while a sibling directory sharing a name prefix correctly succeeds.
- `test_generate_ast_contract.py` proves the emitted source is registered by the real `api/extlink_ast.extract_extlink_metadata` with exactly the expected signal set, `float` dtypes, correct per-kind `stale_policy`, and demonstrates D-36's forced runbook ordering via the real `api/extlink_keys.derive_extlink_keys` — 7 tests, zero skips.
- 90 tests total in `dlc_link` (30 from plan 01 + 15 config_read + 38 generate + 7 ast-contract), all green, `dlclive`/`torch`/`cv2`/`pandas` all absent.

## Task Commits

Each task was committed atomically:

1. **Task 1: config.yaml and pose_cfg.yaml readers with recorded provenance** - `81ba6bc` (feat)
2. **Task 2: The source templates, the generator CLI, and the generation-time validation gate** - `ab7c87f` (feat)
3. **Task 3: Prove the emitted source is consumable by the real backend AST extractor** - `0b079dc` (test)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `dlc_link/src/dlc_link/config_read.py` - `BodypartSource`, `load_yaml` (ruamel/PyYAML dual backend), `read_dlc_config`, `read_pose_cfg`, `from_explicit_list`, `select`, `warn_multianimal_identity`
- `dlc_link/src/dlc_link/templates.py` - `render_lib_source`, `render_signal_map`; the canonical `liveness_hook` snippet embedded verbatim; whole-block `repr()` docstring safety
- `dlc_link/src/dlc_link/generate.py` - `GenerationError`, `GenerationResult`, `generate()`, the D-15 re-parse validation gate; thin `main()` re-export
- `dlc_link/src/dlc_link/generate_cli.py` - argparse CLI, the D-44/D-46 out-dir-not-in-project refusal
- `dlc_link/tests/test_config_read.py` - 15 tests: sentinel handling, candidate counting, class-labelled `select()`, identity warning, PyYAML fallback
- `dlc_link/tests/test_generate.py` - 38 tests: signal counts, D-39/D-44/D-46/allow-signals refusals, pose-order provenance, no-egress assertion, sha256 pairing, CLI file-write behaviour
- `dlc_link/tests/test_generate_ast_contract.py` - 7 tests against the real `api/extlink_ast.py`/`api/extlink_keys.py`
- `dlc_link/tests/fixtures/dlc3_multianimal_config.yaml` - transcribed from the real target project's config.yaml (72 candidates)
- `dlc_link/tests/fixtures/dlc3_singleanimal_config.yaml`, `tf_pose_cfg.yaml`, `pose_order_declared.txt` - hand-written schema fixtures

## Decisions Made
- **`identity` field added to `BodypartSource`:** the plan's literal field list for `BodypartSource` omits `identity`, but `warn_multianimal_identity(source)` has no other way to read the config's `identity` key. Added as `Optional[bool]`, populated from `config.yaml`'s `identity` key in `read_dlc_config`, `None` elsewhere. (Rule 2 — missing critical functionality.)
- **Whole-block `repr()` for docstrings, not per-value:** analysed that per-value `repr()` embedded inside a hand-written `"""..."""` block cannot fully prevent a triple-quote collision (Python's `repr()` only escapes the ONE delimiter character it chooses; a string containing both `'` and `"` forces single-quote delimiting, leaving embedded `"""` unescaped). Building the full docstring text as a plain runtime string and then emitting `repr(full_text)` as the single literal token in the rendered source is the provably safe construction, since `repr()` of any `str` is guaranteed to be syntactically valid Python source. Individual values are still shown via `!r` formatting WITHIN that text for readability before the outer `repr()` wraps the whole thing.
- **`generate.py` split into `generate.py` + `generate_cli.py`:** the plan's single-file design for the CLI + validation gate would have been ~513 lines, over the project's 300-line production-file standard (hard limit 500). Split argparse/file-writing into `generate_cli.py`; `dlc_link.generate.main()` is a thin lazy-import wrapper so the declared `dlc-link-generate = dlc_link.generate:main` console script (pyproject.toml, from plan 35-01) needs no change. Both files are under 300 lines (284 and 193 respectively).
- **D-39 refuse-all-candidates gate exempted for explicit-list mode:** discovered while testing that in explicit-list mode (no `--config`/`--pose-cfg`), the source's own candidate list is constructed FROM the same `--bodyparts` flag as `wanted`, so it always equals `wanted` by construction — applying the "don't select every candidate" gate there would make D-10's documented escape hatch (generating a demo lib before the real config is in hand) permanently unusable. Exempted `source_format == "explicit-list"` from that specific check; the budget (`--allow-signals`) and every D-15 check still apply unconditionally.
- **sqlalchemy stub for the AST-contract test, not a package install:** `api/extlink_keys.py` (and the `api/lib_version_resolution.py` it imports) import `sqlalchemy` at module scope for functions (`pilot_extlink_keys`, `module_extlink_signals`) this test never calls; `derive_extlink_keys` itself is pure. The dev host outside the `api` Docker image has no `sqlalchemy` installed. Per the deviation rules, a `pip install` is excluded from auto-fix (package-legitimacy risk) even though `sqlalchemy` is already a first-party pinned dependency of this exact repository. Vendoring `derive_extlink_keys`'s logic is explicitly forbidden by the plan. Resolved with a minimal `sys.modules["sqlalchemy"]` stub (a `ModuleType` with a no-op `text` attribute) installed only if the real package is absent — the actual `derive_extlink_keys` function that runs is 100% the real, unmodified file.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] `BodypartSource` needed an `identity` field**
- **Found during:** Task 1
- **Issue:** The plan's field list for `BodypartSource` does not include `identity`, but `warn_multianimal_identity(source)` (required by the same task) must read the config's `identity` key to decide whether to warn.
- **Fix:** Added `identity: Optional[bool] = None` to `BodypartSource`, populated from `config.yaml`'s `identity` key (strict bool check; `None` when absent or not a bool) in `read_dlc_config`. `read_pose_cfg`/`from_explicit_list` leave it `None`.
- **Files modified:** `dlc_link/src/dlc_link/config_read.py`
- **Verification:** `test_warn_multianimal_identity_false_names_stitch_tracklets` / `test_warn_multianimal_identity_true_is_none` pass.
- **Committed in:** `81ba6bc` (Task 1 commit)

**2. [Rule 3 - Blocking issue] Comment text "No @command methods" defeated the plan's own verify script**
- **Found during:** Task 2 verification (the plan's literal `<verify>` command asserts `'@command' not in lib`)
- **Issue:** My first draft of `render_lib_source` documented the deliberate omission of command-decorated methods with a comment containing the literal substring `@command`, which the plan's own automated check (correctly) treats as evidence a `@command` decorator was emitted.
- **Fix:** Reworded the comment to "No command-decorated methods" / "No event-decorated methods", preserving the same documented rationale without the literal `@command` substring.
- **Files modified:** `dlc_link/src/dlc_link/templates.py`
- **Verification:** Plan's exact verify block (`assert 'def release' not in lib and '@command' not in lib`) passes; re-ran full generation end-to-end.
- **Committed in:** `ab7c87f` (Task 2 commit)

**3. [Rule 1 - Bug] The D-39 "refuse every candidate" gate made D-10's explicit-list escape hatch unusable**
- **Found during:** Task 2, writing `test_no_config_flag_falls_back_to_explicit_list_with_warning`
- **Issue:** In explicit-list mode (no `--config`/`--pose-cfg`), `from_explicit_list(bodyparts)` builds the source's candidate list directly from `--bodyparts`, so `wanted` always equals the full candidate set by construction, and the D-39 gate would refuse EVERY explicit-list invocation, defeating D-10's purpose (generate a demo lib before the real config is available).
- **Fix:** Skip the "wanted covers every candidate" check when `source.source_format == "explicit-list"`. Every other D-15/D-39 check (the message budget, stale policy, etc.) still applies unconditionally in that mode.
- **Files modified:** `dlc_link/src/dlc_link/generate.py`
- **Verification:** `test_no_config_flag_falls_back_to_explicit_list_with_warning` passes; `test_wanted_covering_every_candidate_raises_d39` (config-backed mode) still correctly refuses.
- **Committed in:** `ab7c87f` (Task 2 commit)

**4. [Rule 3 - Blocking issue] sqlalchemy not installed on the dev host, breaking the AST-contract test's import of `api/extlink_keys.py`**
- **Found during:** Task 3 verification
- **Issue:** `api/extlink_keys.py` imports `sqlalchemy` at module scope (via itself and `api/lib_version_resolution.py`) for functions unrelated to `derive_extlink_keys`. The dev host (outside the `api` Docker image) has no `sqlalchemy` installed, so importing the module for the one pure function this test needs failed with `ModuleNotFoundError`.
- **Fix:** A `pip install sqlalchemy` is explicitly excluded from auto-fix (package-legitimacy checkpoint required, even for an already-pinned first-party dependency), and vendoring `derive_extlink_keys`'s logic is explicitly forbidden by the plan. Installed a minimal `sys.modules["sqlalchemy"]` stub (only when the real package is absent) exposing a no-op `text` attribute, satisfying the unrelated top-level import without installing anything or copying any logic — the real `derive_extlink_keys` function runs unmodified.
- **Files modified:** `dlc_link/tests/test_generate_ast_contract.py`
- **Verification:** `python3 -m pytest -q tests/test_generate_ast_contract.py -rs` reports 7 passed, 0 skipped, and does not import a vendored copy of any extractor logic.
- **Committed in:** `0b079dc` (Task 3 commit)

---

**Total deviations:** 4 (1 Rule 2 - missing field; 1 Rule 3 - self-defeating verify-script substring; 1 Rule 1 - bug in D-39's interaction with explicit-list mode; 1 Rule 3 - blocking missing host dependency worked around without installing or vendoring)
**Impact on plan:** No scope creep. All four fixes are narrow, documented, and either add a field the plan's own required behavior needed, fix wording to match the plan's own literal check, fix a real usability bug the plan's own D-10 intent requires, or unblock a real backend-import test without an unverified install or a vendored copy.

## Issues Encountered
- Initial worktree HEAD was on 3 unrelated commits ("initial commit", "added session", "able to stop and start task") rather than this repo's `d6cc43a` tip. Per the mandatory worktree-branch-check, `git reset --hard d6cc43ad5161b285061fb4223cbce83561cd7a29` was run (branch remained `worktree-agent-a424e25f7fa7167ae` throughout, `git status --short` was clean before the reset) before any plan work began.
- `docker compose exec -T api python -m pytest -q tests/` could not be run from this worktree (`service "api" is not running` under this worktree's own compose project name/network) — the `mics_api` container visible via `docker ps` belongs to the main checkout's compose project. This plan makes zero changes to `api/` or `sdk/` (`git status --porcelain api/ sdk/` is empty), so the 452-pass baseline is not expected to be affected; not spot-checked in this worktree, consistent with plan 35-01's summary noting the same limitation.

## User Setup Required

None — no external service configuration required. This plan performs no install; the one dependency gap encountered (`sqlalchemy`, dev-host-only, test-scoped) was worked around with a `sys.modules` stub rather than installed.

## Next Phase Readiness

- `dlc_link.config_read`, `dlc_link.templates`, and `dlc_link.generate`/`generate_cli` are ready for plan 35-04 (the live adapter, which imports the generated `<source_id>_signals.py` map) and plan 35-06/35-07 (which run `dlc-link-generate` against the real target project and demo lib).
- `sdk/`, `api/`, `/home/ido/mics_core/`, and `/home/ido/pi-mirror/` are all untouched by this plan (`git status --porcelain api/ sdk/` empty; `mics_core` clean; no files under `pi-mirror` were written by this session — its pre-existing dirty state predates this plan and was never touched).
- The full `dlc_link` test suite (90 tests) is green on the dev host with `dlclive`/`torch`/`cv2`/`pandas` all absent, confirming the plan's core objective end-to-end, including a live CLI run producing a valid, `ast`-parseable, no-egress lib source and a correctly-paired signal map (`LIB_SHA256` verified against the actual lib bytes).

## Self-Check: PASSED

All 11 created files verified present on disk; all 3 task commit hashes (`81ba6bc`, `ab7c87f`, `0b079dc`) verified present in git history.
