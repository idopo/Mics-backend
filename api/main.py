# api/main.py
from typing import List

from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlmodel import SQLModel, Session as SQLModelSession, select
from auth import verify_token
from db import engine, get_session
from models import (
    Subject,
    SubjectCreate,
    SubjectRead,
    SubjectProtocolRun,
    AssignProtocolPayload,
    ProtocolTemplate,
    ProtocolStepTemplate,
    ProtocolCreate,
    ProtocolRead,

    TaskDefinition,
    TaskInheritance,
    PilotTaskCapability,
    TaskDescriptor,
    PilotTaskHandshake,

    Pilot,
    PilotCreate,
    PilotRead,
    Session,
    SessionRun,
    SessionRunCreate,
    SessionRunRead,
    SessionRunStatus,
    RunProgress,
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


@app.post("/pilots/{pilot_id}/tasks")
def upsert_pilot_tasks(
    pilot_id: int,
    payload: PilotTaskHandshake,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        pilot = db.query(Pilot).get(pilot_id)
        if not pilot:
            raise HTTPException(404, "Pilot not found")

        # --------------------------------------------------
        # PHASE 1: ensure all TaskDefinitions exist
        # --------------------------------------------------
        task_defs_by_name: dict[str, TaskDefinition] = {}

        for task in payload.tasks:
            task_def = (
                db.query(TaskDefinition)
                .filter(TaskDefinition.file_hash == task.file_hash)
                .one_or_none()
            )

            if not task_def:
                task_def = TaskDefinition(
                    task_name=task.task_name,
                    base_class_name=task.base_class,
                    module=task.module,
                    params=task.params,
                    hardware=task.hardware,
                    file_hash=task.file_hash,
                )
                db.add(task_def)
                db.flush()

            task_defs_by_name[task.task_name] = task_def

        # --------------------------------------------------
        # PHASE 2: resolve inheritance (STRICT)
        # --------------------------------------------------
        for task in payload.tasks:
            if not task.base_class:
                continue

            child_def = task_defs_by_name[task.task_name]
            base_def = task_defs_by_name.get(task.base_class)

            if not base_def:
                raise HTTPException(
                    400,
                    f"Base class '{task.base_class}' not found for task '{task.task_name}'",
                )

            exists = (
                db.query(TaskInheritance)
                .filter(
                    TaskInheritance.task_definition_id == child_def.id,
                    TaskInheritance.base_definition_id == base_def.id,
                )
                .one_or_none()
            )

            if not exists:
                db.add(
                    TaskInheritance(
                        task_definition_id=child_def.id,
                        base_definition_id=base_def.id,
                    )
                )

        # --------------------------------------------------
        # PHASE 3: upsert pilot task capabilities (DEDUPED)
        # --------------------------------------------------
        now = datetime.utcnow()

        unique_task_defs = {td.id: td for td in task_defs_by_name.values()}.values()

        for task_def in unique_task_defs:
            cap = (
                db.query(PilotTaskCapability)
                .filter(
                    PilotTaskCapability.pilot_id == pilot.id,
                    PilotTaskCapability.task_definition_id == task_def.id,
                )
                .one_or_none()
            )

            if cap:
                cap.last_seen_at = now
            else:
                db.add(
                    PilotTaskCapability(
                        pilot_id=pilot.id,
                        task_definition_id=task_def.id,
                        last_seen_at=now,
                    )
                )

        db.commit()

        return {
            "status": "ok",
            "pilot_id": pilot.id,
            "tasks_received": len(payload.tasks),
        }

    finally:
        db.close()



# ----------------------------------------------------------
# SESSION RUNS (Pilot-bound blueprint execution)
# ----------------------------------------------------------

@app.post("/session-runs", response_model=SessionRunRead, status_code=201)
def create_session_run(
    payload: SessionRunCreate,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        mode = (payload.mode or "new").lower()

        # --------------------------------------------------
        # 1) Find recoverable run (STOPPED/ERROR), unless mode == "new"
        # --------------------------------------------------
        recoverable = None
        if mode != "new":
            recoverable = (
                db.query(SessionRun)
                .filter(
                    SessionRun.session_id == payload.session_id,
                    SessionRun.pilot_id == payload.pilot_id,
                    SessionRun.status.in_([
                        SessionRunStatus.STOPPED,
                        SessionRunStatus.ERROR,
                    ]),
                )
                .order_by(SessionRun.id.desc())
                .first()
            )

        # --------------------------------------------------
        # 2) Resume: reuse row, keep progress, keep index
        # --------------------------------------------------
        if recoverable and mode == "resume":
            recoverable.status = SessionRunStatus.PENDING
            recoverable.started_at = datetime.utcnow()
            recoverable.ended_at = None
            recoverable.error_type = None
            recoverable.error_message = None
            recoverable.mode = mode
            recoverable.overrides = payload.overrides or None
            db.commit()
            db.refresh(recoverable)
            return recoverable

        # --------------------------------------------------
        # 3) Restart: reuse row, reset progress, keep index
        # --------------------------------------------------
        if recoverable and mode == "restart":
            prog = (
                db.query(RunProgress)
                .filter(RunProgress.run_id == recoverable.id)
                .one_or_none()
            )
            if prog:
                db.delete(prog)
                db.flush()  # ensure deleted before continuing

            recoverable.status = SessionRunStatus.PENDING
            recoverable.started_at = datetime.utcnow()
            recoverable.ended_at = None
            recoverable.error_type = None
            recoverable.error_message = None
            recoverable.mode = mode
            recoverable.overrides = payload.overrides or None

            # ✅ DO NOT touch recoverable.session_run_index
            db.commit()
            db.refresh(recoverable)
            return recoverable

        # --------------------------------------------------
        # 4) Otherwise: create a BRAND NEW SessionRun row
        #    and assign a new session_run_index by bumping Session.run_counter
        # --------------------------------------------------

        # Ensure Session exists
        session_obj = db.query(Session).get(payload.session_id)
        if not session_obj:
            session_obj = Session(
                id=payload.session_id,
                name=f"Blueprint {payload.session_id}",
                label=f"Blueprint {payload.session_id}",
                # run_counter defaults to 0 in DB/model
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)

        # Ensure Pilot exists
        pilot_obj = db.query(Pilot).get(payload.pilot_id)
        if not pilot_obj:
            raise HTTPException(404, "Pilot not found")

        # ✅ Lock the session row to atomically increment run_counter
        locked_session = (
            db.query(Session)
            .filter(Session.id == session_obj.id)
            .with_for_update()
            .one()
        )
        locked_session.run_counter = int(locked_session.run_counter or 0) + 1
        new_index = locked_session.run_counter

        # Create the run
        run = SessionRun(
            session_id=session_obj.id,
            pilot_id=pilot_obj.id,
            status=SessionRunStatus.PENDING,
            subject_key="",  # server sets after flush
            mode=mode,       # usually "new"
            overrides=payload.overrides or None,
            session_run_index=new_index,  # ✅ stable index
        )

        db.add(run)
        db.flush()  # assigns run.id

        # Set subject_key after we have the run id
        run.subject_key = f"bp_s{session_obj.id}_r{run.id}"

        db.commit()
        db.refresh(run)
        return run

    finally:
        db.close()


@app.get("/sessions/{session_id}/pilots/{pilot_id}/latest-run")
def latest_run(session_id: int, pilot_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        run = (
            db.query(SessionRun)
            .filter(SessionRun.session_id == session_id, SessionRun.pilot_id == pilot_id)
            .order_by(SessionRun.id.desc())
            .first()
        )
        if not run:
            return None

        prog = run.progress
        return {
            "run": {
                "id": run.id,
                "status": run.status,
                "mode": run.mode,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
                "error_type": run.error_type,
                "error_message": run.error_message,
            },
            "progress": {
                "current_step": prog.current_step_idx if prog else None,
                "current_trial": prog.current_trial if prog else None,
            },
        }
    finally:
        db.close()


from sqlalchemy import desc
from sqlalchemy.orm import Session as OrmSession
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy import desc

class LatestRunsBulkPayload(BaseModel):
    session_ids: List[int]

@app.post("/sessions/pilots/{pilot_id}/latest-runs")
def latest_runs_bulk(pilot_id: int, payload: LatestRunsBulkPayload, _: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        out: Dict[str, Any] = {}

        for session_id in payload.session_ids:
            run = (
                db.query(SessionRun)
                .filter(SessionRun.session_id == session_id, SessionRun.pilot_id == pilot_id)
                .order_by(desc(SessionRun.id))
                .first()
            )

            if not run:
                out[str(session_id)] = None
                continue

            prog = run.progress
            out[str(session_id)] = {
                "run": {
                    "id": run.id,
                    "session_id": run.session_id,
                    "pilot_id": run.pilot_id,
                    "status": run.status,
                    "mode": getattr(run, "mode", "new") or "new",
                    "started_at": run.started_at,
                    "ended_at": run.ended_at,
                },
                "progress": {
                    "current_step": prog.current_step_idx if prog else None,
                    "current_trial": prog.current_trial if prog else None,
                },
            }

        return out
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
def stop_session_run(run_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        # idempotent
        if run.status == SessionRunStatus.STOPPED:
            return run

        if run.status not in (
            SessionRunStatus.RUNNING,
            SessionRunStatus.PENDING,
        ):
            raise HTTPException(
                400, f"Cannot stop run in status={run.status}"
            )

        run.status = SessionRunStatus.STOPPED
        run.ended_at = datetime.utcnow()

        # ⚠️ DO NOT reset RunProgress
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


@app.post("/runs/{run_id}/progress/increment")
def increment_trial_counter(run_id: int, _: dict = Depends(verify_token)):
    """
    Increments the trial counter for a SessionRun.
    Creates RunProgress if needed, loading step0 from ProtocolStepTemplate.
    Graduation logic is handled here.
    """
    db = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        # ------------- LOAD OR CREATE PROGRESS ROW -------------
        prog = run.progress
        if not prog:
            # 1) find SubjectProtocolRun for this session
            template_run = (
                db.query(SubjectProtocolRun)
                .filter(SubjectProtocolRun.session_id == run.session_id)
                .first()
            )
            if not template_run:
                raise HTTPException(500, "No template SubjectProtocolRun found")

            # 2) load protocol steps manually (NO relationship)
            steps = (
                db.query(ProtocolStepTemplate)
                .filter(ProtocolStepTemplate.protocol_id == template_run.protocol_id)
                .order_by(ProtocolStepTemplate.order_index)
                .all()
            )
            if not steps:
                raise HTTPException(500, "Protocol has no steps")

            step0 = steps[0]
            grad = step0.params.get("graduation", {}) if step0.params else {}

            prog = RunProgress(
                run_id=run_id,
                current_step_idx=0,
                current_trial=0,
                graduation_type=grad.get("type"),
                graduation_params=grad.get("value"),
                session_progress_index=run.session_run_index,
            )
            db.add(prog)
            db.commit()
            db.refresh(prog)

        # ------------- INCREMENT TRIAL COUNTER -------------
        prog.current_trial += 1
        db.commit()
        db.refresh(prog)

        # ------------- CHECK GRADUATION -------------
        should_graduate = False
        if prog.graduation_type == "NTrials":
            # graduation_params.current_trial == N required trials
            n_required = int(prog.graduation_params.get("current_trial", 0))

            # Defensive: 0 means "never graduate"
            if n_required > 0 and prog.current_trial >= n_required:
                should_graduate = True


        return {
            "should_graduate": should_graduate,
            "current_trial": prog.current_trial,
            "current_step": prog.current_step_idx,
        }

    finally:
        db.close()


@app.post("/runs/{run_id}/progress/advance_step")
def advance_step(run_id: int, _: dict = Depends(verify_token)):
    db = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        prog = run.progress
        if not prog:
            raise HTTPException(400, "Progress not initialized")

        # get protocol steps for this run
        template_runs = db.query(SubjectProtocolRun).filter(
            SubjectProtocolRun.session_id == run.session_id
        ).all()
        proto_id = template_runs[0].protocol_id
        steps = db.query(ProtocolStepTemplate).filter(
            ProtocolStepTemplate.protocol_id == proto_id
        ).order_by(ProtocolStepTemplate.order_index).all()

        if prog.current_step_idx >= len(steps) - 1:
            return {"finished": True}

        prog.current_step_idx += 1
        prog.current_trial = 0

        next_step = steps[prog.current_step_idx]
        grad = next_step.params.get("graduation", {})

        prog.graduation_type = grad.get("type")
        prog.graduation_params = grad.get("value")

        db.commit()
        db.refresh(prog)

        return {
            "finished": False,
            "current_step": prog.current_step_idx,
            "graduation": prog.graduation_type,
        }

    finally:
        db.close()

@app.get("/session-runs/by-subject-key/{key}", response_model=SessionRunRead)
def get_run_by_subject_key(key: str, _: dict = Depends(verify_token)):
    db = SA_SessionLocal()
    try:
        run = db.query(SessionRun).filter(SessionRun.subject_key == key).one_or_none()
        if not run:
            raise HTTPException(404, "Run not found")
        return run
    finally:
        db.close()



@app.post("/session-runs/{run_id}/mark-running", response_model=SessionRunRead)
def mark_run_running(
    run_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # ✅ idempotent: already running is OK
        if run.status == SessionRunStatus.RUNNING:
            return run

        # ✅ allow resume from STOPPED
        if run.status not in (
            SessionRunStatus.PENDING,
            SessionRunStatus.STOPPED,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Run {run_id} cannot start from status={run.status}",
            )

        run.status = SessionRunStatus.RUNNING
        run.started_at = datetime.utcnow()
        run.ended_at = None

        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()

@app.post("/session-runs/{run_id}/error", response_model=SessionRunRead)
def mark_run_error(
    run_id: int,
    error_type: str = "UnknownError",
    error_message: str = "",
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        run.status = SessionRunStatus.ERROR
        run.ended_at = datetime.utcnow()
        run.error_type = str(error_type)
        run.error_message = str(error_message)

        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()



@app.post("/session-runs/legacy-start", response_model=SessionRunRead, status_code=201)
def legacy_create_and_start_session_run(
    payload: SessionRunCreate,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
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

        pilot_obj = db.query(Pilot).get(payload.pilot_id)
        if not pilot_obj:
            raise HTTPException(status_code=404, detail="Pilot not found")

        run = SessionRun(
            session_id=session_obj.id,
            pilot_id=pilot_obj.id,
            status=SessionRunStatus.RUNNING,
            subject_key="",
        )
        db.add(run)
        db.flush()

        run.subject_key = f"bp_s{session_obj.id}_r{run.id}"
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


@app.get("/session-runs/{run_id}", response_model=SessionRunRead)
def get_session_run(
    run_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run
    finally:
        db.close()

@app.post("/session-runs/{run_id}/complete", response_model=SessionRunRead)
def complete_session_run(
    run_id: int,
    _: dict = Depends(verify_token),
):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        # 1️⃣ mark run completed
        run.status = SessionRunStatus.COMPLETED
        run.ended_at = datetime.utcnow()

        # 2️⃣ re-arm subjects for next execution
        template_runs = (
            db.query(SubjectProtocolRun)
            .filter(SubjectProtocolRun.session_id == run.session_id)
            .all()
        )

        for tr in template_runs:
            subj = db.query(Subject).get(tr.subject_id)
            if subj:
                subj.next_protocol_id = tr.protocol_id
                db.add(subj)

        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()



@app.get("/session-runs/{run_id}/with-progress")
def get_run_with_progress(run_id: int, _: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        run = db.query(SessionRun).get(run_id)
        if not run:
            raise HTTPException(404, "Run not found")

        prog = run.progress

        return {
            "run": {
                "id": run.id,
                "session_id": run.session_id,
                "pilot_id": run.pilot_id,
                "status": run.status,
                "subject_key": run.subject_key,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
            },
            "progress": {
                "current_step": prog.current_step_idx if prog else None,
                "current_trial": prog.current_trial if prog else None,
                # ✅ ADD THIS
                "session_progress_index": (
                    prog.session_progress_index if prog else run.session_run_index
                ),
            },
        }
    finally:
        db.close()




@app.get("/tasks")
def list_tasks(_: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        tasks = db.query(TaskDefinition).order_by(TaskDefinition.task_name).all()
        return [
            {
                "id": t.id,
                "task_name": t.task_name,
                "base_class": t.base_class_name,
                "module": t.module,
                "default_params": t.params or {},
            }
            for t in tasks
        ]
    finally:
        db.close()


@app.get("/sessions/{session_id}/pilots/{pilot_id}/start-options")
def start_options(session_id: int, pilot_id: int, _: dict = Depends(verify_token)):
    """
    Return whether there's an active run, a recoverable run (STOPPED/ERROR),
    and existing progress for that run.
    """
    db: OrmSession = SA_SessionLocal()
    try:
        # active RUNNING run for this pilot + session
        active = (
            db.query(SessionRun)
            .filter(
                SessionRun.session_id == session_id,
                SessionRun.pilot_id == pilot_id,
                SessionRun.status == SessionRunStatus.RUNNING,
            )
            .one_or_none()
        )

        # recoverable STOPPED / ERROR run
        recoverable = (
            db.query(SessionRun)
            .filter(
                SessionRun.session_id == session_id,
                SessionRun.pilot_id == pilot_id,
                SessionRun.status.in_([SessionRunStatus.STOPPED, SessionRunStatus.ERROR]),
            )
            .order_by(SessionRun.id.desc())
            .first()
        )

        progress = None
        if recoverable:
            prog = db.query(RunProgress).filter(RunProgress.run_id == recoverable.id).one_or_none()
            if prog:
                progress = {
                    "current_step": prog.current_step_idx,
                    "current_trial": prog.current_trial,
                    "graduation_type": prog.graduation_type,
                    "graduation_params": prog.graduation_params,
                }

        return {
            "session_id": session_id,
            "pilot_id": pilot_id,
            "active_run": {"id": active.id, "status": active.status} if active else None,
            "recoverable_run": {"id": recoverable.id, "status": recoverable.status} if recoverable else None,
            "progress": progress,
            "can_resume": recoverable is not None and progress is not None,
            "can_start_over": True,  # always allow restart (resets progress)
        }
    finally:
        db.close()



# @app.get("/tasks/leaf")
# def list_leaf_tasks(_: dict = Depends(verify_token)):
#     db: OrmSession = SA_SessionLocal()
#     try:
#         # ---------------------------------------------
#         # 1) Find all base task IDs
#         # ---------------------------------------------
#         base_task_ids = {
#             row.base_definition_id
#             for row in db.query(TaskInheritance.base_definition_id).all()
#         }

#         # ---------------------------------------------
#         # 2) Select tasks that are NOT base classes
#         # ---------------------------------------------
#         leaf_tasks = (
#             db.query(TaskDefinition)
#             .filter(~TaskDefinition.id.in_(base_task_ids))
#             .order_by(TaskDefinition.task_name)
#             .all()
#         )

#         # ---------------------------------------------
#         # 3) Resolve merged hardware (task + bases)
#         # ---------------------------------------------
#         def resolve_hardware(task_def: TaskDefinition) -> Dict[str, Any]:
#             merged: Dict[str, Any] = {}

#             visited = set()
#             stack = [task_def]

#             while stack:
#                 cur = stack.pop()
#                 if cur.id in visited:
#                     continue
#                 visited.add(cur.id)

#                 if cur.hardware:
#                     merged.update(cur.hardware)

#                 parents = (
#                     db.query(TaskDefinition)
#                     .join(
#                         TaskInheritance,
#                         TaskInheritance.base_definition_id == TaskDefinition.id,
#                     )
#                     .filter(TaskInheritance.task_definition_id == cur.id)
#                     .all()
#                 )

#                 stack.extend(parents)

#             return merged

#         # ---------------------------------------------
#         # 4) Serialize
#         # ---------------------------------------------
#         return [
#             {
#                 "id": t.id,
#                 "task_name": t.task_name,
#                 "base_class": t.base_class_name,
#                 "module": t.module,
#                 "default_params": t.params or {},
#                 "merged_hardware": resolve_hardware(t),
#             }
#             for t in leaf_tasks
#         ]

#     finally:
#         db.close()


@app.get("/tasks/leaf")
def list_leaf_tasks(_: dict = Depends(verify_token)):
    db: OrmSession = SA_SessionLocal()
    try:
        # If table is empty, return empty list (not 500)
        all_tasks = db.query(TaskDefinition).all()
        if not all_tasks:
            return []

        base_names = {
            t.base_class_name
            for t in all_tasks
            if t.base_class_name
        }

        leaf_tasks = [
            t for t in all_tasks
            if t.task_name not in base_names
        ]

        return [
            {
                "id": t.id,
                "task_name": t.task_name,
                "base_class": t.base_class_name,
                "module": t.module,
                "default_params": t.params or {},
                "hardware": t.hardware or {},
                "file_hash": t.file_hash,
            }
            for t in leaf_tasks
        ]

    except Exception as e:
        # 🔥 CRITICAL: surface real error
        raise HTTPException(
            status_code=500,
            detail=f"/tasks/leaf failed: {type(e).__name__}: {e}",
        )
    finally:
        db.close()
