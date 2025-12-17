# api/main.py
from typing import List

from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from sqlmodel import SQLModel, Session as SQLModelSession, select
from auth import verify_token
from db import engine, get_session
from models import (  # also non-relative
    Subject,
    SubjectCreate,
    SubjectRead,
    SubjectProtocolRun,
    AssignProtocolPayload,
    ProtocolTemplate,
    ProtocolStepTemplate,
    ProtocolCreate,
    ProtocolRead,
    Pilot,
    PilotCreate,
    PilotRead,
    Session,
    SessionRun,
    SessionRunCreate,
    SessionRunRead,
    SessionRunStatus,
)

# IMPORTANT: we’ll use a classic SQLAlchemy Session for SA models
SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

app = FastAPI(title="MICS Backend API")


# ----------------------------------------------------------
# INIT
# ----------------------------------------------------------
@app.on_event("startup")
def startup():
    # Create tables for SQLModel side
    SQLModel.metadata.create_all(engine)
    # And for pure SQLAlchemy side
    from models import Base
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------------------------------------
# SUBJECTS (SQLModel)
# ----------------------------------------------------------

@app.get("/subjects", response_model=List[SubjectRead])
def list_subjects(
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    return session.exec(select(Subject)).all()


@app.post("/subjects", response_model=SubjectRead, status_code=201)
def create_subject(
    payload: SubjectCreate,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    existing = session.exec(select(Subject).where(Subject.name == payload.name)).first()
    if existing:
        raise HTTPException(400, "Subject already exists")

    subj = Subject(name=payload.name)
    session.add(subj)
    session.commit()
    session.refresh(subj)
    return subj


@app.get("/subjects/{subject_name}/runs")
def list_subject_runs(
    subject_name: str,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    subject = session.exec(select(Subject).where(Subject.name == subject_name)).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    runs = session.exec(
        select(SubjectProtocolRun).where(SubjectProtocolRun.subject_id == subject.id)
    ).all()

    return runs


# ----------------------------------------------------------
# SAFE DEFERRED ASSIGNMENT (set next_protocol_id)
# ----------------------------------------------------------

@app.post("/subjects/{subject_name}/assign_protocol")
def assign_protocol(
    subject_name: str,
    payload: AssignProtocolPayload,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    subject = session.exec(select(Subject).where(Subject.name == subject_name)).first()
    if not subject:
        raise HTTPException(404, "Subject not found")

    protocol = session.get(ProtocolTemplate, payload.protocol_id)
    if not protocol:
        raise HTTPException(404, "Protocol does not exist")

    subject.next_protocol_id = payload.protocol_id
    session.add(subject)
    session.commit()

    return {
        "status": "assigned",
        "subject": subject.name,
        "next_protocol_id": payload.protocol_id,
        "protocol_name": protocol.name,
        "note": "Run will be created only when a session starts.",
    }


# ----------------------------------------------------------
# PROTOCOL CREATION & LISTING
# ----------------------------------------------------------

@app.post("/protocols", response_model=ProtocolRead, status_code=201)
def create_protocol(
    payload: ProtocolCreate,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    existing = session.exec(
        select(ProtocolTemplate).where(ProtocolTemplate.name == payload.name)
    ).first()
    if existing:
        raise HTTPException(400, "Protocol already exists")

    prot = ProtocolTemplate(name=payload.name, description=payload.description)
    session.add(prot)
    session.commit()
    session.refresh(prot)

    for s in payload.steps:
        step = ProtocolStepTemplate(
            order_index=s.order_index,
            step_name=s.step_name,
            task_type=s.task_type,
            params=s.params,
            protocol_id=prot.id,
        )
        session.add(step)

    session.commit()

    steps = session.exec(
        select(ProtocolStepTemplate).where(ProtocolStepTemplate.protocol_id == prot.id)
    ).all()

    return ProtocolRead(
        id=prot.id,
        name=prot.name,
        description=prot.description,
        created_at=prot.created_at,
        steps=steps,
    )


@app.get("/protocols", response_model=List[ProtocolRead])
def list_protocols(
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    protos = session.exec(select(ProtocolTemplate)).all()
    output: List[ProtocolRead] = []

    for p in protos:
        steps = session.exec(
            select(ProtocolStepTemplate).where(ProtocolStepTemplate.protocol_id == p.id)
        ).all()
        output.append(
            ProtocolRead(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
                steps=steps,
            )
        )

    return output


@app.get("/protocols/{protocol_id}", response_model=ProtocolRead)
def get_protocol(
    protocol_id: int,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    p = session.get(ProtocolTemplate, protocol_id)
    if not p:
        raise HTTPException(404, "Protocol not found")

    steps = session.exec(
        select(ProtocolStepTemplate).where(ProtocolStepTemplate.protocol_id == protocol_id)
    ).all()

    return ProtocolRead(
        id=p.id,
        name=p.name,
        description=p.description,
        created_at=p.created_at,
        steps=steps,
    )


# ----------------------------------------------------------
# INTERNAL HELPER: start session for all pending subjects
# ----------------------------------------------------------

def _start_session_for_pending_subjects(db: SQLModelSession) -> dict:
    """
    Internal helper used by /sessions/start and /sessions/{id}/launch.
    Creates a new session_id and SubjectProtocolRun rows for all subjects
    that currently have next_protocol_id set.
    """

    last_session_id = db.exec(
        select(SubjectProtocolRun.session_id).order_by(SubjectProtocolRun.session_id.desc())
    ).first()
    next_session_id = (last_session_id or 0) + 1

    subjects = db.exec(select(Subject).where(Subject.next_protocol_id != None)).all()

    if not subjects:
        return {
            "status": "no_subjects_waiting",
            "session_id": next_session_id,
            "runs_started": [],
        }

    started_runs = []

    for subj in subjects:
        if subj.next_protocol_id is None:
            continue

        run = SubjectProtocolRun(
            subject_id=subj.id,
            protocol_id=subj.next_protocol_id,
            current_step=0,
            session_id=next_session_id,
            started_at=datetime.utcnow(),
            finished_at=None,
        )

        db.add(run)
        db.commit()
        db.refresh(run)

        subj.current_run_id = run.id
        subj.next_protocol_id = None
        db.add(subj)
        db.commit()

        started_runs.append(
            {
                "subject": subj.name,
                "run_id": run.id,
                "protocol_id": run.protocol_id,
                "session_id": next_session_id,
                "started_at": run.started_at,
            }
        )

    return {
        "status": "session_started",
        "session_id": next_session_id,
        "runs_started": started_runs,
    }


@app.post("/sessions/start")
def start_session(
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    return _start_session_for_pending_subjects(session)


# ----------------------------------------------------------
# SESSION LISTING / BLUEPRINTS (using SubjectProtocolRun.session_id)
# ----------------------------------------------------------

@app.get("/sessions")
def list_sessions(
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    runs = session.exec(select(SubjectProtocolRun)).all()
    by_session = {}

    for r in runs:
        by_session.setdefault(r.session_id, []).append(r)

    summaries = []
    for session_id, sruns in sorted(by_session.items(), key=lambda kv: kv[0], reverse=True):
        started_at = min(r.started_at for r in sruns)
        summaries.append(
            {
                "session_id": session_id,
                "started_at": started_at,
                "n_runs": len(sruns),
            }
        )

    return summaries


@app.get("/sessions/{session_id}")
def get_session_detail(
    session_id: int,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    runs = session.exec(
        select(SubjectProtocolRun).where(SubjectProtocolRun.session_id == session_id)
    ).all()

    if not runs:
        raise HTTPException(404, "Session not found")

    started_at = min(r.started_at for r in runs)

    run_details = []
    for r in runs:
        subj = session.get(Subject, r.subject_id)
        proto = session.get(ProtocolTemplate, r.protocol_id)

        run_details.append(
            {
                "run_id": r.id,
                "subject_id": r.subject_id,
                "subject_name": subj.name if subj else f"id={r.subject_id}",
                "protocol_id": r.protocol_id,
                "protocol_name": proto.name if proto else f"id={r.protocol_id}",
                "started_at": r.started_at,
                "finished_at": r.finished_at,
            }
        )

    return {
        "session_id": session_id,
        "started_at": started_at,
        "n_runs": len(runs),
        "runs": run_details,
    }


@app.post("/sessions/{session_id}/launch")
def launch_session_blueprint(
    session_id: int,
    session: SQLModelSession = Depends(get_session),
    _: dict = Depends(verify_token),
):
    template_runs = session.exec(
        select(SubjectProtocolRun).where(SubjectProtocolRun.session_id == session_id)
    ).all()

    if not template_runs:
        raise HTTPException(404, "Session not found")

    for r in template_runs:
        subj = session.get(Subject, r.subject_id)
        if not subj:
            continue
        subj.next_protocol_id = r.protocol_id
        session.add(subj)

    session.commit()

    result = _start_session_for_pending_subjects(session)
    result["source_session_id"] = session_id
    result["status"] = "blueprint_launched"
    return result


# ----------------------------------------------------------
# PILOTS (pure SQLAlchemy)
# ----------------------------------------------------------

@app.get("/pilots", response_model=List[PilotRead])
def list_pilots(
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        pilots = db.query(Pilot).all()
        return pilots
    finally:
        db.close()


@app.post("/pilots", response_model=PilotRead)
def create_or_update_pilot(
    payload: PilotCreate,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        existing = db.query(Pilot).filter(Pilot.name == payload.name).one_or_none()

        if existing:
            for k, v in payload.dict().items():
                setattr(existing, k, v)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing

        new_pilot = Pilot(**payload.dict())
        db.add(new_pilot)
        db.commit()
        db.refresh(new_pilot)
        return new_pilot
    finally:
        db.close()

@app.get("/pilots/{pilot_id}", response_model=PilotRead)
def get_pilot(
    pilot_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        pilot = db.query(Pilot).get(pilot_id)
        if not pilot:
            raise HTTPException(status_code=404, detail="Pilot not found")
        return pilot
    finally:
        db.close()



# ----------------------------------------------------------
# SESSION RUNS (Pilot‑bound blueprint execution)
# ----------------------------------------------------------

@app.post("/session-runs", response_model=SessionRunRead, status_code=201)
@app.post("/session-runs", response_model=SessionRunRead, status_code=201)
def create_session_run(
    payload: SessionRunCreate,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        # 1) Only one RUNNING run per blueprint session
        active = (
            db.query(SessionRun)
            .filter(
                SessionRun.session_id == payload.session_id,
                SessionRun.status == SessionRunStatus.RUNNING,
            )
            .one_or_none()
        )
        if active:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Session {payload.session_id} already has an active run "
                    f"on pilot {active.pilot_id}"
                ),
            )

        # 2) Get OR CREATE a Session row with this id
        session_obj = db.query(Session).get(payload.session_id)
        if not session_obj:
            session_obj = Session(
                id=payload.session_id,
                name=f"Blueprint {payload.session_id}",
                label=f"Blueprint {payload.session_id}",
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)

        # 3) Pilot must already exist
        pilot_obj = db.query(Pilot).get(payload.pilot_id)
        if not pilot_obj:
            raise HTTPException(status_code=404, detail="Pilot not found")

        # 4) Create SessionRun
        run = SessionRun(
            session_id=session_obj.id,
            pilot_id=pilot_obj.id,
            status=SessionRunStatus.RUNNING,
            subject_key="",  # set after flush
        )
        db.add(run)
        db.flush()  # assigns run.id

        run.subject_key = f"bp_s{session_obj.id}_r{run.id}"
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()




@app.get("/sessions/{session_id}/active-run", response_model=SessionRunRead | None)
def get_active_run(
    session_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = (
            db.query(SessionRun)
            .filter(
                SessionRun.session_id == session_id,
                SessionRun.status == SessionRunStatus.RUNNING,
            )
            .one_or_none()
        )
        return run
    finally:
        db.close()


@app.post("/session-runs/{run_id}/stop", response_model=SessionRunRead)
def stop_session_run(
    run_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        run.status = SessionRunStatus.STOPPED
        run.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()
