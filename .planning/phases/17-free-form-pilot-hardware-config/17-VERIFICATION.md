---
phase: 17-free-form-pilot-hardware-config
verified: 2026-05-28T11:28:43Z
status: passed
score: 12/12 must-haves verified
---

# Phase 17: Free-Form Pilot Hardware Config Verification Report

**Phase Goal:** Decouple pilot_hardware_config from the hardware_modules registry so entries are free-form (pilot_id, name) key pairs with no FK dependency — mirroring Pi prefs.json HARDWARE dict structure. Frontend and backend consumers updated to use name-keyed lookups throughout.
**Verified:** 2026-05-28T11:28:43Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Plan 01)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | GET /api/pilots/{id}/hardware-config returns rows with {id, pilot_id, name, config} | VERIFIED | `pilot_hardware_config.py` list endpoint returns `{"id": r.id, "pilot_id": r.pilot_id, "name": r.name, "config": r.config}` — no `hardware_module_id` field (line 32) |
| 2 | PUT /api/pilots/{id}/hardware-config/{name} creates or updates a row keyed by name | VERIFIED | Route at line 37 uses `name: str` path param; upserts via `filter_by(pilot_id=pilot_id, name=name)` (lines 44–51) |
| 3 | DELETE /api/pilots/{id}/hardware-config/{name} removes the row by name | VERIFIED | Route at line 58 uses `name: str`; queries and deletes by name (lines 62–70) |
| 4 | Seed endpoint writes rows by name, mapping Pi 'class' key to config['class_name'] | VERIFIED | Seed POST at line 74; maps `"class"` → `config["class_name"]` (lines 86–88); no module lookup |
| 5 | Existing rows are preserved after migration (name backfilled from hardware_modules) | VERIFIED | Migration step 2 backfills `name` via JOIN on `hardware_module_id` only where `name IS NULL` (lines 226–232 of db.py) |

### Observable Truths (Plan 02)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 6 | Dispatch spec SQL uses WHERE name = :name instead of hardware_module_id | VERIFIED | `toolkit_dispatch.py` line 99: `" WHERE pilot_id = :pid AND name = :name"` — zero occurrences of `hardware_module_id = :mid` |
| 7 | Preflight validate SQL uses WHERE name = :name instead of hardware_module_id | VERIFIED | `toolkit_dispatch.py` line 235: `" WHERE pilot_id = :pid AND name = :name"` — confirmed by grep |
| 8 | Deleting a hardware module does NOT delete pilot hardware config rows | VERIFIED | `hardware_modules.py` has zero occurrences of `filter_by(hardware_module_id=module_id).delete()` and no `PilotHardwareConfig` import |
| 9 | HardwareCheckModal PUT URL uses encodeURIComponent(issue.module_name), not issue.module_id | VERIFIED | `HardwareCheckModal.tsx` line 179: `encodeURIComponent(issue.module_name)` |
| 10 | HardwareCheckModal does not strip class_name from config before saving | VERIFIED | No `delete configToSave['class_name']` anywhere in HardwareCheckModal.tsx; config merged as-is (line 177) |
| 11 | PilotHardwareConfig page shows free-form table: Name | class_name badge | Params | Edit/Delete | VERIFIED | Full rewrite at `PilotHardwareConfig.tsx` lines 168–252: table with Name/Class/Params/Actions columns; badge uses `status-running`; Edit and Delete buttons present |
| 12 | Add Entry form allows free-form name input with optional module picker for pre-fill | VERIFIED | Lines 255–309: free-form `<input>` for name, optional `<select>` for module pre-fill, JSON `<textarea>`, Add button |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `api/db.py` | `run_pilot_hw_config_name_migration()` with `uq_pilot_hw_config_pilot_name` | VERIFIED | Lines 214–278; all 5 idempotent migration steps present |
| `api/models.py` | `PilotHardwareConfig` with `name` col, nullable `hardware_module_id`, `uq_pilot_hw_config_pilot_name` | VERIFIED | Lines 705–713; model matches spec exactly |
| `api/routers/pilot_hardware_config.py` | Name-keyed CRUD endpoints (GET, PUT, DELETE, POST seed) | VERIFIED | 95 lines; all 4 routes present, spec-compliant |
| `api/routers/toolkit_dispatch.py` | Name-keyed SQL for dispatch and preflight | VERIFIED | Both SQL lookups use `WHERE name = :name`; no `hardware_module_id = :mid` |
| `web_ui/react-src/src/types/index.ts` | `PilotHardwareConfigRow` with `name: string` | VERIFIED | Line 435: `name: string`; `hardware_module_id` field removed from this interface |
| `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx` | Free-form config CRUD table + Add Entry form | VERIFIED | 312 lines (within 500-line hard limit); full rewrite confirmed |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `api/main.py` | `api/db.py` | `import run_pilot_hw_config_name_migration` + call at startup | WIRED | Line 14: imported; line 145: `run_pilot_hw_config_name_migration(engine)` called |
| `api/routers/pilot_hardware_config.py` | `api/models.py` | `PilotHardwareConfig` ORM model | WIRED | Line 11: imported; lines 30, 44, 51, 63, 80, 90: used with `filter_by(pilot_id=..., name=...)` |
| `web_ui/react-src/src/components/HardwareCheckModal.tsx` | `api/routers/pilot_hardware_config.py` | PUT `/api/pilots/{id}/hardware-config/{name}` | WIRED | Line 179: `apiFetch(...hardware-config/${encodeURIComponent(issue.module_name)}`, method PUT) |
| `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx` | `api/routers/pilot_hardware_config.py` | `upsertPilotHardwareConfig(pilotId, name, config)` | WIRED | Line 7–8: imported; lines 77, 84, 110, 148: used with name string parameter |

