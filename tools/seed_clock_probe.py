#!/usr/bin/env python3
"""Idempotent seeder for the `clock_probe` toolkit (Phase 31 Plan 12, Tasks 1-2).

Builds a NEW backend-authored toolkit, two NEW task definitions, one protocol and one test
subject -- entirely through the existing API endpoints (never raw SQL), the same reasoning as
plan 11's withdrawn publisher: the endpoints carry validation the probe should be subject to
like any other toolkit.

Plan 11 ("The deployed gpio.py IS the repo's gpio.py") was WITHDRAWN 2026-08-24 by user decision
-- hardware-lib version pinning is deliberate design, not drift to be closed by repointing
existing pins. See withdrawn/README.md. This seeder therefore does NOT reference "the version
plan 11 promoted" (nothing was promoted); it pins to an explicit hardware_lib_versions.id
verified directly in the database:

    hardware_lib_versions.id = 159  (lib 8 "gpio.py", version_number=5, state=beta)
    sha256 = 9322ecfd68bb48ef60e484444d05ca76a9453c3b34ea70facecf689c7d0c83d7

Verified 2026-08-24: that sha256 is BYTE-IDENTICAL to mics_core's
autopilot/autopilot/hardware/gpio.py at commit 09d32e1 ("feat(31-C2): convert the raw tick
inside assign_cb, on the one clock (PLAT-18/27)"), and the source contains
`_edge_timestamp_adapter`. Do not change GPIO_PINNED_VERSION_ID without re-verifying both facts
-- run `python3 tools/seed_clock_probe.py --verify-only` to re-check.

Design intent (do not violate, see the executor's <design_intent_do_not_violate>):
  - Additive writes only, through the existing API endpoints. Never raw SQL.
  - Never modifies, repoints, promotes or touches any EXISTING toolkit, task definition, or
    hardware-lib pin. This script only ever creates NEW rows named `clock_probe*` /
    `clock_probe_rig`, or links/pins that belong to those new rows.
  - Never calls PATCH /hardware-libs/{id}/mark-stable or any promotion/rollback endpoint.

Known traps this script deliberately avoids (see the plan's <known_traps>):
  1. FDA `{"param": ...}` args are dead on the Pi -- both task definitions use literal args only.
  2. `special: INC_TRIAL_COUNTER` is a silent no-op -- neither task definition references it or
     depends on graduation/trial counting.
  3. `{"view": <hardware>}` as a condition operand was never rig-exercised -- both task
     definitions condition only on `{"view": "TIMER"}`, exactly like task def 553 (`door_test`).
  4. `hw_lib_versions` must be pinned explicitly -- see GPIO_PINNED_VERSION_ID above; this
     script pins it on both task definitions rather than relying on the `stable` rung.

Usage:
    python3 tools/seed_clock_probe.py [--api-url http://localhost:8000]
    python3 tools/seed_clock_probe.py --verify-only   # only check the gpio pin, no writes

Re-running is a no-op that reprints the same ids (idempotent by name/content lookup) -- see
each `ensure_*` function below for how.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import jwt
import requests

# ---------------------------------------------------------------------------
# Fixed identifiers, verified in the database 2026-08-24 (see the plan's <the_hardware> table)
# ---------------------------------------------------------------------------

MODULE_OPTO_TRIGGER = 65  # Digital_Out, lib 8 (gpio) -- the stimulus, the module the whole probe exists to exercise
MODULE_NOSE_POKE_IR = 64  # Digital_In,  lib 8 (gpio) -- input edge path; assign_cb registration is under test
MODULE_TIMER = 6  # TIMER, lib 11 -- loop driver (trap 2: not a trial counter)
MODULE_COMPUTE = 24  # ComputeOps, lib 45 -- present in every backend toolkit, included for parity

HARDWARE_MODULE_IDS = [MODULE_OPTO_TRIGGER, MODULE_NOSE_POKE_IR, MODULE_TIMER, MODULE_COMPUTE]

GPIO_LIB_ID = 8
GPIO_PINNED_VERSION_ID = 159  # see module docstring -- explicit pin, per trap 4

TOOLKIT_NAME = "clock_probe"
SUBJECT_NAME = "clock_probe_rig"  # matches the door_test_rig precedent -- can never be confused with an animal
PROTOCOL_NAME = "clock_probe"

REQUEST_TIMEOUT_S = 15  # every network call is bounded -- no unbounded requests, per repo policy


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _mint_token() -> str:
    """Mint a short-lived HS256 JWT matching api/auth.py's verify_token requirements.

    Reads JWT_SECRET/JWT_ALGORITHM/JWT_AUDIENCE/JWT_ISSUER from the environment, falling back to
    docker-compose.yml's dev defaults (pishoto/HS256/mics-clients/mics-api) so this runs
    unmodified against the local stack.
    """
    secret = os.environ.get("JWT_SECRET", "pishoto")
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    audience = os.environ.get("JWT_AUDIENCE", "mics-clients")
    issuer = os.environ.get("JWT_ISSUER", "mics-api")
    now = int(time.time())
    payload = {
        "sub": "seed_clock_probe",
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + 3600,
        "scope": "mics",
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# FDA v2 documents -- literal args only, TIMER conditions only (traps 1-3)
# ---------------------------------------------------------------------------

def build_short_fda() -> dict[str, Any]:
    """~10 minutes, the reusable regression asset. ~1 Hz edges, ~600 edge pairs.

    Neither this nor build_soak_fda references a param, a trial counter, or a graduation
    criterion (traps 1 and 2) -- both loops are driven by TIMER conditions only (trap 3), exactly
    as task def 553 (door_test) proves works.
    """
    return {
        "version": 2,
        "initial_state": "start",
        "description": (
            "clock_probe_short -- ~10 minute regression asset. Toggles Opto_Trigger at ~1 Hz "
            "so every edge produces two dispatched records (logging_utils.py:97 and task.py:283 "
            "routes) if the module is configured record=True + trigger. Cannot fail the "
            "monotonicity check (C1) on its own -- 10 minutes contains no 32-bit tick wrap; "
            "only clock_probe_soak tests the wrap. Literal args only, TIMER-only conditions, no "
            "trial counter -- see tools/seed_clock_probe.py module docstring for why."
        ),
        "variables": {},
        "trigger_assignments": [],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [1], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [False], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [1], "type": "timer", "method": "set"},
                ]
            },
        },
        "transitions": [
            {"from": "start", "to": "pulse_on", "description": "begin the pulse loop"},
            {
                "from": "pulse_on",
                "to": "pulse_off",
                "description": "pulse has been high 1 s",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
            {
                "from": "pulse_off",
                "to": "pulse_on",
                "description": "pulse has been low 1 s - next cycle",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
        ],
    }


def build_soak_fda() -> dict[str, Any]:
    """>= 4 h 30 m, the backend twin of C4's soak.

    Wrap arithmetic (stated here, not just in the plan, so the next reader does not have to
    re-derive it): a 32-bit monotonic tick in nanoseconds wraps every 2**32 / 1e9 =
    4294.967296 s. Three complete wraps = 3 x 4294.967296 s = 12884.901888 s = 3 h 34 m 45 s.
    The run is scheduled for >= 4 h 30 m so there is >= 55 minutes of margin at each end and the
    soak is guaranteed to contain three *complete* crossings, not two-and-a-bit.
    """
    return {
        "version": 2,
        "initial_state": "start",
        "description": (
            "clock_probe_soak -- >= 4 h 30 m. Same pulse loop as clock_probe_short, slower "
            "(TIMER.set(5) instead of 1) so the index gets a few thousand documents rather than "
            "hundreds of thousands. 3 wrap crossings = 3 x 4294.967296 s = 3 h 34 m 45 s minimum "
            "-- scheduled duration leaves margin at both ends. Nothing in this FDA changes for "
            "the forced wall-clock step (Task 4 Step 4); the task simply keeps pulsing across "
            "it. Literal args only, TIMER-only conditions, no trial counter -- see "
            "tools/seed_clock_probe.py module docstring for why."
        ),
        "variables": {},
        "trigger_assignments": [],
        "states": {
            "start": {},
            "pulse_on": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [True], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [5], "type": "timer", "method": "set"},
                ]
            },
            "pulse_off": {
                "entry_actions": [
                    {"ref": "Opto_Trigger", "args": [False], "type": "hardware", "method": "set"},
                    {"ref": "TIMER", "args": [5], "type": "timer", "method": "set"},
                ]
            },
        },
        "transitions": [
            {"from": "start", "to": "pulse_on", "description": "begin the pulse loop"},
            {
                "from": "pulse_on",
                "to": "pulse_off",
                "description": "pulse has been high 5 s",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
            {
                "from": "pulse_off",
                "to": "pulse_on",
                "description": "pulse has been low 5 s - next cycle",
                "condition_tree": {"op": "==", "left": {"view": "TIMER"}, "right": 0},
            },
        ],
    }


# ---------------------------------------------------------------------------
# Thin HTTP helpers -- bounded timeout on every call, no retry loops
# ---------------------------------------------------------------------------

def _post(session: requests.Session, base: str, path: str, body: dict) -> dict:
    r = session.post(f"{base}{path}", json=body, timeout=REQUEST_TIMEOUT_S)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text}")
    return r.json()


def _put(session: requests.Session, base: str, path: str, body: dict) -> dict:
    r = session.put(f"{base}{path}", json=body, timeout=REQUEST_TIMEOUT_S)
    if r.status_code >= 400:
        raise RuntimeError(f"PUT {path} -> {r.status_code}: {r.text}")
    return r.json()


def _get(session: requests.Session, base: str, path: str) -> requests.Response:
    return session.get(f"{base}{path}", timeout=REQUEST_TIMEOUT_S)


# ---------------------------------------------------------------------------
# Pin verification -- run before any write, per plan_corrections
# ---------------------------------------------------------------------------

def verify_gpio_pin(session: requests.Session, base: str) -> dict:
    """Confirm GPIO_PINNED_VERSION_ID exists under lib 8 and carries the edge-timestamp adapter.

    STOPS (raises) rather than guessing if either fact no longer holds -- a probe that pins to
    an unverified version proves nothing, which is exactly the failure mode plan 11 found.
    """
    r = _get(session, base, f"/api/hardware-libs/{GPIO_LIB_ID}/versions")
    if r.status_code != 200:
        raise RuntimeError(f"GET hardware-libs/{GPIO_LIB_ID}/versions -> {r.status_code}: {r.text}")
    versions = r.json()
    pinned = next((v for v in versions if v["id"] == GPIO_PINNED_VERSION_ID), None)
    if pinned is None:
        raise RuntimeError(
            f"STOP: hardware_lib_versions.id={GPIO_PINNED_VERSION_ID} not found under lib "
            f"{GPIO_LIB_ID} -- the pin in this script no longer matches the database."
        )
    has_adapter = "_edge_timestamp_adapter" in (pinned.get("source_code") or "")
    if not has_adapter:
        raise RuntimeError(
            f"STOP: hardware_lib_versions.id={GPIO_PINNED_VERSION_ID} does NOT carry "
            f"_edge_timestamp_adapter -- this is not the version plan 12 expects."
        )
    print(
        f"[verified] lib {GPIO_LIB_ID} version {GPIO_PINNED_VERSION_ID} "
        f"(version_number={pinned['version_number']}, state={pinned['state']}) "
        f"carries _edge_timestamp_adapter: yes"
    )
    return pinned


# ---------------------------------------------------------------------------
# Idempotent ensure_* steps
# ---------------------------------------------------------------------------

def ensure_toolkit(session: requests.Session, base: str) -> dict:
    """Find by name first (POST /toolkits has no name-uniqueness check of its own)."""
    r = _get(session, base, f"/api/toolkits/by-name/{TOOLKIT_NAME}")
    if r.status_code == 200:
        variants = r.json()
        toolkit = variants[0]
        print(f"[idempotent] toolkit '{TOOLKIT_NAME}' already exists: id={toolkit['id']}")
        return toolkit
    if r.status_code != 404:
        raise RuntimeError(f"GET toolkits/by-name/{TOOLKIT_NAME} -> {r.status_code}: {r.text}")

    payload = {
        "name": TOOLKIT_NAME,
        "hardware_module_ids": HARDWARE_MODULE_IDS,
        "flags": [],
        "params_schema": [],
    }
    toolkit = _post(session, base, "/api/toolkits", payload)
    print(f"[created] toolkit '{TOOLKIT_NAME}' id={toolkit['id']}")
    return toolkit


def ensure_hw_lib_link(session: requests.Session, base: str, toolkit_id: int) -> dict:
    """POST /toolkits/{id}/hardware-libs is naturally idempotent (upserts default_version_id)."""
    payload = {"hardware_lib_id": GPIO_LIB_ID, "version_id": GPIO_PINNED_VERSION_ID}
    result = _post(session, base, f"/api/toolkits/{toolkit_id}/hardware-libs", payload)
    print(f"[linked] lib {GPIO_LIB_ID} -> toolkit {toolkit_id} (default_version_id={GPIO_PINNED_VERSION_ID})")
    return result


def ensure_task_definition(
    session: requests.Session, base: str, toolkit: dict, display_name: str, fda_json: dict
) -> dict:
    """POST /task-definitions already returns the existing record for identical fda_json content
    (matched by file_hash) -- idempotency is the API's, not reimplemented here.
    """
    payload = {
        "display_name": display_name,
        "toolkit_name": toolkit["name"],
        "toolkit_id": toolkit["id"],
        "fda_json": fda_json,
    }
    defn = _post(session, base, "/api/task-definitions", payload)
    print(f"[ensured] task definition '{display_name}' id={defn['id']}")
    return defn


def pin_hw_lib_version(session: requests.Session, base: str, defn_id: int) -> dict:
    """Explicit per-task-definition pin (trap 4) -- PUT is an upsert, safe to call every run."""
    payload = {"version_id": GPIO_PINNED_VERSION_ID}
    result = _put(session, base, f"/api/task-definitions/{defn_id}/hw-lib-versions/{GPIO_LIB_ID}", payload)
    print(f"[pinned] task definition {defn_id}: hw_lib_versions[{GPIO_LIB_ID}] = {GPIO_PINNED_VERSION_ID}")
    return result


def ensure_protocol(session: requests.Session, base: str, short_defn: dict, soak_defn: dict) -> dict:
    """/protocols has no /api prefix (see api/main.py) and 400s on a duplicate name -- list first."""
    r = _get(session, base, "/protocols")
    if r.status_code != 200:
        raise RuntimeError(f"GET /protocols -> {r.status_code}: {r.text}")
    for existing in r.json():
        if existing["name"] == PROTOCOL_NAME:
            print(f"[idempotent] protocol '{PROTOCOL_NAME}' already exists: id={existing['id']}")
            return existing

    # NTrials graduation set absurdly high, matching door_test's precedent (protocol 59): inert
    # here regardless, since neither task definition ever sends INC_TRIAL_COUNTER (trap 2).
    graduation_params = {"graduation": {"type": "NTrials", "value": {"current_trial": 100000}}}
    payload = {
        "name": PROTOCOL_NAME,
        "description": (
            "Clock probe regression protocol (Phase 31 Plan 12). Step 1 is the ~10 minute "
            "clock_probe_short shape-and-provenance check; step 2 is the >= 4 h 30 m "
            "clock_probe_soak wrap-crossing check. Graduation is set so it never fires from "
            "trial counting -- neither task definition sends INC_TRIAL_COUNTER (trap 2); stop "
            "each run from the UI."
        ),
        "steps": [
            {
                "order_index": 0,
                "step_name": "1. clock_probe_short",
                "task_type": TOOLKIT_NAME,
                "params": graduation_params,
                "task_definition_id": short_defn["id"],
            },
            {
                "order_index": 1,
                "step_name": "2. clock_probe_soak",
                "task_type": TOOLKIT_NAME,
                "params": graduation_params,
                "task_definition_id": soak_defn["id"],
            },
        ],
    }
    protocol = _post(session, base, "/protocols", payload)
    print(f"[created] protocol '{PROTOCOL_NAME}' id={protocol['id']}")
    return protocol


def ensure_subject(session: requests.Session, base: str) -> dict:
    """POST /subjects 400s on a duplicate name -- list first."""
    r = _get(session, base, "/subjects")
    if r.status_code != 200:
        raise RuntimeError(f"GET /subjects -> {r.status_code}: {r.text}")
    for existing in r.json():
        if existing["name"] == SUBJECT_NAME:
            print(f"[idempotent] subject '{SUBJECT_NAME}' already exists: id={existing['id']}")
            return existing

    subject = _post(session, base, "/subjects", {"name": SUBJECT_NAME})
    print(f"[created] subject '{SUBJECT_NAME}' id={subject['id']}")
    return subject


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("MICS_API_URL", "http://localhost:8000"))
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only verify the gpio pin (id, presence, adapter) against the DB. No writes.",
    )
    args = parser.parse_args()

    base = args.api_url.rstrip("/")
    token = _mint_token()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    verify_gpio_pin(session, base)
    if args.verify_only:
        return 0

    toolkit = ensure_toolkit(session, base)
    ensure_hw_lib_link(session, base, toolkit["id"])

    short_fda = build_short_fda()
    soak_fda = build_soak_fda()

    short_defn = ensure_task_definition(session, base, toolkit, "clock_probe_short", short_fda)
    pin_hw_lib_version(session, base, short_defn["id"])

    soak_defn = ensure_task_definition(session, base, toolkit, "clock_probe_soak", soak_fda)
    pin_hw_lib_version(session, base, soak_defn["id"])

    protocol = ensure_protocol(session, base, short_defn, soak_defn)
    subject = ensure_subject(session, base)

    print("\n=== clock_probe seed summary ===")
    print(f"toolkit_id:          {toolkit['id']}")
    print(f"task_def_short_id:   {short_defn['id']}")
    print(f"task_def_soak_id:    {soak_defn['id']}")
    print(f"protocol_id:         {protocol['id']}")
    print(f"subject_key:         {subject['name']} (id={subject['id']})")
    print(f"gpio_version_id:     {GPIO_PINNED_VERSION_ID} (lib {GPIO_LIB_ID}), adapter: yes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
