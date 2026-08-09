# extlink_driver — hand-drive an ExternalHardware signal from your laptop

A cross-platform (macOS / Windows / Linux, current Python) command-line tool that lets you type a
signal name and a value and watch the rig's FDA respond, live. It is **additional to**
`~/pi-mirror/scripts/dev/extlink_smoke.py` (plan 18-11's pass/fail probe) — that script only
answers "does the transport work"; this tool is for sitting at a keyboard and watching a state
machine move. It must never be copied into `~/pi-mirror/`, which is rsynced to the Pi.

## Install

The only dependencies are `pyzmq` and `msgpack`. Same command on macOS, Windows, and Linux:

```bash
python3 -m pip install pyzmq msgpack
```

`python3 tools/extlink_driver/extlink_driver.py --help` works even before you run this — `zmq`
and `msgpack` are imported only inside the mode you actually use, never at import time.

## What must be true on the rig first

The Pi needs a `router_bind` `ExternalHardware` module already registered for the target pilot:
a `class_name`, `role: "router_bind"`, a `listen_port`, and a `source_id`, all present in that
pilot's `pilot_hardware_config.config` row. This tool only ever dials in as a DEALER — **the Pi
binds the ROUTER, never this tool** (`role: router_bind` only) — so your laptop's IP never has to
be written into any config row, and a DHCP/Wi-Fi change on your end can't break the setup.

## The three invocations

Substitute your rig's real host/port/source-id; the values below are the ones plan 18-12's
checkpoint uses for its `dlc_cam1` demo module.

**Interactive** (default mode — type a line, watch it send):

```bash
python3 tools/extlink_driver/extlink_driver.py --pi-host 132.77.72.28 \
    --listen-port 5599 --source-id dlc_cam1
> left_paw_x 0.7        # sends a SIG
> object_detected {"object": "paw", "confidence": 0.9}   # a {...} value sends an EVT instead
```

Ctrl-D (or Ctrl-Z on Windows) exits cleanly. A blank line or a line with no value just reprompts
— it will never crash on a stray Enter.

**`--sweep`** — hands-free: ramps the signal up then down between `--min`/`--max`, repeating, so
any threshold inside the range is crossed in both directions with nobody touching the keyboard:

```bash
python3 tools/extlink_driver/extlink_driver.py --pi-host 132.77.72.28 \
    --listen-port 5599 --source-id dlc_cam1 \
    --sweep left_paw_x --min 0.0 --max 1.0 --sweep-hz 5 --seconds 30
```

**`--rate`** — the soak driver, N Hz for a duration:

```bash
python3 tools/extlink_driver/extlink_driver.py --pi-host 132.77.72.28 \
    --listen-port 5599 --source-id dlc_cam1 \
    --rate 60 --signal left_paw_x --seconds 30
```

## Registering `extlink_demo_fda.json`

`extlink_demo_fda.json` is a throwaway task definition, **not an existing lab task**: three
states (`wait` -> `armed` -> `fired` -> `wait`), no entry actions anywhere — no valve, no reward,
no `INC_TRIAL_COUNTER` — so it is safe to run on the rig pilot with no animal in the box. State
changes are dispatched to ES by the FDA itself, so the state name alone is the observable.

The file deliberately ships only the boring scaffolding (states, the initial state, the
unconditional `fired -> wait` return edge). **The two signal-gated transitions
(`wait -> armed`, `armed -> fired`) are not in the file — you add them by hand, in the browser, in
the FDA editor.** That authoring step is the actual proof that the extlink option group and picker
work; shipping the transitions in this JSON file would let that check be satisfied by `curl`
instead and prove nothing about the editor.

To add them: open `/react/` -> the `extlink_demo` task definition in the FDA editor. On the
`wait -> armed` edge, add a condition, set the left operand type to **view**, and open the picker
— look for the option group labelled **`dlc_cam1 signals`** (the pattern is
`"<source_id> signals"`), containing an item labelled **`left_paw_x (float)`** whose value is the
resolved key `dlc_cam1.left_paw_x`. Set the operator to `>` and the right operand to the literal
`0.5`. Add the mirror transition `armed -> fired` on `< 0.2`. Save — it should save with no 422,
and reopening the definition should still show the operand selected (not "(unknown)").

With both transitions authored, the three invocations above become observable: typing
`left_paw_x 0.7` should move `wait -> armed`; `left_paw_x 0.1` should move `armed -> fired` and
then immediately `fired -> wait`; `--sweep` should cycle the state on its own.

## Why there is no latency readout

Comparing this laptop's send-timestamp against the Pi's `ts_pi_recv` would measure clock skew, not
latency — the two machines are not NTP-synced to each other. That measurement belongs to Phase 28
(TTL vs Network Sync Validation). This is a deliberate deferral: do not add a `--measure-latency`
flag that would silently report a number that isn't what it claims to be.

## The soak recipe

```bash
python3 tools/extlink_driver/extlink_driver.py --pi-host <host> \
    --listen-port <port> --source-id <source_id> \
    --rate 60 --signal <signal> --seconds 30
```

This is a soak, not a benchmark — no latency number is printed anywhere, and none should be added.
Pass/fail is observed on the rig side, not the laptop:

- the pilot process stays up
- the FDA keeps transitioning
- any bounded ingress/egress queue drops are **reported** (a drop is fine; a silent one is not)
- ES ingestion keeps up with the state changes

## Not this tool's job

`~/pi-mirror/scripts/dev/extlink_smoke.py` (plan 18-11) is the pass/fail probe used in automated
and scripted checks. This tool is for a person at a keyboard. Keep both; do not merge them, and
never copy this directory into `~/pi-mirror/`.
