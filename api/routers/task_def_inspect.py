# api/routers/task_def_inspect.py
"""Read-only variable-usage inspector for the FDA editor (Plan 23-07, CMP-15).

Thin composition over variable_scan's three functions plus one row fetch — no analysis
logic lives here. Deliberately a backend route rather than a TypeScript re-implementation:
duplicating the FDA walker in two languages is exactly the drift fda_vocabulary.py/
detector_keys.py exist to avoid.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from auth import verify_token
from db import engine
from variable_scan import scan_variable_readers, scan_variable_writers

router = APIRouter(tags=["task-def-inspect"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_sa_session():
    db: OrmSession = _SA_SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/task-definitions/{task_def_id}/variable-usage")
def get_variable_usage(
    task_def_id: int,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    """{"variables": {name: {writers, readers, never_written, initial_value}}} for every
    declared variable, including ones with no readers and no writers."""
    row = db.execute(
        text("SELECT fda_json FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task definition not found")

    fda_json = row.fda_json or {}
    variables = fda_json.get("variables") if isinstance(fda_json, dict) else None
    if not isinstance(variables, dict):
        return {"variables": {}}

    writers = scan_variable_writers(fda_json)
    readers = scan_variable_readers(fda_json)

    return {
        "variables": {
            name: {
                "writers": writers.get(name, []),
                "readers": readers.get(name, []),
                "never_written": name not in writers,
                "initial_value": spec.get("initial_value") if isinstance(spec, dict) else None,
            }
            for name, spec in variables.items()
        }
    }
