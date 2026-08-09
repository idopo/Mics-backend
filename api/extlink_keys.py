"""External-hardware ("extlink") signal aggregation (Phase 18 Plan 13, EXTLINK-19).

Mirrors `detector_keys.module_detector_channels`' contract and ADVISORY-ONLY posture: this
result decides what the FDA editor OFFERS (plan 18-14's picker), never what a save/preflight
gate accepts for one specific pilot — that stays `routers/toolkit_dispatch.py`'s job.

Signal NAMES come from a hardware-lib version's `ast_metadata.extlink` block (plan 18-07) and
are pilot-INVARIANT. `source_id` comes from PER-PILOT `pilot_hardware_config.config`, so two
pilots configuring the same module with different `source_id` values are a real cross-pilot
conflict — the identical `conflict` rule `module_detector_channels` already carries.

No FastAPI imports; `sqlalchemy.text` only; caller-owned `db` — same no-connection posture
`detector_keys.py` / `hw_introspect.py` both hold.
"""
from sqlalchemy import text as sa_text

from lib_version_resolution import resolve_lib_versions


def extlink_signals_from_ast(ast_metadata: dict | None) -> list[dict]:
    """[{"name", "dtype"}], sorted by name, from `ast_metadata["extlink"]` (plan 18-07's shape:
    `{ClassName: {"signals": {name: {"dtype": ..., ...}}}}`). `None`/malformed input at any
    level yields `[]` — never raises."""
    if not isinstance(ast_metadata, dict):
        return []
    extlink = ast_metadata.get("extlink")
    if not isinstance(extlink, dict):
        return []
    dtype_by_name: dict[str, str | None] = {}
    for block in extlink.values():
        if not isinstance(block, dict):
            continue
        signals = block.get("signals")
        if not isinstance(signals, dict):
            continue
        for name, info in signals.items():
            if not isinstance(name, str) or not name:
                continue
            dtype = info.get("dtype") if isinstance(info, dict) else None
            dtype_by_name[name] = dtype if isinstance(dtype, str) else None
    return [{"name": name, "dtype": dtype_by_name[name]} for name in sorted(dtype_by_name)]


def has_extlink_block(ast_metadata: dict | None) -> bool:
    """True iff this lib version declares at least one extlink class."""
    if not isinstance(ast_metadata, dict):
        return False
    extlink = ast_metadata.get("extlink")
    return isinstance(extlink, dict) and bool(extlink)


def derive_extlink_keys(config: dict | None, signal_names: list[str]) -> list[str]:
    """`f"{source_id}.{name}"` for each signal, PLUS `f"{source_id}.alive"` always — a
    control-only module (zero signals) still registers exactly one key. Requires
    `config["source_id"]` to be a non-empty string; otherwise `[]`. Never raises."""
    if not isinstance(config, dict):
        return []
    source_id = config.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        return []
    names = {n for n in (signal_names or []) if isinstance(n, str) and n} | {"alive"}
    return sorted(f"{source_id}.{n}" for n in names)


def pilot_extlink_keys(db, version_id: int | None, config: dict | None) -> list[str]:
    """One pilot's derived extlink keys for a single already-resolved lib version — the
    preflight step-6 call site (`routers/toolkit_dispatch.py`) already has `version_id`/`config`
    from its own per-module loop and must not re-derive `module_extlink_signals`' cross-pilot
    query shape just to resolve ONE pilot. `version_id=None` (CMP-17 rung "none") still runs
    `derive_extlink_keys` against an empty signal list, so a control-only module keeps its
    `.alive` key even with no deployable lib version."""
    signal_names: list[str] = []
    if version_id:
        row = db.execute(
            sa_text("SELECT ast_metadata FROM hardware_lib_versions WHERE id = :id"),
            {"id": version_id},
        ).fetchone()
        signal_names = [s["name"] for s in extlink_signals_from_ast(row.ast_metadata if row else None)]
    return derive_extlink_keys(config, signal_names)


