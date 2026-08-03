"""Toolkit dispatch-class and preflight-validate endpoints (Phase 11-02, Phase 13).

Separate from routers/toolkits.py (already >500 lines).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession, sessionmaker

from auth import verify_token
from compute_provisioning import compute_module_names, provision_compute_configs
from db import engine
from detector_keys import derive_channels, derive_view_keys, resolve_view_key_issues
from lib_version_resolution import resolve_lib_version_id
from variable_scan import variable_never_written_issues

logger = logging.getLogger(__name__)

router = APIRouter(tags=["toolkit-dispatch"])

_SA_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_sa_session():
    db: OrmSession = _SA_SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/toolkits/{toolkit_id}/dispatch-spec")
def get_dispatch_spec(
    toolkit_id: int,
    pilot_id: int,
    task_def_id: int | None = None,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    """Return hardware dict, pin config, flags, and params schema for a backend-authored toolkit.

    Used by the orchestrator to inject spec into the START payload before sending to Pi.
    """
    toolkit = db.execute(
        text(
            "SELECT id, hardware_module_ids, flags, params_schema, is_backend_authored"
            " FROM task_toolkits WHERE id = :id"
        ),
        {"id": toolkit_id},
    ).fetchone()
    if not toolkit:
        raise HTTPException(status_code=404, detail="Toolkit not found")

    hardware: dict = {}
    prefs_hardware: dict = {}
    unresolved_libs: list[dict] = []

    # Pin lookup moved outside the module loop -- previously re-queried per module (free fix).
    hw_versions: dict = {}
    if task_def_id:
        td_row = db.execute(
            text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
            {"id": task_def_id},
        ).fetchone()
        hw_versions = (td_row.hw_lib_versions if td_row and td_row.hw_lib_versions else {})

    for module_id in (toolkit.hardware_module_ids or []):
        module = db.execute(
            text("SELECT id, name, class_name, hardware_lib_id FROM hardware_modules WHERE id = :id"),
            {"id": module_id},
        ).fetchone()
        if not module:
            continue

        pinned_version_id = hw_versions.get(str(module.hardware_lib_id))
        version_id, reason = resolve_lib_version_id(
            db, module.hardware_lib_id, toolkit_id=toolkit_id, pinned_version_id=pinned_version_id,
        )
        if version_id is None:
            unresolved_libs.append({
                "module_name": module.name, "lib_id": module.hardware_lib_id, "reason": reason,
            })
            continue

        version = db.execute(
            text("SELECT source_code FROM hardware_lib_versions WHERE id = :id"),
            {"id": version_id},
        ).fetchone()
        if not version:
            unresolved_libs.append({
                "module_name": module.name, "lib_id": module.hardware_lib_id, "reason": "none",
            })
            continue

        hardware.setdefault("Modules", {})[module.name] = {
            module.name: {
                "class_name": module.class_name,
                "source_code": version.source_code,
            }
        }

        cfg = db.execute(
            text(
                "SELECT config FROM pilot_hardware_config"
                " WHERE pilot_id = :pid AND name = :name"
            ),
            {"pid": pilot_id, "name": module.name},
        ).fetchone()
        if cfg:
            prefs_hardware.setdefault("Modules", {})[module.name] = cfg.config

    return {
        "hardware": hardware,
        "prefs_hardware": prefs_hardware,
        "flags": toolkit.flags or {},
        "params_schema": toolkit.params_schema or {},
        "is_backend_authored": bool(toolkit.is_backend_authored),
        "unresolved_libs": unresolved_libs,
    }


@router.get("/toolkits/{toolkit_id}/dispatch-class")
def get_dispatch_class(
    toolkit_id: int,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    """Return the Pi class name to dispatch for a toolkit.

    Falls back to 'mics_task' if no locked_state_source or class_name is stored.
    """
    row = db.execute(
        text("SELECT locked_state_source, is_backend_authored FROM task_toolkits WHERE id = :id"),
        {"id": toolkit_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Toolkit not found")

    if not row.locked_state_source:
        return {"class_name": "mics_task", "is_backend_authored": bool(row.is_backend_authored)}

    cls_row = db.execute(
        text("SELECT class_name FROM available_locked_states WHERE task_filename = :fname LIMIT 1"),
        {"fname": row.locked_state_source},
    ).fetchone()
    class_name = cls_row.class_name if cls_row and cls_row.class_name else "mics_task"
    return {"class_name": class_name, "is_backend_authored": bool(row.is_backend_authored)}


# Every preflight issue kind this module can emit. Mirrored (must stay in sync) by the
# `PreflightIssue` union in `HardwareCheckModal.tsx` — plan 23-09's job to extend it.
PREFLIGHT_ISSUE_KINDS = frozenset({
    "missing",                    # no pilot_hardware_config row for a required module
    "incomplete_config",          # hardware module config has no non-class_name keys
    "class_mismatch",             # stored class_name != module's declared class_name
    "fda_ref_unresolved",         # FDA hardware action refs a name the pilot has no config for
    "view_key_unresolved",        # DVK-06/11: view/detector operand resolves to no real key
    "variable_never_written",     # CMP-15: a transition reads a variable nothing ever writes
    "lib_version_unresolved",     # CMP-17 rung 5: no beta/stable version deployable for a lib
    "compute_lib_import_failed",  # CMP-19c RESERVED: compute lib failed to import on the Pi
})


def compute_lib_import_failed_issue(module_name: str, lib_filename: str, error: str) -> dict:
    """Shape for the RESERVED `compute_lib_import_failed` issue kind (CMP-19c). Not emitted
    anywhere yet — reserves the surfacing path before there is a Pi-side reporter to call it."""
    return {
        "module_id": None,
        "module_name": module_name,
        "issue": "compute_lib_import_failed",
        "lib_filename": lib_filename,
        "detail": f"Compute lib '{lib_filename}' failed to import on the Pi: {error}",
    }


@router.post("/sessions/{session_id}/preflight-validate/{pilot_id}")
def preflight_validate(
    session_id: int,
    pilot_id: int,
    _: dict = Depends(verify_token),
    db: OrmSession = Depends(get_sa_session),
):
    """Validate that a pilot has all hardware modules configured for the session's current step.

    Returns ok=True if validation passes or if the session is not backend-authored.
    Returns ok=False with a list of issues if any hardware config is missing or mismatched.
    Each issue includes module_id so the React client can call PUT directly to fix it.
    """
    # 1. Get the current step index from run_progress for this session on this pilot
    run_row = db.execute(
        text(
            "SELECT sr.id, rp.current_step_idx"
            " FROM session_runs sr"
            " LEFT JOIN run_progress rp ON rp.run_id = sr.id"
            " WHERE sr.session_id = :sid AND sr.pilot_id = :pid"
            "   AND sr.status NOT IN ('completed', 'error')"
            " ORDER BY sr.id DESC"
            " LIMIT 1"
        ),
        {"sid": session_id, "pid": pilot_id},
    ).fetchone()

    # If no active/pending run found, use step 0 (pre-start check)
    current_step_idx = 0
    if run_row and run_row.current_step_idx is not None:
        current_step_idx = run_row.current_step_idx

    # 2. Load session → get one of its subject_protocol_runs to find protocol_id
    spr_row = db.execute(
        text(
            "SELECT protocol_id FROM subject_protocol_runs WHERE session_id = :sid LIMIT 1"
        ),
        {"sid": session_id},
    ).fetchone()
    if not spr_row:
        logger.warning("preflight_validate: no subject_protocol_run for session %s", session_id)
        return {"ok": True, "issues": [], "skip_reason": "no_protocol_run"}

    protocol_id = spr_row.protocol_id

    # 3. Load the protocol step at current_step_idx
    step_row = db.execute(
        text(
            "SELECT task_definition_id FROM protocol_step_templates"
            " WHERE protocol_id = :pid ORDER BY order_index ASC"
            " LIMIT 1 OFFSET :step_idx"
        ),
        {"pid": protocol_id, "step_idx": current_step_idx},
    ).fetchone()
    if not step_row or not step_row.task_definition_id:
        return {"ok": True, "issues": [], "skip_reason": "not_backend_authored"}

    task_def_id = step_row.task_definition_id

    # 4. Load task definition → get toolkit_id
    td_row = db.execute(
        text("SELECT toolkit_id FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()
    if not td_row or not td_row.toolkit_id:
        return {"ok": True, "issues": [], "skip_reason": "not_backend_authored"}

    toolkit_id = td_row.toolkit_id

    # 5. Load toolkit → check is_backend_authored and get hardware_module_ids
    # `flags` is selected here (not just for dispatch) so step 8 can build its valid-key set
    # without a second toolkit query.
    toolkit_row = db.execute(
        text("SELECT is_backend_authored, hardware_module_ids, flags FROM task_toolkits WHERE id = :id"),
        {"id": toolkit_id},
    ).fetchone()
    if not toolkit_row or not toolkit_row.is_backend_authored:
        return {"ok": True, "issues": [], "skip_reason": "not_backend_authored"}

    module_ids = toolkit_row.hardware_module_ids or []

    # Compute-aware step 6, part 1: self-heal a pilot missing a config row for a compute
    # module before the per-module loop runs. A compute module has no per-rig hardware to
    # configure, so a missing row is a registration gap the pilot shouldn't be blamed for.
    compute_names = compute_module_names(db, module_ids)
    if compute_names:
        try:
            provision_compute_configs(db, module_ids, pilot_ids=[pilot_id])
            db.commit()
        except Exception:
            logger.warning(
                "preflight_validate: compute-config self-heal failed for pilot %s", pilot_id,
                exc_info=True,
            )

    # Fetch existing pilot configs once — shared by steps 6 and 7 for "copy from" suggestions.
    existing_configs = [
        {"name": row[0], "config": row[1]}
        for row in db.execute(
            text("SELECT name, config FROM pilot_hardware_config WHERE pilot_id = :pid ORDER BY name"),
            {"pid": pilot_id},
        ).fetchall()
    ]
    configured_names = {e["name"] for e in existing_configs}

    # Build name→class_name map from all toolkit modules for expected_class hints.
    module_class_by_name: dict[str, str] = {}
    for mid in module_ids:
        m = db.execute(
            text("SELECT name, class_name FROM hardware_modules WHERE id = :id"),
            {"id": mid},
        ).fetchone()
        if m:
            module_class_by_name[m.name] = m.class_name

    # Pin lookup for CMP-17 rung 5 (lib_version_unresolved) — same pattern as get_dispatch_spec.
    hw_versions_row = db.execute(
        text("SELECT hw_lib_versions FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()
    hw_versions = (hw_versions_row.hw_lib_versions if hw_versions_row and hw_versions_row.hw_lib_versions else {})

    # 6. Check each hardware module
    issues: list[dict] = []
    # Collected here (not re-queried) for step 8's DVK-06/11 view-key resolution — same cfg_row
    # this loop already fetches per module.
    module_channels: dict[str, list[int]] = {}
    module_keys: dict[str, list[str]] = {}
    device_names: dict[str, str] = {}
    for module_id in module_ids:
        module = db.execute(
            text("SELECT id, name, class_name, hardware_lib_id FROM hardware_modules WHERE id = :id"),
            {"id": module_id},
        ).fetchone()
        if not module:
            continue

        # CMP-17 rung 5: report a lib with no deployable version by name and reason, replacing
        # what was today a silent skip in get_dispatch_spec. Independent of config presence, so
        # checked here regardless of whether the "missing"/"incomplete_config" branches below fire.
        pinned_version_id = hw_versions.get(str(module.hardware_lib_id))
        version_id, reason = resolve_lib_version_id(
            db, module.hardware_lib_id, toolkit_id=toolkit_id, pinned_version_id=pinned_version_id,
        )
        if reason == "none":
            lib_row = db.execute(
                text("SELECT name, filename FROM hardware_libs WHERE id = :id"),
                {"id": module.hardware_lib_id},
            ).fetchone()
            lib_label = lib_row.filename if lib_row else str(module.hardware_lib_id)
            issues.append({
                "module_id": module.id,
                "module_name": module.name,
                "issue": "lib_version_unresolved",
                "detail": f"No beta/stable version available for lib '{lib_label}' (module {module.name})",
                "lib_id": module.hardware_lib_id,
            })

        cfg_row = db.execute(
            text(
                "SELECT config FROM pilot_hardware_config"
                " WHERE pilot_id = :pid AND name = :name"
            ),
            {"pid": pilot_id, "name": module.name},
        ).fetchone()

        if not cfg_row:
            issues.append({
                "module_id": module.id,
                "module_name": module.name,
                "issue": "missing",
                "detail": f"Pilot has no config for hardware module {module.name}",
                "expected_class": module.class_name,
                "existing_configs": existing_configs,
            })
            continue

        cfg = cfg_row.config or {}
        device_name = cfg.get("device_name")
        if isinstance(device_name, str) and device_name:
            device_names[module.name] = device_name
        channels = derive_channels(cfg)
        if channels:
            module_channels[module.name] = channels
            module_keys[module.name] = derive_view_keys(cfg)

        non_class_keys = [k for k in cfg if k != "class_name"]

        # A compute module has no pins, addresses, or durations -- {"class_name": ...} alone
        # IS a complete config for it. The original check assumed every module needs at least
        # one real parameter; that only holds for hardware modules.
        if not non_class_keys and module.name not in compute_names:
            issues.append({
                "module_id": module.id,
                "module_name": module.name,
                "issue": "incomplete_config",
                "detail": f"Config for {module.name} is empty — no hardware parameters set",
                "config": cfg,
            })
            continue

        # class_mismatch: only check if class_name is present (skip for legacy rows)
        stored_class = cfg.get("class_name")
        if stored_class is not None and stored_class != module.class_name:
            issues.append({
                "module_id": module.id,
                "module_name": module.name,
                "issue": "class_mismatch",
                "detail": (
                    f"Config has class '{stored_class}', "
                    f"module expects '{module.class_name}'"
                ),
                "expected_class": module.class_name,
                "stored_class": stored_class,
                "config": cfg,
            })

    # 7. Validate FDA hardware refs against configured pilot modules.
    # Skip refs already reported in step 6 to avoid duplicates.
    td_full = db.execute(
        text("SELECT fda_json FROM task_definitions WHERE id = :id"),
        {"id": task_def_id},
    ).fetchone()

    if td_full and td_full.fda_json:
        already_flagged = {i["module_name"] for i in issues}
        unresolved: set[str] = set()
        for state_def in (td_full.fda_json.get("states") or {}).values():
            for action in (state_def.get("entry_actions") or []):
                if action.get("type") == "hardware":
                    ref = action.get("ref")
                    if ref and ref not in configured_names and ref not in already_flagged:
                        unresolved.add(ref)
        for ref in sorted(unresolved):
            issues.append({
                "module_id": None,
                "module_name": ref,
                "issue": "fda_ref_unresolved",
                "detail": f"FDA references hardware '{ref}' but pilot has no config for that name",
                "expected_class": module_class_by_name.get(ref),
                "existing_configs": existing_configs,
            })

        # 8. DVK-06/11: resolve view keys and detector channels against THIS pilot's declared
        # wiring. Deliberately nested inside the `if td_full and td_full.fda_json:` block above
        # (not after it) — `already_flagged` is only defined inside that `if`, and step 8 reuses
        # it as `skip_modules` rather than rebuilding it. Wrapped in its own try/except: preflight
        # already treats a broken check as non-blocking (Phase 13), and a new check must not
        # become the first thing that can hard-fail a session start.
        try:
            detector_keys = [k for keys in module_keys.values() for k in keys]
            variables = td_full.fda_json.get("variables")
            valid_keys = (
                set(detector_keys)
                | set((toolkit_row.flags or {}).keys())
                | set(variables.keys() if isinstance(variables, dict) else [])
                | {"trial_counter"}
                | set(module_class_by_name.keys())
            )
            issues.extend(resolve_view_key_issues(
                td_full.fda_json,
                valid_keys=valid_keys,
                device_names=device_names,
                module_channels=module_channels,
                detector_keys=detector_keys,
                skip_modules=already_flagged,
            ))
        except Exception:
            logger.warning(
                "preflight_validate: view-key resolution failed for session %s pilot %s",
                session_id, pilot_id, exc_info=True,
            )

        # 9. CMP-15: report a transition reading a variable nothing writes anywhere in the FDA.
        # Same non-blocking posture as step 8 — nested in this guard, own try/except.
        try:
            issues.extend(variable_never_written_issues(td_full.fda_json))
        except Exception:
            logger.warning(
                "preflight_validate: variable_never_written scan failed for session %s pilot %s",
                session_id, pilot_id, exc_info=True,
            )

    return {"ok": len(issues) == 0, "issues": issues}
