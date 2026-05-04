# api/db.py
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    with Session(engine) as session:
        yield session


def run_subject_column_migrations(eng):
    """Add new nullable columns to existing subjects table.
    Safe to run repeatedly (IF NOT EXISTS). Must be called AFTER create_all
    so the subjects table exists on fresh deployments.
    """
    new_columns = [
        ("strain",              "TEXT"),
        ("genotype",            "TEXT"),
        ("mother_name",         "TEXT"),
        ("father_name",         "TEXT"),
        ("dob",                 "DATE"),
        ("sex",                 "TEXT"),
        ("rfid",                "INTEGER"),
        ("lead_researcher_id",  "INTEGER"),
        ("arrival_date",        "DATE"),
        ("in_quarantine",       "BOOLEAN DEFAULT FALSE"),
        ("location",            "TEXT"),
        ("holding_conditions",  "TEXT"),
        ("group_type",          "TEXT"),
        ("group_details",       "TEXT"),
        ("notes",               "TEXT"),
    ]
    with eng.connect() as conn:
        for col_name, col_type in new_columns:
            conn.execute(text(
                f"ALTER TABLE subjects ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            ))
        conn.commit()


def run_lab_column_migrations(eng):
    """Add is_hidden to researchers and iacuc_protocols. Safe to run repeatedly."""
    migrations = [
        ("researchers",     "is_hidden", "BOOLEAN DEFAULT FALSE"),
        ("iacuc_protocols", "is_hidden", "BOOLEAN DEFAULT FALSE"),
    ]
    with eng.connect() as conn:
        for table, col_name, col_type in migrations:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            ))
        conn.commit()


def run_toolkit_migrations(eng):
    """Add toolkit columns to task_definitions; safe to run repeatedly (IF NOT EXISTS)."""
    migrations = [
        ("task_definitions", "toolkit_name",  "TEXT"),
        ("task_definitions", "display_name",  "TEXT"),
        ("task_definitions", "fda_json",      "JSONB"),
    ]
    with eng.connect() as conn:
        for table, col_name, col_type in migrations:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            ))
        conn.commit()


def run_protocol_migrations(eng):
    """Add task_definition_id FK to protocol_step_templates; safe to run repeatedly."""
    with eng.connect() as conn:
        conn.execute(text(
            "ALTER TABLE protocol_step_templates "
            "ADD COLUMN IF NOT EXISTS task_definition_id INTEGER "
            "REFERENCES task_definitions(id) ON DELETE SET NULL"
        ))
        conn.commit()


def run_task_definition_toolkit_id_migration(eng):
    """Phase 09: add task_definitions.toolkit_id (FK → task_toolkits.id) and
    backfill from legacy toolkit_name. Idempotent."""
    with eng.begin() as conn:
        conn.execute(text(
            "ALTER TABLE task_definitions "
            "ADD COLUMN IF NOT EXISTS toolkit_id INTEGER REFERENCES task_toolkits(id)"
        ))
        has_toolkit_name = conn.execute(text("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'task_definitions' AND column_name = 'toolkit_name'
        """)).scalar()
        if has_toolkit_name:
            conn.execute(text("""
                UPDATE task_definitions td
                SET toolkit_id = (
                    SELECT tt.id FROM task_toolkits tt
                    WHERE tt.name = td.toolkit_name
                    ORDER BY tt.is_canonical DESC, tt.created_at ASC
                    LIMIT 1
                )
                WHERE td.toolkit_name IS NOT NULL AND td.toolkit_id IS NULL
            """))


def run_hw_lib_pin_migrations(eng):
    """Phase 09: add ast_metadata to hardware_lib_versions (for existing rows) and
    create task_definition_hw_lib_pins. Both idempotent."""
    with eng.begin() as conn:
        conn.execute(text(
            "ALTER TABLE hardware_lib_versions "
            "ADD COLUMN IF NOT EXISTS ast_metadata JSONB"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task_definition_hw_lib_pins (
                task_def_id       INTEGER NOT NULL REFERENCES task_definitions(id),
                hardware_lib_id   INTEGER NOT NULL REFERENCES hardware_libs(id),
                pinned_version_id INTEGER NOT NULL REFERENCES hardware_lib_versions(id),
                PRIMARY KEY (task_def_id, hardware_lib_id)
            )
        """))


def run_canonical_migrations(eng):
    """Add is_canonical to task_toolkits and needs_migration to task_definitions; safe to run repeatedly."""
    migrations = [
        ("task_toolkits",    "is_canonical",    "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("task_definitions", "needs_migration", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ]
    with eng.connect() as conn:
        for table, col_name, col_type in migrations:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
            ))
        conn.commit()


def run_toolkit_backend_authored_migrations(eng):
    """Phase 11: add backend-authored columns to task_toolkits and create available_locked_states.
    Safe to run repeatedly (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)."""
    with eng.begin() as conn:
        # Extend task_toolkits with Phase 11 columns
        conn.execute(text(
            "ALTER TABLE task_toolkits ADD COLUMN IF NOT EXISTS hardware_module_ids JSONB DEFAULT '[]'::jsonb"
        ))
        conn.execute(text(
            "ALTER TABLE task_toolkits ADD COLUMN IF NOT EXISTS locked_state_source TEXT"
        ))
        conn.execute(text(
            "ALTER TABLE task_toolkits ADD COLUMN IF NOT EXISTS is_backend_authored BOOLEAN DEFAULT FALSE"
        ))
        # Create available_locked_states table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS available_locked_states (
                id SERIAL PRIMARY KEY,
                pilot_id INTEGER NOT NULL REFERENCES pilots(id),
                task_filename TEXT NOT NULL,
                state_names JSONB NOT NULL,
                is_legacy_filename BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (pilot_id, task_filename)
            )
        """))
        # Phase 11-02: add class_name to available_locked_states
        conn.execute(text(
            "ALTER TABLE available_locked_states ADD COLUMN IF NOT EXISTS class_name VARCHAR"
        ))