def module_extlink_signals(db, module_names: list[str]) -> list[dict]:
    """Per module, the union of derived extlink view keys across every pilot configuring it.

    A module qualifies as external if EITHER its resolved lib version's `ast_metadata` carries
    an `extlink` block OR its per-pilot config carries both `role` and `source_id` (a
    control-only lib whose only decorator is a `liveness_hook` override declares no
    `@signal`/`@event`/`@command` at all, so plan 18-07 emits no `extlink` key for it — yet such
    a module still owns a real `.alive` tracker). A pilot whose config derives no keys is
    dropped from `by_pilot`; a module whose configured rows all derive nothing is omitted
    entirely — same rule `module_detector_channels` applies.
    """
    if not module_names:
        return []
    hw_rows = db.execute(
        sa_text(
            "SELECT id, name, hardware_lib_id FROM hardware_modules "
            "WHERE name = ANY(:names) ORDER BY id"
        ),
        {"names": list(module_names)},
    ).fetchall()
    resolved = resolve_lib_versions(db, [row.hardware_lib_id for row in hw_rows])
    version_ids = {vid for vid, _reason in resolved.values() if vid}
    ast_by_version: dict[int, dict] = {}
    if version_ids:
        version_rows = db.execute(
            sa_text("SELECT id, ast_metadata FROM hardware_lib_versions WHERE id = ANY(:ids)"),
            {"ids": list(version_ids)},
        ).fetchall()
        ast_by_version = {row.id: row.ast_metadata for row in version_rows}

    # Union signal names per module name (two hardware_modules rows could in principle share a
    # name) — iterated in id order for determinism, same posture as hw_introspect.
    signals_by_module: dict[str, dict[str, str | None]] = {}
    for hw_row in hw_rows:
        version_id, _reason = resolved.get(hw_row.hardware_lib_id, (None, "none"))
        for sig in extlink_signals_from_ast(ast_by_version.get(version_id)):
            signals_by_module.setdefault(hw_row.name, {}).setdefault(sig["name"], sig["dtype"])

    config_rows = db.execute(
        sa_text(
            "SELECT phc.name AS module_name, phc.pilot_id, p.name AS pilot_name, phc.config "
            "FROM pilot_hardware_config phc "
            "JOIN pilots p ON p.id = phc.pilot_id "
            "WHERE phc.name = ANY(:names) "
            "ORDER BY phc.name, p.name"
        ),
        {"names": list(module_names)},
    ).fetchall()

    groups: dict[str, list[dict]] = {}
    for row in config_rows:
        cfg = row.config if isinstance(row.config, dict) else {}
        signal_names = sorted(signals_by_module.get(row.module_name, {}))
        is_external = bool(signal_names) or (
            isinstance(cfg.get("role"), str) and bool(cfg.get("role"))
            and isinstance(cfg.get("source_id"), str) and bool(cfg.get("source_id"))
        )
        if not is_external:
            continue
        keys = derive_extlink_keys(cfg, signal_names)
        if not keys:
            continue
        groups.setdefault(row.module_name, []).append({
            "pilot_id": row.pilot_id,
            "pilot_name": row.pilot_name,
            "source_id": cfg.get("source_id"),
            "keys": keys,
        })

    result = []
    for module_name in sorted(groups):
        by_pilot = sorted(groups[module_name], key=lambda p: p["pilot_name"])
        source_ids = sorted({p["source_id"] for p in by_pilot if p["source_id"]})
        all_keys = sorted({k for p in by_pilot for k in p["keys"]})
        signal_names = sorted(signals_by_module.get(module_name, {}))
        signals = [{"name": n, "dtype": signals_by_module[module_name][n]} for n in signal_names]
        conflict = len({frozenset(p["keys"]) for p in by_pilot}) > 1
        result.append({
            "module_name": module_name,
            "source_ids": source_ids,
            "signals": signals,
            "keys": all_keys,
            "conflict": conflict,
            "by_pilot": by_pilot,
        })
    return result
