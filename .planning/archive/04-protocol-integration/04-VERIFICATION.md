---
phase: 04-protocol-integration
verified: 2026-03-24T10:00:00Z
status: passed
score: 9/9 must-haves verified
gaps: []
human_verification:
  - test: "Start a session whose protocol step has a real task_definition_id with non-null fda_json"
    expected: "Orchestrator Docker logs show 'Injected state_machine from task_definition N into START payload for run R step 0'"
    why_human: "Requires a running Pi, live session, and actual task_definition rows with fda_json — cannot verify end-to-end injection path with grep alone"
  - test: "Open /react/protocols-create with at least one task definition in DB that has fda_json set"
    expected: "Palette shows display_name or task_name entries (not raw class names); clicking one opens param inputs from toolkit.params_schema; NTrials graduation field still visible"
    why_human: "Visual palette content depends on live DB data; cannot confirm UI renders correctly without a browser"
  - test: "Open overrides modal for a legacy protocol step (task_definition_id=null)"
    expected: "Param inputs still appear correctly using getLeafTasks fallback path"
    why_human: "Fallback branch logic verified in code but runtime behavior needs browser confirmation with an actual legacy protocol"
---

# Phase 04: Protocol Integration — Verification Report

**Phase Goal:** Wire task definitions into the protocol system — steps reference definitions, orchestrator injects FDA, canonical variant tracking enabled.
**Verified:** 2026-03-24
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | protocol_step_templates table has a task_definition_id nullable FK column | VERIFIED | `run_protocol_migrations()` in `api/db.py` line 75-83: `ALTER TABLE protocol_step_templates ADD COLUMN IF NOT EXISTS task_definition_id INTEGER REFERENCES task_definitions(id) ON DELETE SET NULL` |
| 2 | GET /api/protocols/{id} response includes task_definition_id per step | VERIFIED | `ProtocolStepTemplate` ORM model has `task_definition_id: Optional[int] = None` (models.py line 106); `ProtocolRead` uses `List[ProtocolStepTemplate]` — field flows through automatically |
| 3 | POST /api/protocols accepts task_definition_id per step | VERIFIED | `ProtocolStepTemplateCreate` has `task_definition_id: Optional[int] = None` (models.py line 210); `create_protocol()` passes `task_definition_id=s.task_definition_id` (main.py line 682) |
| 4 | Protocol builder palette shows task definitions (not raw leaf tasks) | VERIFIED | `ProtocolsCreate.tsx`: queries `getTaskDefinitions` + `getToolkits`; `paletteItems` filtered to `td.fda_json != null`; `addStep()` takes `TaskDefinitionFull`; no `getLeafTasks` import present |
| 5 | Step is saved with task_definition_id and params from toolkit.params_schema | VERIFIED | `ProtocolsCreate.tsx` mutation (line 104): `task_definition_id: s.task_definition_id`; `addStep()` (line 122-123): paramSpec from `toolkit?.params_schema` |
| 6 | Session start injects state_machine into Pi START payload when task_definition_id present | VERIFIED | Both `_build_first_step_task` (line 605) and `_build_step_task` (line 663) in `orchestrator_station.py`: `task_def_id = step.get("task_definition_id")` → calls `self.api.get_task_definition()` → sets `task["state_machine"] = task_def["fda_json"]` |
| 7 | Legacy steps (task_definition_id=null) are unaffected — no state_machine injected | VERIFIED | Both orchestrator functions guard with `if task_def_id:` — None return from `.get()` skips injection entirely |
| 8 | PATCH /api/toolkits/{id}/set-canonical marks one variant canonical; others become non-canonical | VERIFIED | `set_canonical_toolkit()` in `api/routers/toolkits.py` line 156-205: bulk UPDATE sets all variants of same name to `is_canonical=False`, then sets target to `is_canonical=True` |
| 9 | task_definitions response includes needs_migration=true when toolkit has non-canonical variants | VERIFIED | `list_task_definitions()` SELECT includes `needs_migration` column (line 253); response dict includes `"needs_migration": r.needs_migration` (line 265); set-canonical endpoint bulk-UPDATE sets needs_migration=TRUE for all definitions of that toolkit name |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/db.py` | `run_protocol_migrations()` + `run_canonical_migrations()` | VERIFIED | Both functions present at lines 75 and 86; called at startup in `api/main.py` lines 125-126 |
| `api/models.py` | `ProtocolStepTemplate.task_definition_id`; `ProtocolStepTemplateCreate.task_definition_id`; `TaskToolkit.is_canonical`; `TaskDefinition.needs_migration` | VERIFIED | Lines 106, 210, 602, 525 respectively; all substantive Column/Field declarations |
| `api/main.py` | `create_protocol()` saves task_definition_id; startup calls both migrations | VERIFIED | Line 682: `task_definition_id=s.task_definition_id`; lines 14, 125-126: import + startup calls |
| `orchestrator/orchestrator/orchestrator_station.py` | Both `_build_first_step_task` and `_build_step_task` read `step.get("task_definition_id")` | VERIFIED | Lines 605 and 663: `task_def_id = step.get("task_definition_id")`; no remaining `(step.get("params") or {}).get("task_definition_id")` pattern |
| `api/routers/toolkits.py` | `PATCH /toolkits/{id}/set-canonical`; `is_canonical` in toolkit response; `needs_migration` in task definitions response | VERIFIED | Endpoint at line 156; `_build_toolkit_row` includes `is_canonical` at line 54; `list_task_definitions` includes `needs_migration` at line 265 |
| `web_ui/react-src/src/pages/protocols-create/ProtocolsCreate.tsx` | Palette uses task definitions; `task_definition_id` in save payload; `graduation_ntrials` still present | VERIFIED | Queries `getTaskDefinitions`+`getToolkits`; `paletteItems` built from filtered task defs; save payload includes `task_definition_id`; `graduation_ntrials` field at lines 97-99 and rendered at line 280 |
| `web_ui/react-src/src/pages/pilot-sessions/OverridesModal.tsx` | toolkit params_schema used when step.task_definition_id present; getLeafTasks fallback kept | VERIFIED | Lines 265-271: `tdId = step.task_definition_id` → `taskDefById.get(tdId)` → toolkit lookup; falls back to `tasksByName.get(norm(step.task_type))?.default_params`; `getLeafTasks` still imported and queried at lines 4 and 89 |
| `web_ui/react-src/src/types/index.ts` | `ProtocolStep` interface has `task_definition_id?: number \| null` | VERIFIED | Line 120: `task_definition_id?: number \| null` present in `ProtocolStep` interface |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `api/db.py run_protocol_migrations()` | `api/main.py startup` | imported and called in lifespan | WIRED | `api/main.py` line 14 imports it; line 125 calls `run_protocol_migrations(engine)` |
| `api/main.py create_protocol()` | `ProtocolStepTemplate.task_definition_id` | `task_definition_id=s.task_definition_id` in constructor | WIRED | main.py line 682 passes the field |
| `api/db.py run_canonical_migrations()` | `api/main.py startup` | imported and called after run_protocol_migrations | WIRED | main.py line 126 calls `run_canonical_migrations(engine)` |
| `ProtocolsCreate.tsx addStep()` | `StepDraft.task_definition_id` | `TaskDefinitionFull.id` stored when user clicks palette item | WIRED | ProtocolsCreate.tsx line 127: `task_definition_id: td.id` in setSteps call |
| `ProtocolsCreate.tsx mutation` | `POST /api/protocols steps[].task_definition_id` | save payload includes field | WIRED | ProtocolsCreate.tsx line 104: `task_definition_id: s.task_definition_id` |
| `OverridesModal.tsx step.task_definition_id` | `ToolkitRead.params_schema` | client-side join via taskDefById + toolkitByName maps | WIRED | OverridesModal.tsx lines 265-271: lookup chain present and used in spec resolution |
| `orchestrator._build_first_step_task` | `step['task_definition_id']` | top-level step field from GET /api/protocols/{id} | WIRED | Line 605: `task_def_id = step.get("task_definition_id")` |
| `orchestrator._build_step_task` | `step['task_definition_id']` | top-level step field from GET /api/protocols/{id} | WIRED | Line 663: `task_def_id = step.get("task_definition_id")` |
| `orchestrator._build_step_task` | `self.api.get_task_definition(task_def_id)` | `MicsApiClient.get_task_definition()` | WIRED | Lines 608 and 666: call present in both functions with error handling |
| `PATCH /api/toolkits/{id}/set-canonical` | `task_definitions.needs_migration` | raw SQL UPDATE sets needs_migration=TRUE | WIRED | toolkits.py lines 180-186: `UPDATE task_definitions SET needs_migration = TRUE WHERE toolkit_name = :name` |

---

### Requirements Coverage

All requirement IDs claimed across plans for this phase: PROTO-01, PROTO-02, PROTO-03, PROTO-04, VAR-07.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROTO-01 | 04-01, 04-02 | Protocol step picker shows task definitions; params from toolkit params_schema | SATISFIED | ProtocolsCreate.tsx palette driven by `getTaskDefinitions`; paramSpec from `toolkit.params_schema` |
| PROTO-02 | 04-03 | Protocol step stores task_definition_id; session start injects fda_json as state_machine | SATISFIED | task_definition_id column on protocol_step_templates; orchestrator injects `task["state_machine"] = task_def["fda_json"]` |
| PROTO-03 | 04-01, 04-02 | GET /api/tasks/leaf deprecated; GET /api/task-definitions used instead | SATISFIED | ProtocolsCreate.tsx no longer imports getLeafTasks — replaced with getTaskDefinitions; OverridesModal uses getTaskDefinitions as primary (getLeafTasks retained as fallback only) |
| PROTO-04 | 04-02 | Overrides modal uses toolkit params_schema via task definition; fallback to task.default_params | SATISFIED | OverridesModal.tsx lines 265-271: params_schema used when task_definition_id present; tasksByName.get fallback for legacy steps |
| VAR-07 | 04-03 | PATCH /api/toolkits/{id}/set-canonical marks canonical; others flagged needs_migration=true | SATISFIED | set_canonical_toolkit endpoint implemented; is_canonical column on task_toolkits; needs_migration column on task_definitions |

No orphaned requirements: REQUIREMENTS.md maps exactly PROTO-01 through PROTO-04 and VAR-07 to Phase 4. All five are claimed and satisfied.

Note: The REQUIREMENTS.md phase tracking table (line 170) still shows "PROTO-01 through PROTO-04 | Phase 4 | Pending" — this is stale prose tracking, not the authoritative requirements list. The inline checkboxes at lines 84-87 show `[x]` for all four, and the code confirms implementation.

---

### Anti-Patterns Found

No blocker or warning-level anti-patterns found across the six modified files:

- No TODO/FIXME/HACK comments in changed files
- No stub return values (`return {}`, `return []`, `return null`)
- No console.log-only handlers
- No empty function bodies

---

### Human Verification Required

#### 1. End-to-end FDA injection into Pi START payload

**Test:** Create a task definition with `fda_json` set, build a protocol step that references it, start a session on a live pilot, and observe orchestrator logs.
**Expected:** Orchestrator Docker logs contain `Injected state_machine from task_definition <N> into START payload for run <R> step 0`
**Why human:** Requires a running Pi connected to the orchestrator, a real DB with populated task_definitions.fda_json, and an active session — cannot be verified via static analysis.

#### 2. Protocol builder palette visual display

**Test:** Navigate to `/react/protocols-create` with at least one task definition in the DB that has `fda_json != null`.
**Expected:** The left palette shows `display_name ?? task_name` labels sorted by toolkit_name, not raw Python class names. Clicking an item adds a step with param inputs driven by toolkit.params_schema. NTrials graduation input is still visible.
**Why human:** Visual UI content depends on live DB data; correct rendering cannot be confirmed from source code alone.

#### 3. Overrides modal fallback for legacy protocols

**Test:** Open the overrides modal for a protocol session whose steps have `task_definition_id = null`.
**Expected:** Param input fields still render correctly using the getLeafTasks fallback path (same behavior as before Phase 4).
**Why human:** Fallback branch is correct in the code, but runtime rendering with actual legacy data needs browser confirmation.

---

### Gaps Summary

No gaps. All automated checks passed. All truths are verified against actual code. The phase goal — "Wire task definitions into the protocol system — steps reference definitions, orchestrator injects FDA, canonical variant tracking enabled" — is fully achieved.

Three items require human confirmation because they depend on live DB data, a running pilot, or browser rendering. These are integration smoke tests, not evidence of missing implementation.

---

_Verified: 2026-03-24T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
