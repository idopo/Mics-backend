"""Canonical `liveness_hook` for `ExternalHardware` subclasses on the mics_core stack (DLC-06).

**WORKAROUND for Defect B, a Phase 31 bug -- not a sanctioned exemption.** See
`35-LIVENESS-FINDINGS.md` (D-49/D-50/D-51). `external_hardware_binding.py`'s default liveness
predicate subtracts a wall-clock `now_ms` (`_now_ms()`, `time.time()`-derived) from
`_last_msg_ts_ms`, which the mics_core ingress stamps from the ONE CLOCK
(`clock.to_utc_ns(clock.now_from_tick())`, see `external_hardware_ingress.py:_now_ms_and_mono_ns`).
That is a cross-clock subtraction and a violation of the one-clock invariant Phase 31 Plan 10
itself introduced (commit `1f35782`) -- it is not a documented exemption, and the in-source
comment claiming otherwise is inaccurate (D-49). This hook REPLACES the comparison with a
like-for-like one, reading the current time from the SAME source the ingress stamp came from,
without touching a single Pi file. This phase is forbidden from editing the substrate (DLC-01),
so this is a lib-level route-around, not a resolution -- the actual fix belongs to Phase 31/18,
which owns `external_hardware_binding.py`'s `_now_ms()`.

**This hook fixes Defect B. It does NOT address Defect A** -- the still-undiagnosed 2026-08-09
liveness fault that the removed "DIAGNOSTIC OVERRIDE (v2)" was written to hide. A rig run passing
with this hook installed is evidence that the clock-domain mismatch is gone; it is NOT evidence
that Defect A (candidate A1: the egress probe, corroborated but not yet demonstrated) is
understood or resolved. Do not read a passing quiet test as proof Defect A never existed.

**Declared at CLASS level ONLY, never assigned in `__init__`** -- `external_hardware.py`'s
`validate_role_liveness` reads `getattr(type(self), "liveness_hook", None) is not None`, so an
instance-level assignment is invisible to that check and construction fails closed, but
confusingly (`external_hardware.py:60-70`).
"""


def liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms):
    """The passed-in `now_ms` is not used because it is `time.time()`-derived
    (`external_hardware_binding.py:_now_ms()`) while `last_msg_ts_ms` is one-clock-derived on
    the mics_core stack, so subtracting them crosses clock domains; on the pi-mirror stack this
    hook is numerically identical to `default_liveness` because both sides are `time.time()`
    there (`pi-mirror/.../external_hardware_ingress.py` stamps `int(time.time() * 1000)`).
    """
    if last_msg_ts_ms is None:
        return False
    try:
        # Imported here, not at module scope: a module-level import would run at lib-exec
        # time (this file is `exec`'d from `hardware_lib_versions.source_code`), before
        # `autopilot.hardware.external_hardware_ingress` is necessarily importable.
        from autopilot.hardware.external_hardware_ingress import now_ms as ingress_now_ms
        current = ingress_now_ms()
    except Exception:
        # Degrade to the substrate default rather than raising into the LivenessPoller,
        # which runs on its own daemon thread but whose exceptions would otherwise silently
        # stop the poll (T-35-06).
        current = now_ms

    if not getattr(self, "_liveness_hook_logged_once", False):
        self._liveness_hook_logged_once = True
        # One-shot diagnostic: measures the actual offset between the two clocks on a real
        # rig run, landing in the pilot journal via self.logger (never print -- this runs
        # inside the pilot process, not a script with a controlling terminal).
        self.logger.warning(
            "liveness_hook: one-shot clock check (last_msg_ts_ms=%s, now_ms=%s, "
            "ingress_now_ms=%s)", last_msg_ts_ms, now_ms, current,
        )

    return (current - last_msg_ts_ms) < stale_ms
