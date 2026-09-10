"""Rig checkpoint sender (Phase 34, Plan 09, Task 1): the exact script the USER runs, by
hand, against a real Pi to observe the four phase-closing hardware behaviours. Public API
only (34-09-PLAN.md decision 1) -- no `mics_link._internal`, no reaching past
`mics_link.__all__`. If this script ever needs something the README does not document,
that is a finding about the API, not a reason to import a private name.

No number printed by this script could be read as latency (decision 2): only counts,
states and a plain wall-clock duration are ever printed. Phase 28 owns timing.

`--host` is REQUIRED and has no default -- see the note above DEFAULT_PORT. Port,
source_id and signal default to the standing `ExtlinkDemo` fixture (sdk/README.md
section 3): `5599`, `demo`, `left_paw_x`, all overridable by flag.

    python3 sdk/examples/rig_checkpoint_sender.py --host <pilot-address> --mode transition
    python3 sdk/examples/rig_checkpoint_sender.py --host <pilot-address> --mode quiet --seconds 20
    python3 sdk/examples/rig_checkpoint_sender.py --host <pilot-address> --mode soak --rate 60 --seconds 30
    python3 sdk/examples/rig_checkpoint_sender.py --host <pilot-address> --mode reconnect --seconds 120

All four modes exit cleanly on Ctrl-C (a `KeyboardInterrupt` around the mode's own loop,
never a bare `except:`) and print a final `stats.snapshot()` before exiting.
"""
import argparse
import sys
import time

from mics_link import connect

# `--host` deliberately has NO default. A placeholder default would be worse than none:
# a ZMQ DEALER connecting to an address nobody answers does not raise -- it queues, and
# this script would print clean stats while nothing ever reached a Pi. That is the exact
# "you get silence, not an error" failure described below, and the same reasoning that
# removed the default port from this project's other client CLI (commit 8191d4b).
#
# WHICH pilot to point it at, and why it matters (user direction 2026-08-30): prefer the
# pilot running mics_core, because the frozen golden corpus is pinned to mics_core's
# external_hardware_wire.py -- that pilot exercises the exact runtime the byte-parity
# corpus came from. A pilot still on pi-mirror works but needs a caveat recorded.
#
# Read the address, port and source_id from that pilot's own `pilot_hardware_config`
# row rather than assuming these defaults match it. Note that some rows carry
# `required: false`: with no readiness gate a run proceeds even if this sender never
# connects, so a wrong address yields silence rather than an error.
DEFAULT_PORT = 5599
DEFAULT_SOURCE_ID = "demo"
DEFAULT_SIGNAL = "left_paw_x"


def _print_stats(link, prefix="final"):
    counts = link.stats.snapshot()
    print(
        "{}: enqueued={} sent={} dropped={} abandoned={} send_failed={}".format(
            prefix,
            counts["enqueued"],
            counts["sent"],
            counts["dropped"],
            counts["abandoned"],
            counts["send_failed"],
        )
    )


# extlink_demo's left_paw_x is declared `stale_after_ms=200, stale_policy="return_default"`
# (hardware lib 177 v2), so the Pi reverts it to 0.0 just 200ms after the last frame. A single
# send followed by a sleep therefore leaves the signal live for 200ms out of every hold window
# and at its default for the rest -- the FDA samples on its own cadence and almost never lands
# inside that sliver. Rig run 581 (2026-08-30) did exactly this: 6 sends, 0 drops, 0 send
# failures, and every one of the 16 FDA reads in ES saw 0.0, so no transition ever fired.
# The value must therefore be HELD by resending it, not sent once.
HOLD_REFRESH_HZ = 10.0


def _hold(link, signal, value, hold_s, refresh_hz=HOLD_REFRESH_HZ):
    """Keep `signal` at `value` for `hold_s` by resending at `refresh_hz`.

    The refresh period (100ms at 10Hz) must stay comfortably under the signal's
    `stale_after_ms`; do not lower this rate without checking that declaration.
    """
    period = 1.0 / refresh_hz
    deadline = time.time() + hold_s
    sends = 0
    while time.time() < deadline:
        link.send_signal(signal, value)
        sends += 1
        time.sleep(period)
    return sends


