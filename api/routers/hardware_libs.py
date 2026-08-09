# api/routers/hardware_libs.py
import ast
import hashlib
import json
import logging
import os
import py_compile
import tempfile
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text as sa_text
from sqlalchemy.orm import sessionmaker

from auth import verify_token
from db import engine
from fda_utils import ref_label, scan_fda_for_refs
from lib_version_resolution import resolve_lib_version_id
from models import (
    HardwareLib,
    HardwareLibVersion,
    TaskDefinition,
    TaskToolkit,
    ToolkitHardwareLib,
)

router = APIRouter(tags=["hardware-libs"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _revalidate_task_def(db, task_def_id: int) -> None:
    """Re-run validation for a task def using its current pins and update status."""
    from routers.toolkits import _validate_task_definition
    row = db.execute(
        sa_text("SELECT fda_json, toolkit_id FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()
    if not row or not row.fda_json:
        return
    fda = row.fda_json if isinstance(row.fda_json, dict) else json.loads(row.fda_json)
    v_status, v_msg = _validate_task_definition(db, fda, row.toolkit_id, task_def_id)
    db.execute(
        sa_text(
            "UPDATE task_definitions SET validation_status = :s, validation_message = :m WHERE id = :id"
        ),
        {"s": v_status, "m": v_msg, "id": task_def_id},
    )
    db.commit()


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

    result = {"classes": classes}
    try:
        from extlink_ast import extract_extlink_metadata
        extlink = extract_extlink_metadata(tree)
        if extlink:
            result["extlink"] = extlink
    except Exception as e:
        logging.getLogger(__name__).warning("extlink metadata extraction failed: %s", e)
    return result


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
    declared_imports: Optional[list[str]] = None


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
    version_id: Optional[int] = None


class VersionSelectBody(BaseModel):
    version_id: int


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
        "declared_imports": v.declared_imports or [],
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
        "kind": lib.kind,
        "ast_metadata": lib.ast_metadata,
        "active_version_id": lib.active_version_id,
        "stable_version_id": lib.stable_version_id,
        "active_state": active_version.state if active_version else None,
        "source_code": active_version.source_code if active_version else None,
        "declared_imports": (active_version.declared_imports or []) if active_version else [],
        "validation_error": active_version.validation_error if active_version else None,
        "created_at": lib.created_at,
        "updated_at": lib.updated_at,
    }


def _validate_compute_lib(source_code: str, declared_imports: list[str]) -> None:
    """CMP-04 + CMP-19 hard gates for a `kind='compute'` upload/update.

    a) every class with an in-file base (a `class X(Something):`) must define `release()` --
       `Task.end()` calls `release()` unconditionally on every hardware object on every run.
    b) every declared import must be a Pi stdlib module already vetted for a compute lib --
       third-party packages need per-Pi package management, deferred (CMP-19).
    """
    from hw_introspect import resolve_class_methods

    for node in ast.walk(ast.parse(source_code)):
        if isinstance(node, ast.ClassDef) and node.bases:
            methods, _closed = resolve_class_methods(source_code, node.name)
            if "release" not in methods:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"class '{node.name}' must define release() -- Task.end() calls "
                        f"release() on every hardware object on every run"
                    ),
                )

    if not declared_imports:
        return
    from seed_compute import COMPUTE_STDLIB_ALLOWLIST

    for imp in declared_imports:
        if imp not in COMPUTE_STDLIB_ALLOWLIST:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"declared import '{imp}' is not allowed -- allowed stdlib imports: "
                    f"{sorted(COMPUTE_STDLIB_ALLOWLIST)} -- third-party packages are deferred "
                    f"pending per-Pi package management (CMP-19)"
                ),
            )


def _create_version(
    db,
    lib_id: int,
    source_code: str,
    next_version_number: int,
    declared_imports: list[str] | None = None,
) -> HardwareLibVersion:
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
        declared_imports=declared_imports,
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
    kind: str = Form("hardware"),
    declared_imports: str = Form("[]"),
    _: dict = Depends(verify_token),
):
    if kind not in ("hardware", "compute"):
        raise HTTPException(status_code=422, detail=f"kind must be 'hardware' or 'compute' (got '{kind}')")
    try:
        imports_list = json.loads(declared_imports)
        assert isinstance(imports_list, list) and all(isinstance(i, str) for i in imports_list)
    except Exception:
        raise HTTPException(status_code=422, detail="declared_imports must be a JSON array of strings")

    source_code = file.file.read().decode("utf-8")
    db = _SA_SessionLocal()
    try:
        if kind == "compute":
            _validate_compute_lib(source_code, imports_list)

        lib = HardwareLib(name=name, filename=file.filename, kind=kind)
        db.add(lib)
        db.flush()  # get lib.id

        version = _create_version(db, lib.id, source_code, next_version_number=1, declared_imports=imports_list)

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


