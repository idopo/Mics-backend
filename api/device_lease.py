"""Device-lease arbitration + extlink config-field validation (Phase 18, EXTLINK-10/17/18).

One OpenEphys-style external box has one record node; several pilots may carry a config that
points at it. Two pilots issuing RECORD would clobber each other's session, and the Pi cannot
arbitrate this itself -- it does not know other pilots exist. This module is the backend-side
lease: one row per normalized `host`, enforced atomically by a Postgres UNIQUE constraint (see
`api/db.py::run_device_lease_migration`), never by a single-holder check in Python.

Residual-risk boundary: Phase 18's safety net (`reconcile_leases`, called from plan 18-09's
orchestrator loop) releases the lease row and lets the run be marked errored. It does NOT reach
out to the foreign device and command it to stop -- the backend has no channel to an arbitrary
device's control API, by design ("the Pi owns both channels" is locked, see `18-CONTEXT.md`). A
crashed pilot can therefore leave an external recorder running until a human notices; Phase 26
decides whether OpenEphys needs its own additional device-side reconciliation.

Deliberately imports nothing from `routers/` -- `routers/toolkit_dispatch.py` imports THIS
module, one direction only (same relationship `detector_keys.py` / `variable_scan.py` already
have with that router).
"""
from datetime import datetime, timezone

from sqlalchemy import text

# The three transport roles a `pilot_hardware_config` row for an external module may declare.
# Every role check in this module is driven off these constants, never a hard-coded string --
# that is precisely how the third role ("none", control-only) got missed in earlier drafts.
ROLE_ROUTER_BIND = "router_bind"
ROLE_SUB_CONNECT = "sub_connect"
ROLE_NONE = "none"  # control-only, no inbound socket (EXTLINK-18)

_VALID_ROLES = frozenset({ROLE_ROUTER_BIND, ROLE_SUB_CONNECT, ROLE_NONE})

_LEASE_COLUMNS = "host, pilot_id, pilot_name, session_id, run_id, subject_key, acquired_at"


def normalize_host(host: str | None) -> str:
    """Collapse `"132.77.9.9:37497"`, `"http://132.77.9.9:5556/"`, `" 132.77.9.9 "` and
    `"132.77.9.9"` to the same lease key. Same box on two ports must be one lease -- a
    `host:port` key would let a second pilot's HTTP-only config quietly admit a conflicting
    ZMQ config for the same physical device."""
    if not host:
        return ""
    h = host.strip().lower()
    if "://" in h:
        h = h.split("://", 1)[1]
    h = h.split("/", 1)[0]
    h = h.split(":", 1)[0]
    return h


def is_extlink_config(cfg: dict | None) -> bool:
    """True iff `cfg["role"]` is one of the three known roles. A control-only (`role: "none"`)
    module is still an external module: it is lease-checked and config-validated exactly like
    a `sub_connect`/`router_bind` one."""
    return isinstance(cfg, dict) and cfg.get("role") in _VALID_ROLES


def _config_issue(module_name: str, module_id, message: str) -> dict:
    return {
        "module_id": module_id,
        "module_name": module_name,
        "issue": "extlink_config_invalid",
        "detail": f"{module_name}: {message}",
    }