def run_transition(link, signal, cycles=3, high=0.7, low=0.1, hold_s=2.0):
    """Crosses task def 434's two authored transitions (`>0.5` then `<0.2`) `cycles`
    times: `wait -> armed -> fired -> wait`, HOLDING each value across its window.
    """
    for cycle in range(1, cycles + 1):
        print("cycle {}/{}: holding {}={} for {}s (expect wait->armed)".format(
            cycle, cycles, signal, high, hold_s))
        n = _hold(link, signal, high, hold_s)
        print("  held with {} frames at {}Hz".format(n, HOLD_REFRESH_HZ))
        print("cycle {}/{}: holding {}={} for {}s (expect armed->fired->wait)".format(
            cycle, cycles, signal, low, hold_s))
        n = _hold(link, signal, low, hold_s)
        print("  held with {} frames at {}Hz".format(n, HOLD_REFRESH_HZ))


def run_quiet(link, signal, seconds):
    """Sends ONE signal, then nothing at all for `seconds` while the SDK's own heartbeat
    keeps `<source_id>.alive` true. Prints a one-line-per-second countdown so the user can
    correlate with what they observe on the rig.
    """
    print("sending one signal: {}=0.3, then going quiet for {}s".format(signal, seconds))
    link.send_signal(signal, 0.3)
    for remaining in range(seconds, 0, -1):
        print("quiet: {}s remaining, connected={}".format(remaining, link.connected))
        time.sleep(1.0)


def run_soak(link, signal, rate, seconds):
    """Sends at `rate` Hz for `seconds`, printing cumulative sent + `stats.dropped` once a
    second. Mirrors the retired `extlink_driver.py --rate` shape. No latency line, ever.
    """
    interval_s = 1.0 / rate
    deadline = time.monotonic() + seconds
    next_print = time.monotonic() + 1.0
    next_send = time.monotonic()
    total_sent = 0
    toggle_high = True
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_send:
            value = 0.7 if toggle_high else 0.1
            toggle_high = not toggle_high
            link.send_signal(signal, value)
            total_sent += 1
            next_send += interval_s
        if now >= next_print:
            counts = link.stats.snapshot()
            print("soak: sent={} stats.dropped={}".format(total_sent, counts["dropped"]))
            next_print += 1.0
        time.sleep(min(interval_s, 0.05))


def run_reconnect(link, signal, seconds):
    """Sends one signal per second for `seconds`. `on_state_change` (wired by the caller
    before this runs) prints CONNECTED/DISCONNECTED with a timestamp, so the user can watch
    a pilot restart reflected live. `seq` continuity is verified in ES, not printed here
    (34-CONTEXT.md: `seq` is never surfaced to the caller).
    """
    for i in range(seconds):
        link.send_signal(signal, 0.7 if i % 2 == 0 else 0.1)
        print("reconnect: send #{} connected={}".format(i + 1, link.connected))
        time.sleep(1.0)


def _on_state_change(connected):
    ts = time.strftime("%H:%M:%S")
    print("[{}] {}".format(ts, "CONNECTED" if connected else "DISCONNECTED"))


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="rig_checkpoint_sender",
        description="USER-RUN rig checkpoint sender for MICS-Link phase 34-09.",
    )
    parser.add_argument("--mode", required=True, choices=("transition", "quiet", "soak", "reconnect"))
    parser.add_argument("--host", required=True, help="target pilot address; no default, see module docstring")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--signal", default=DEFAULT_SIGNAL)
    parser.add_argument("--seconds", type=int, default=20, help="quiet/reconnect duration")
    parser.add_argument("--rate", type=float, default=60.0, help="soak send rate, Hz")
    parser.add_argument("--cycles", type=int, default=3, help="transition mode: cycle count")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)

    print("connecting to {}:{} as source_id={}".format(args.host, args.port, args.source_id))
    link = connect(
        args.host, args.port, args.source_id, on_state_change=_on_state_change
    )
    try:
        if args.mode == "transition":
            run_transition(link, args.signal, cycles=args.cycles)
        elif args.mode == "quiet":
            run_quiet(link, args.signal, args.seconds)
        elif args.mode == "soak":
            run_soak(link, args.signal, args.rate, args.seconds)
        elif args.mode == "reconnect":
            run_reconnect(link, args.signal, args.seconds)
    except KeyboardInterrupt:
        print("interrupted by Ctrl-C")
    finally:
        _print_stats(link)
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
