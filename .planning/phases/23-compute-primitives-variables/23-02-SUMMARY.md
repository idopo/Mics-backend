---
phase: 23-compute-primitives-variables
plan: 02
subsystem: api
tags: [fastapi, sqlalchemy, postgres, hardware-libs, compute-primitives, migrations]

# Dependency graph
requires:
  - phase: 23-01
    provides: "api/tests/test_hardware_lib_kind.py contract-pinning kind-column migration, seed_compute_ops_lib idempotency, and POST /api/hardware-libs kind='compute'/declared_imports behavior"
provides:
  - "hardware_libs.kind ('hardware'|'compute') + hardware_lib_versions.declared_imports columns, migrated idempotently via run_hardware_lib_kind_migration"
  - "_validate_compute_lib: release()-override gate (CMP-04/Pitfall 3) + stdlib-only declared_imports allowlist gate (CMP-19), enforced on both upload and source-update"
  - "api/seed_libs/compute_ops.py + api/seed_compute.py: the seed Compute Ops lib (13 ops, Hardware subclass) seeded idempotently at API startup as a stable hardware_libs row + COMPUTE hardware_modules row"
  - "api/compute_provisioning.py: auto-provisioning of the per-pilot pilot_hardware_config row a compute module needs before init_hardware() will instantiate it, wired into POST /api/hardware-modules"
affects: [23-03-fda-validation-compute, 23-04-pi-compute-dispatch, 23-05-lib-version-resolution, 23-06-gui-compute-action, 23-10-pi-deploy-and-rig-proof]

tech-stack:
  added: []
  patterns:
    - "kind column reuses the established run_*_migration(eng) ADD COLUMN IF NOT EXISTS shape from db.py, called once from main.py's startup migration block"
    - "_validate_compute_lib lazily imports seed_compute.COMPUTE_STDLIB_ALLOWLIST inside the function body (not module-level) to avoid a hardware_libs.py <-> seed_compute.py import-order dependency at API-module-load time"
    - "seed_compute_ops_lib runs raw SQL inside one engine.begin() transaction at startup, wrapped in try/except so a seeding failure never blocks API boot -- same posture as every run_*_migration function"
    - "compute_provisioning.py takes a caller-owned db session and commits nothing, matching hw_introspect.py's no-own-connection posture"

key-files:
  created:
    - api/seed_libs/compute_ops.py
    - api/seed_compute.py
    - api/compute_provisioning.py
  modified:
    - api/models.py
    - api/db.py
    - api/main.py
    - api/routers/hardware_libs.py
    - api/routers/hardware_modules.py
    - api/tests/test_hardware_lib_kind.py

key-decisions:
  - "_validate_compute_lib checks 'has release()' only for classes with an in-file base (ast.ClassDef.bases non-empty), found via a plain ast.walk (not a new hw_introspect walker) since hw_introspect has no public 'has bases' predicate -- resolve_class_methods is still reused for the method-existence check itself"
  - "declared_imports allowlist check is skipped entirely when declared_imports is empty, so the lazy `from seed_compute import COMPUTE_STDLIB_ALLOWLIST` import never fires for a plain compute upload with no declared imports -- this made 3 of 5 Wave-0 xfail route tests genuine passes in this plan's Task 1 alone, before seed_compute.py existed"
  - "_lib_dict gained a declared_imports field (from the active version) alongside kind, sourced from a concurrent sibling agent's commit (3190c15) that picked up my then-uncommitted working-tree edit -- verified byte-identical to what this plan needed, left as-is rather than re-committing"
  - "test_seed_compute_ops_lib_idempotent_created_flag_and_single_row deletes any pre-existing compute_ops.py lib row before asserting created=True on the first call, since the live api service's own startup seeding already ran against the same persistent dev DB this integration test runs against"

requirements-completed: [CMP-04, CMP-12, CMP-19]

# Metrics
duration: ~50min
completed: 2026-08-03
---

# Phase 23 Plan 02: Compute Lib Storage Substrate Summary

