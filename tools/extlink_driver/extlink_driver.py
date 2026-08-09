#!/usr/bin/env python3
"""Interactive/scripted driver for a `role: router_bind` ExternalHardware module
(Phase 18, Plan 15). Runs on a researcher's laptop and dials in as a ZMQ DEALER;
the Pi binds the ROUTER, so this machine's address never appears in
`pilot_hardware_config`. Three mutually exclusive modes: interactive stdin
(default), --sweep, --rate. No ack handling and no latency measurement -- the
laptop and rig are not NTP-synced, so a send-timestamp vs. `ts_pi_recv`
comparison would measure clock skew, not latency (that belongs to Phase 28).
`zmq`/`msgpack` are imported only inside the mode handlers, never at module
scope, so --help works before either is installed.
"""
import argparse
import sys
import time

DEFAULT_SWEEP_SECONDS = 60.0
DEFAULT_RATE_SECONDS = 30.0
SWEEP_STEPS_PER_LEG = 20


def build_parser():
    parser = argparse.ArgumentParser(
        description="Drive a router_bind ExternalHardware module's signals/events "
        "by hand or hands-free, from a laptop."
    )
    parser.add_argument("--pi-host", required=True, help="Host/IP the Pi's ROUTER is bound on")
    parser.add_argument("--listen-port", required=True, type=int, help="Port the Pi's ROUTER is bound on (pilot_hardware_config.config.listen_port)")
    parser.add_argument("--source-id", required=True, help="DEALER identity; must match pilot_hardware_config.config.source_id")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sweep", metavar="SIGNAL", help="Hands-free: ramp SIGNAL up then down between --min/--max, repeating, so a threshold anywhere in range is crossed in both directions")
    mode.add_argument("--rate", metavar="N", type=float, help="Soak: send --signal at N Hz for --seconds. This is a soak, not a benchmark -- no latency number is printed. Pass/fail lives on the rig side (pilot stays up, the FDA keeps transitioning, bounded-queue drops are reported, ES ingestion keeps up).")

    parser.add_argument("--signal", help="Signal name to drive; required with --rate")
    parser.add_argument("--min", type=float, default=0.0, help="Sweep floor (default 0.0)")
    parser.add_argument("--max", type=float, default=1.0, help="Sweep ceiling (default 1.0)")
    parser.add_argument("--sweep-hz", type=float, default=5.0, help="Sweep send rate (default 5)")
    parser.add_argument("--seconds", type=float, default=None, help="Duration: sweep default {:.0f}s, rate default {:.0f}s".format(DEFAULT_SWEEP_SECONDS, DEFAULT_RATE_SECONDS))
    return parser


def _import_wire():
    try:
        import extlink_wire
    except ImportError:
        sys.exit("msgpack is required. Install it with: pip install pyzmq msgpack")
    return extlink_wire


def _connect(args):
    try:
        import zmq
    except ImportError:
        sys.exit("pyzmq is required to connect. Install it with: pip install pyzmq msgpack")
    ctx = zmq.Context()
    sock = ctx.socket(zmq.DEALER)
    sock.setsockopt(zmq.IDENTITY, args.source_id.encode("utf-8"))
    sock.connect("tcp://{}:{}".format(args.pi_host, args.listen_port))
    return ctx, sock


def run_interactive(args):
    wire = _import_wire()
    ctx, sock = _connect(args)
    print("Connected as DEALER identity={} -> tcp://{}:{}".format(
        args.source_id, args.pi_host, args.listen_port))
    print("Type '<signal> <value>' for a SIG, or '<event> {\"k\": v}' for an EVT. Ctrl-D to quit.")
    seq = 0
    try:
        while True:
            try:
                line = input("> ")
            except EOFError:
                print()
                break
            parsed = wire.parse_command(line)
            if parsed is None:
                print("could not parse -- expected '<name> <value>', e.g. 'left_paw_x 0.7'")
                continue
            kind, name, value = parsed
            frame = (
                wire.sig_frame(name, value, seq)
                if kind == "SIG" else wire.evt_frame(name, value, seq)
            )
            sock.send(frame)
            print("sent {} {} = {} (seq {})".format(kind, name, value, seq))
            seq += 1
    except KeyboardInterrupt:
        print()
    finally:
        sock.close()
        ctx.term()


def run_sweep(args):
    wire = _import_wire()
    ctx, sock = _connect(args)
    seconds = DEFAULT_SWEEP_SECONDS if args.seconds is None else args.seconds
    interval = 1.0 / args.sweep_hz
    span = args.max - args.min
    print("Sweeping '{}' between {} and {} at {} Hz for {:.0f}s (Ctrl-C to stop early)".format(
        args.sweep, args.min, args.max, args.sweep_hz, seconds))
    seq = 0
    start = time.time()
    try:
        while time.time() - start < seconds:
            for direction in (1, -1):
                for i in range(SWEEP_STEPS_PER_LEG + 1):
                    if time.time() - start >= seconds:
                        return
                    fraction = i / float(SWEEP_STEPS_PER_LEG)
                    if direction == -1:
                        fraction = 1.0 - fraction
                    value = args.min + span * fraction
                    sock.send(wire.sig_frame(args.sweep, value, seq))
                    seq += 1
                    time.sleep(interval)
    except KeyboardInterrupt:
        print()
    finally:
        sock.close()
        ctx.term()


def run_rate(args):
    if not args.signal:
        sys.exit("--rate requires --signal SIGNAL_NAME")
    wire = _import_wire()
    ctx, sock = _connect(args)
    seconds = DEFAULT_RATE_SECONDS if args.seconds is None else args.seconds
    interval = 1.0 / args.rate
    print(
        "Soaking '{}' at {} Hz for {:.0f}s -- this is a soak, not a benchmark; no latency "
        "is measured. Pass/fail lives on the rig: pilot stays up, the FDA keeps "
        "transitioning, bounded-queue drops are reported, ES ingestion keeps up.".format(
            args.signal, args.rate, seconds
        )
    )
    seq = 0
    sent = 0
    start = time.time()
    last_report = start
    try:
        while time.time() - start < seconds:
            sock.send(wire.sig_frame(args.signal, seq, seq))
            seq += 1
            sent += 1
            now = time.time()
            if now - last_report >= 1.0:
                print("sent {} (elapsed {:.0f}s)".format(sent, now - start))
                last_report = now
            time.sleep(interval)
    except KeyboardInterrupt:
        print()
    finally:
        print("done: sent {} messages in {:.1f}s".format(sent, time.time() - start))
        sock.close()
        ctx.term()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.rate is not None and not args.signal:
        parser.error("--rate requires --signal")
    if args.sweep:
        run_sweep(args)
    elif args.rate is not None:
        run_rate(args)
    else:
        run_interactive(args)


if __name__ == "__main__":
    main()
