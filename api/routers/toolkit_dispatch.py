"""Toolkit dispatch-class endpoint (Phase 11-02).

Returns the Python class name the orchestrator should use when starting a run
for a backend-authored toolkit. Separate from routers/toolkits.py (already >500 lines).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from auth import verify_token
from db import engine

router = APIRouter(tags=["toolkit-dispatch"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_sa_session():
    db: OrmSession = _SA_SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/toolkits/{toolkit_id}/dispatch-class")
def get_dispatch_class(
    toolkit_id: int,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    """Return the Pi class name to dispatch for a toolkit.

    Falls back to 'mics_task' if no locked_state_source or class_name is stored.
    """
    row = db.execute(
        text("SELECT locked_state_source, is_backend_authored FROM task_toolkits WHERE id = :id"),
        {"id": toolkit_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Toolkit not found")

    if not row.locked_state_source:
        return {"class_name": "mics_task", "is_backend_authored": bool(row.is_backend_authored)}

    cls_row = db.execute(
        text("SELECT class_name FROM available_locked_states WHERE task_filename = :fname LIMIT 1"),
        {"fname": row.locked_state_source},
    ).fetchone()
    class_name = cls_row.class_name if cls_row and cls_row.class_name else "mics_task"
    return {"class_name": class_name, "is_backend_authored": bool(row.is_backend_authored)}
