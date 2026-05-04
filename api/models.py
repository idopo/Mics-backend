# api/models.py
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Dict, Any, List, Literal

import enum

from sqlalchemy import Column, JSON as SAJSON
from sqlalchemy import (
    Boolean,
    Integer,
    String,
    Text,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
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

    # Biology
    strain: Optional[str] = None
    genotype: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    dob: Optional[date] = None
    sex: Optional[str] = None
    rfid: Optional[int] = None

    # Administrative
    lead_researcher_id: Optional[int] = None  # bare int — no FK constraint (no migration for existing DBs)
    arrival_date: Optional[date] = None
    in_quarantine: Optional[bool] = Field(default=False)
    location: Optional[str] = None
    holding_conditions: Optional[str] = None
    group_type: Optional[str] = None
    group_details: Optional[str] = None
    notes: Optional[str] = None


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
    # bare int — no FK constraint at SQLModel level (task_definitions is SQLAlchemy-owned)
    task_definition_id: Optional[int] = None


# ============================================================
# NEW SQLModel TABLES (Project / Experiment hierarchy)
# ============================================================

class Researcher(SQLModel, table=True):
    __tablename__ = "researchers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_hidden: bool = Field(default=False)


class IACUCProtocol(SQLModel, table=True):
    __tablename__ = "iacuc_protocols"
    id: Optional[int] = Field(default=None, primary_key=True)
    number: str = Field(unique=True, index=True)
    title: str
    expires_at: Optional[date] = None
    is_hidden: bool = Field(default=False)


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None
    iacuc_id: Optional[int] = Field(default=None, foreign_key="iacuc_protocols.id")
    lead_researcher_id: Optional[int] = Field(default=None, foreign_key="researchers.id")
    results_notes: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Experiment(SQLModel, table=True):
    __tablename__ = "experiments"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    project_id: int = Field(foreign_key="projects.id")
    description: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExperimentProtocol(SQLModel, table=True):
    __tablename__ = "experiment_protocols"
    experiment_id: int = Field(foreign_key="experiments.id", primary_key=True)
    protocol_id: int = Field(foreign_key="protocol_templates.id", primary_key=True)


class SubjectProject(SQLModel, table=True):
    __tablename__ = "subject_projects"
    subject_id: int = Field(foreign_key="subjects.id", primary_key=True)
    project_id: int = Field(foreign_key="projects.id", primary_key=True)


class WeightMeasurement(SQLModel, table=True):
    __tablename__ = "weight_measurements"
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    measured_at: date
    weight_grams: float
    notes: Optional[str] = None


class SubjectSurgery(SQLModel, table=True):
    __tablename__ = "subject_surgeries"
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subjects.id", index=True)
    procedure_type: str
    performed_at: Optional[date] = None
    notes: Optional[str] = None


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
    strain: Optional[str] = None
    sex: Optional[str] = None
    group_type: Optional[str] = None


class AssignProtocolPayload(SQLModel):
    protocol_id: int


class ProtocolStepTemplateCreate(SQLModel):
    order_index: int
    step_name: str
    task_type: str
    params: Optional[Dict[str, Any]] = None
    task_definition_id: Optional[int] = None


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
# NEW DTOs (Project / Experiment / Subject extensions)
# ============================================================

class ResearcherCreate(SQLModel):
    name: str
    email: Optional[str] = None

class ResearcherUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None

class ResearcherRead(SQLModel):
    id: int
    name: str
    email: Optional[str] = None


class IACUCCreate(SQLModel):
    number: str
    title: str
    expires_at: Optional[date] = None

class IACUCRead(SQLModel):
    id: int
    number: str
    title: str
    expires_at: Optional[date] = None


class WeightCreate(SQLModel):
    measured_at: date
    weight_grams: float
    notes: Optional[str] = None

class WeightRead(SQLModel):
    id: int
    subject_id: int
    measured_at: date
    weight_grams: float
    notes: Optional[str] = None


class SurgeryCreate(SQLModel):
    procedure_type: str
    performed_at: Optional[date] = None
    notes: Optional[str] = None

class SurgeryRead(SQLModel):
    id: int
    subject_id: int
    procedure_type: str
    performed_at: Optional[date] = None
    notes: Optional[str] = None


class ProjectCreate(SQLModel):
    name: str
    description: Optional[str] = None
    iacuc_id: Optional[int] = None
    lead_researcher_id: Optional[int] = None
    results_notes: Optional[str] = None
    notes: Optional[str] = None

class ProjectRead(SQLModel):
    id: int
    name: str
    description: Optional[str] = None
    iacuc_id: Optional[int] = None
    lead_researcher_id: Optional[int] = None
    results_notes: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class ExperimentCreate(SQLModel):
    name: str
    project_id: int
    description: Optional[str] = None
    notes: Optional[str] = None

class ExperimentRead(SQLModel):
    id: int
    name: str
    project_id: int
    description: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class SubjectUpdate(SQLModel):
    strain: Optional[str] = None
    genotype: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    dob: Optional[date] = None
    sex: Optional[str] = None
    rfid: Optional[int] = None
    lead_researcher_id: Optional[int] = None
    arrival_date: Optional[date] = None
    in_quarantine: Optional[bool] = None
    location: Optional[str] = None
    holding_conditions: Optional[str] = None
    group_type: Optional[str] = None
    group_details: Optional[str] = None
    notes: Optional[str] = None


# SubjectExtendedRead defined last so WeightRead/SurgeryRead/ProjectRead are in scope
class SubjectExtendedRead(SQLModel):
    id: int
    name: str
    current_run_id: Optional[int] = None
    next_protocol_id: Optional[int] = None
    strain: Optional[str] = None
    genotype: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    dob: Optional[date] = None
    sex: Optional[str] = None
    rfid: Optional[int] = None
    lead_researcher_id: Optional[int] = None
    arrival_date: Optional[date] = None
    in_quarantine: Optional[bool] = None
    location: Optional[str] = None
    holding_conditions: Optional[str] = None
    group_type: Optional[str] = None
    group_details: Optional[str] = None
    notes: Optional[str] = None
    weights: List[WeightRead] = []
    surgeries: List[SurgeryRead] = []
    projects: List[ProjectRead] = []


# Resolve forward references (required for Pydantic v1 with nested schemas)
SubjectExtendedRead.update_forward_refs()


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
        from_attributes = True


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    label = Column(String, nullable=True)

    run_counter = Column(Integer, nullable=False, default=0)

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
        SAEnum(
            SessionRunStatus,
            name="session_run_status",
            native_enum=True,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=SessionRunStatus.PENDING,
    )

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    error_type = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    session = relationship("Session", back_populates="runs")
    pilot = relationship("Pilot")
    progress = relationship("RunProgress", uselist=False, backref="run")
    mode = Column(String, nullable=False, default="new")
    overrides = Column(SAJSON, nullable=True) 
    session_run_index = Column(Integer, nullable=False) 


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

    session_progress_index = Column(Integer, nullable=False)

# ------------------ SessionRun Pydantic Schemas ------------------------

class SessionRunCreate(BaseModel):
    session_id: int
    pilot_id: int
    subject_key: Optional[str] = None  # server sets this
    mode: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None 

class SessionRunRead(BaseModel):
    id: int
    session_id: int
    pilot_id: int
    subject_key: str
    status: SessionRunStatus
    started_at: datetime
    ended_at: Optional[datetime]
    mode: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None 

    class Config:
        from_attributes = True


# ------------------ TASK DEFINITIONS ------------------------

class TaskDefinition(Base):
    __tablename__ = "task_definitions"

    id = Column(Integer, primary_key=True)

    task_name = Column(String, index=True, nullable=False)
    base_class_name = Column(String, nullable=True)

    module = Column(String, nullable=False)

    params = Column(SAJSON, nullable=True)
    hardware = Column(SAJSON, nullable=True)

    file_hash = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    needs_migration = Column(Boolean, nullable=False, server_default="false", default=False)
    toolkit_id = Column(Integer, ForeignKey("task_toolkits.id"), nullable=True)


class TaskInheritance(Base):
    __tablename__ = "task_inheritance"

    task_definition_id = Column(
        Integer,
        ForeignKey("task_definitions.id"),
        primary_key=True,
    )

    base_definition_id = Column(
        Integer,
        ForeignKey("task_definitions.id"),
        primary_key=True,
    )


class PilotTaskCapability(Base):
    __tablename__ = "pilot_task_capabilities"

    pilot_id = Column(
        Integer,
        ForeignKey("pilots.id"),
        primary_key=True,
    )

    task_definition_id = Column(
        Integer,
        ForeignKey("task_definitions.id"),
        primary_key=True,
    )

    last_seen_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class TaskDescriptor(BaseModel):
    task_name: str
    base_class: Optional[str] = None
    module: str
    params: Optional[Dict[str, Any]] = None
    hardware: Optional[Dict[str, Any]] = None
    file_hash: str


class PilotTaskHandshake(BaseModel):
    tasks: List[TaskDescriptor]


class StartOnPilotPayload(BaseModel):
    pilot_id: int
    mode: Optional[Literal["resume", "restart", "new"]] = None
    overrides: Optional[Dict[str, Any]] = None


# ============================================================
# TOOLKIT TABLES (task_toolkits, toolkit_pilot_origins)
# ============================================================

class TaskToolkit(Base):
    __tablename__ = "task_toolkits"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)           # Python class name e.g. "AppetitiveTaskReal"
    hw_hash = Column(String, nullable=False)                    # SHA256 of sorted SEMANTIC_HARDWARE dict
    states = Column(SAJSON, nullable=True)                      # list of state names from HANDSHAKE.STAGE_NAMES
    flags = Column(SAJSON, nullable=True)                       # dict from HANDSHAKE.FLAGS
    params_schema = Column(SAJSON, nullable=True)               # normalized params dict (same shape as TaskDefinition.params)
    semantic_hardware = Column(SAJSON, nullable=True)           # dict: friendly_name -> [group, id]
    callable_methods = Column(SAJSON, nullable=True)            # list of callable method names
    required_packages = Column(SAJSON, nullable=True)           # list of pip package strings
    file_hash = Column(String, nullable=True)                   # hash of toolkit source file
    is_canonical = Column(Boolean, nullable=False, server_default="false", default=False)
    # Phase 11: backend-authored toolkit columns (added via run_toolkit_backend_authored_migrations)
    hardware_module_ids = Column(SAJSON, default=list)          # list of HardwareModule IDs
    locked_state_source = Column(String, nullable=True)         # task filename on Pi e.g. "appetitive.py"
    is_backend_authored = Column(Boolean, default=False)        # True = created via UI, False = from HANDSHAKE
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "hw_hash", name="uq_toolkit_name_hw_hash"),
    )


