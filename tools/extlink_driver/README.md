# extlink_driver — retired proof of concept

**This driver has been removed.** It was a Phase 18 proof of concept for hand-driving an
`ExternalHardware` signal from a laptop and watching the rig's FDA respond. The supported way to
do this now is the `mics_link` SDK — see `sdk/README.md`, and `sdk/examples/` for worked senders,
including a ten-line sender targeting this exact rig fixture.

`extlink_wire.py`, `extlink_driver.py` and `test_extlink_wire.py` are gone from this directory and
from git. Nothing in this repo still imports them. Their behaviour was already extracted before
deletion: the frame codec (byte-exact parity with the Pi's `external_hardware_wire.py`) and the
AST import-hygiene guard live in `sdk/src/mics_link/wire.py`, `sdk/tests/test_wire_parity.py` and
`sdk/tests/test_import_hygiene.py` (phase 34 wave 1); the CSV/stdin token coercion (bool-before-int
ordering) lives in `sdk/src/mics_link/values.py` (phase 34 wave 2).

## What still lives here

- `extlink_demo_fda.json` — the throwaway task-definition fixture used by the phase 34-09 rig
  checkpoint. Unmodified by this plan: three states (`wait -> armed -> fired -> wait`), no entry
  actions, safe to run on the rig with no animal in the box.

## Rig prerequisites (the standing fixture)

This fixture is already standing on pilot 1 and is the worked example every SDK sender in this
phase targets. These IDs are the only written record of this fixture outside the DB — preserve
them if this file is edited again.

- **Pilot:** pilot 1 (`pilot_raspberry_lior`), host `132.77.72.28`
- **Toolkit:** 100
- **Hardware module:** 62 (`ExtlinkDemo`)
- **Hardware lib:** 177
- **Task definition:** 434 (`extlink_demo`)
- **`pilot_hardware_config` row:** 21, `config` column, verbatim:
  ```json
  {"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,
   "host":"132.77.73.125","source_id":"demo","stale_ms":3000,
   "required":true,"wait_timeout_s":30,"egress_fail_threshold":3}
  ```
- **What a sender needs from that row:** `source_id` (`demo`) is the DEALER identity the sender
  MUST use — a mismatch is dropped silently by the Pi's ROUTER, no NAK. `listen_port` (`5599`) is
  the port the Pi's ROUTER is bound on. The pilot's own host/IP (`132.77.72.28`) is what the
  sender dials — **not** the `host` field in the JSON above, which is this module's own *egress*
  probe target, a different thing entirely.
- **Role:** `router_bind` only — the Pi binds, the sender dials in as a DEALER. A sender's own
  IP never has to be written into any config row.
- **Signals/events:** `left_paw_x` / `right_paw_x` (`float`), event `object_detected`, plus the
  always-present `demo.alive` tracker.
- **FDA transitions:** `wait -> armed` on `demo.left_paw_x > 0.5`, `armed -> fired` on
  `demo.left_paw_x < 0.2`, `fired -> wait` unconditional, no terminal state. These are
  hand-authored in the browser FDA editor, not shipped in `extlink_demo_fda.json` — authoring
  them is the actual proof that the extlink option group and picker work in the editor.
- **Standing dependency (inherited from Phase 18's teardown decision):** the `ExtlinkDemo`
  module needs a TCP echo listener on the dev host at `132.77.73.125:5597` to stay running.
  Without it, `demo.alive` flips false after three egress-probe failures and the readiness gate
  times out. See `18-HARDWARE-VALIDATION.md` §3 — start this first, not as a debugging surprise.

## Why there is no latency readout

Comparing a sender machine's send-timestamp against the Pi's `ts_pi_recv` would measure clock
skew, not latency — the two machines are not NTP-synced to each other. That measurement belongs
to Phase 28 (TTL vs Network Sync Validation). This is a deliberate deferral, carried forward into
the SDK's own README: do not add a latency-measuring flag that would silently report a number
that isn't what it claims to be.

## Stale artifact

`extlink_driver_mac.zip` at the repo root is now **stale** — it bundles a copy of the deleted
`extlink_wire.py`/`extlink_driver.py` codec. It is untracked and belongs to the user, so this
plan does not delete it; it is noted here only so a future reader doesn't mistake it for a
working copy of anything.
