# api/routers/hardware_modules.py
from typing import Any, Dict, List, Optional

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text as sa_text
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from hw_introspect import class_capabilities, resolve_class_methods
from models import HardwareLib, HardwareLibVersion, HardwareModule

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


def _module_row(module: HardwareModule, lib: HardwareLib | None) -> dict:
    return {
        "id": module.id,
        "name": module.name,
        "display_name": module.display_name,
        "hardware_lib_id": module.hardware_lib_id,
        "class_name": module.class_name,
        "description": module.description,
        "created_at": module.created_at,
        "lib_filename": lib.filename if lib else None,
        "lib_kind": lib.kind if lib else None,
    }


@router.get("/api/hardware-modules")
def list_hardware_modules(token=Depends(verify_token)):
    with _SA_SessionLocal() as session:
        rows = (
            session.query(HardwareModule, HardwareLib)
            .join(HardwareLib, HardwareModule.hardware_lib_id == HardwareLib.id)
            .order_by(HardwareModule.id)
            .all()
        )
        return [_module_row(m, lib) for m, lib in rows]


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
        lib = session.get(HardwareLib, module.hardware_lib_id)
        return _module_row(module, lib)


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
def get_hardware_module_methods(
    module_id: int,
    task_def_id: Optional[int] = Query(None),
    token=Depends(verify_token),
):
    with _SA_SessionLocal() as session:
        module = session.get(HardwareModule, module_id)
        if not module:
            raise HTTPException(status_code=404, detail="not found")

        ast_meta = None
        source_code = None

        # When a task_def_id is provided, prefer the version assigned to that task def.
        if task_def_id:
            td_row = session.execute(
                sa_text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
                {"id": task_def_id},
            ).fetchone()
            hw_versions = td_row.hw_lib_versions if td_row and td_row.hw_lib_versions else {}
            sel_id = hw_versions.get(str(module.hardware_lib_id))
            if sel_id:
                v_row = session.execute(
                    sa_text("SELECT ast_metadata, source_code FROM hardware_lib_versions WHERE id = :id"),
                    {"id": sel_id},
                ).fetchone()
                if v_row and v_row.ast_metadata:
                    ast_meta = v_row.ast_metadata if isinstance(v_row.ast_metadata, dict) else json.loads(v_row.ast_metadata)
                    source_code = v_row.source_code

        if ast_meta is None:
            lib = session.get(HardwareLib, module.hardware_lib_id)
            if not lib:
                raise HTTPException(status_code=404, detail="linked hardware lib not found")
            ast_meta = lib.ast_metadata or {}
            if lib.active_version_id:
                active_version = session.get(HardwareLibVersion, lib.active_version_id)
                source_code = active_version.source_code if active_version else None

        class_info = _find_class_in_ast(ast_meta, module.class_name)
        if not class_info:
            raise HTTPException(
                status_code=422,
                detail=f"class_name '{module.class_name}' not found in lib AST",
            )

        # Union own AST methods with in-file-inherited ones (e.g. Touch_Detector gets MPR121's
        # detect_change/read) so the editor's method dropdown offers them instead of falling
        # back to a free-text box. Inherited entries carry no arg metadata the AST doesn't have.
        merged: dict[str, dict] = {m["name"]: m for m in class_info.get("methods", [])}
        if source_code:
            inherited_names, _closed = resolve_class_methods(source_code, module.class_name)
            for name in inherited_names:
                merged.setdefault(name, {"name": name, "args": []})

        # Reuse, do not duplicate: hw_introspect.class_capabilities is the one detector-capability
        # predicate on the backend — see its docstring for why it is a capability check, not the
        # Pi's runtime check_for_detectors.
        is_detector = class_capabilities(source_code, module.class_name)["is_detector"] if source_code else False

        return {
            "module_id": module.id,
            "module_name": module.name,
            "class_name": module.class_name,
            "methods": sorted(merged.values(), key=lambda m: m["name"]),
            "is_detector": is_detector,
        }
