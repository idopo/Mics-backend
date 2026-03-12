# Subject Extension + Project / Experiment Entities — Implementation Plan

**Status:** PLANNED — not started
**Date:** 2026-03-11
**Context:** Extends the minimal `Subject` model and adds a Project → Experiment → Protocol administrative hierarchy to the MICS backend.

---

## Background

The current `Subject` (`api/models.py:27`) has only 3 fields: `name`, `current_run_id`, `next_protocol_id`. The lab needs it to represent a real mouse subject (biology, lineage, housing, surgery, weight history) and to situate subjects within an administrative hierarchy.

### Entity Hierarchy

```
Researcher  (skeleton only — full auth/login deferred to later stage)
    │
    ├──── many Subjects  (lead_researcher_id FK)
    └──── many Projects  (lead_researcher_id FK)

IACUCProtocol  (shared across projects — number + title + expiration)
    └──── many Projects

Project
    └──── many Experiments
                └──── many ProtocolTemplates  (existing, via join table)

Subject  (extended with biology + housing + admin fields)
    ├──── many WeightMeasurement  (time-series: date + grams)
    ├──── many SubjectSurgery     (procedure type + date + notes)
    └──── many Projects           (via SubjectProject join table)
```

### Design Decisions Made

| Question | Decision |
|---|---|
| Lineage | Plain text `mother_name` / `father_name` — no FK to Subject |
| Experiment vs Protocol | New layer above existing: Project → Experiment → Protocol (existing unchanged) |
| Researchers | Separate table skeleton; FK on Subject + Project; full auth deferred |
| IACUC | Separate `iacuc_protocols` table; Projects FK to it; multiple projects can share one |
| Weight / Surgery | Separate normalized tables (not JSON) |
| Migration | Startup SQL function: `ALTER TABLE subjects ADD COLUMN IF NOT EXISTS ...` |
| Breaking changes | Zero — all new Subject columns are nullable; existing endpoints untouched |

---

## Phase 1 — models.py: New Tables + Subject Extension

**File:** `api/models.py`

### New SQLModel tables (all `table=True`)

```python
from datetime import date  # add to imports

class Researcher(SQLModel, table=True):
    __tablename__ = "researchers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class IACUCProtocol(SQLModel, table=True):
    __tablename__ = "iacuc_protocols"
    id: Optional[int] = Field(default=None, primary_key=True)
    number: str = Field(unique=True, index=True)   # e.g. "IL-123-2024"
    title: str
    expires_at: Optional[date] = None


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


class ExperimentProtocol(SQLModel, table=True):   # join table
    __tablename__ = "experiment_protocols"
    experiment_id: int = Field(foreign_key="experiments.id", primary_key=True)
    protocol_id: int = Field(foreign_key="protocol_templates.id", primary_key=True)


class SubjectProject(SQLModel, table=True):        # join table
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
    procedure_type: str   # "OF implant" | "ePhys implant" | "injection" | "RFID chipping" | custom
    performed_at: Optional[date] = None
    notes: Optional[str] = None
```

### Extended Subject table — add these nullable columns to the existing `Subject` class

```python
# Biology
strain: Optional[str] = None
genotype: Optional[str] = None          # "-/-" | "+/-" | "+/+" | custom string
mother_name: Optional[str] = None       # plain text — no FK
father_name: Optional[str] = None       # plain text — no FK
dob: Optional[date] = None
sex: Optional[str] = None               # "Male" | "Female"
rfid: Optional[int] = None

# Administrative
lead_researcher_id: Optional[int] = Field(default=None, foreign_key="researchers.id")
arrival_date: Optional[date] = None
in_quarantine: Optional[bool] = Field(default=False)
location: Optional[str] = None          # room number / cage ID
holding_conditions: Optional[str] = None  # "isolated" | "group" | "reverse cycle" | ...
group_type: Optional[str] = None        # "Experimental" | "Control" | "Pilot"
group_details: Optional[str] = None
notes: Optional[str] = None             # free text
```

### New Pydantic schemas to add to models.py

```python
# Researcher
class ResearcherCreate(SQLModel):
    name: str
    email: Optional[str] = None

class ResearcherRead(SQLModel):
    id: int
    name: str
    email: Optional[str] = None

# IACUC
class IACUCCreate(SQLModel):
    number: str
    title: str
    expires_at: Optional[date] = None

class IACUCRead(SQLModel):
    id: int
    number: str
    title: str
    expires_at: Optional[date] = None

# Project
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
    notes: Optional[str] = None
    created_at: datetime

# Experiment
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

# Subject extended
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
    weights: List["WeightRead"] = []
    surgeries: List["SurgeryRead"] = []
    projects: List["ProjectRead"] = []

# Weight
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

# Surgery
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
```

