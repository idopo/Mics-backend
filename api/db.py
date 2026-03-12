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
