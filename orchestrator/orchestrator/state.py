# orchestrator/state.py
import time
import threading
from typing import Dict, Any, Optional


class OrchestratorState:
    """
    Thread-safe in-memory state shared between:
      - ZMQ gateway thread(s)
      - worker threads
      - FastAPI request threads
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._pilots: Dict[str, Dict[str, Any]] = {}
        self._last_seen: Dict[str, float] = {}

    def update_handshake(self, pilot: str, payload: dict) -> None:
        now = time.time()
        with self._lock:
            # merge rather than replace, to preserve previous fields
            cur = self._pilots.get(pilot, {})
            cur.update(payload)
            self._pilots[pilot] = cur
            self._last_seen[pilot] = now

    def update_ping(self, pilot: str) -> None:
        with self._lock:
            self._last_seen[pilot] = time.time()

    def set_state(self, pilot: str, state_value: Any) -> None:
        with self._lock:
            cur = self._pilots.get(pilot, {})
            cur["state"] = state_value
            self._pilots[pilot] = cur
            self._last_seen[pilot] = time.time()

    def get_pilot(self, pilot: str) -> Optional[dict]:
        with self._lock:
            p = self._pilots.get(pilot)
            return dict(p) if p else None

    def is_connected(self, pilot: str, timeout: float = 10.0) -> bool:
        now = time.time()
        with self._lock:
            ts = self._last_seen.get(pilot)
            return ts is not None and (now - ts) < timeout

    def snapshot(self, timeout: float = 10.0) -> dict:
        now = time.time()
        with self._lock:
            # include pilots even if only handshake exists but no ping after
            pilots = set(self._pilots.keys()) | set(self._last_seen.keys())
            out = {}
            for pilot in sorted(pilots):
                ts = self._last_seen.get(pilot)
                age = None if ts is None else round(now - ts, 2)
                out[pilot] = {
                    "connected": (ts is not None and (now - ts) < timeout),
                    "last_seen_sec": age,
                    "state": self._pilots.get(pilot, {}).get("state"),
                    "ip": self._pilots.get(pilot, {}).get("ip"),
                }
            return out
