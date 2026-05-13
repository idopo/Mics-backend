# api/routers/hardware_libs.py
import ast
import hashlib
import os
import py_compile
import tempfile
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from models import (
    HardwareLib,
    HardwareLibVersion,
    TaskDefinitionHwLibPin,
    TaskToolkit,
    ToolkitHardwareLib,
)

router = APIRouter(tags=["hardware-libs"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def extract_ast_metadata(source_code: str) -> dict:
    """Parse Python source and return class/method structure for GUI and diffing.

    Includes __init__ so Phase 10 can derive constructor args for hardware config fields.
    Shape: {classes: [{name, methods: [{name, args: [{name, annotation, default}]}]}]}
    """
    tree = ast.parse(source_code)
    classes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = []
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            args = []
            for arg in item.args.args:
                if arg.arg == "self":
                    continue
                annotation = ast.unparse(arg.annotation) if arg.annotation else None
                args.append({"name": arg.arg, "annotation": annotation})
            defaults = item.args.defaults
            for i, default in enumerate(defaults):
                args[len(args) - len(defaults) + i]["default"] = ast.unparse(default)
            methods.append({"name": item.name, "args": args})
        classes.append({"name": node.name, "methods": methods})
    return {"classes": classes}


def validate_source(source_code: str, filename: str = "<string>") -> tuple[bool, str | None]:
    """AST parse + py_compile check. Returns (ok, error_message)."""
    try:
        ast.parse(source_code, filename=filename)
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(source_code.encode())
        tmp = f.name
    try:
        py_compile.compile(tmp, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)
    finally:
        os.unlink(tmp)


def sha256(source_code: str) -> str:
    return hashlib.sha256(source_code.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Pydantic request bodies
# ---------------------------------------------------------------------------

class SourceUpdateBody(BaseModel):
    source_code: str


class ValidateBody(BaseModel):
    ok: bool
    error: Optional[str] = None
    pilot: Optional[str] = None


class MarkStableBody(BaseModel):
    reason: Optional[str] = None
    pilot: Optional[str] = None


class RollbackBody(BaseModel):
    version_id: int


class LinkLibBody(BaseModel):
    hardware_lib_id: int


class PinBody(BaseModel):
    pinned_version_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _version_dict(v: HardwareLibVersion) -> Dict[str, Any]:
    return {
        "id": v.id,
        "hardware_lib_id": v.hardware_lib_id,
        "version_number": v.version_number,
        "source_code": v.source_code,
        "sha256_hash": v.sha256_hash,
        "state": v.state,
        "ast_metadata": v.ast_metadata,
        "created_at": v.created_at,
        "stable_at": v.stable_at,
        "stable_reason": v.stable_reason,
        "stable_pilot": v.stable_pilot,
        "validation_error": v.validation_error,
    }


def _lib_dict(lib: HardwareLib, active_version: HardwareLibVersion | None = None) -> Dict[str, Any]:
    return {
        "id": lib.id,
        "name": lib.name,
        "filename": lib.filename,
        "ast_metadata": lib.ast_metadata,
        "active_version_id": lib.active_version_id,
        "stable_version_id": lib.stable_version_id,
        "active_state": active_version.state if active_version else None,
        "source_code": active_version.source_code if active_version else None,
        "validation_error": active_version.validation_error if active_version else None,
        "created_at": lib.created_at,
        "updated_at": lib.updated_at,
    }


def _create_version(db, lib_id: int, source_code: str, next_version_number: int) -> HardwareLibVersion:
    """Validate source, create version row in beta state, return it."""
    ok, err = validate_source(source_code)
    state = "beta" if ok else "unvalidated"
    meta = extract_ast_metadata(source_code) if ok else None
    version = HardwareLibVersion(
        hardware_lib_id=lib_id,
        version_number=next_version_number,
        source_code=source_code,
        sha256_hash=sha256(source_code),
        state=state,
        ast_metadata=meta,
        validation_error=err,
    )
    db.add(version)
    db.flush()  # get version.id before commit
    return version


# ---------------------------------------------------------------------------
# Hardware lib CRUD
# ---------------------------------------------------------------------------

@router.post("/hardware-libs")
def upload_hardware_lib(
    name: str = Form(...),
    file: UploadFile = File(...),
    _: dict = Depends(verify_token),
):
    source_code = file.file.read().decode("utf-8")
    db = _SA_SessionLocal()
    try:
        lib = HardwareLib(name=name, filename=file.filename)
        db.add(lib)
        db.flush()  # get lib.id

        version = _create_version(db, lib.id, source_code, next_version_number=1)

        if version.state == "unvalidated":
            db.rollback()
            raise HTTPException(status_code=422, detail=version.validation_error)

        lib.active_version_id = version.id
        lib.ast_metadata = version.ast_metadata
        db.commit()
        db.refresh(lib)
        return _lib_dict(lib, version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/hardware-libs")
def list_hardware_libs(_: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        libs = db.query(HardwareLib).order_by(HardwareLib.name).all()
        result = []
        for lib in libs:
            av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
            result.append(_lib_dict(lib, av))
        return result
    finally:
        db.close()


@router.get("/hardware-libs/{lib_id}")
def get_hardware_lib(lib_id: int, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        lib = db.get(HardwareLib, lib_id)
        if not lib:
            raise HTTPException(status_code=404, detail="Hardware lib not found")
        av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
        return _lib_dict(lib, av)
    finally:
        db.close()


@router.put("/hardware-libs/{lib_id}")
def update_hardware_lib_source(
    lib_id: int,
    body: SourceUpdateBody,
    _: dict = Depends(verify_token),
):
    db = _SA_SessionLocal()
    try:
        lib = db.get(HardwareLib, lib_id)
        if not lib:
            raise HTTPException(status_code=404, detail="Hardware lib not found")

        last_version = (
            db.query(HardwareLibVersion)
            .filter(HardwareLibVersion.hardware_lib_id == lib_id)
            .order_by(HardwareLibVersion.version_number.desc())
            .first()
        )
        next_num = (last_version.version_number + 1) if last_version else 1
        version = _create_version(db, lib_id, body.source_code, next_num)

        if version.state == "unvalidated":
            db.rollback()
            raise HTTPException(status_code=422, detail=version.validation_error)

        lib.active_version_id = version.id
        lib.ast_metadata = version.ast_metadata
        db.commit()
        db.refresh(lib)
        return _lib_dict(lib, version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/hardware-libs/{lib_id}")
def delete_hardware_lib(lib_id: int, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        lib = db.get(HardwareLib, lib_id)
        if not lib:
            raise HTTPException(status_code=404, detail="Hardware lib not found")
        linked = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.hardware_lib_id == lib_id
        ).first()
        if linked:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete: lib is linked to one or more toolkits",
            )
        # Must null the back-pointers before deleting versions due to circular FK.
        # Use raw SQL in an explicit transaction to guarantee ordering.
        from sqlalchemy import text as sa_text
        db.close()
        with engine.begin() as conn:
            conn.execute(sa_text(
                "UPDATE hardware_libs SET active_version_id=NULL, stable_version_id=NULL WHERE id=:id"
            ), {"id": lib_id})
            conn.execute(sa_text(
                "DELETE FROM hardware_lib_versions WHERE hardware_lib_id=:id"
            ), {"id": lib_id})
            conn.execute(sa_text("DELETE FROM hardware_libs WHERE id=:id"), {"id": lib_id})
        return {"deleted": lib_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Version endpoints
# ---------------------------------------------------------------------------

@router.get("/hardware-libs/{lib_id}/versions")
def list_versions(lib_id: int, state: Optional[str] = None, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        q = db.query(HardwareLibVersion).filter(HardwareLibVersion.hardware_lib_id == lib_id)
        if state:
            q = q.filter(HardwareLibVersion.state == state)
        versions = q.order_by(HardwareLibVersion.version_number.desc()).all()
        return [_version_dict(v) for v in versions]
    finally:
        db.close()


@router.patch("/hardware-libs/versions/{version_id}/validate")
def validate_version(version_id: int, body: ValidateBody, _: dict = Depends(verify_token)):
    """Called by orchestrator after Pi import test result."""
    db = _SA_SessionLocal()
    try:
        version = db.get(HardwareLibVersion, version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        version.state = "beta" if body.ok else "unvalidated"
        version.validation_error = body.error
        if body.ok and body.pilot:
            version.stable_pilot = body.pilot
        db.commit()
        return _version_dict(version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.patch("/hardware-libs/{lib_id}/mark-stable")
def mark_stable(lib_id: int, body: MarkStableBody = None, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        lib = db.get(HardwareLib, lib_id)
        if not lib or not lib.active_version_id:
            raise HTTPException(status_code=404, detail="Hardware lib or active version not found")
        version = db.get(HardwareLibVersion, lib.active_version_id)
        from datetime import datetime
        version.state = "stable"
        version.stable_at = datetime.utcnow()
        version.stable_reason = (body.reason if body else None) or "user"
        version.stable_pilot = body.pilot if body else None
        lib.stable_version_id = version.id
        db.commit()
        db.refresh(lib)
        return _lib_dict(lib, version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/hardware-libs/{lib_id}/rollback")
def rollback_version(lib_id: int, body: RollbackBody, _: dict = Depends(verify_token)):
    """Clone source from a past version into a new version row (state=beta)."""
    db = _SA_SessionLocal()
    try:
        lib = db.get(HardwareLib, lib_id)
        if not lib:
            raise HTTPException(status_code=404, detail="Hardware lib not found")
        target = db.get(HardwareLibVersion, body.version_id)
        if not target or target.hardware_lib_id != lib_id:
            raise HTTPException(status_code=404, detail="Version not found for this lib")

        last_version = (
            db.query(HardwareLibVersion)
            .filter(HardwareLibVersion.hardware_lib_id == lib_id)
            .order_by(HardwareLibVersion.version_number.desc())
            .first()
        )
        next_num = (last_version.version_number + 1) if last_version else 1
        version = _create_version(db, lib_id, target.source_code, next_num)
        lib.active_version_id = version.id
        lib.ast_metadata = version.ast_metadata
        db.commit()
        db.refresh(lib)
        return _lib_dict(lib, version)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Toolkit ↔ hardware lib link endpoints
# ---------------------------------------------------------------------------

@router.get("/toolkits/{toolkit_id}/hardware-libs")
def list_toolkit_hardware_libs(toolkit_id: int, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        toolkit = db.get(TaskToolkit, toolkit_id)
        if not toolkit:
            raise HTTPException(status_code=404, detail="Toolkit not found")
        links = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id
        ).all()
        result = []
        for link in links:
            lib = db.get(HardwareLib, link.hardware_lib_id)
            if lib:
                av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
                result.append(_lib_dict(lib, av))
        return {"libs": result}
    finally:
        db.close()


@router.post("/toolkits/{toolkit_id}/hardware-libs")
def link_hardware_lib(toolkit_id: int, body: LinkLibBody, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        if not db.get(TaskToolkit, toolkit_id):
            raise HTTPException(status_code=404, detail="Toolkit not found")
        if not db.get(HardwareLib, body.hardware_lib_id):
            raise HTTPException(status_code=404, detail="Hardware lib not found")
        existing = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id,
            ToolkitHardwareLib.hardware_lib_id == body.hardware_lib_id,
        ).first()
        if existing:
            return {"toolkit_id": toolkit_id, "hardware_lib_id": body.hardware_lib_id}
        link = ToolkitHardwareLib(toolkit_id=toolkit_id, hardware_lib_id=body.hardware_lib_id)
        db.add(link)
        db.commit()
        return {"toolkit_id": toolkit_id, "hardware_lib_id": body.hardware_lib_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/toolkits/{toolkit_id}/hardware-libs/{lib_id}")
def unlink_hardware_lib(toolkit_id: int, lib_id: int, _: dict = Depends(verify_token)):
    db = _SA_SessionLocal()
    try:
        link = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id,
            ToolkitHardwareLib.hardware_lib_id == lib_id,
        ).first()
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")
        db.delete(link)
        db.commit()
        return {"unlinked": {"toolkit_id": toolkit_id, "hardware_lib_id": lib_id}}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# AST diff utility
# ---------------------------------------------------------------------------

def diff_ast(old_meta: dict, new_meta: dict) -> dict:
    """Compare two ast_metadata dicts; return removed/changed/added methods."""
    removed, changed, added = [], [], []
    old_classes = {c["name"]: {m["name"]: m for m in c["methods"]} for c in old_meta.get("classes", [])}
    new_classes = {c["name"]: {m["name"]: m for m in c["methods"]} for c in new_meta.get("classes", [])}
    for cls_name, old_methods in old_classes.items():
        new_methods = new_classes.get(cls_name, {})
        for method_name, old_m in old_methods.items():
            if method_name not in new_methods:
                removed.append({"class_name": cls_name, "method_name": method_name})
            elif old_m["args"] != new_methods[method_name]["args"]:
                changed.append({
                    "class_name": cls_name,
                    "method_name": method_name,
                    "old_args": old_m["args"],
                    "new_args": new_methods[method_name]["args"],
                })
        for method_name in new_methods:
            if method_name not in old_methods:
                added.append({"class_name": cls_name, "method_name": method_name})
    return {"removed_methods": removed, "changed_signatures": changed, "added_methods": added}


# ---------------------------------------------------------------------------
# AST diff endpoint
# ---------------------------------------------------------------------------

@router.get("/hardware-libs/{lib_id}/versions/diff")
def versions_diff(
    lib_id: int,
    # `from` is a Python keyword — use Query alias to accept ?from=<id>&to=<id>
    from_id: int = Query(..., alias="from"),
    to_id: int = Query(..., alias="to"),
    _: dict = Depends(verify_token),
):
    """GET /api/hardware-libs/{lib_id}/versions/diff?from=<v_id>&to=<v_id>"""
    db = _SA_SessionLocal()
    try:
        v_from = db.get(HardwareLibVersion, from_id)
        v_to = db.get(HardwareLibVersion, to_id)
        if not v_from or v_from.hardware_lib_id != lib_id:
            raise HTTPException(status_code=404, detail=f"Version {from_id} not found for this lib")
        if not v_to or v_to.hardware_lib_id != lib_id:
            raise HTTPException(status_code=404, detail=f"Version {to_id} not found for this lib")
        old_meta = v_from.ast_metadata or extract_ast_metadata(v_from.source_code)
        new_meta = v_to.ast_metadata or extract_ast_metadata(v_to.source_code)
        return diff_ast(old_meta, new_meta)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pin management endpoints
# ---------------------------------------------------------------------------

def _resolve_task_toolkit_id(db, task_def_id: int) -> int | None:
    """Return toolkit_id for a task definition, or None if not set."""
    from sqlalchemy import text as sa_text
    row = db.execute(
        sa_text("SELECT toolkit_id FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Task definition not found")
    return row.toolkit_id


@router.get("/task-definitions/{task_def_id}/hw-lib-pins")
def get_hw_lib_pins(task_def_id: int, _: dict = Depends(verify_token)):
    """List pin state for all hw libs linked to this task def's toolkit.

    Each entry shows the pinned version (if any) and the current active version,
    so the UI can highlight when they differ.
    """
    db = _SA_SessionLocal()
    try:
        toolkit_id = _resolve_task_toolkit_id(db, task_def_id)
        if toolkit_id is None:
            return []

        links = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id
        ).all()

        result = []
        for link in links:
            lib = db.get(HardwareLib, link.hardware_lib_id)
            if not lib:
                continue
            pin = db.query(TaskDefinitionHwLibPin).filter(
                TaskDefinitionHwLibPin.task_def_id == task_def_id,
                TaskDefinitionHwLibPin.hardware_lib_id == lib.id,
            ).first()
            av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
            pv = db.get(HardwareLibVersion, pin.pinned_version_id) if pin else None
            result.append({
                "hardware_lib_id": lib.id,
                "lib_name": lib.name,
                "lib_filename": lib.filename,
                "pinned_version_id": pv.id if pv else None,
                "pinned_version_number": pv.version_number if pv else None,
                "pinned_version_state": pv.state if pv else None,
                "active_version_id": av.id if av else None,
                "active_version_number": av.version_number if av else None,
                "active_version_state": av.state if av else None,
            })
        return result
    finally:
        db.close()


@router.put("/task-definitions/{task_def_id}/hw-lib-pins/{lib_id}")
def set_hw_lib_pin(
    task_def_id: int,
    lib_id: int,
    body: PinBody,
    _: dict = Depends(verify_token),
):
    """Pin a task definition to a specific hw lib version."""
    db = _SA_SessionLocal()
    try:
        toolkit_id = _resolve_task_toolkit_id(db, task_def_id)
        if toolkit_id is None:
            raise HTTPException(status_code=422, detail="Task definition has no toolkit; cannot pin")

        # Lib must be linked to the toolkit
        link = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id,
            ToolkitHardwareLib.hardware_lib_id == lib_id,
        ).first()
        if not link:
            raise HTTPException(status_code=422, detail="Lib is not linked to this task definition's toolkit")

        # Version must belong to this lib
        version = db.get(HardwareLibVersion, body.pinned_version_id)
        if not version or version.hardware_lib_id != lib_id:
            raise HTTPException(status_code=422, detail="Version does not belong to this lib")

        pin = db.query(TaskDefinitionHwLibPin).filter(
            TaskDefinitionHwLibPin.task_def_id == task_def_id,
            TaskDefinitionHwLibPin.hardware_lib_id == lib_id,
        ).first()
        if pin:
            pin.pinned_version_id = body.pinned_version_id
        else:
            pin = TaskDefinitionHwLibPin(
                task_def_id=task_def_id,
                hardware_lib_id=lib_id,
                pinned_version_id=body.pinned_version_id,
            )
            db.add(pin)
        db.commit()

        lib = db.get(HardwareLib, lib_id)
        av = db.get(HardwareLibVersion, lib.active_version_id) if lib and lib.active_version_id else None
        return {
            "hardware_lib_id": lib_id,
            "lib_name": lib.name if lib else None,
            "lib_filename": lib.filename if lib else None,
            "pinned_version_id": version.id,
            "pinned_version_number": version.version_number,
            "pinned_version_state": version.state,
            "active_version_id": av.id if av else None,
            "active_version_number": av.version_number if av else None,
            "active_version_state": av.state if av else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/task-definitions/{task_def_id}/hw-lib-pins/{lib_id}")
def delete_hw_lib_pin(task_def_id: int, lib_id: int, _: dict = Depends(verify_token)):
    """Remove a version pin; task def reverts to active version for this lib."""
    db = _SA_SessionLocal()
    try:
        pin = db.query(TaskDefinitionHwLibPin).filter(
            TaskDefinitionHwLibPin.task_def_id == task_def_id,
            TaskDefinitionHwLibPin.hardware_lib_id == lib_id,
        ).first()
        if not pin:
            raise HTTPException(status_code=404, detail="No pin found for this task def / lib combination")
        db.delete(pin)
        db.commit()
        return {"deleted": {"task_def_id": task_def_id, "hardware_lib_id": lib_id}}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
