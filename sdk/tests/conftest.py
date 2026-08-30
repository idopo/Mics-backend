"""Makes `mics_link` importable from the src/ layout without an editable install.

The dev host's Python is externally-managed (PEP 668) and this repo deliberately avoids
installing sdk/ into it — Task 3's install smoke instead installs into an isolated
`--target` directory. Tests run straight against the source tree via this sys.path shim,
which is the standard idiom for a src-layout package exercised without `pip install -e`.
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))
