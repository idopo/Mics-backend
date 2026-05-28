# Phase 17: Free-Form Pilot Hardware Config - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning
**Source:** Pre-designed plan from previous session (`/home/ido/.claude/plans/it-seems-like-the-glowing-hellman.md`)

<domain>
## Phase Boundary

Decouple `pilot_hardware_config` from the `hardware_modules` FK so entries are identified by `(pilot_id, name)` instead of `(pilot_id, hardware_module_id)`. This mirrors how the Pi's `prefs.json` HARDWARE dict works — free-form named entries, no persistent link to the module registry.

Scope: DB migration + model update + API router rewrite + dispatch/preflight SQL fix + cascade-delete removal + TypeScript types + API client + React page rewrite + HardwareCheckModal fix.

NOT in scope: any change to preflight logic beyond the SQL lookup (Phase 13 preflight behavior stays; only the WHERE clause changes).

</domain>

<decisions>
## Implementation Decisions

### DB Migration (locked)
- Add `name VARCHAR` column to `pilot_hardware_config`
- Backfill `name` from `hardware_modules.name` via JOIN for existing rows
- Drop `pilot_hardware_config_pilot_id_hardware_module_id_key` unique constraint
- Make `hardware_module_id` nullable (do not drop the column — keep for backward compat)
- Add `uq_pilot_hw_config_pilot_name UNIQUE (pilot_id, name)` constraint
- Migration goes in `api/db.py` as `run_pilot_hw_config_name_migration(eng)`, called at startup

### SQLAlchemy Model (locked)
- `name = Column(String, nullable=True)` added to `PilotHardwareConfig`
- `hardware_module_id` becomes `nullable=True`
- `__table_args__` unique constraint: `(pilot_id, name, name="uq_pilot_hw_config_pilot_name")`

### API Router Identity (locked)
- Path param changes from `module_id: int` to `name: str`
- Response shape: `{id, pilot_id, name, config}` — no `hardware_module_id` exposed
- `class_name` is stored inside `config` as provided by caller — no injection from DB

### Seed Endpoint (locked)
- Remove module lookup; write by name
- Map Pi's `"class"` key → `config["class_name"]` in seed handler

### Dispatch / Preflight SQL (locked)
- `get_dispatch_spec` and `preflight_validate` in `api/routers/toolkit_dispatch.py` both change `WHERE hardware_module_id = :mid` → `WHERE name = :name`
- `module.name` is already available in the issue shape — no additional API changes needed

### Cascade Delete (locked)
- Remove the cascade-delete line in `api/routers/hardware_modules.py` that deletes `pilot_hardware_config` rows by `hardware_module_id`
- Config entries are now independent; module deletion must not affect them

### TypeScript (locked)
- `PilotHardwareConfigRow` changes `hardware_module_id: number` → `name: string`
- `upsertPilotHardwareConfig(pilotId, name: string, config)` → PUT with `encodeURIComponent(name)`
- `deletePilotHardwareConfig(pilotId, name: string)` → DELETE with `encodeURIComponent(name)`

### HardwareCheckModal Fix (locked)
- PUT URL: `hardware-config/${encodeURIComponent(issue.module_name)}` (was `hardware-config/${issue.module_id}`)
- Do NOT strip `class_name` from configToSave — the new API stores config as-is
- Map keys: change `pendingEdits` / `onEdit` keying from `issue.module_id` → `issue.module_name`

### React Page (locked)
- Data source: existing `pilot_hardware_config` rows (not all hardware modules)
- Table: Name | class_name badge | Params (key:value) | Edit / Delete
- Edit mode: JSON textarea for full config; Save/Cancel; no inline rename
- Add Entry form: Name input + optional module picker for pre-fill + config JSON textarea + Add button
- Module picker: calls `getHardwareModuleMethods(moduleId)` → builds `{class_name, ...initArgs}` template → fills textarea
- CSS: existing classes only (`card`, `button-primary`, `button-secondary`, `button-danger`, `badge status-running`)

### Claude's Discretion
- Wave structure / plan splitting (planner decides)
- Exact error handling for JSON parse errors in the Add Entry form
- Whether to split into 1 or 2 PLAN.md files

</decisions>

<specifics>
## Specific References

- `api/db.py` — follow existing migration pattern (e.g., `run_lab_column_migrations()`)
- `api/main.py` lines 14 + 135-144 — import + call pattern for migrations (file is ~2097 lines, DON'T add more routes)
- `api/models.py` ~line 705 — `PilotHardwareConfig` class
- `api/routers/pilot_hardware_config.py` — currently 123 lines; full rewrite, keep under 300
- `api/routers/toolkit_dispatch.py` `get_dispatch_spec` ~line 96, `preflight_validate` ~line 232
- `api/routers/hardware_modules.py` ~line 137 — cascade delete line to remove
- `web_ui/react-src/src/types/index.ts` — `PilotHardwareConfigRow`
- `web_ui/react-src/src/api/hardware_modules.ts` — `upsertPilotHardwareConfig`, `deletePilotHardwareConfig`
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` — line 181 (PUT URL), lines 178-179 (class_name strip)
- `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx` — full rewrite

</specifics>

<deferred>
## Deferred Ideas

- Inline rename UX (name is identity key; rename = delete + re-add is the decided approach)
- Migrating the `hardware_module_id` column away entirely (keep nullable for now)

</deferred>

---

*Phase: 17-free-form-pilot-hardware-config*
*Context gathered: 2026-05-28 from pre-session plan*
