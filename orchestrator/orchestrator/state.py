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
            cur = self._pilots.get(pilot, {})

            # 🔑 Preserve active_run across handshake updates
            active_run = cur.get("active_run")

            cur.update(payload)

            if active_run is not None:
                cur["active_run"] = active_run

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
        # TEMP: Pi doesn't send ping/state yet.
        # If we have ever seen a handshake (or any state), treat as connected.
        with self._lock:
            return pilot in self._pilots


    def snapshot(self, timeout: float = 15.0) -> dict:
        now = time.time()
        with self._lock:
            out = {}
            for pilot, data in self._pilots.items():
                ts = self._last_seen.get(pilot)
                age = None if ts is None else now - ts

                out[pilot] = {
                    "connected": age is not None and age < timeout,
                    "last_seen_sec": None if age is None else round(age, 2),
                    "state": data.get("state"),
                    "ip": data.get("ip"),
                    "active_run": data.get("active_run"),
                }
            return out
    def set_active_run(self, pilot: str, run: dict | None):
        with self._lock:
            cur = self._pilots.get(pilot, {})
            cur["active_run"] = run
            self._pilots[pilot] = cur
    def resolve_pilot_key(self, *, db_name: str | None = None, ip: str | None = None) -> str:
        """
        Resolve the ZMQ/orchestrator pilot key (e.g. 'pilot_raspberry_lior')
        from backend pilot info.
        """
        with self._lock:
            # 1) Direct match
            if db_name and db_name in self._pilots:
                return db_name

            # 2) Common prefix form: pilot_<name>
            if db_name:
                pref = f"pilot_{db_name}"
                if pref in self._pilots:
                    return pref

            # 3) Match by IP (most reliable)
            if ip:
                for key, info in self._pilots.items():
                    if info.get("ip") == ip:
                        return key

        raise KeyError(
            f"Pilot not found in orchestrator state (db_name={db_name!r}, ip={ip!r})"
        )