def _diff_removed_methods(old_meta: dict, new_meta: dict) -> dict[str, set[str]]:
    """Return {class_name: {removed_method_names}} for methods removed in new vs old AST."""
    old_classes = {c["name"]: {m["name"] for m in c.get("methods", [])} for c in (old_meta or {}).get("classes", [])}
    new_classes = {c["name"]: {m["name"] for m in c.get("methods", [])} for c in (new_meta or {}).get("classes", [])}
    removed: dict[str, set[str]] = {}
    for cls_name, old_methods in old_classes.items():
        new_methods = new_classes.get(cls_name, set())
        diff = old_methods - new_methods
        if diff:
            removed[cls_name] = diff
    return removed


def _flag_broken_task_defs(db, lib_id: int, removed_methods: dict[str, set[str]]) -> list[int]:
    """Scan task definitions linked to lib_id and flag any that reference removed methods.

    Skips definitions pinned to a specific version of this lib (they are insulated).
    Returns list of affected (flagged) definition IDs.
    """
    if not removed_methods:
        return []

    # Find all toolkits that use this lib
    toolkit_links = db.query(ToolkitHardwareLib).filter(
        ToolkitHardwareLib.hardware_lib_id == lib_id
    ).all()
    toolkit_ids = [tl.toolkit_id for tl in toolkit_links]
    if not toolkit_ids:
        return []

    # Find all task definitions linked to those toolkits
    task_defs = db.query(TaskDefinition).filter(
        TaskDefinition.toolkit_id.in_(toolkit_ids)
    ).all()

    affected_ids: list[int] = []
    from sqlalchemy import text as sa_text

    for task_def in task_defs:
        # Load fda_json via raw SQL (migrated column, not on ORM class)
        row = db.execute(
            sa_text("SELECT fda_json FROM task_definitions WHERE id = :id"),
            {"id": task_def.id},
        ).fetchone()
        if not row or not row.fda_json:
            continue

        import json as _json
        fda = row.fda_json if isinstance(row.fda_json, dict) else _json.loads(row.fda_json)
        refs = scan_fda_for_refs(fda)

        for ref_entry in refs:
            # "compute" widened in lockstep with fda_utils.scan_fda_for_refs (Plan 23-03 CMP-11)
            # — a compute-op rename/removal must flag dependent task defs the same way a
            # hardware-op one does; scan_fda_for_refs alone was not enough, this filter was the
            # second half of the same gate.
            if ref_entry["action_type"] not in ("hardware", "compute"):
                continue
            ref_method = ref_entry.get("method")
            if not ref_method:
                continue
            for cls_name, removed in removed_methods.items():
                if ref_method in removed:
                    msg = (
                        f"{ref_label(ref_entry)}: "
                        f"{ref_entry['ref']}.{ref_method} removed from lib (class {cls_name})"
                    )
                    db.execute(sa_text(
                        "UPDATE task_definitions "
                        "SET validation_status = 'broken', validation_message = :msg "
                        "WHERE id = :id"
                    ), {"msg": msg, "id": task_def.id})
                    affected_ids.append(task_def.id)
                    break
            else:
                continue
            break

    return affected_ids


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

        if lib.kind == "compute":
            _validate_compute_lib(body.source_code, body.declared_imports or [])

        # Capture old AST before overwrite for impact diff
        old_ast = lib.ast_metadata

        last_version = (
            db.query(HardwareLibVersion)
            .filter(HardwareLibVersion.hardware_lib_id == lib_id)
            .order_by(HardwareLibVersion.version_number.desc())
            .first()
        )
        next_num = (last_version.version_number + 1) if last_version else 1
        version = _create_version(db, lib_id, body.source_code, next_num, declared_imports=body.declared_imports)

        if version.state == "unvalidated":
            db.rollback()
            raise HTTPException(status_code=422, detail=version.validation_error)

        lib.active_version_id = version.id
        lib.ast_metadata = version.ast_metadata

        # Diff AST and flag any broken task definitions
        removed_methods = _diff_removed_methods(old_ast, version.ast_metadata)
        affected_ids = _flag_broken_task_defs(db, lib_id, removed_methods)

        db.commit()
        db.refresh(lib)
        result = _lib_dict(lib, version)
        result["impact"] = {
            "removed_methods": {k: sorted(v) for k, v in removed_methods.items()},
            "affected_definition_ids": affected_ids,
        }
        return result
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
def list_toolkit_hardware_libs(
    toolkit_id: int, task_def_id: int | None = None, _: dict = Depends(verify_token),
):
    """List a toolkit's hardware libs, each carrying the CMP-17 resolution (Plan 23-05):
    `resolved_version_id`/`resolved_state`/`resolved_source_code`/`resolution_reason`, computed
    by `resolve_lib_version_id` with the task def's `hw_lib_versions` pin when `task_def_id` is
    given. Resolution still runs with no `task_def_id` (the pin rung simply never fires).
    Existing keys are unchanged so the orchestrator's current reads keep working during rollout.
    """
    db = _SA_SessionLocal()
    try:
        toolkit = db.get(TaskToolkit, toolkit_id)
        if not toolkit:
            raise HTTPException(status_code=404, detail="Toolkit not found")

        pinned: dict[int, int] = {}
        if task_def_id:
            td_row = db.execute(
                sa_text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
                {"id": task_def_id},
            ).fetchone()
            hw_versions = td_row.hw_lib_versions if td_row and td_row.hw_lib_versions else {}
            if isinstance(hw_versions, dict):
                pinned = {int(k): v for k, v in hw_versions.items()}

        links = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id
        ).all()
        result = []
        for link in links:
            lib = db.get(HardwareLib, link.hardware_lib_id)
            if lib:
                av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
                entry = _lib_dict(lib, av)
                entry["default_version_id"] = link.default_version_id

                resolved_id, reason = resolve_lib_version_id(
                    db, lib.id, toolkit_id=toolkit_id, pinned_version_id=pinned.get(lib.id),
                )
                resolved_version = db.get(HardwareLibVersion, resolved_id) if resolved_id else None
                entry["resolved_version_id"] = resolved_id
                entry["resolved_state"] = resolved_version.state if resolved_version else None
                entry["resolved_source_code"] = resolved_version.source_code if resolved_version else None
                entry["resolution_reason"] = reason

                result.append(entry)
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
            if body.version_id is not None:
                existing.default_version_id = body.version_id
                db.commit()
            return {"toolkit_id": toolkit_id, "hardware_lib_id": body.hardware_lib_id}
        link = ToolkitHardwareLib(
            toolkit_id=toolkit_id,
            hardware_lib_id=body.hardware_lib_id,
            default_version_id=body.version_id,
        )
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


