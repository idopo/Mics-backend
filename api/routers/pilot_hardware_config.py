# api/routers/pilot_hardware_config.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from models import HardwareModule, PilotHardwareConfig

router = APIRouter(tags=["pilot-hardware-config"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

logger = logging.getLogger(__name__)


class UpsertConfigBody(BaseModel):
    config: Dict[str, Any]


class SeedBody(BaseModel):
    hardware: Dict[str, Any]


@router.get("/api/pilots/{pilot_id}/hardware-config")
def list_pilot_hardware_config(pilot_id: int, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        rows = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id)
            .all()
        )
        return [
            {
                "id": r.id,
                "pilot_id": r.pilot_id,
                "hardware_module_id": r.hardware_module_id,
                "config": r.config,
            }
            for r in rows
        ]


@router.put("/api/pilots/{pilot_id}/hardware-config/{module_id}")
def upsert_pilot_hardware_config(
    pilot_id: int, module_id: int, body: UpsertConfigBody, token=Depends(verify_token)
):
    with _SA_SessionLocal() as session:
        row = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id, hardware_module_id=module_id)
            .first()
        )
        if row:
            row.config = body.config
        else:
            row = PilotHardwareConfig(
                pilot_id=pilot_id,
                hardware_module_id=module_id,
                config=body.config,
            )
            session.add(row)
        session.commit()
        session.refresh(row)
        return {"id": row.id, "pilot_id": row.pilot_id, "hardware_module_id": row.hardware_module_id}


@router.delete("/api/pilots/{pilot_id}/hardware-config/{module_id}")
def delete_pilot_hardware_config(pilot_id: int, module_id: int, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        row = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id, hardware_module_id=module_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="not found")
        session.delete(row)
        session.commit()
        return {"deleted": True}


@router.post("/api/pilots/{pilot_id}/hardware-config/seed")
def seed_pilot_hardware_config(pilot_id: int, body: SeedBody, token=Depends(verify_token)):
    """Seed pilot config from a raw HARDWARE dict (orchestrator-internal, one-time migration)."""
    with _SA_SessionLocal() as session:
        existing = (
            session.query(PilotHardwareConfig)
            .filter_by(pilot_id=pilot_id)
            .count()
        )
        if existing > 0:
            return {"seeded": 0, "skipped": "config rows already exist"}

        seeded = 0
        for hw_name, hw_cfg in body.hardware.items():
            module = session.query(HardwareModule).filter_by(name=hw_name).first()
            if not module:
                logger.warning("seed_pilot_hardware_config: no HardwareModule named %r — skipping", hw_name)
                continue
            config = {k: v for k, v in hw_cfg.items() if k != "class"}
            session.add(
                PilotHardwareConfig(
                    pilot_id=pilot_id,
                    hardware_module_id=module.id,
                    config=config,
                )
            )
            seeded += 1

        session.commit()
        return {"seeded": seeded}
