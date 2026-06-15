"""User-facing session configuration and toolkit-wide constants.

A `SessionConfig` is the minimal entry a user writes in the notebook's `SESSIONS`
block. Everything else (ephys folder, recording path, spike file, effective
channels) is derived by convention in `mics.resolve`.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- toolkit-wide defaults (named + overridable; never hardcode inside funcs) ---
SESSIONS_ROOT = "/mnt/mics-smb/yizharlab/Ido/Mics/sessions"
ES_PRIMARY = "http://132.77.73.217:9200"
ES_SECONDARY = "http://132.77.73.125:9200"

DEFAULTS = {
    "trigger_channel": 17,
    "ttl_channel": 16,
    "sampling_rate": 30000,
}


@dataclass
class SessionConfig:
    """One session as the user declares it.

    Required: ``key`` (e.g. ``"m74s4"``), ``es_subject`` (the descriptive ES
    subject string, e.g. ``"m74_cue_reward"`` — NOT the key), ``es_session``.

    Everything else is optional and only overrides derived/default values.
    """

    key: str
    es_subject: str
    es_session: int | None = None

    # Elasticsearch source (defaults to the primary host / v2 index)
    es_host: str = ES_PRIMARY
    es_index: str = "event_log_v2"
    run_id: int | None = None  # new-portal only; legacy sessions leave None

    # Optional path overrides (else derived from convention under SESSIONS_ROOT)
    ephys_folder: str | None = None
    record_node: str | None = None
    spike_path: str | None = None

    # Optional acquisition overrides (else DEFAULTS)
    trigger_channel: int | None = None
    ttl_channel: int | None = None
    sampling_rate: int | None = None