---

## Phase 2 — db.py: Startup Migration Function

**File:** `api/db.py`

Add this function (run before `create_all` in `main.py` startup):

```python
from sqlalchemy import text

def run_subject_column_migrations(engine):
    """Add new nullable columns to existing subjects table. Safe to run repeatedly."""
    new_columns = [
        ("strain",             "TEXT"),
        ("genotype",           "TEXT"),
        ("mother_name",        "TEXT"),
        ("father_name",        "TEXT"),
        ("dob",                "DATE"),
        ("sex",                "TEXT"),
        ("rfid",               "INTEGER"),
        ("lead_researcher_id", "INTEGER"),
        ("arrival_date",       "DATE"),
        ("in_quarantine",      "BOOLEAN DEFAULT FALSE"),
        ("location",           "TEXT"),
        ("holding_conditions", "TEXT"),
        ("group_type",         "TEXT"),
        ("group_details",      "TEXT"),
        ("notes",              "TEXT"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in new_columns:
            conn.execute(text(
                f"ALTER TABLE subjects ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            ))
        conn.commit()
```

**In `main.py` startup handler (currently around line 97-102):**

```python
@app.on_event("startup")
async def on_startup():
    run_subject_column_migrations(engine)  # ADD THIS LINE FIRST
    SQLModel.metadata.create_all(engine)   # existing
    Base.metadata.create_all(engine)       # existing
```

---

## Phase 3 — main.py: New API Endpoints

**File:** `api/main.py`

Insert after existing subjects block (~line 800). All use `Depends(get_session)` (SQLModel session).

### Researchers (skeleton)
```
GET  /api/researchers           → list all ResearcherRead
POST /api/researchers           → create, returns ResearcherRead
```

### IACUC
```
GET  /api/iacuc                 → list all IACUCRead (for dropdown)
POST /api/iacuc                 → create, returns IACUCRead
```

### Projects
```
GET  /api/projects              → list ProjectRead[]
POST /api/projects              → create, returns ProjectRead
GET  /api/projects/{id}         → ProjectRead + embedded experiments list
```

### Experiments
```
GET  /api/experiments?project_id={id}     → ExperimentRead[] filtered by project
POST /api/experiments                     → create, returns ExperimentRead
GET  /api/experiments/{id}               → ExperimentRead + protocols list
POST /api/experiments/{id}/protocols/{protocol_id}   → assign protocol to experiment
DELETE /api/experiments/{id}/protocols/{protocol_id} → unassign
```

### Subject extensions
```
GET    /api/subjects/{id}              → SubjectExtendedRead (extended — replaces old)
PATCH  /api/subjects/{id}             → SubjectUpdate, returns SubjectExtendedRead
POST   /api/subjects/{id}/projects/{project_id}  → assign to project
DELETE /api/subjects/{id}/projects/{project_id}  → remove from project
POST   /api/subjects/{id}/weights     → WeightCreate, returns WeightRead
GET    /api/subjects/{id}/weights     → WeightRead[] sorted by date desc
POST   /api/subjects/{id}/surgeries   → SurgeryCreate, returns SurgeryRead
GET    /api/subjects/{id}/surgeries   → SurgeryRead[] sorted by date desc
```

### Existing endpoints — DO NOT CHANGE
- `GET /api/subjects` — still returns `SubjectRead` (id, name, current_run_id, next_protocol_id)
- `POST /api/subjects` — still takes `SubjectCreate(name: str)` only
- All `/api/sessions`, `/api/pilots`, `/api/protocols`, `/api/tasks` endpoints — untouched

---

## Verification Checklist

```bash
# 1. Rebuild and start
docker compose up --build

# 2. Health check
curl http://localhost:8000/health

# 3. Check new columns exist in subjects table
# (use postgres MCP: "list columns in subjects table")

# 4. Create a researcher
curl -s -X POST http://localhost:8000/api/researchers \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Researcher", "email": "alice@lab.ac.il"}'

# 5. Create IACUC
curl -s -X POST http://localhost:8000/api/iacuc \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"number": "IL-001-2025", "title": "Learning cage behavioral study", "expires_at": "2027-06-01"}'

# 6. Create project
curl -s -X POST http://localhost:8000/api/projects \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Learning Project", "iacuc_id": 1}'

# 7. Create experiment
curl -s -X POST http://localhost:8000/api/experiments \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Optogenetics cohort", "project_id": 1}'

# 8. Patch an existing subject with biological fields
curl -s -X PATCH http://localhost:8000/api/subjects/1 \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"strain": "C57BL/6", "sex": "Male", "dob": "2025-06-15", "genotype": "+/-"}'

# 9. Add a weight measurement
curl -s -X POST http://localhost:8000/api/subjects/1/weights \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"measured_at": "2026-03-11", "weight_grams": 24.5}'

# 10. Confirm existing subjects list still works
curl -s http://localhost:8000/api/subjects \
  -H "Authorization: Bearer $MICS_API_TOKEN"
# Must return same shape as before: [{id, name, current_run_id, next_protocol_id}, ...]
```

