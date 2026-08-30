"""The ONE named place the canonical-golden-corpus-reference decision lives (Phase 34, Plan 01).

Decision (locked, do not re-litigate): the canonical reference for the Pi's wire codec is
``~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py``. Direct user
direction, 2026-08-26: "we are working on mics_core." ``~/pi-mirror/...`` is the SECONDARY,
skip-if-absent drift check. The two trees were verified byte-identical (md5
76dd4f8dae27ca207720bd2980260928) both on 2026-08-26 and again at 34-01 execution time on
2026-08-30 — this decision changes which path is NAMED as the source of truth, not the
corpus bytes.

Both paths are outside this repo and are read-only from every test in this package: never
edit, never write, never git-touch either tree (SDK-01).
"""
import importlib.util

import pytest

CANONICAL_PI_WIRE_PATH = "/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py"
SECONDARY_PI_WIRE_PATH = "/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py"


def load_pi_wire(path):
    """Load the Pi's wire codec module by file path, isolated from this package's own
    ``mics_link.wire`` (different module name, no sys.path pollution). Skips the calling
    test (not a hard failure) when the path doesn't exist — the same posture the retired
    POC driver's test suite (``tools/extlink_driver/``, deleted in plan 34-05) used,
    retargeted rather than reinvented.
    """
    import os

    if not os.path.exists(path):
        pytest.skip("Pi wire module not found at {} — cannot run interop test".format(path))
    spec = importlib.util.spec_from_file_location("ehw_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
