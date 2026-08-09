"""HTTP surface for device-lease arbitration (Phase 18, EXTLINK-16/17).

Thin composition over `api/device_lease.py` -- no arbitration logic of its own. The
orchestrator's `start_run`/`stop_run`/`on_task_error` and its `_lease_reconcile_loop`
(plan 18-09 task 2) are the production callers; the `DELETE` route is the manual escape
hatch for a wedged lease that reconciliation itself cannot clear.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from auth import verify_token
from db import engine
from device_lease import (
    acquire_lease,
    force_release,
    list_leases,
    reconcile_leases,
    release_leases_for_run,
)

router = APIRouter(tags=["device-leases"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_sa_session():
    db: OrmSession = _SA_SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AcquireRequest(BaseModel):
    host: str
    pilot_id: int
    pilot_name: str | None = None
    session_id: int | None = None
    run_id: int | None = None
    subject_key: str | None = None


class ReconcileRequest(BaseModel):
    heartbeats: dict[str, str]
    stale_after_s: int | None = None


@router.get("/device-leases")
def list_device_leases(
    _: dict = Depends(verify_token), db: OrmSession = Depends(get_sa_session),
):
    return list_leases(db)


@router.post("/device-leases/acquire")
def acquire_device_lease(
    body: AcquireRequest,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    # 200 in both outcomes -- the orchestrator logs and continues on a conflict rather
    # than treating it as a transport error; preflight is the real gate.
    acquired, holder = acquire_lease(
        db, body.host, body.pilot_id, body.pilot_name, body.session_id, body.run_id,
        body.subject_key,
    )
    return {"acquired": acquired, "holder": holder}


@router.delete("/device-leases/{host}")
def force_release_device_lease(
    host: str, _: dict = Depends(verify_token), db: OrmSession = Depends(get_sa_session),
):
    # normalize_host runs inside force_release itself, so "132.77.9.9:5556" and
    # "132.77.9.9" release the same row.
    return {"released": force_release(db, host)}


@router.post("/device-leases/release-for-run/{run_id}")
def release_device_leases_for_run(
    run_id: int, _: dict = Depends(verify_token), db: OrmSession = Depends(get_sa_session),
):
    return {"released": release_leases_for_run(db, run_id)}


@router.post("/device-leases/reconcile")
def reconcile_device_leases(
    body: ReconcileRequest,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    kwargs = {} if body.stale_after_s is None else {"stale_after_s": body.stale_after_s}
    return {"released": reconcile_leases(db, body.heartbeats, **kwargs)}
