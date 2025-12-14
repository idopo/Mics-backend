# api/models.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field


# ============================================================
# DATABASE TABLES (SQLModel only)
# ============================================================

class Subject(SQLModel, table=True):
    __tablename__ = "subjects"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

    # Pointer to the currently active run for this subject (if any)
    current_run_id: Optional[int] = Field(
        default=None,
        foreign_key="subject_protocol_runs.id",
    )


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
    params: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    protocol_id: int = Field(foreign_key="protocol_templates.id")


class ProtocolSession(SQLModel, table=True):
    """
    One execution 'event' of a protocol.
    Can include one or many subjects (each has a SubjectProtocolRun).
    """
    __tablename__ = "protocol_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)

    protocol_id: int = Field(foreign_key="protocol_templates.id")
    label: Optional[str] = None

    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class SubjectProtocolRun(SQLModel, table=True):
    """
    A single subject's run inside a protocol (and optionally inside a ProtocolSession).
    """
    __tablename__ = "subject_protocol_runs"

    id: Optional[int] = Field(default=None, primary_key=True)

    subject_id: int = Field(foreign_key="subjects.id")
    protocol_id: int = Field(foreign_key="protocol_templates.id")

    # NEW: link this run to a protocol session (can be null for old runs)
    session_id: Optional[int] = Field(
        default=None,
        foreign_key="protocol_sessions.id",
    )

    current_step: int = Field(default=0)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


# ============================================================
# DTO MODELS (For API input/output)
# ============================================================

class SubjectCreate(SQLModel):
    name: str


class SubjectRead(SQLModel):
    id: int
    name: str
    current_run_id: Optional[int] = None


class AssignProtocolPayload(SQLModel):
    protocol_id: int


class StartSessionPayload(SQLModel):
    """
    Used by /sessions/start and by the assign_protocol wrapper.
    """
    protocol_id: int
    subject_names: List[str]
    label: Optional[str] = None


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