**One new `hardware_libs.kind` column + `declared_imports` field, a `release()`/stdlib-import upload gate, the seed Compute Ops lib (13 stdlib ops), and auto-provisioned per-pilot config rows — a compute lib now round-trips through upload → seed → module registration → per-pilot instantiation with zero Pi-side change.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-08-03 (session start)
- **Completed:** 2026-08-03T09:36:00Z
- **Tasks:** 3/3
- **Files modified:** 6 modified, 3 created

## Accomplishments

- `hardware_libs.kind` ('hardware'|'compute', default 'hardware') and `hardware_lib_versions.declared_imports` (JSONB) added via `run_hardware_lib_kind_migration`, idempotent (verified twice-in-a-row, no error, columns present exactly once).
- `POST /api/hardware-libs` and `PUT /api/hardware-libs/{id}` both gate `kind='compute'` uploads through `_validate_compute_lib`: a class with an in-file base lacking `release()` is rejected 422 naming `release()` and `Task.end()`; a `declared_imports` entry outside `seed_compute.COMPUTE_STDLIB_ALLOWLIST` is rejected 422 naming the offender and the allowlist; `kind not in ('hardware','compute')` is rejected 422.
- `api/seed_libs/compute_ops.py`: the 13 CONTEXT-locked stdlib ops (`random_choice`, `random_int`, `random_float`, `random_bool`, `assign`, `add`, `subtract`, `multiply`, `divide`, `modulo`, `minimum`, `maximum`, `clamp`) as a `Hardware` subclass with a mandatory `release()` no-op and `@log_action` on every op. No comparison/boolean-logic ops.
- `api/seed_compute.py::seed_compute_ops_lib(engine)` idempotently seeds that source as a `hardware_libs` row (`kind='compute'`), a v1 `hardware_lib_versions` row (`state='stable'`, `stable_reason='seed'`, both `active_version_id` and `stable_version_id` pointing at it), and a `COMPUTE` `hardware_modules` row — wired into `main.py` startup after the kind-column migration.
- `api/compute_provisioning.py::provision_compute_configs` auto-provisions the trivial `{"class_name": ...}` `pilot_hardware_config` row every registered pilot needs before a compute module will instantiate, wired into `create_hardware_module`. Verified live: creating a compute-kind module produced one config row per pilot (2/2 pilots); re-running provisioning created nothing new; an existing row (even with extra keys) is never touched.
- Full backend suite green throughout: 296 → 302 passed (net new tests from this plan), 1 skipped, 0 failed, at every task boundary.

## Task Commits

1. **Task 1: `kind` column, declared_imports, and the compute upload gate** - `7b490eb` (feat)
2. **Task 2: Seed compute lib source + idempotent seeding** - `a0ceebc` (feat)
3. **Task 3: Auto-provision the per-pilot config row for compute modules** - `b9a0519` (feat)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified

- `api/models.py` - `HardwareLib.kind`, `HardwareLibVersion.declared_imports`
- `api/db.py` - `run_hardware_lib_kind_migration` (idempotent ADD COLUMN IF NOT EXISTS)
- `api/main.py` - startup wiring: migration call + `seed_compute_ops_lib(engine)` (4-line total diff across both additions)
- `api/routers/hardware_libs.py` - `kind`/`declared_imports` threaded through `_lib_dict`/`_version_dict`/`_create_version`; new `_validate_compute_lib`; `upload_hardware_lib`/`update_hardware_lib_source` gate compute uploads
- `api/routers/hardware_modules.py` - `_module_row` gains `lib_kind`; `create_hardware_module` calls `provision_compute_configs`
- `api/seed_libs/compute_ops.py` (new) - the seed compute lib source
- `api/seed_compute.py` (new) - idempotent seeder + `COMPUTE_STDLIB_ALLOWLIST`
- `api/compute_provisioning.py` (new) - `compute_module_names`/`provision_compute_configs`
- `api/tests/test_hardware_lib_kind.py` - every Wave-0 skip/importorskip/xfail removed; added seed-source behaviour tests and compute-provisioning unit tests (17 tests total, all real passes)

## Decisions Made

