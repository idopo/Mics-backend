"""Replay entry point (Phase 34, Plan 07, SDK-12): plays a recorded `(t, signal, value)`
file through a `mics_link` client at real time, at a scale factor, or as fast as possible.
This is the phase's own regression vehicle and the mechanism by which Phase 35 is proven
without a camera, a trained model or an animal — and afterwards, the way a DLC-driven task
is re-run deterministically.

`read_rows`/`ReplayStats` are implemented in `mics_link/replay_io.py` and re-exported here
unchanged — the split keeps both files under the project's 300-line cap; every name this
module's own `<interfaces>` block promises (`ReplayStats`, `read_rows`, `replay`, `main`)
still resolves from `mics_link.replay`, split or not. `replay()`/`main()` land in Task 2 of
this plan, alongside `mics_link.timing.Pacer`.
"""
from .replay_io import ReplayStats, read_rows  # noqa: F401 (re-exported, see docstring)

__all__ = ["ReplayStats", "read_rows"]
