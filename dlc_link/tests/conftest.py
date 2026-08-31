"""Makes `dlc_link` AND `mics_link` importable from their src/ layouts without an
editable install.

The dev host's Python is externally-managed (PEP 668) and this repo deliberately avoids
installing either package into it, so tests run straight against both source trees via
this sys.path shim — the same idiom `sdk/tests/conftest.py` uses for `mics_link` alone.
`dlc_link` depends on `mics-link` as an ordinary third-party dependency (never a
path-relative import in production code); this shim exists only so the test suite can
exercise both source trees with no install step. The `sdk/src` insertion is a read of
that tree, never a write.
"""
import os
import sys

_HERE = os.path.dirname(__file__)
_DLC_LINK_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SDK_SRC = os.path.abspath(os.path.join(_HERE, "..", "..", "sdk", "src"))

for _path in (_DLC_LINK_SRC, _SDK_SRC):
    if _path not in sys.path:
        sys.path.insert(0, _path)
