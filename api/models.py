# api/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List

import enum

from sqlalchemy import Column, JSON as SAJSON
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

from sqlmodel import SQLModel, Field
from pydantic import BaseModel


# ============================================================
# SQLModel TABLES (new DB schema: subjects / protocols)
# ============================================================

class Subject(SQLModel, table=True):
    __tablename__ = "subjects"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

    # Current run actually active during execution
    current_run_id: Optional[int] = Field(
        default=None, foreign_key="subject_protocol_runs.id"
    )

    # Next protocol to use when session begins
    next_protocol_id: Optional[int] = Field(
        default=None, foreign_key="protocol_templates.id"
    )


class SubjectProtocolRun(SQLModel, table=True):
    __tablename__ = "subject_protocol_runs"

    id: Optional[int] = Field(default=None, primary_key=True)

    subject_id: int = Field(foreign_key="subjects.id")
    protocol_id: int = Field(foreign_key="protocol_templates.id")

    # belongs to a global session (blueprint/session)
    session_id: int

    current_step: int = Field(default=0)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class ProtocolTemplate(SQLModel, table=True):
    __tablename__ = "protocol_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProtocolStepTemplate(SQLModel, table=True):
    __tablename__ = "protocol_step_templates"

    id: Optional[int] = Field(default=None, primary_key=True)

    order_index: int
    step_name: str
    task_type: str

    # Arbitrary params we pass to Pilot
    params: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(SAJSON)
    )

    protocol_id: int = Field(foreign_key="protocol_templates.id")


# ============================================================
# DTOs for API (Pydantic / SQLModel schemas)
# ============================================================

class SubjectCreate(SQLModel):
    name: str


class SubjectRead(SQLModel):
    id: int
    name: str
    current_run_id: Optional[int] = None
    next_protocol_id: Optional[int] = None


class AssignProtocolPayload(SQLModel):
    protocol_id: int


class ProtocolStepTemplateCreate(SQLModel):
    order_index: int
    step_name: str
    task_type: str
    params: Optional[Dict[str, Any]] = None


class ProtocolCreate(SQLModel):
    name: str
    description: Optional[str] = None
    steps: List[ProtocolStepTemplateCreate]


class ProtocolRead(SQLModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    steps: List[ProtocolStepTemplate]


# ============================================================
# LEGACY SQLAlchemy TABLES (Pilots, Sessions, SessionRun)
# ============================================================

Base = declarative_base()


class Pilot(Base):
    __tablename__ = "pilots"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    ip = Column(String, nullable=True)
    prefs = Column(SAJSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PilotBase(BaseModel):
    name: str
    ip: Optional[str] = None
    prefs: Optional[dict] = None


class PilotCreate(PilotBase):
    pass


class PilotRead(PilotBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    label = Column(String, nullable=True)

    runs = relationship("SessionRun", back_populates="session")


class SessionRunStatus(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"
    PENDING = "pending"


class SessionRun(Base):
    __tablename__ = "session_runs"

    id = Column(Integer, primary_key=True)

    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    pilot_id = Column(Integer, ForeignKey("pilots.id"), nullable=False)

    subject_key = Column(String, nullable=False)

    status = Column(
        SAEnum(SessionRunStatus, name="session_run_status"),
        nullable=False,
        default=SessionRunStatus.PENDING,
    )

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="runs")
    pilot = relationship("Pilot")
    progress = relationship("RunProgress", uselist=False, backref="run")



# Added cleanly & correctly:
class RunProgress(Base):
    __tablename__ = "run_progress"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("session_runs.id"), nullable=False)

    current_step_idx = Column(Integer, nullable=False, default=0)
    current_trial = Column(Integer, nullable=False, default=0)

    graduation_type = Column(String, nullable=True)
    graduation_params = Column(SAJSON, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ------------------ SessionRun Pydantic Schemas ------------------------

class SessionRunCreate(BaseModel):
    session_id: int
    pilot_id: int
    subject_key: Optional[str] = None  # server sets this

class SessionRunRead(BaseModel):
    id: int
    session_id: int
    pilot_id: int
    subject_key: str
    status: SessionRunStatus
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        orm_mode = True   # for Pydantic v1
        # from_attributes = True  # if using Pydantic v2