---

## Files to Modify

| File | Type of change |
|---|---|
| `api/models.py` | Add 8 new SQLModel tables + extend Subject + ~10 new Pydantic schemas |
| `api/db.py` | Add `run_subject_column_migrations()` function |
| `api/main.py` | Call migration at startup + add ~15 new endpoints |

**SQLAlchemy tables (pilots, sessions, session_runs, run_progress, task_definitions) — zero changes.**

---

## Phase 4 — UI (React SPA)

**Use the `frontend-design` skill** when implementing these pages. Invoke it with `/frontend-design` before building each page.

All pages live under `web_ui/react-src/src/pages/`. Add routes in `App.tsx`. Use existing CSS classes from `style.css` (see MEMORY.md for the full class list).

### New routes to add in App.tsx

```
/react/subjects/:id/detail        SubjectDetail page
/react/projects-ui                Projects list + create
/react/projects/:id               Project detail + experiments
/react/experiments/:id            Experiment detail + protocol assignment
```

### Page: SubjectDetail (`/react/subjects/:id/detail`)

Two-column layout using existing `container split` pattern:
- **Left panel**: all biological fields (strain, genotype, sex, DOB, RFID, mother/father)
  - Editable inline via PATCH `/api/subjects/{id}` on blur/save
  - Genotype as dropdown: `-/-`, `+/-`, `+/+` + free text option
  - Sex as radio: Male / Female
- **Right panel**: tabbed
  - Tab 1 — **Admin**: location, holding conditions, group type, lead researcher, arrival date, quarantine toggle, notes
  - Tab 2 — **Weight Log**: table of `measured_at` + `weight_grams` + notes, with "Add measurement" form at bottom
  - Tab 3 — **Surgeries**: checklist-style list (procedure type + date + notes), "Add surgery" form
  - Tab 4 — **Projects**: chips showing assigned projects, button to assign/remove
- Navigate to this page from the existing subject list (click subject name → detail)

### Page: ProjectsUI (`/react/projects-ui`)

Two-panel layout (same as existing protocols-ui pattern):
- **Left**: scrollable list of projects (`scroll-list`), each showing name + IACUC number + experiment count
- **Right**: "Create Project" form — name, description, IACUC dropdown (from `GET /api/iacuc`), lead researcher dropdown (from `GET /api/researchers`), notes

### Page: ProjectDetail (`/react/projects/:id`)

- Header card: project name, IACUC info, lead researcher
- Section: Experiments list with "Create Experiment" inline form (name + description)
- Each experiment row is clickable → navigates to ExperimentDetail

### Page: ExperimentDetail (`/react/experiments/:id`)

Two-panel layout:
- **Left**: protocols assigned to this experiment (list with remove button)
- **Right**: protocol picker — same palette as `protocols-create` page, "Add to experiment" button calls `POST /api/experiments/{id}/protocols/{protocol_id}`

### API queries needed (add to `src/api/`)

New file `src/api/lab.ts`:
- `useResearchers()` → `GET /api/researchers`
- `useIACUC()` → `GET /api/iacuc`
- `useProjects()` → `GET /api/projects`
- `useProject(id)` → `GET /api/projects/{id}`
- `useExperiment(id)` → `GET /api/experiments/{id}`
- `useSubjectDetail(id)` → `GET /api/subjects/{id}` (returns SubjectExtendedRead)
- `useSubjectWeights(id)` → `GET /api/subjects/{id}/weights`
- `useSubjectSurgeries(id)` → `GET /api/subjects/{id}/surgeries`
- mutations: `patchSubject`, `addWeight`, `addSurgery`, `assignProject`, `assignProtocolToExperiment`

### Skill usage

When implementing each page, run `/frontend-design` first. Provide it:
- The page layout description above
- The existing CSS class list from MEMORY.md
- The API shape from the endpoint (curl it first to get real response)
- Examples of similar existing pages (e.g., `PilotSessions.tsx` for the tabbed layout pattern)

---

## Future Phases (deferred)

- **Researcher auth**: login per researcher, filter "my subjects" view
- **IACUC expiry alerts**: notify when approval approaching expiry
- **Weight chart**: plot weight over time (recharts or similar)
- **ToolKit + FDA redesign**: separate plan in `toolkit_fda_plan.md`
