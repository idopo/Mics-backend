# api/routers/hardware_modules.py
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from models import HardwareLib, HardwareModule

router = APIRouter(tags=["hardware-modules"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class HardwareModuleCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    hardware_lib_id: int
    class_name: str
    description: Optional[str] = None


class HardwareModuleUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    hardware_lib_id: Optional[int] = None
    class_name: Optional[str] = None
    description: Optional[str] = None


def _find_class_in_ast(ast_metadata: dict, class_name: str) -> Optional[dict]:
    classes = (ast_metadata or {}).get("classes", [])
    return next((c for c in classes if c.get("name") == class_name), None)


def _validate_class_name(session, hardware_lib_id: int, class_name: str) -> None:
    lib = session.get(HardwareLib, hardware_lib_id)
    if not lib:
        raise HTTPException(status_code=422, detail="hardware_lib_id not found")
    if not _find_class_in_ast(lib.ast_metadata or {}, class_name):
        raise HTTPException(
            status_code=422,
            detail=f"class_name '{class_name}' not found in lib AST",
        )


@router.get("/api/hardware-modules")
def list_hardware_modules(token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        rows = session.query(HardwareModule).order_by(HardwareModule.id).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "display_name": r.display_name,
                "hardware_lib_id": r.hardware_lib_id,
                "class_name": r.class_name,
                "description": r.description,
                "created_at": r.created_at,
            }
            for r in rows
        ]


@router.post("/api/hardware-modules")
def create_hardware_module(body: HardwareModuleCreate, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        _validate_class_name(session, body.hardware_lib_id, body.class_name)
        existing = session.query(HardwareModule).filter_by(name=body.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="name already exists")
        module = HardwareModule(
            name=body.name,
            display_name=body.display_name,
            hardware_lib_id=body.hardware_lib_id,
            class_name=body.class_name,
            description=body.description,
        )
        session.add(module)
        session.commit()
        session.refresh(module)
        return {"id": module.id, "name": module.name}


@router.get("/api/hardware-modules/{module_id}")
def get_hardware_module(module_id: int, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        module = session.get(HardwareModule, module_id)
        if not module:
            raise HTTPException(status_code=404, detail="not found")
        return {
            "id": module.id,
            "name": module.name,
            "display_name": module.display_name,
            "hardware_lib_id": module.hardware_lib_id,
            "class_name": module.class_name,
            "description": module.description,
            "created_at": module.created_at,
        }


@router.put("/api/hardware-modules/{module_id}")
def update_hardware_module(module_id: int, body: HardwareModuleUpdate, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        module = session.get(HardwareModule, module_id)
        if not module:
            raise HTTPException(status_code=404, detail="not found")
        lib_id = body.hardware_lib_id if body.hardware_lib_id is not None else module.hardware_lib_id
        class_name = body.class_name if body.class_name is not None else module.class_name
        _validate_class_name(session, lib_id, class_name)
        if body.name is not None:
            module.name = body.name
        if body.display_name is not None:
            module.display_name = body.display_name
        if body.hardware_lib_id is not None:
            module.hardware_lib_id = body.hardware_lib_id
        if body.class_name is not None:
            module.class_name = body.class_name
        if body.description is not None:
            module.description = body.description
        session.commit()
        return {"id": module.id, "name": module.name}


@router.delete("/api/hardware-modules/{module_id}")
def delete_hardware_module(module_id: int, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        module = session.get(HardwareModule, module_id)
        if not module:
            raise HTTPException(status_code=404, detail="not found")
        session.delete(module)
        session.commit()
        return {"deleted": module_id}


@router.get("/api/hardware-modules/{module_id}/methods")
def get_hardware_module_methods(module_id: int, token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        module = session.get(HardwareModule, module_id)
        if not module:
            raise HTTPException(status_code=404, detail="not found")
        lib = session.get(HardwareLib, module.hardware_lib_id)
        if not lib:
            raise HTTPException(status_code=404, detail="linked hardware lib not found")
        class_info = _find_class_in_ast(lib.ast_metadata or {}, module.class_name)
        if not class_info:
            raise HTTPException(
                status_code=422,
                detail=f"class_name '{module.class_name}' not found in lib AST",
            )
        return {
            "module_id": module.id,
            "module_name": module.name,
            "class_name": module.class_name,
            "methods": class_info.get("methods", []),
        }
