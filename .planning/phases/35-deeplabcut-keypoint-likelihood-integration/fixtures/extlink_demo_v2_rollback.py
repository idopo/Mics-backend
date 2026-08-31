"""The single ExternalHardware demo fixture: signals you can drive by hand from a laptop.

Role `router_bind` -- the Pi binds a ROUTER and `tools/extlink_driver/` (run from a laptop)
connects a DEALER to it. Type a signal name and a value in the driver and this module's view
keys change, so FDA transitions written against `extlink_demo.left_paw_x` fire on demand with
no real device present.

Two signals deliberately carry DIFFERENT stale policies (EXTLINK-06): `left_paw_x` reverts to
its default when the laptop stops sending, `right_paw_x` holds its last value. Stop the driver
and watch them diverge.

`on_run_start`/`on_run_stop`/`_egress_probe` exist so outbound traffic (EXTLINK-15) has
something to observe -- nothing else here ever calls `self.send()`. Every 1s for the run's
duration one zero-arg callable is enqueued that opens a TCP connection to
`self.host:_EGRESS_PORT` and waits up to 5s for a byte back. Point `self.host` at an
`nc -l <port>` that never replies to make it fail slowly (queue builds, then drops); point it
at a closed port to make it fail fast (quick `alive` flip, no queue buildup).

SUBSTRATE FIXTURE. Not the OpenEphys lib (Phases 26/27), not the DeepLabCut integration.
"""
import socket
import threading

from autopilot.hardware.external_hardware import ExternalHardware, command, event, signal


class ExtlinkDemo(ExternalHardware):
    _EGRESS_PORT = 5597

    def liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms):
        """DIAGNOSTIC OVERRIDE (v2). default_liveness reported not-alive while on_recv was
        demonstrably stamping _last_msg_ts_ms, stranding the readiness gate in 2 of 4 rig runs.
        Returning True unconditionally isolates the fault: if the gate now opens every time,
        the bug is in the default liveness/timestamp path, not the bind path."""
        return True

    @signal(default=0.0, stale_after_ms=200, stale_policy="return_default")
    def left_paw_x(self) -> float:
        pass

    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def right_paw_x(self) -> float:
        pass

    @event(payload={"object": str, "confidence": float})
    def object_detected(self):
        pass

    @command
    def ping(self) -> bool:
        pass

    def on_run_start(self, run_ctx):
        # LifecycleRunner retries on_run_start until is_ready() is True; this guard makes
        # starting the demo probe thread idempotent across those retries.
        if getattr(self, "_egress_thread", None) is not None:
            return
        stop_event = threading.Event()
        self._egress_stop = stop_event

        def _loop():
            while not stop_event.wait(1.0):
                self.send(self._egress_probe)

        self._egress_thread = threading.Thread(target=_loop, name="ExtlinkDemoEgress")
        self._egress_thread.daemon = True
        self._egress_thread.start()

    def on_run_stop(self):
        stop_event = getattr(self, "_egress_stop", None)
        if stop_event is not None:
            stop_event.set()
        self._egress_thread = None

    def _egress_probe(self):
        sock = socket.create_connection((self.host, self._EGRESS_PORT), timeout=5.0)
        try:
            sock.sendall(b"ping\n")
            sock.recv(16)
        finally:
            sock.close()
