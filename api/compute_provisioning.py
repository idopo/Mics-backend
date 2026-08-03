"""Auto-provisioning of the trivial per-pilot `pilot_hardware_config` row a compute module
needs before `init_hardware()` will instantiate it on the Pi.

WHY THIS EXISTS: `toolkit_hardware_libs` governs version pinning and the `LOAD_HARDWARE_LIBS`
file-write/test-import path ONLY. Pi reachability as `self.hardware["Modules"][ref]` is governed
exclusively by `hardware_modules` + `toolkit.hardware_module_ids` + a `pilot_hardware_config` row
-- without that row, `init_hardware()` raises `KeyError`, logs, and silently skips the module.
Any `compute` action referencing that module then dies later at FDA-load time with a bare
`KeyError` on `self._semantic_hw[ref]`. Auto-provisioning is the user's locked decision
(23-CONTEXT, 2026-08-03): a manual per-rig step for something with no hardware would reintroduce
exactly the per-rig fragility Phases 09-13 removed. The row stays real and inspectable in
`PilotHardwareConfig.tsx`.

Takes a caller-owned `db` session -- same posture as `hw_introspect.py`, which never opens a
connection itself. Stdlib + sqlalchemy `text` only. Commits nothing -- the caller owns the
transaction.
"""
import json

from sqlalchemy import text as sa_text


def compute_module_names(db, module_ids: list[int]) -> dict[str, str]:
    """{module_name: class_name} for the subset of module_ids whose lib kind is 'compute'."""
    if not module_ids:
        return {}
    rows = db.execute(
        sa_text(
            "SELECT hm.name, hm.class_name FROM hardware_modules hm "
            "JOIN hardware_libs hl ON hl.id = hm.hardware_lib_id "
            "WHERE hm.id = ANY(:ids) AND hl.kind = 'compute'"
        ),
        {"ids": list(module_ids)},
    ).fetchall()
    return {row.name: row.class_name for row in rows}


def provision_compute_configs(db, module_ids, pilot_ids=None) -> list[tuple[int, str]]:
    """Create the trivial {"class_name": ...} pilot_hardware_config row a compute module needs
    before init_hardware() will instantiate it. Idempotent -- never touches an existing row,
    even one with extra keys a researcher added by hand. pilot_ids=None means every pilot."""
    names = compute_module_names(db, module_ids)
    if not names:
        return []

    if pilot_ids is None:
        pilot_ids = [row.id for row in db.execute(sa_text("SELECT id FROM pilots")).fetchall()]
    if not pilot_ids:
        return []

    existing = {
        (row.pilot_id, row.name)
        for row in db.execute(
            sa_text("SELECT pilot_id, name FROM pilot_hardware_config WHERE name = ANY(:names)"),
            {"names": list(names)},
        ).fetchall()
    }

    created: list[tuple[int, str]] = []
    for pilot_id in pilot_ids:
        for name, class_name in names.items():
            if (pilot_id, name) in existing:
                continue
            db.execute(
                sa_text(
                    "INSERT INTO pilot_hardware_config (pilot_id, name, config) "
                    "VALUES (:pilot_id, :name, :config)"
                ),
                {"pilot_id": pilot_id, "name": name, "config": json.dumps({"class_name": class_name})},
            )
            created.append((pilot_id, name))
    return created