---

## Requirements Coverage

Requirements declared: HW-08, HW-11 (both plans). No `REQUIREMENTS.md` mapping to verify against — requirements are internal phase labels.

---

## Anti-Patterns Found

None. Zero occurrences of TODO/FIXME/PLACEHOLDER/XXX across all 9 modified files.

File sizes within limits:
- `api/routers/pilot_hardware_config.py`: 95 lines (under 150-line plan limit)
- `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx`: 312 lines (12 over 300-line soft limit, under 500-line hard limit — not a blocker)

---

## Commits Verified

All 6 commits referenced in summaries confirmed present in git log:

| Commit | Description |
|--------|-------------|
| `0201210` | DB migration for name-keyed pilot_hardware_config |
| `06b0cbc` | Update PilotHardwareConfig ORM model and wire migration |
| `e50863d` | Rewrite pilot_hardware_config router as name-keyed |
| `8e43fda` | Name-keyed SQL for dispatch+preflight, remove cascade delete |
| `56e1965` | Name-keyed TS types, API client, and HardwareCheckModal |
| `3a47b6a` | Rewrite PilotHardwareConfig — free-form table + Add Entry form |

---

## Human Verification Required

### 1. Preflight pass with name-keyed config

**Test:** Start a session on a pilot that has hardware config rows (populated by name). Trigger a preflight check for a backend-authored toolkit that references those hardware modules.
**Expected:** Preflight passes — no "missing config" errors — confirming the name-based SQL lookup resolves correctly against named rows from the Pi HANDSHAKE or seed.
**Why human:** Requires a running system with a real pilot that has HANDSHAKE-seeded config rows; cannot verify the SQL join between `hardware_module_ids` on toolkit and `name` on config rows without a live DB.

### 2. Add Entry via module pre-fill

**Test:** Open the Hardware Config page for a pilot. In Add Entry, select a module from the picker; verify the JSON textarea pre-fills with `{"class_name": "<module class>"}`. Enter a free-form name and click Add.
**Expected:** New row appears in the table with the chosen name (not constrained to any module registry name).
**Why human:** React rendering and form interaction cannot be verified by grep.

---

## Summary

Phase 17 goal is fully achieved. All 12 must-have truths verified against the actual codebase:

- DB migration adds the `name` column, backfills from `hardware_modules`, drops the old FK-based unique constraint, makes `hardware_module_id` nullable, and adds `uq_pilot_hw_config_pilot_name`. Migration is idempotent and wired into startup.
- The ORM model reflects the new identity key.
- The router is a clean 95-line rewrite with GET/PUT/DELETE/seed all operating on `name` strings.
- Both SQL consumers (dispatch spec and preflight validation) use `WHERE name = :name`. No `hardware_module_id = :mid` SQL remains.
- The cascade-delete line was removed from `hardware_modules.py`; config rows are now independent of the module registry.
- TypeScript: `PilotHardwareConfigRow.name: string` replaces `hardware_module_id: number`; API client uses `encodeURIComponent(name)`; HardwareCheckModal keys by `module_name` and no longer strips `class_name`.
- The React page is a free-form table mirroring prefs.json structure with inline JSON edit and Add Entry form.

No stubs, no orphaned artifacts, no anti-patterns.

---

_Verified: 2026-05-28T11:28:43Z_
_Verifier: Claude (gsd-verifier)_
