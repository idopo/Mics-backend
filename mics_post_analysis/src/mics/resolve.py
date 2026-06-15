"""Convention-driven session resolver.

Turns a minimal :class:`~mics.config.SessionConfig` into a
:class:`ResolvedSession` by inspecting the SMB sessions share. Ephys and spikes
are OPTIONAL: a session with no recording folder resolves cleanly as
events-only (no exception).

Filesystem access here is strictly read-only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULTS, SESSIONS_ROOT, SessionConfig

log = logging.getLogger(__name__)

# key like "m74s4" -> subject "m74", session number "4" (non-greedy subject so
# the final s<n> token is the session, even when the subject itself contains s).
_KEY_RE = re.compile(r"^(?P<subject>.+?)s(?P<n>\d+)$")


@dataclass
class ResolvedSession:
    # carried from config
    key: str
    es_subject: str
    es_session: int | None
    es_host: str
    es_index: str
    run_id: int | None

    # effective acquisition settings
    trigger_channel: int
    ttl_channel: int
    sampling_rate: int

    # derived paths (None when absent)
    ephys_folder: Path | None
    recording_path: Path | None
    record_node: str | None
    spike_path: Path | None
    spike_kind: str | None  # "pickle" | "xls" | None

    @property
    def has_ephys(self) -> bool:
        return self.recording_path is not None

    @property
    def has_spikes(self) -> bool:
        return self.spike_path is not None

    def summary(self) -> str:
        es_host = self.es_host.split("//")[-1]
        ephys = f"✓ {self.record_node}" if self.has_ephys else "—"
        spikes = self.spike_kind or "—"
        return (
            f"{self.key}: ES {es_host}/{self.es_index} {self.es_subject} "
            f"s{self.es_session} | ephys {ephys} | spikes {spikes}"
        )


def _parse_key(key: str) -> tuple[str | None, int | None]:
    m = _KEY_RE.match(key)
    if not m:
        return None, None
    return m.group("subject"), int(m.group("n"))


def _find_ephys_folder(root: Path, subject: str | None, n: int | None) -> Path | None:
    if subject is None or n is None:
        return None
    matches = sorted(root.glob(f"{subject}s{n}_*"))
    if not matches:
        return None
    if len(matches) > 1:
        log.warning("Multiple ephys folders for %ss%s; using newest: %s", subject, n, matches[-1].name)
    return matches[-1]


def _find_recording(folder: Path) -> tuple[Path | None, str | None]:
    for rec in sorted(folder.glob("Record Node */experiment1/recording1")):
        # record_node is the "Record Node NNN" directory name
        record_node = rec.parents[1].name
        return rec, record_node
    return None, None


def _find_spikes(root: Path, folder: Path | None, subject: str | None, n: int | None) -> tuple[Path | None, str | None]:
    if subject is not None and n is not None:
        pkl = root / f"spikes_{subject}s{n}.pkl"
        if pkl.exists():
            return pkl, "pickle"
    if folder is not None:
        xls = folder / "processed.xls"
        if xls.exists():
            return xls, "xls"
    return None, None


def resolve_one(cfg: SessionConfig, root: str | Path = SESSIONS_ROOT) -> ResolvedSession:
    root = Path(root)
    subject, n = _parse_key(cfg.key)

    # ephys folder: override wins, else convention glob
    folder = Path(cfg.ephys_folder) if cfg.ephys_folder else _find_ephys_folder(root, subject, n)
    if folder is not None and not folder.exists():
        log.warning("ephys_folder override does not exist: %s", folder)
        folder = None

    recording_path, record_node = (None, None)
    if folder is not None:
        recording_path, record_node = _find_recording(folder)
    if cfg.record_node:  # explicit override
        record_node = cfg.record_node

    # spikes: override wins, else convention (pickle preferred, inline xls fallback)
    if cfg.spike_path:
        sp = Path(cfg.spike_path)
        spike_path, spike_kind = (sp, "pickle" if sp.suffix == ".pkl" else "xls") if sp.exists() else (None, None)
    else:
        spike_path, spike_kind = _find_spikes(root, folder, subject, n)

    return ResolvedSession(
        key=cfg.key,
        es_subject=cfg.es_subject,
        es_session=cfg.es_session,
        es_host=cfg.es_host,
        es_index=cfg.es_index,
        run_id=cfg.run_id,
        trigger_channel=cfg.trigger_channel if cfg.trigger_channel is not None else DEFAULTS["trigger_channel"],
        ttl_channel=cfg.ttl_channel if cfg.ttl_channel is not None else DEFAULTS["ttl_channel"],
        sampling_rate=cfg.sampling_rate if cfg.sampling_rate is not None else DEFAULTS["sampling_rate"],
        ephys_folder=folder,
        recording_path=recording_path,
        record_node=record_node,
        spike_path=spike_path,
        spike_kind=spike_kind,
    )


def load_sessions(configs: list[SessionConfig], root: str | Path = SESSIONS_ROOT) -> list[ResolvedSession]:
    return [resolve_one(c, root) for c in configs]
