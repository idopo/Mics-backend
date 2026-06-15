"""MICS Offline Analysis Toolkit.

Assemble MICS behavioral data offline: Elasticsearch events (always) plus
Open Ephys signals and sorted spikes (optional, when a recording exists),
unified onto one clock.
"""

from .config import DEFAULTS, ES_PRIMARY, ES_SECONDARY, SESSIONS_ROOT, SessionConfig
from .resolve import ResolvedSession, load_sessions, resolve_one

__all__ = [
    "SessionConfig",
    "ResolvedSession",
    "resolve_one",
    "load_sessions",
    "SESSIONS_ROOT",
    "ES_PRIMARY",
    "ES_SECONDARY",
    "DEFAULTS",
]
