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


def attach_compute_defaults(db, toolkit_id: int) -> dict:
    """Give a toolkit the compute lib every toolkit is expected to have.

    Compute is not a per-toolkit opt-in (user decision, 2026-08-03) -- a researcher should
    never have to discover that `random_int` exists but is not wired up. Both halves are
    required and they are governed by different tables (see this module's docstring):
    the `toolkit_hardware_libs` row drives version pinning + LOAD_HARDWARE_LIBS, and the
    module id in `hardware_module_ids` is what makes the module reachable on the Pi.

    Idempotent, and a silent no-op on a DB where the compute lib has not been seeded yet --
    toolkit creation must never fail because of this. Commits nothing; caller owns the txn.
    """
    lib_rows = db.execute(
        sa_text("SELECT id FROM hardware_libs WHERE kind = 'compute'")
    ).fetchall()
    if not lib_rows:
        return {"linked": [], "modules_added": []}
    lib_ids = [row.id for row in lib_rows]

    module_rows = db.execute(
        sa_text(
            "SELECT hm.id FROM hardware_modules hm "
            "JOIN hardware_libs hl ON hl.id = hm.hardware_lib_id "
            "WHERE hl.kind = 'compute'"
        )
    ).fetchall()
    module_ids = [row.id for row in module_rows]

    already_linked = {
        row.hardware_lib_id
        for row in db.execute(
            sa_text("SELECT hardware_lib_id FROM toolkit_hardware_libs WHERE toolkit_id = :tid"),
            {"tid": toolkit_id},
        ).fetchall()
    }

    linked: list[int] = []
    for lib_id in lib_ids:
        if lib_id in already_linked:
            continue
        db.execute(
            sa_text(
                "INSERT INTO toolkit_hardware_libs (toolkit_id, hardware_lib_id, default_version_id) "
                "SELECT :toolkit_id, :hardware_lib_id, "
                "COALESCE(stable_version_id, active_version_id) FROM hardware_libs WHERE id = :hardware_lib_id"
            ),
            {"toolkit_id": toolkit_id, "hardware_lib_id": lib_id},
        )
        linked.append(lib_id)

    modules_added: list[int] = []
    if module_ids:
        row = db.execute(
            sa_text("SELECT hardware_module_ids FROM task_toolkits WHERE id = :id"),
            {"id": toolkit_id},
        ).fetchall()
        current = list((row[0].hardware_module_ids if row else None) or [])
        missing = [m for m in module_ids if m not in current]
        if missing:
            db.execute(
                sa_text(
                    "UPDATE task_toolkits SET hardware_module_ids = CAST(:hmids AS jsonb) WHERE id = :id"
                ),
                {"hmids": json.dumps(current + missing), "id": toolkit_id},
            )
            modules_added = missing

    return {"linked": linked, "modules_added": modules_added}


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