def validate_extlink_config(module_name: str, module_id, cfg: dict | None) -> list[dict]:
    """EXTLINK-10/18 field validation. A `cfg` with no `role` key at all is not an extlink
    config and emits nothing -- this check is inert for every non-extlink hardware/compute
    module in the system."""
    if not isinstance(cfg, dict) or "role" not in cfg:
        return []

    role = cfg.get("role")
    issues: list[dict] = []

    if role not in _VALID_ROLES:
        issues.append(_config_issue(
            module_name, module_id,
            f"unknown role '{role}' (must be one of {sorted(_VALID_ROLES)})",
        ))
    elif role == ROLE_SUB_CONNECT:
        if not cfg.get("host"):
            issues.append(_config_issue(module_name, module_id, "sub_connect requires 'host'"))
        elif cfg.get("connect_port") is None:
            issues.append(_config_issue(module_name, module_id, "sub_connect requires 'connect_port'"))
    elif role == ROLE_ROUTER_BIND:
        if cfg.get("listen_port") is None:
            issues.append(_config_issue(module_name, module_id, "router_bind requires 'listen_port'"))
    elif role == ROLE_NONE:
        # Neither port is invented nor required -- role "none" opens no inbound socket at all --
        # but `host` is still the egress target and the lease key, so it stays mandatory.
        if not cfg.get("host"):
            issues.append(_config_issue(
                module_name, module_id,
                "role 'none' still requires 'host' (egress target / lease key)",
            ))

    if not cfg.get("source_id"):
        issues.append(_config_issue(module_name, module_id, "missing 'source_id'"))

    wait_timeout_s = cfg.get("wait_timeout_s")
    if (
        not isinstance(wait_timeout_s, int) or isinstance(wait_timeout_s, bool)
        or not (5 <= wait_timeout_s <= 600)
    ):
        issues.append(_config_issue(
            module_name, module_id,
            f"'wait_timeout_s' must be an int in [5, 600], got {wait_timeout_s!r}",
        ))

    stale_ms = cfg.get("stale_ms")
    if isinstance(stale_ms, bool) or not isinstance(stale_ms, (int, float)) or stale_ms <= 0:
        issues.append(_config_issue(
            module_name, module_id, f"'stale_ms' must be a positive number, got {stale_ms!r}",
        ))

    egress_fail_threshold = cfg.get("egress_fail_threshold")
    if (
        isinstance(egress_fail_threshold, bool)
        or not isinstance(egress_fail_threshold, (int, float))
        or egress_fail_threshold <= 0
    ):
        issues.append(_config_issue(
            module_name, module_id,
            f"'egress_fail_threshold' must be a positive number, got {egress_fail_threshold!r}",
        ))

    return issues


def device_held_issue(module_name: str, module_id, host: str, holder: dict) -> dict:
    """Shape pinned by `18-03-PLAN.md`'s interfaces block -- `HardwareCheckModal.tsx` mirrors
    this exactly (plan 18-09)."""
    detail = (
        f"{host} is held by pilot '{holder.get('pilot_name')}' "
        f"(subject {holder.get('subject_key')}, run {holder.get('run_id')}) "
        f"since {holder.get('acquired_at')}"
    )
    return {
        "module_id": module_id,
        "module_name": module_name,
        "issue": "device_held",
        "host": host,
        "holder": holder,
        "detail": detail,
    }


def _row_to_lease(row) -> dict:
    return {
        "host": row.host,
        "pilot_id": row.pilot_id,
        "pilot_name": row.pilot_name,
        "session_id": row.session_id,
        "run_id": row.run_id,
        "subject_key": row.subject_key,
        "acquired_at": row.acquired_at,
    }


def list_leases(db) -> list[dict]:
    """All current leases -- backs plan 18-09's `GET /api/device-leases`."""
    rows = db.execute(text(f"SELECT {_LEASE_COLUMNS} FROM device_leases")).fetchall()
    return [_row_to_lease(row) for row in rows]


def get_lease(db, host: str) -> dict | None:
    row = db.execute(
        text(f"SELECT {_LEASE_COLUMNS} FROM device_leases WHERE host = :host"),
        {"host": normalize_host(host)},
    ).fetchone()
    return _row_to_lease(row) if row else None


def acquire_lease(
    db, host: str, pilot_id: int, pilot_name: str | None, session_id, run_id, subject_key,
) -> tuple[bool, dict | None]:
    """Atomic on the `host` UNIQUE constraint -- the INSERT either lands or is silently
    rejected by Postgres, never both racing to overwrite. A same-pilot re-acquire (idempotent
    restart, retry) reads back as its own lease and returns `(True, ...)`; a different pilot
    reads back the existing holder and returns `(False, holder)` without ever touching the row."""
    normalized = normalize_host(host)
    db.execute(
        text(
            "INSERT INTO device_leases (host, pilot_id, pilot_name, session_id, run_id,"
            " subject_key, acquired_at)"
            " VALUES (:host, :pilot_id, :pilot_name, :session_id, :run_id, :subject_key,"
            " :acquired_at)"
            " ON CONFLICT (host) DO NOTHING"
        ),
        {
            "host": normalized, "pilot_id": pilot_id, "pilot_name": pilot_name,
            "session_id": session_id, "run_id": run_id, "subject_key": subject_key,
            "acquired_at": datetime.now(timezone.utc),
        },
    )
    db.commit()
    lease = get_lease(db, normalized)
    if lease is None:
        return False, None
    return lease["pilot_id"] == pilot_id, lease


