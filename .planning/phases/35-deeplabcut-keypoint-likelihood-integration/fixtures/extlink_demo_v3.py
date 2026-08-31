# VERSION 3 candidate (authored by plan 35-02, not yet published -- plan 35-09 uploads it).
# Changes exactly ONE thing versus version 2 (`hardware_lib_versions` id 137): the
# `liveness_hook` method. Everything else -- class name, signals, decorators, egress
# behaviour, `declared_imports` -- is byte-identical to `extlink_demo_v2_rollback.py`.
# `liveness_hook` v2 hardcoded `return True` ("DIAGNOSTIC OVERRIDE (v2)"), a workaround for
# an undiagnosed 2026-08-09 liveness fault (Defect A, see 35-LIVENESS-FINDINGS.md) that was
# never removed. This version replaces the override with the canonical clock-consistent hook
# from `fixtures/liveness_hook_snippet.py` (emitted verbatim below), which is itself a
# WORKAROUND for a separate, later, VERIFIED-IN-SOURCE defect (Defect B: a cross-clock
# subtraction introduced by Phase 31 Plan 10, commit `1f35782` -- see D-49/D-50/D-51). This
# hook fixes Defect B. It does NOT fix Defect A -- removing the override is expected to be
# SAFE only once plan 35-09 confirms the `.125:5597` egress listener is up (A1, corroborated
# by design documentation and timeline, not yet reproduced). If Defect A resurfaces once the
# override is gone, that is Defect A being observed for the first time, not a regression
# introduced by this change.
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
        """The passed-in `now_ms` is not used because it is `time.time()`-derived
        (`external_hardware_binding.py:_now_ms()`) while `last_msg_ts_ms` is one-clock-derived
        on the mics_core stack, so subtracting them crosses clock domains; on the pi-mirror
        stack this hook is numerically identical to `default_liveness` because both sides are
        `time.time()` there. WORKAROUND for Defect B (a Phase 31 bug, not a sanctioned
        exemption -- see 35-LIVENESS-FINDINGS.md D-49/D-50/D-51); does NOT address Defect A,
        the still-undiagnosed 2026-08-09 fault this method's v2 override was hiding.
        """
        if last_msg_ts_ms is None:
            return False
        try:
            # Imported here, not at module scope: this file is `exec`'d from
            # `hardware_lib_versions.source_code`, before `autopilot.hardware
            # .external_hardware_ingress` is necessarily importable at module-exec time.
            from autopilot.hardware.external_hardware_ingress import now_ms as ingress_now_ms
            current = ingress_now_ms()
        except Exception:
            # Degrade to the substrate default rather than raising into the LivenessPoller.
            current = now_ms

        if not getattr(self, "_liveness_hook_logged_once", False):
            self._liveness_hook_logged_once = True
            self.logger.warning(
                "liveness_hook: one-shot clock check (last_msg_ts_ms=%s, now_ms=%s, "
                "ingress_now_ms=%s)", last_msg_ts_ms, now_ms, current,
            )

        return (current - last_msg_ts_ms) < stale_ms

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