@router.get("/task-definitions/{task_def_id}/hw-lib-versions")
def get_hw_lib_versions(task_def_id: int, _: dict = Depends(verify_token)):
    """List hw lib version selections for all libs linked to this task def's toolkit."""
    db = _SA_SessionLocal()
    try:
        toolkit_id = _resolve_task_toolkit_id(db, task_def_id)
        if toolkit_id is None:
            return []

        td_row = db.execute(
            sa_text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
            {"id": task_def_id},
        ).fetchone()
        hw_versions = (td_row.hw_lib_versions if td_row and td_row.hw_lib_versions else {})

        links = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id
        ).all()

        result = []
        for link in links:
            lib = db.get(HardwareLib, link.hardware_lib_id)
            if not lib:
                continue
            av = db.get(HardwareLibVersion, lib.active_version_id) if lib.active_version_id else None
            sel_id = hw_versions.get(str(lib.id))
            sv = db.get(HardwareLibVersion, sel_id) if sel_id else None
            result.append({
                "hardware_lib_id": lib.id,
                "lib_name": lib.name,
                "lib_filename": lib.filename,
                "selected_version_id": sv.id if sv else None,
                "selected_version_number": sv.version_number if sv else None,
                "selected_version_state": sv.state if sv else None,
                "active_version_id": av.id if av else None,
                "active_version_number": av.version_number if av else None,
                "active_version_state": av.state if av else None,
            })
        return result
    finally:
        db.close()


@router.put("/task-definitions/{task_def_id}/hw-lib-versions/{lib_id}")
def set_hw_lib_version(
    task_def_id: int,
    lib_id: int,
    body: VersionSelectBody,
    _: dict = Depends(verify_token),
):
    """Set the hw lib version used by a task definition."""
    db = _SA_SessionLocal()
    try:
        toolkit_id = _resolve_task_toolkit_id(db, task_def_id)
        if toolkit_id is None:
            raise HTTPException(status_code=422, detail="Task definition has no toolkit")

        link = db.query(ToolkitHardwareLib).filter(
            ToolkitHardwareLib.toolkit_id == toolkit_id,
            ToolkitHardwareLib.hardware_lib_id == lib_id,
        ).first()
        if not link:
            raise HTTPException(status_code=422, detail="Lib is not linked to this task definition's toolkit")

        version = db.get(HardwareLibVersion, body.version_id)
        if not version or version.hardware_lib_id != lib_id:
            raise HTTPException(status_code=422, detail="Version does not belong to this lib")

        db.execute(
            sa_text(
                "UPDATE task_definitions SET hw_lib_versions = "
                "COALESCE(hw_lib_versions, '{}'::jsonb) || jsonb_build_object(:key, :val) "
                "WHERE id = :id"
            ),
            {"key": str(lib_id), "val": body.version_id, "id": task_def_id},
        )
        db.commit()
        _revalidate_task_def(db, task_def_id)

        lib = db.get(HardwareLib, lib_id)
        av = db.get(HardwareLibVersion, lib.active_version_id) if lib and lib.active_version_id else None
        return {
            "hardware_lib_id": lib_id,
            "lib_name": lib.name if lib else None,
            "lib_filename": lib.filename if lib else None,
            "selected_version_id": version.id,
            "selected_version_number": version.version_number,
            "selected_version_state": version.state,
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
