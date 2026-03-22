"""Toolkit and task-definition CRUD endpoints (Plan 02-03)."""
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, text as sa_text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

# Imports from parent package (api/ is on sys.path in Docker)
from auth import verify_token
from db import engine
from models import (
    Pilot,
    TaskDefinition,
    TaskDefinitionCreate,
    TaskDefinitionUpdate,
    TaskToolkit,
    ToolkitPilotOrigin,
)

router = APIRouter(tags=["toolkits"])

# Session factory shared with main.py (same engine, same DB)
_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ---------------------------------------------------------------------------
# Toolkit endpoints
# ---------------------------------------------------------------------------

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
        "flags": t.flags,
        "params_schema": t.params_schema,
        "semantic_hardware": t.semantic_hardware,
        "callable_methods": t.callable_methods,
        "required_packages": t.required_packages,
        "file_hash": t.file_hash,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
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

        fda_counts_rows = (
            db.query(TaskDefinition.toolkit_name, func.count(TaskDefinition.id))
            .filter(TaskDefinition.toolkit_name.isnot(None))
            .group_by(TaskDefinition.toolkit_name)
            .all()
        )
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

        fda_count = (
            db.query(func.count(TaskDefinition.id))
            .filter(TaskDefinition.toolkit_name == name)
            .scalar()
        ) or 0

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

        fda_count = (
            db.query(func.count(TaskDefinition.id))
            .filter(TaskDefinition.toolkit_name == toolkit.name)
            .scalar()
        ) or 0

        origins_map = {toolkit_id: pilot_names}
        return _build_toolkit_row(toolkit, origins_map, fda_count)
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
# Task-definition CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("/task-definitions")
def list_task_definitions(_: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        rows = db.execute(sa_text(
            "SELECT id, task_name, display_name, toolkit_name, fda_json, file_hash, created_at "
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

        # task_name = display_name + short content hash for uniqueness
        short_hash = fda_hash[:8]
        task_name = f"{payload.display_name}-{short_hash}"

        existing = db.query(TaskDefinition).filter(TaskDefinition.task_name == task_name).one_or_none()
        if existing:
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

        # Set new columns (display_name, toolkit_name, fda_json) via raw SQL
        # These columns were added by IF NOT EXISTS migration and are not declared in ORM class
        db.execute(sa_text(
            "UPDATE task_definitions SET display_name = :dn, toolkit_name = :tn, fda_json = :fj WHERE id = :id"
        ), {
            "dn": payload.display_name,
            "tn": payload.toolkit_name,
            "fj": json.dumps(payload.fda_json),
            "id": defn.id,
        })
        db.commit()

        return {
            "id": defn.id,
            "task_name": task_name,
            "display_name": payload.display_name,
            "toolkit_name": payload.toolkit_name,
            "fda_json": payload.fda_json,
            "file_hash": fda_hash,
            "created_at": defn.created_at,
        }
    finally:
        db.close()


@router.get("/task-definitions/{defn_id}")
def get_task_definition(defn_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = _SA_SessionLocal()
    try:
        row = db.execute(sa_text(
            "SELECT id, task_name, display_name, toolkit_name, fda_json, file_hash, created_at "
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
        }
    finally:
        db.close()


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

        if updates:
            set_parts = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = defn_id
            db.execute(sa_text(f"UPDATE task_definitions SET {set_parts} WHERE id = :id"), updates)
            db.commit()

        return {"status": "ok", "id": defn_id}
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
