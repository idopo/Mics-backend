# api/routers/pilot_hardware_config.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from models import PilotHardwareConfig

router = APIRouter(tags=["pilot-hardware-config"])
_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
logger = logging.getLogger(__name__)


class UpsertConfigBody(BaseModel):
    config: Dict[str, Any]


class SeedBody(BaseModel):
    hardware: Dict[str, Any]


@router.get("/api/pilots/{pilot_id}/hardware-config")
def list_pilot_hardware_config(pilot_id: int, token=Depends(verify_token)):
    """Return all hardware config entries for a pilot."""
    with _SA_SessionLocal() as session:
        rows = session.query(PilotHardwareConfig).filter_by(pilot_id=pilot_id).all()
        return [
            {"id": r.id, "pilot_id": r.pilot_id, "name": r.name, "config": r.config}
            for r in rows
        ]


@router.put("/api/pilots/{pilot_id}/hardware-config/{name}")
def upsert_pilot_hardware_config(
    pilot_id: int, name: str, body: UpsertConfigBody, token=Depends(verify_token)
):
    """Create or update a hardware config entry by name. Config stored as-is (caller includes class_name)."""
    with _SA_SessionLocal() as session:
        row = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id, name=name)
            .first()
        )
        if row:
            row.config = body.config
        else:
            row = PilotHardwareConfig(pilot_id=pilot_id, name=name, config=body.config)
            session.add(row)
        session.commit()
        session.refresh(row)
        return {"id": row.id, "pilot_id": row.pilot_id, "name": row.name, "config": row.config}


@router.delete("/api/pilots/{pilot_id}/hardware-config/{name}")
def delete_pilot_hardware_config(pilot_id: int, name: str, token=Depends(verify_token)):
    """Delete a hardware config entry by name."""
    with _SA_SessionLocal() as session:
        row = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id, name=name)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        session.delete(row)
        session.commit()
        return {"deleted": True}


@router.post("/api/pilots/{pilot_id}/hardware-config/seed")
def seed_pilot_hardware_config(pilot_id: int, body: SeedBody, token=Depends(verify_token)):
    """Seed pilot config from a raw HARDWARE dict (orchestrator-internal, one-time migration).
    Maps Pi 'class' key -> config['class_name']. Skips if any config rows already exist.
    """
    with _SA_SessionLocal() as session:
        existing = session.query(PilotHardwareConfig).filter_by(pilot_id=pilot_id).count()
        if existing > 0:
            return {"seeded": 0, "skipped": "config rows already exist"}

        seeded = 0
        for hw_name, hw_cfg in body.hardware.items():
            config = {k: v for k, v in hw_cfg.items() if k != "class"}
            if "class" in hw_cfg:
                config["class_name"] = hw_cfg["class"]
            session.add(
                PilotHardwareConfig(pilot_id=pilot_id, name=hw_name, config=config)
            )
            seeded += 1

        session.commit()
        return {"seeded": seeded}