See `key-decisions` in frontmatter. Summary: the release()-check scopes to classes with an in-file base (a plain `ast.walk`, not a new `hw_introspect` walker, since no public "has bases" predicate exists there); the stdlib-allowlist import is lazy so an upload with no `declared_imports` never touches `seed_compute` at all (this is what let 3 of 5 Wave-0 xfail tests become genuine passes in Task 1, before `seed_compute.py` existed in Task 2); the seed-idempotency test cleans up any row the live api service's own startup seeding already created against the shared dev DB, so "first call creates" is provable rather than an artifact of container boot order.

## Deviations from Plan

None — plan executed exactly as written, task order and file budgets all held (`db.py` 290 lines, `seed_compute.py` 105 lines, `compute_provisioning.py` 72 lines, `hardware_libs.py` growth 68 lines against an 80-line budget, `hardware_modules.py`'s router diff exactly 6 lines, `main.py`'s cumulative diff 4 insertions/1 deletion across both tasks).

One environmental complication, not a plan deviation: **this session ran concurrently with sibling executor agents on other Phase 23 plans (23-03, 23-04) in the same working tree.** Their in-progress, uncommitted edits to `api/fda_validation.py`, `api/fda_utils.py`, `api/routers/toolkits.py`, and several test files were visible in `git status`/`git diff` throughout this session and were never staged or committed by this plan — verified by diffing each touched file against a hand-edited patch before every `git add`, and once by reconstructing a clean per-hunk patch (`git apply --cached`) to strip a foreign hunk that had landed in the same file (`hardware_libs.py::_flag_broken_task_defs`) I was editing for Task 1. One of my own working-tree edits (`_lib_dict`'s `declared_imports` field) was itself swept into a sibling agent's commit (`3190c15`, plan 23-04) before I committed Task 2 — confirmed byte-identical to what this plan needed via `git show`, left as-is rather than re-committing or rewriting shared history.

## Issues Encountered

- `test_seed_compute_ops_lib_idempotent_created_flag_and_single_row` initially failed against the real (persistent, shared) dev DB: the live `api` container's own startup already seeds the same row before the test runs, so `created` was `False` on the test's first call too. Fixed by having the test delete any pre-existing seed row (lib + version + module) before asserting, mirroring the existing `_cmp12_probe` cleanup pattern in this same file.
- `_lib_dict` initially omitted `declared_imports`, causing `test_upload_compute_lib_declared_import_stdlib_only_accepted` to fail with `KeyError`. Fixed by adding it alongside `kind`.
- Concurrent-agent isolation (see Deviations) cost extra verification steps (`git diff`/`git show` audits before every stage) but did not require any functional rework.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The full compute-lib storage substrate (kind column, upload gate, seed lib, auto-provisioning) is live and verified against the real Postgres dev DB, not just mocks.
- Plan 23-05 (lib-version-resolution) can rely on `hardware_libs.kind`/`stable_version_id` being populated correctly for the seed lib (both `active_version_id` and `stable_version_id` point at v1, `state='stable'`) — its CMP-17 chain has something real to resolve.
- Plan 23-06 (GUI compute action) and the `HardwareLibs.tsx` `kind` filter chip can rely on every `GET /api/hardware-libs` row carrying `kind`, and every `GET /api/hardware-modules` row carrying `lib_kind`.
- Plans 23-03/23-04 (already executed by concurrent sibling agents per git history) consume `hardware_modules`/`hardware_libs.kind` directly; no coordination gap found — `git log` shows a clean linear history with each plan's commits interleaved but non-overlapping in content.
- Not yet done (per this plan's own scope): the toolkit-hardware_libs link step (`POST /toolkits/{id}/hardware-libs`) is unrelated to auto-provisioning (Pitfall 1, correctly not conflated) — a compute lib still needs to be added to a toolkit's `hardware_module_ids` separately before the Pi treats it as reachable; that wiring is unchanged by this plan and was already correct.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

- FOUND: api/seed_libs/compute_ops.py
- FOUND: api/seed_compute.py
- FOUND: api/compute_provisioning.py
- FOUND: api/tests/test_hardware_lib_kind.py
- FOUND commit: 7b490eb
- FOUND commit: a0ceebc
- FOUND commit: b9a0519
