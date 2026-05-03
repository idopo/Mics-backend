"""Locked-states CRUD endpoints (Phase 11).

Locked states are Pi task file state-method lists announced via HANDSHAKE.
The orchestrator upserts them here; the UI reads them to populate toolkit creation.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from auth import verify_token
from db import engine

router = APIRouter(tags=["locked-states"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class LockedStateUpsertPayload(BaseModel):
    state_names: List[str]


# ---------------------------------------------------------------------------
# GET /locked-states — all entries grouped by task_filename
# ---------------------------------------------------------------------------

@router.get("/locked-states")
def list_locked_states(_: dict = Depends(verify_token)):
    """Return all available locked-state entries grouped by task filename."""
    db: OrmSession = _SA_SessionLocal()
    try:
        rows = db.execute(sa_text(
            "SELECT als.id, als.pilot_id, als.task_filename, als.state_names, "
            "       als.is_legacy_filename, als.updated_at, p.name AS pilot_name "
            "FROM available_locked_states als "
            "JOIN pilots p ON p.id = als.pilot_id "
            "ORDER BY als.task_filename, p.name"
        )).fetchall()

        by_file: Dict[str, Any] = {}
        for row in rows:
            fname = row.task_filename
            if fname not in by_file:
                by_file[fname] = {
                    "state_names": row.state_names,
                    "pilots": [],
                    "pilot_ids": [],
                    "is_legacy_filename": row.is_legacy_filename,
                    "updated_at": row.updated_at,
                }
            by_file[fname]["pilots"].append(row.pilot_name)
            by_file[fname]["pilot_ids"].append(row.pilot_id)

        return {"by_file": by_file}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /locked-states/{pilot_id}/{task_filename}
# ---------------------------------------------------------------------------

@router.get("/locked-states/{pilot_id}/{task_filename:path}")
def get_locked_state(pilot_id: int, task_filename: str, _: dict = Depends(verify_token)):
    """Return the locked-state entry for a specific pilot + task filename."""
    db: OrmSession = _SA_SessionLocal()
    try:
        row = db.execute(sa_text(
            "SELECT id, pilot_id, task_filename, state_names, is_legacy_filename, updated_at "
            "FROM available_locked_states "
            "WHERE pilot_id = :pid AND task_filename = :fname"
        ), {"pid": pilot_id, "fname": task_filename}).fetchone()
        if not row:
            raise HTTPException(404, "No locked states found for this pilot + filename")
        return {
            "id": row.id,
            "pilot_id": row.pilot_id,
            "task_filename": row.task_filename,
            "state_names": row.state_names,
            "is_legacy_filename": row.is_legacy_filename,
            "updated_at": row.updated_at,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# PUT /locked-states/{pilot_id}/{task_filename} — upsert (orchestrator internal)
# ---------------------------------------------------------------------------

@router.put("/locked-states/{pilot_id}/{task_filename:path}")
def upsert_locked_state(
    pilot_id: int,
    task_filename: str,
    payload: LockedStateUpsertPayload,
    _: dict = Depends(verify_token),
):
    """Upsert locked states for a pilot + task filename (called by orchestrator on HANDSHAKE)."""
    import json

    # Detect legacy filename: class-name filenames never end in lowercase char before .py
    # Convention: if the stem has any uppercase letter AND matches known class-name pattern,
    # it's a legacy entry. We simply check for uppercase letters in the stem.
    stem = task_filename.removesuffix(".py")
    is_legacy = any(c.isupper() for c in stem)

    db: OrmSession = _SA_SessionLocal()
    try:
        existing = db.execute(sa_text(
            "SELECT id FROM available_locked_states "
            "WHERE pilot_id = :pid AND task_filename = :fname"
        ), {"pid": pilot_id, "fname": task_filename}).fetchone()

        state_names_json = json.dumps(payload.state_names)

        if existing:
            db.execute(sa_text(
                "UPDATE available_locked_states "
                "SET state_names = :sn::jsonb, is_legacy_filename = :legacy, updated_at = NOW() "
                "WHERE id = :id"
            ), {"sn": state_names_json, "legacy": is_legacy, "id": existing.id})
        else:
            db.execute(sa_text(
                "INSERT INTO available_locked_states "
                "(pilot_id, task_filename, state_names, is_legacy_filename, updated_at) "
                "VALUES (:pid, :fname, :sn::jsonb, :legacy, NOW())"
            ), {"pid": pilot_id, "fname": task_filename, "sn": state_names_json, "legacy": is_legacy})

        db.commit()
        return {"status": "ok", "pilot_id": pilot_id, "task_filename": task_filename,
                "state_count": len(payload.state_names), "is_legacy_filename": is_legacy}
    finally:
        db.close()
