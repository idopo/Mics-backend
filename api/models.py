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

    # Active run pointer
    current_run_id: Optional[int] = Field(default=None, foreign_key="subject_protocol_runs.id")


class SubjectProtocolRun(SQLModel, table=True):
    __tablename__ = "subject_protocol_runs"

    id: Optional[int] = Field(default=None, primary_key=True)

    subject_id: int = Field(foreign_key="subjects.id")
    protocol_id: int = Field(foreign_key="protocol_templates.id")

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
    params: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    protocol_id: int = Field(foreign_key="protocol_templates.id")


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