class ToolkitPilotOrigin(Base):
    __tablename__ = "toolkit_pilot_origins"

    id = Column(Integer, primary_key=True)
    toolkit_id = Column(Integer, ForeignKey("task_toolkits.id"), nullable=False)
    pilot_id = Column(Integer, ForeignKey("pilots.id"), nullable=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("toolkit_id", "pilot_id", name="uq_origin_toolkit_pilot"),
    )


# ============================================================
# HARDWARE LIBS (Phase 09)
# HardwareLibVersion declared before HardwareLib to satisfy FK ordering.
# active_version_id / stable_version_id use use_alter=True to break the
# circular dependency: hardware_libs ↔ hardware_lib_versions.
# ============================================================

class HardwareLibVersion(Base):
    __tablename__ = "hardware_lib_versions"

    id = Column(Integer, primary_key=True)
    hardware_lib_id = Column(Integer, ForeignKey("hardware_libs.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    source_code = Column(Text, nullable=False)
    sha256_hash = Column(String, nullable=False)
    state = Column(String, default="unvalidated")  # unvalidated | beta | stable
    ast_metadata = Column(SAJSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    stable_at = Column(DateTime, nullable=True)
    stable_reason = Column(String, nullable=True)   # 'user' | 'protocol_run'
    stable_pilot = Column(String, nullable=True)
    validation_error = Column(Text, nullable=True)


class HardwareLib(Base):
    __tablename__ = "hardware_libs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    ast_metadata = Column(SAJSON, nullable=True)
    active_version_id = Column(
        Integer,
        ForeignKey("hardware_lib_versions.id", use_alter=True, name="fk_hw_lib_active_version"),
        nullable=True,
    )
    stable_version_id = Column(
        Integer,
        ForeignKey("hardware_lib_versions.id", use_alter=True, name="fk_hw_lib_stable_version"),
        nullable=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ToolkitHardwareLib(Base):
    __tablename__ = "toolkit_hardware_libs"

    toolkit_id = Column(Integer, ForeignKey("task_toolkits.id"), primary_key=True)
    hardware_lib_id = Column(Integer, ForeignKey("hardware_libs.id"), primary_key=True)


class TaskDefinitionHwLibPin(Base):
    __tablename__ = "task_definition_hw_lib_pins"

    task_def_id = Column(Integer, ForeignKey("task_definitions.id"), primary_key=True)
    hardware_lib_id = Column(Integer, ForeignKey("hardware_libs.id"), primary_key=True)
    pinned_version_id = Column(Integer, ForeignKey("hardware_lib_versions.id"), nullable=False)


# ============================================================
# HARDWARE MODULES + PILOT HARDWARE CONFIG (Phase 10)
# ============================================================

class HardwareModule(Base):
    __tablename__ = "hardware_modules"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=True)
    hardware_lib_id = Column(Integer, ForeignKey("hardware_libs.id"), nullable=False)
    class_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PilotHardwareConfig(Base):
    __tablename__ = "pilot_hardware_config"

    id = Column(Integer, primary_key=True)
    pilot_id = Column(Integer, ForeignKey("pilots.id"), nullable=False)
    hardware_module_id = Column(Integer, ForeignKey("hardware_modules.id"), nullable=False)
    config = Column(SAJSON, nullable=False)
    __table_args__ = (UniqueConstraint("pilot_id", "hardware_module_id"),)


# ============================================================
# AVAILABLE LOCKED STATES (Phase 11)
# Populated by HANDSHAKE; used in backend-authored toolkit creation.
# ============================================================

class AvailableLockedState(Base):
    __tablename__ = "available_locked_states"

    id = Column(Integer, primary_key=True)
    pilot_id = Column(Integer, ForeignKey("pilots.id"), nullable=False)
    task_filename = Column(String, nullable=False)          # e.g. "appetitive.py" (or reconstructed class name for legacy)
    state_names = Column(SAJSON, nullable=False)            # list of method name strings
    is_legacy_filename = Column(Boolean, default=False)     # True if filename is class-name-derived (AppetitiveTaskReal.py)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("pilot_id", "task_filename"),)


# ============================================================
# TOOLKIT + TASK DEFINITION PYDANTIC SCHEMAS
# ============================================================

class TaskToolkitRead(BaseModel):
    id: int
    name: str
    hw_hash: str
    states: Optional[List[str]] = None
    flags: Optional[Dict[str, Any]] = None
    params_schema: Optional[Dict[str, Any]] = None
    semantic_hardware: Optional[Dict[str, Any]] = None
    callable_methods: Optional[List[str]] = None
    required_packages: Optional[List[str]] = None
    file_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    pilot_origins: List[str] = []   # pilot names list populated by endpoint
    fda_count: int = 0              # count of task_definitions referencing this toolkit

    class Config:
        from_attributes = True


class FlagDefinition(BaseModel):
    name: str
    tracker_type: str  # Counter_Tracker | Boolean_Tracker | Trial_Tracker | Tracker
    initial_value: Any = 0


class ParamDefinition(BaseModel):
    name: str
    type: str
    default: Any = None


class BackendToolkitCreate(BaseModel):
    name: str
    locked_state_source: str           # task filename e.g. "appetitive.py"
    selected_states: List[str]         # subset of state_names for that file
    hardware_module_ids: List[int] = []
    flags: List[FlagDefinition] = []
    params_schema: List[ParamDefinition] = []


class BackendToolkitPatch(BaseModel):
    hardware_module_ids: Optional[List[int]] = None
    flags: Optional[List[FlagDefinition]] = None
    params_schema: Optional[List[ParamDefinition]] = None


class TaskDefinitionCreate(BaseModel):
    display_name: str
    toolkit_name: str
    fda_json: Dict[str, Any]
    toolkit_id: Optional[int] = None


class TaskDefinitionUpdate(BaseModel):
    display_name: Optional[str] = None
    fda_json: Optional[Dict[str, Any]] = None
    toolkit_id: Optional[int] = None


class TaskDefinitionRead(BaseModel):
    id: int
    task_name: str
    display_name: Optional[str] = None
    toolkit_name: Optional[str] = None
    fda_json: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None
    file_hash: str
    created_at: datetime

    class Config:
        from_attributes = True
