# api/main.py
from typing import List
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status
from sqlmodel import SQLModel, Session, select

from db import engine, get_session
from auth import verify_token

from models import (
    Subject,
    SubjectCreate,
    SubjectRead,
    ProtocolTemplate,
    ProtocolStepTemplate,
    ProtocolCreate,
    ProtocolRead,
    ProtocolStepTemplateCreate,
    AssignProtocolPayload,
    StartSessionPayload,
    SubjectProtocolRun,
    ProtocolSession,
)


app = FastAPI(title="MICS Backend API")


# ----------------------------------------------------------
# Startup: Ensure tables exist
# ----------------------------------------------------------
@app.on_event("startup")
def startup():
    SQLModel.metadata.create_all(engine)


# ----------------------------------------------------------
# Health check
# ----------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ----------------------------------------------------------
# SUBJECTS
# ----------------------------------------------------------

@app.get("/subjects", response_model=List[SubjectRead])
def list_subjects(
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    return session.exec(select(Subject)).all()


@app.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    existing = session.exec(
        select(Subject).where(Subject.name == payload.name)
    ).first()

    if existing:
        raise HTTPException(400, "Subject already exists")

    subject = Subject(name=payload.name)
    session.add(subject)
    session.commit()
    session.refresh(subject)
    return subject


@app.get("/subjects/{subject_name}/runs")
def list_subject_runs(
    subject_name: str,
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    # Find subject by name
    subject = session.exec(
        select(Subject).where(Subject.name == subject_name)
    ).first()

    if not subject:
        raise HTTPException(404, "Subject not found")

    runs = session.exec(
        select(SubjectProtocolRun).where(
            SubjectProtocolRun.subject_id == subject.id
        )
    ).all()

    return runs


# ----------------------------------------------------------
# SESSIONS (NEW CORE CONCEPT)
# ----------------------------------------------------------

@app.post("/sessions/start")
def start_protocol_session(
    payload: StartSessionPayload,
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    """
    Start a protocol session for one or more subjects.

    This is the *core* logic. Even the per-subject assign_protocol endpoint
    will call into this.
    """
    protocol = session.get(ProtocolTemplate, payload.protocol_id)
    if not protocol:
        raise HTTPException(404, "Protocol not found")

    # Create session object first
    protocol_session = ProtocolSession(
        protocol_id=payload.protocol_id,
        label=payload.label,
    )
    session.add(protocol_session)
    session.flush()  # get protocol_session.id

    created_runs = []

    # Loop subjects; any failure will raise before commit (transaction aborts)
    for subj_name in payload.subject_names:
        subj = session.exec(
            select(Subject).where(Subject.name == subj_name)
        ).first()

        if not subj:
            # let the caller know exactly which subject is invalid
            raise HTTPException(404, f"Subject not found: {subj_name}")

        # Close old run if exists and is still open
        if subj.current_run_id:
            old_run = session.get(SubjectProtocolRun, subj.current_run_id)
            if old_run and old_run.finished_at is None:
                old_run.finished_at = datetime.utcnow()
                session.add(old_run)

        # Create new run linked to this session
        new_run = SubjectProtocolRun(
            subject_id=subj.id,
            protocol_id=protocol.id,
            session_id=protocol_session.id,
            current_step=0,
        )
        session.add(new_run)
        session.flush()  # populate new_run.id

        # Update subject pointer
        subj.current_run_id = new_run.id
        session.add(subj)

        created_runs.append(
            {
                "subject": subj.name,
                "run_id": new_run.id,
                "current_step": new_run.current_step,
            }
        )

    # All good, commit everything
    session.commit()

    return {
        "status": "ok",
        "protocol": protocol.name,
        "protocol_id": protocol.id,
        "session_id": protocol_session.id,
        "subjects": created_runs,
        "label": protocol_session.label,
        "started_at": protocol_session.started_at,
    }


# Thin wrapper – keeps old API but uses sessions under the hood
@app.post("/subjects/{subject_name}/assign_protocol")
def assign_protocol(
    subject_name: str,
    payload: AssignProtocolPayload,
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    """
    Backwards-compatible endpoint used by the Terminal GUI.

    Internally this just calls /sessions/start with a single subject.
    """
    start_payload = StartSessionPayload(
        protocol_id=payload.protocol_id,
        subject_names=[subject_name],
        label=None,
    )

    # Re-use the core session logic
    return start_protocol_session(
        payload=start_payload,
        session=session,
        jwt=jwt,
    )


# ----------------------------------------------------------
# PROTOCOLS
# ----------------------------------------------------------

@app.post("/protocols", response_model=ProtocolRead, status_code=201)
def create_protocol(
    payload: ProtocolCreate,
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    existing = session.exec(
        select(ProtocolTemplate).where(ProtocolTemplate.name == payload.name)
    ).first()

    if existing:
        raise HTTPException(400, "Protocol already exists")

    protocol = ProtocolTemplate(
        name=payload.name,
        description=payload.description,
    )
    session.add(protocol)
    session.commit()
    session.refresh(protocol)

    # create steps
    for step_in in payload.steps:
        step = ProtocolStepTemplate(
            order_index=step_in.order_index,
            step_name=step_in.step_name,
            task_type=step_in.task_type,
            params=step_in.params,
            protocol_id=protocol.id,
        )
        session.add(step)

    session.commit()

    steps = session.exec(
        select(ProtocolStepTemplate).where(
            ProtocolStepTemplate.protocol_id == protocol.id
        )
    ).all()

    return ProtocolRead(
        id=protocol.id,
        name=protocol.name,
        description=protocol.description,
        created_at=protocol.created_at,
        steps=steps,
    )


@app.get("/protocols", response_model=List[ProtocolRead])
def list_protocols(
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    protocols = session.exec(select(ProtocolTemplate)).all()

    output: List[ProtocolRead] = []
    for p in protocols:
        steps = session.exec(
            select(ProtocolStepTemplate).where(
                ProtocolStepTemplate.protocol_id == p.id
            )
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
    session: Session = Depends(get_session),
    jwt: dict = Depends(verify_token),
):
    p = session.get(ProtocolTemplate, protocol_id)
    if not p:
        raise HTTPException(status_code=404, detail="Protocol not found")

    steps = session.exec(
        select(ProtocolStepTemplate).where(
            ProtocolStepTemplate.protocol_id == protocol_id
        )
    ).all()

    return ProtocolRead(
        id=p.id,
        name=p.name,
        description=p.description,
        created_at=p.created_at,
        steps=steps,
    )