def release_leases_for_run(db, run_id: int) -> list[str]:
    """Removes every lease held by `run_id`; returns the hosts that were released."""
    rows = db.execute(
        text("SELECT host FROM device_leases WHERE run_id = :run_id"), {"run_id": run_id},
    ).fetchall()
    hosts = [row.host for row in rows]
    if hosts:
        db.execute(text("DELETE FROM device_leases WHERE run_id = :run_id"), {"run_id": run_id})
        db.commit()
    return hosts


def force_release(db, host: str) -> bool:
    """Manual escape hatch for a wedged lease. Returns whether a row existed to remove."""
    result = db.execute(
        text("DELETE FROM device_leases WHERE host = :host"), {"host": normalize_host(host)},
    )
    db.commit()
    return bool(result.rowcount)


def _seconds_since(iso_ts: str, now: datetime) -> float:
    ts = datetime.fromisoformat(iso_ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


def reconcile_leases(
    db, heartbeats: dict, now: datetime | None = None, stale_after_s: int = 90,
) -> list[dict]:
    """Releases a lease whose holding pilot is ABSENT from `heartbeats`, or whose heartbeat
    timestamp is older than `stale_after_s`. `heartbeats` maps `pilot_name -> ISO-8601
    updated_at` -- the orchestrator's Redis `_redis_touch` value (plan 18-09). Pure over the
    injected map: this function never reads Redis itself, which is what makes it unit-testable
    with a fabricated stale timestamp instead of a real timeout."""
    now = now or datetime.now(timezone.utc)
    rows = db.execute(text(f"SELECT {_LEASE_COLUMNS} FROM device_leases")).fetchall()

    released: list[dict] = []
    for row in rows:
        heartbeat = heartbeats.get(row.pilot_name)
        stale = heartbeat is None or _seconds_since(heartbeat, now) > stale_after_s
        if not stale:
            continue
        db.execute(text("DELETE FROM device_leases WHERE host = :host"), {"host": row.host})
        released.append({
            "host": row.host,
            "pilot": row.pilot_name,
            "pilot_name": row.pilot_name,
            "run_id": row.run_id,
            "session_id": row.session_id,
            "subject_key": row.subject_key,
            "reason": "absent" if heartbeat is None else "stale",
        })

    if released:
        db.commit()
    return released


def preflight_device_lease_issues(db, pilot_id: int, modules: list, configs: dict) -> list[dict]:
    """One `device_held` issue per module whose normalized `host` is leased by a DIFFERENT
    pilot. A lease never blocks its own holder."""
    issues: list[dict] = []
    for module in modules:
        cfg = configs.get(module.name)
        if not is_extlink_config(cfg):
            continue
        host = cfg.get("host")
        if not host:
            continue
        lease = get_lease(db, host)
        if lease and lease["pilot_id"] != pilot_id:
            issues.append(device_held_issue(module.name, module.id, lease["host"], lease))
    return issues


def preflight_lease_and_config_issues(db, pilot_id: int, modules_and_configs: list[tuple]) -> list[dict]:
    """Step 10's single call site (`toolkit_dispatch.py`): combines the lease check and the
    extlink config-field check over the module list step 6 already fetched, so the router's
    call site stays a few lines regardless of how much logic lives here."""
    modules = [module for module, _cfg in modules_and_configs]
    configs = {module.name: cfg for module, cfg in modules_and_configs}
    issues = preflight_device_lease_issues(db, pilot_id, modules, configs)
    for module, cfg in modules_and_configs:
        issues.extend(validate_extlink_config(module.name, module.id, cfg))
    return issues
