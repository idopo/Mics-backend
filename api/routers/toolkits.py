"""Toolkit and task-definition CRUD endpoints (Plan 02-03)."""
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

# Imports from parent package (api/ is on sys.path in Docker)
from auth import verify_token
from db import engine
from fda_utils import scan_fda_for_refs
from models import (
    BackendToolkitCreate,
    BackendToolkitPatch,
    HardwareLib,
    HardwareLibVersion,
    HardwareModule,
    Pilot,
    TaskDefinition,
    TaskDefinitionCreate,
    TaskDefinitionUpdate,
    TaskToolkit,
    ToolkitHardwareLib,
    ToolkitPilotOrigin,
)

router = APIRouter(tags=["toolkits"])

# Session factory shared with main.py (same engine, same DB)
_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

_ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:9000")


# ---------------------------------------------------------------------------
# Toolkit endpoints
# ---------------------------------------------------------------------------

def _normalize_flags(flags: dict | None) -> dict:
    """Normalize flags to {flag_name: {tracker_type, initial_value}} regardless of origin.

    HANDSHAKE-origin stores type as a nested dict with class_name; backend-authored
    stores tracker_type directly. Both shapes are normalized to the flat form here.
    """
    if not flags:
        return {}
    normalized = {}
    for name, info in flags.items():
        if "tracker_type" in info:
            tracker_type = info["tracker_type"]
        else:
            type_field = info.get("type", {})
            tracker_type = type_field.get("class_name", "Counter_Tracker") if isinstance(type_field, dict) else "Counter_Tracker"
        normalized[name] = {"tracker_type": tracker_type, "initial_value": info.get("initial_value", 0)}
    has_trial = any(v.get("tracker_type") == "Trial_Tracker" for v in normalized.values())
    if not has_trial:
        normalized["trial_counter"] = {"tracker_type": "Trial_Tracker", "initial_value": 0}
    return normalized


def _build_toolkit_row(
    t: TaskToolkit,
    origins_map: Dict[int, List[str]],
    fda_count: int,
) -> Dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "hw_hash": t.hw_hash,
        "states": t.states,
        "flags": _normalize_flags(t.flags),
        "params_schema": t.params_schema,
        "semantic_hardware": t.semantic_hardware,
        "callable_methods": t.callable_methods,
        "required_packages": t.required_packages,
        "file_hash": t.file_hash,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "is_canonical": t.is_canonical,
        "is_backend_authored": t.is_backend_authored or False,
        "hardware_module_ids": t.hardware_module_ids or [],
        "locked_state_source": t.locked_state_source,
        "pilot_origins": sorted(origins_map.get(t.id, [])),
        "fda_count": fda_count,
    }


@router.get("/toolkits")
def list_toolkits(_: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        toolkits = db.query(TaskToolkit).order_by(TaskToolkit.name, TaskToolkit.created_at).all()

        origins_rows = (
            db.query(ToolkitPilotOrigin, Pilot)
            .join(Pilot, ToolkitPilotOrigin.pilot_id == Pilot.id)
            .all()
        )
        origins_map: Dict[int, List[str]] = {}
        for origin, pilot in origins_rows:
            origins_map.setdefault(origin.toolkit_id, []).append(pilot.name)

        # toolkit_name is a migrated column not in ORM class — use raw SQL
        fda_counts_rows = db.execute(sa_text(
            "SELECT toolkit_name, COUNT(id) FROM task_definitions "
            "WHERE toolkit_name IS NOT NULL GROUP BY toolkit_name"
        )).fetchall()
        fda_count_by_name: Dict[str, int] = {row[0]: row[1] for row in fda_counts_rows}

        return [
            _build_toolkit_row(t, origins_map, fda_count_by_name.get(t.name, 0))
            for t in toolkits
        ]
    finally:
        db.close()


# IMPORTANT: register /by-name/{name} BEFORE /{toolkit_id} to avoid routing ambiguity
@router.get("/toolkits/by-name/{name}")
def get_toolkits_by_name(name: str, _: dict = Depends(verify_token)):
    """Return all toolkit variants (rows) matching the given class name.

    Multiple rows can exist for the same name when SEMANTIC_HARDWARE changes between Pi deploys.
    """
    db: OrmSession = _SA_SessionLocal()
    try:
        toolkits = (
            db.query(TaskToolkit)
            .filter(TaskToolkit.name == name)
            .order_by(TaskToolkit.created_at.desc())
            .all()
        )
        if not toolkits:
            raise HTTPException(404, f"No toolkits found with name '{name}'")

        toolkit_ids = [t.id for t in toolkits]
        origins_rows = (
            db.query(ToolkitPilotOrigin, Pilot)
            .join(Pilot, ToolkitPilotOrigin.pilot_id == Pilot.id)
            .filter(ToolkitPilotOrigin.toolkit_id.in_(toolkit_ids))
            .all()
        )
        origins_map: Dict[int, List[str]] = {}
        for origin, pilot in origins_rows:
            origins_map.setdefault(origin.toolkit_id, []).append(pilot.name)

        # toolkit_name is a migrated column — use raw SQL
        fda_count = db.execute(sa_text(
            "SELECT COUNT(id) FROM task_definitions WHERE toolkit_name = :name"
        ), {"name": name}).scalar() or 0

        return [_build_toolkit_row(t, origins_map, fda_count) for t in toolkits]
    finally:
        db.close()


@router.get("/toolkits/{toolkit_id}")
def get_toolkit(toolkit_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        toolkit = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none()
        if not toolkit:
            raise HTTPException(404, "Toolkit not found")

        origins_rows = (
            db.query(ToolkitPilotOrigin, Pilot)
            .join(Pilot, ToolkitPilotOrigin.pilot_id == Pilot.id)
            .filter(ToolkitPilotOrigin.toolkit_id == toolkit_id)
            .all()
        )
        pilot_names = sorted([pilot.name for _, pilot in origins_rows])

        # toolkit_name is a migrated column — use raw SQL
        fda_count = db.execute(sa_text(
            "SELECT COUNT(id) FROM task_definitions WHERE toolkit_name = :name"
        ), {"name": toolkit.name}).scalar() or 0

        origins_map = {toolkit_id: pilot_names}
        return _build_toolkit_row(toolkit, origins_map, fda_count)
    finally:
        db.close()


@router.patch("/toolkits/{toolkit_id}/set-canonical")
def set_canonical_toolkit(toolkit_id: int, _: dict = Depends(verify_token)):
    """
    Mark this toolkit variant as the canonical one for its name.
    All other variants with the same name become non-canonical.
    All task definitions for this toolkit name are flagged needs_migration=True
    (conservative: user must review which definitions are compatible with the canonical variant).
    """
    db: OrmSession = _SA_SessionLocal()
    try:
        target = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none()
        if not target:
            raise HTTPException(404, "Toolkit not found")

        toolkit_name = target.name

        # Clear canonical on all variants with this name
        db.query(TaskToolkit).filter(TaskToolkit.name == toolkit_name).update(
            {"is_canonical": False}, synchronize_session=False
        )
        # Set canonical on the target
        target.is_canonical = True

        # Flag all task definitions for this toolkit name as needing migration review
        db.execute(
            sa_text(
                "UPDATE task_definitions SET needs_migration = TRUE "
                "WHERE toolkit_name = :name"
            ),
            {"name": toolkit_name},
        )

        db.commit()
        db.refresh(target)

        origins_rows = (
            db.query(ToolkitPilotOrigin, Pilot)
            .join(Pilot, ToolkitPilotOrigin.pilot_id == Pilot.id)
            .filter(ToolkitPilotOrigin.toolkit_id == toolkit_id)
            .all()
        )
        origins_map = {toolkit_id: [p.name for _, p in origins_rows]}
        fda_count = db.execute(
            sa_text("SELECT COUNT(id) FROM task_definitions WHERE toolkit_name = :name"),
            {"name": toolkit_name},
        ).scalar() or 0

        return _build_toolkit_row(target, origins_map, fda_count)
    finally:
        db.close()


@router.get("/toolkits/{toolkit_id}/diff/{other_id}")
def diff_toolkits(toolkit_id: int, other_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        a = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none()
        b = db.query(TaskToolkit).filter(TaskToolkit.id == other_id).one_or_none()
        if not a:
            raise HTTPException(404, f"Toolkit {toolkit_id} not found")
        if not b:
            raise HTTPException(404, f"Toolkit {other_id} not found")

        hw_a = a.semantic_hardware or {}
        hw_b = b.semantic_hardware or {}
        keys_a = set(hw_a.keys())
        keys_b = set(hw_b.keys())

        added = {k: hw_b[k] for k in keys_b - keys_a}
        removed = {k: hw_a[k] for k in keys_a - keys_b}
        changed = {
            k: {"from": hw_a[k], "to": hw_b[k]}
            for k in keys_a & keys_b
            if hw_a[k] != hw_b[k]
        }

        return {
            "toolkit_id": toolkit_id,
            "other_id": other_id,
            "added": added,
            "removed": removed,
            "changed": changed,
            "identical": not (added or removed or changed),
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Backend-authored toolkit creation
# ---------------------------------------------------------------------------

@router.post("/toolkits", status_code=201)
def create_backend_toolkit(payload: BackendToolkitCreate, _: dict = Depends(verify_token)):
    """Create a backend-authored toolkit (validated against available_locked_states + hardware_modules)."""
    import hashlib as _hl
    import json as _json

    db: OrmSession = _SA_SessionLocal()
    try:
        # Validate selected_states against available_locked_states (skip when no source file chosen)
        if payload.locked_state_source:
            available_row = db.execute(sa_text(
                "SELECT state_names FROM available_locked_states WHERE task_filename = :fname LIMIT 1"
            ), {"fname": payload.locked_state_source}).fetchone()
            if not available_row:
                raise HTTPException(422, f"No locked states found for file '{payload.locked_state_source}'. "
                                         "Run a HANDSHAKE first.")
            known_states = set(available_row.state_names)
            missing_states = [s for s in payload.selected_states if s not in known_states]
            if missing_states:
                raise HTTPException(422, f"Unknown states for '{payload.locked_state_source}': {missing_states}")

        # Validate: all hardware_module_ids must exist
        if payload.hardware_module_ids:
            existing_ids = {
                row[0] for row in db.execute(
                    sa_text("SELECT id FROM hardware_modules WHERE id = ANY(:ids)"),
                    {"ids": payload.hardware_module_ids},
                ).fetchall()
            }
            missing_hw = [i for i in payload.hardware_module_ids if i not in existing_ids]
            if missing_hw:
                raise HTTPException(422, f"Unknown hardware_module_ids: {missing_hw}")

        # Build flags dict and params_schema dict from lists
        flags_dict = {f.name: {"tracker_type": f.tracker_type, "initial_value": f.initial_value}
                      for f in payload.flags}
        params_dict = {p.name: {"type": p.type, "default": p.default} for p in payload.params_schema}

        # hw_hash derived from hardware_module_ids (no semantic_hardware for backend-authored)
        hw_hash_input = _json.dumps(sorted(payload.hardware_module_ids)).encode()
        hw_hash = _hl.sha256(hw_hash_input).hexdigest()

        toolkit = TaskToolkit(
            name=payload.name,
            hw_hash=hw_hash,
            states=payload.selected_states,
            flags=flags_dict,
            params_schema=params_dict,
            semantic_hardware=None,
            callable_methods=None,
            required_packages=None,
            file_hash=None,
        )
        db.add(toolkit)
        db.flush()

        # Set backend-authored columns via raw SQL (migrated columns)
        db.execute(sa_text(
            "UPDATE task_toolkits SET hardware_module_ids = CAST(:hmids AS jsonb), "
            "locked_state_source = :lss, is_backend_authored = TRUE WHERE id = :id"
        ), {
            "hmids": _json.dumps(payload.hardware_module_ids),
            "lss": payload.locked_state_source,
            "id": toolkit.id,
        })
        db.commit()
        db.refresh(toolkit)

        return _build_toolkit_row(toolkit, {}, 0)
    finally:
        db.close()


def _flag_broken_defs_for_toolkit(
    db: OrmSession,
    toolkit_id: int,
    removed_flag_names: set[str],
    removed_module_names: set[str],
) -> list[int]:
    """Scan task definitions linked to toolkit_id for broken flag/hardware refs.

    Flags broken definitions in the DB and returns their IDs.
    """
    if not removed_flag_names and not removed_module_names:
        return []

    task_defs = db.query(TaskDefinition).filter(
        TaskDefinition.toolkit_id == toolkit_id
    ).all()

    affected_ids: list[int] = []
    for task_def in task_defs:
        row = db.execute(
            sa_text("SELECT fda_json FROM task_definitions WHERE id = :id"),
            {"id": task_def.id},
        ).fetchone()
        if not row or not row.fda_json:
            continue

        fda = row.fda_json if isinstance(row.fda_json, dict) else json.loads(row.fda_json)
        refs = scan_fda_for_refs(fda)

        broken_msgs: list[str] = []
        for ref_entry in refs:
            action_type = ref_entry["action_type"]
            ref = ref_entry.get("ref")
            state = ref_entry["state_name"]

            if action_type == "flag" and ref in removed_flag_names:
                broken_msgs.append(f"State '{state}': flag '{ref}' removed from toolkit")
            if action_type in ("hardware", "timer") and ref in removed_module_names:
                broken_msgs.append(f"State '{state}': hardware module '{ref}' removed from toolkit")

        if broken_msgs:
            db.execute(sa_text(
                "UPDATE task_definitions "
                "SET validation_status = 'broken', validation_message = :msg "
                "WHERE id = :id"
            ), {"msg": "\n".join(broken_msgs), "id": task_def.id})
            affected_ids.append(task_def.id)

    return affected_ids


@router.patch("/toolkits/{toolkit_id}", status_code=200)
def patch_backend_toolkit(
    toolkit_id: int,
    payload: BackendToolkitPatch,
    _: dict = Depends(verify_token),
):
    """Update hardware_module_ids, flags, and/or params_schema on a backend-authored toolkit."""
    import hashlib as _hl
    import json as _json

    _db: OrmSession = _SA_SessionLocal()
    try:
        toolkit = _db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none()
        if not toolkit:
            raise HTTPException(404, "Toolkit not found")
        if not toolkit.is_backend_authored:
            raise HTTPException(400, "Only backend-authored toolkits can be patched via this endpoint")

        # Capture current state before changes for impact detection
        old_module_ids: list[int] = list(toolkit.hardware_module_ids or [])
        old_flag_names: set[str] = set((toolkit.flags or {}).keys())

        if payload.hardware_module_ids is not None:
            existing_ids = {
                row[0] for row in _db.execute(
                    sa_text("SELECT id FROM hardware_modules WHERE id = ANY(:ids)"),
                    {"ids": payload.hardware_module_ids},
                ).fetchall()
            }
            missing_hw = [i for i in payload.hardware_module_ids if i not in existing_ids]
            if missing_hw:
                raise HTTPException(422, f"Unknown hardware_module_ids: {missing_hw}")

            hw_hash = _hl.sha256(
                _json.dumps(sorted(payload.hardware_module_ids)).encode()
            ).hexdigest()
            _db.execute(sa_text(
                "UPDATE task_toolkits SET hardware_module_ids = CAST(:hmids AS jsonb), hw_hash = :hw_hash WHERE id = :id"
            ), {"hmids": _json.dumps(payload.hardware_module_ids), "hw_hash": hw_hash, "id": toolkit_id})
            toolkit.hw_hash = hw_hash

        if payload.flags is not None:
            flags_dict = {f.name: {"tracker_type": f.tracker_type, "initial_value": f.initial_value}
                          for f in payload.flags}
            toolkit.flags = flags_dict

        if payload.params_schema is not None:
            params_dict = {p.name: {"type": p.type, "default": p.default} for p in payload.params_schema}
            toolkit.params_schema = params_dict

        _db.commit()
        _db.refresh(toolkit)

        # Compute removed flags and hardware modules, then scan for broken task definitions
        removed_flag_names: set[str] = set()
        removed_module_names: set[str] = set()

        if payload.flags is not None:
            new_flag_names = {f.name for f in payload.flags}
            removed_flag_names = old_flag_names - new_flag_names

        if payload.hardware_module_ids is not None:
            new_module_ids = set(payload.hardware_module_ids)
            removed_module_ids = set(old_module_ids) - new_module_ids
            if removed_module_ids:
                name_rows = _db.execute(
                    sa_text("SELECT name FROM hardware_modules WHERE id = ANY(:ids)"),
                    {"ids": list(removed_module_ids)},
                ).fetchall()
                removed_module_names = {row.name for row in name_rows}

        affected_ids = _flag_broken_defs_for_toolkit(
            _db, toolkit_id, removed_flag_names, removed_module_names
        )
        if affected_ids:
            _db.commit()

        origins_rows = (
            _db.query(ToolkitPilotOrigin, Pilot)
            .join(Pilot, ToolkitPilotOrigin.pilot_id == Pilot.id)
            .filter(ToolkitPilotOrigin.toolkit_id == toolkit_id)
            .all()
        )
        origins_map = {toolkit_id: sorted([p.name for _, p in origins_rows])}
        fda_count = _db.execute(
            sa_text("SELECT COUNT(id) FROM task_definitions WHERE toolkit_name = :name"),
            {"name": toolkit.name},
        ).scalar() or 0

        result = _build_toolkit_row(toolkit, origins_map, fda_count)
        result["impact"] = {
            "removed_flags": sorted(removed_flag_names),
            "removed_modules": sorted(removed_module_names),
            "affected_definition_ids": affected_ids,
        }
        return result
    finally:
        _db.close()


# ---------------------------------------------------------------------------
# Task-definition CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/task-definitions")
def list_task_definitions(_: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        rows = db.execute(sa_text(
            "SELECT id, task_name, display_name, toolkit_name, fda_json, file_hash, created_at, needs_migration, toolkit_id, "
            "validation_status, validation_message "
            "FROM task_definitions ORDER BY created_at DESC"
        )).fetchall()
        return [
            {
                "id": r.id,
                "task_name": r.task_name,
                "display_name": r.display_name,
                "toolkit_name": r.toolkit_name,
                "fda_json": json.loads(r.fda_json) if isinstance(r.fda_json, str) else r.fda_json,
                "file_hash": r.file_hash,
                "created_at": r.created_at,
                "needs_migration": r.needs_migration,
                "toolkit_id": r.toolkit_id,
                "validation_status": r.validation_status or "ok",
                "validation_message": r.validation_message,
            }
            for r in rows
        ]
    finally:
        db.close()


@router.post("/task-definitions", status_code=201)
def create_task_definition(payload: TaskDefinitionCreate, _: dict = Depends(verify_token)):
    import hashlib as _hl

    db: OrmSession = _SA_SessionLocal()
    try:
        fda_bytes = json.dumps(payload.fda_json, sort_keys=True).encode()
        fda_hash = _hl.sha256(fda_bytes).hexdigest()

        # Return existing record if identical content already saved
        existing = db.query(TaskDefinition).filter(TaskDefinition.file_hash == fda_hash).one_or_none()
        if existing:
            row = db.execute(sa_text(
                "SELECT id, task_name, display_name, toolkit_name, fda_json, file_hash, created_at, toolkit_id "
                "FROM task_definitions WHERE id = :id"
            ), {"id": existing.id}).fetchone()
            return {
                "id": row.id,
                "task_name": row.task_name,
                "display_name": row.display_name,
                "toolkit_name": row.toolkit_name,
                "fda_json": json.loads(row.fda_json) if isinstance(row.fda_json, str) else row.fda_json,
                "file_hash": row.file_hash,
                "created_at": row.created_at,
                "toolkit_id": row.toolkit_id,
            }

        # task_name = display_name + short content hash for uniqueness
        short_hash = fda_hash[:8]
        task_name = f"{payload.display_name}-{short_hash}"

        if db.query(TaskDefinition).filter(TaskDefinition.task_name == task_name).one_or_none():
            task_name = f"{payload.display_name}-{fda_hash[:16]}"

        defn = TaskDefinition(
            task_name=task_name,
            base_class_name=None,
            module="task_definitions",
            params=None,
            hardware=None,
            file_hash=fda_hash,
        )
        db.add(defn)
        db.flush()  # get defn.id

        # Set migrated columns via raw SQL (not declared in ORM class)
        db.execute(sa_text(
            "UPDATE task_definitions SET display_name = :dn, toolkit_name = :tn, fda_json = :fj, toolkit_id = :tid WHERE id = :id"
        ), {
            "dn": payload.display_name,
            "tn": payload.toolkit_name,
            "fj": json.dumps(payload.fda_json),
            "tid": payload.toolkit_id,
            "id": defn.id,
        })

        # Select latest stable version (or latest overall if no stable) for each linked hw lib
        if payload.toolkit_id:
            links = db.query(ToolkitHardwareLib).filter(
                ToolkitHardwareLib.toolkit_id == payload.toolkit_id
            ).all()
            hw_lib_versions: dict[str, int] = {}
            for link in links:
                versions = (
                    db.query(HardwareLibVersion)
                    .filter(HardwareLibVersion.hardware_lib_id == link.hardware_lib_id)
                    .order_by(HardwareLibVersion.version_number.desc())
                    .all()
                )
                if not versions:
                    continue
                stable = next((v for v in versions if v.state == "stable"), None)
                selected = stable or versions[0]
                hw_lib_versions[str(link.hardware_lib_id)] = selected.id
            if hw_lib_versions:
                db.execute(
                    sa_text("UPDATE task_definitions SET hw_lib_versions = :v WHERE id = :id"),
                    {"v": json.dumps(hw_lib_versions), "id": defn.id},
                )

        db.commit()

        return {
            "id": defn.id,
            "task_name": task_name,
            "display_name": payload.display_name,
            "toolkit_name": payload.toolkit_name,
            "fda_json": payload.fda_json,
            "file_hash": fda_hash,
            "created_at": defn.created_at,
            "toolkit_id": payload.toolkit_id,
        }
    finally:
        db.close()


@router.get("/task-definitions/{defn_id}")
def get_task_definition(defn_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        row = db.execute(sa_text(
            "SELECT id, task_name, display_name, toolkit_name, fda_json, file_hash, created_at, toolkit_id, "
            "validation_status, validation_message, hw_lib_versions "
            "FROM task_definitions WHERE id = :id"
        ), {"id": defn_id}).fetchone()
        if not row:
            raise HTTPException(404, "Task definition not found")
        return {
            "id": row.id,
            "task_name": row.task_name,
            "display_name": row.display_name,
            "toolkit_name": row.toolkit_name,
            "fda_json": json.loads(row.fda_json) if isinstance(row.fda_json, str) else row.fda_json,
            "file_hash": row.file_hash,
            "created_at": row.created_at,
            "toolkit_id": row.toolkit_id,
            "validation_status": row.validation_status or "ok",
            "validation_message": row.validation_message,
            "hw_lib_versions": row.hw_lib_versions or {},
        }
    finally:
        db.close()


def _validate_task_definition(
    db: OrmSession,
    fda_json: dict,
    toolkit_id: int | None,
    task_def_id: int | None = None,
) -> tuple[str, str | None]:
    """Re-validate an FDA JSON against its toolkit's current flags and hardware modules.

    Returns (validation_status, validation_message) where status is 'ok' or 'broken'.
    If toolkit_id is None or toolkit not found, returns 'ok' (no context to validate against).
    """
    if not toolkit_id or not fda_json:
        return "ok", None

    toolkit = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none()
    if not toolkit:
        return "ok", None

    refs = scan_fda_for_refs(fda_json)
    # trial_counter is implicitly available in every toolkit (incremented via INC_TRIAL_COUNTER ZMQ message)
    current_flag_names = set((toolkit.flags or {}).keys()) | {"trial_counter"}

    # Build a map of module_name → class_name for hardware method validation
    module_ids = list(toolkit.hardware_module_ids or [])
    hw_module_map: dict[str, str] = {}  # module_name → class_name
    if module_ids:
        module_rows = db.execute(
            sa_text("SELECT name, class_name, hardware_lib_id FROM hardware_modules WHERE id = ANY(:ids)"),
            {"ids": module_ids},
        ).fetchall()
        hw_module_map = {row.name: (row.class_name, row.hardware_lib_id) for row in module_rows}

    # Build class_name → method_names map from lib AST.
    # If task_def_id is given, prefer the version stored in hw_lib_versions over the lib's active AST.
    hw_versions: dict[str, int] = {}
    if task_def_id:
        td_row = db.execute(
            sa_text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
            {"id": task_def_id},
        ).fetchone()
        if td_row and td_row.hw_lib_versions:
            hw_versions = td_row.hw_lib_versions

    lib_class_methods: dict[str, set[str]] = {}  # class_name → {method_names}
    libs_with_ast: set[int] = set()  # lib_ids for which AST was successfully loaded
    seen_lib_ids: set[int] = set()
    for mod_name, (cls_name, lib_id) in hw_module_map.items():
        if lib_id not in seen_lib_ids:
            seen_lib_ids.add(lib_id)
            ast_meta = None

            sel_id = hw_versions.get(str(lib_id))
            if sel_id:
                v_row = db.execute(
                    sa_text("SELECT ast_metadata FROM hardware_lib_versions WHERE id = :id"),
                    {"id": sel_id},
                ).fetchone()
                if v_row and v_row.ast_metadata:
                    ast_meta = v_row.ast_metadata if isinstance(v_row.ast_metadata, dict) else json.loads(v_row.ast_metadata)

            if ast_meta is None:
                lib_row = db.execute(
                    sa_text("SELECT ast_metadata FROM hardware_libs WHERE id = :id"),
                    {"id": lib_id},
                ).fetchone()
                if lib_row and lib_row.ast_metadata:
                    ast_meta = lib_row.ast_metadata if isinstance(lib_row.ast_metadata, dict) else json.loads(lib_row.ast_metadata)

            if ast_meta:
                libs_with_ast.add(lib_id)
                for cls in ast_meta.get("classes", []):
                    lib_class_methods[cls["name"]] = {m["name"] for m in cls.get("methods", [])}

    errors: list[str] = []
    for ref_entry in refs:
        action_type = ref_entry["action_type"]
        ref = ref_entry.get("ref")
        method = ref_entry.get("method")
        state = ref_entry["state_name"]

        if action_type == "flag" and ref not in current_flag_names:
            errors.append(f"State '{state}': flag '{ref}' not in toolkit flags")

        if action_type == "hardware" and ref is not None:
            if hw_module_map and ref not in hw_module_map:
                errors.append(f"State '{state}': hardware module '{ref}' not in toolkit modules")
            elif ref in hw_module_map and method is not None:
                cls_name, lib_id = hw_module_map[ref]
                if lib_id in libs_with_ast:
                    if cls_name not in lib_class_methods:
                        errors.append(f"State '{state}': class '{cls_name}' not found in lib AST")
                    elif method not in lib_class_methods[cls_name]:
                        errors.append(f"State '{state}': {ref}.{method} not found in lib (class {cls_name})")

    if errors:
        return "broken", "\n".join(errors)
    return "ok", None


@router.put("/task-definitions/{defn_id}")
def update_task_definition(defn_id: int, payload: TaskDefinitionUpdate, _: dict = Depends(verify_token)):
    import hashlib as _hl

    db: OrmSession = _SA_SessionLocal()
    try:
        defn = db.query(TaskDefinition).filter(TaskDefinition.id == defn_id).one_or_none()
        if not defn:
            raise HTTPException(404, "Task definition not found")

        updates: Dict[str, Any] = {}
        if payload.fda_json is not None:
            fda_bytes = json.dumps(payload.fda_json, sort_keys=True).encode()
            new_hash = _hl.sha256(fda_bytes).hexdigest()
            defn.file_hash = new_hash
            updates["fda_json"] = json.dumps(payload.fda_json)
        if payload.display_name is not None:
            updates["display_name"] = payload.display_name
        if payload.toolkit_id is not None:
            updates["toolkit_id"] = payload.toolkit_id

        # Re-validate against current toolkit state after applying changes
        effective_fda = payload.fda_json
        if effective_fda is None:
            # Load existing fda_json if not being updated
            existing_row = db.execute(
                sa_text("SELECT fda_json, toolkit_id FROM task_definitions WHERE id = :id"),
                {"id": defn_id},
            ).fetchone()
            if existing_row and existing_row.fda_json:
                effective_fda = (
                    existing_row.fda_json
                    if isinstance(existing_row.fda_json, dict)
                    else json.loads(existing_row.fda_json)
                )

        effective_toolkit_id = payload.toolkit_id if payload.toolkit_id is not None else defn.toolkit_id
        v_status, v_msg = _validate_task_definition(db, effective_fda or {}, effective_toolkit_id, defn_id)
        updates["validation_status"] = v_status
        updates["validation_message"] = v_msg

        if updates:
            set_parts = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = defn_id
            db.execute(sa_text(f"UPDATE task_definitions SET {set_parts} WHERE id = :id"), updates)
            db.commit()

        return {"status": "ok", "id": defn_id, "validation_status": v_status}
    finally:
        db.close()


@router.delete("/task-definitions/{defn_id}")
def delete_task_definition(defn_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        defn = db.query(TaskDefinition).filter(TaskDefinition.id == defn_id).one_or_none()
        if not defn:
            raise HTTPException(404, "Task definition not found")
        db.delete(defn)
        db.commit()
        return {"status": "deleted", "id": defn_id}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Push endpoint — delivers fda_json to a running pilot via orchestrator
# ---------------------------------------------------------------------------

# IMPORTANT: register before generic /{defn_id} routes to avoid ambiguity;
# this path suffix is unique so order doesn't matter here, but be explicit.
@router.post("/task-definitions/{defn_id}/push")
def push_task_definition(
    defn_id: int,
    pilot: str,
    _: dict = Depends(verify_token),
):
    """
    Validate fda_json against toolkit (state names and entry_action hardware refs only),
    then forward UPDATE_FDA to the named pilot via orchestrator POST /push-fda.
    """
    db: OrmSession = _SA_SessionLocal()
    try:
        row = db.execute(sa_text(
            "SELECT id, task_name, toolkit_name, fda_json FROM task_definitions WHERE id = :id"
        ), {"id": defn_id}).fetchone()
        if not row:
            raise HTTPException(404, "Task definition not found")

        fda_json = json.loads(row.fda_json) if isinstance(row.fda_json, str) else row.fda_json
        if fda_json is None:
            raise HTTPException(400, "Task definition has no fda_json")

        # Validate fda_json against toolkit (skip validation if toolkit missing)
        validation_errors: List[str] = []
        if row.toolkit_name:
            toolkit = (
                db.query(TaskToolkit)
                .filter(TaskToolkit.name == row.toolkit_name)
                .order_by(TaskToolkit.updated_at.desc())
                .first()
            )
            if toolkit:
                validation_errors = _validate_fda_against_toolkit(fda_json, toolkit)

        if validation_errors:
            raise HTTPException(422, detail={"errors": validation_errors})

        # Forward to orchestrator /push-fda
        try:
            body_bytes = json.dumps({"pilot_name": pilot, "fda_json": fda_json}).encode()
            req = urllib.request.Request(
                f"{_ORCHESTRATOR_URL}/push-fda",
                data=body_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except urllib.error.HTTPError as e:
            raise HTTPException(502, f"Orchestrator error: {e.read().decode()}")
        except OSError:
            # Covers ConnectionRefusedError, socket errors, etc.
            raise HTTPException(503, "Orchestrator not reachable")

        return {"status": "pushed", "pilot": pilot, "task_definition_id": defn_id}

    finally:
        db.close()


def _validate_fda_against_toolkit(fda_json: dict, toolkit: TaskToolkit) -> List[str]:
    """
    Returns list of error strings. Empty list = valid.

    Validates ONLY:
    - State name keys in fda_json["states"] exist in toolkit.states list
    - hardware entry_action refs (action["type"]=="hardware") exist in toolkit.semantic_hardware keys

    Does NOT validate: transition next_state values, condition refs, or any other fields.
    """
    errors: List[str] = []
    known_states = set(toolkit.states or [])
    known_hw = set((toolkit.semantic_hardware or {}).keys())

    fda_states = fda_json.get("states", {})
    if not isinstance(fda_states, dict):
        return errors

    for state_name in fda_states:
        if known_states and state_name not in known_states:
            errors.append(f"Unknown state: '{state_name}' not in toolkit states")

    for state_name, state_body in fda_states.items():
        if not isinstance(state_body, dict):
            continue
        for action in (state_body.get("entry_actions") or []):
            if not isinstance(action, dict):
                continue
            ref = action.get("ref")
            action_type = action.get("type")
            if action_type == "hardware" and ref and known_hw and ref not in known_hw:
                errors.append(f"State '{state_name}': unknown hardware ref '{ref}'")

    return errors
