import requests
import logging
from typing import List, Dict, Any, Optional
import math


class MicsApiClient:
    """
    Thin wrapper around the MICS backend REST API.
    Handles authentication, protocol operations, subjects, etc.
    """

    def __init__(self, base_url: str, token: str, logger: Optional[logging.Logger] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        self.logger = logger or logging.getLogger("MicsApiClient")

    # -----------------------
    # Generic request helpers
    # -----------------------

    def _get(self, path: str):
        url = f"{self.base_url}{path}"
        self.logger.debug(f"GET {url}")
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict):
        url = f"{self.base_url}{path}"
        self.logger.debug(f"POST {url} -> {payload}")
        resp = requests.post(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, payload: dict):
        url = f"{self.base_url}{path}"
        self.logger.debug(f"PATCH {url} -> {payload}")
        resp = requests.patch(url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str):
        url = f"{self.base_url}{path}"
        self.logger.debug(f"DELETE {url}")
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    # -----------------------
    # Protocol Endpoints
    # -----------------------

    def list_protocols(self) -> List[Dict[str, Any]]:
        return self._get("/protocols")

    def get_protocol(self, protocol_id: int):
        return self._get(f"/protocols/{protocol_id}")

    def create_protocol(self, name: str, description: str, steps: List[Dict[str, Any]]):
        payload = {
            "name": name,
            "description": description,
            "steps": steps,
        }
        return self._post("/protocols", payload)

    # -----------------------
    # Subjects Endpoints
    # -----------------------

    def get_subject(self, subject_id: int):
        return self._get(f"/subjects/{subject_id}")
    
    def list_subjects(self):
        return self._get("/subjects")

    def create_subject(self, name: str):
        payload = {"name": name}
        return self._post("/subjects", payload)

    # -----------------------
    # Assignment Endpoints
    # -----------------------

    def assign_protocol(self, subject_name: str, protocol_id: int):
        """
        Set a subject's next_protocol_id.
        Does NOT start a session.
        """
        payload = {"protocol_id": protocol_id}
        return self._post(f"/subjects/{subject_name}/assign_protocol", payload)
    # -----------------------
    # Session Endpoints
    # -----------------------

        # -----------------------
    # Session Endpoints
    # -----------------------

    def start_session(self) -> Dict[str, Any]:
        """
        Ask backend to create a new session for all subjects that currently
        have next_protocol_id set.
        """
        return self._post("/sessions/start", payload={})
    
        # -----------------------
    # Blueprint / Session Helpers
    # -----------------------

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List existing sessions (blueprints), grouped by session_id.
        """
        return self._get("/sessions")

    def get_session_detail(self, session_id: int) -> Dict[str, Any]:
        """
        Get subjects/protocols for a given session_id.
        """
        return self._get(f"/sessions/{session_id}")

    def launch_session(self, session_id: int) -> Dict[str, Any]:
        """
        Launch a new session cloned from an existing session_id.
        """
        return self._post(f"/sessions/{session_id}/launch", payload={})
    
    def get_session(self, session_id: int) -> Dict[str, Any]:
        """
        Alias for GET /sessions/{id} – returns the blueprint session detail.
        """
        return self.get_session_detail(session_id)

    def get_subject_runs_for_session(self, session_id: int) -> List[Dict[str, Any]]:
        """
        Convenience: return the list of SubjectProtocolRun-like dicts
        for this blueprint session.
        """
        detail = self.get_session_detail(session_id)
        return detail.get("runs", [])

    
        # -----------------------
    # Pilots Endpoints
    # -----------------------




    # -----------------------
    # Pilots Endpoints
    # -----------------------

        # -----------------------
    # Pilots Endpoints
    # -----------------------

    def list_pilots(self) -> List[Dict[str, Any]]:
        """
        GET /pilots
        """
        return self._get("/pilots")

    def create_or_update_pilot(
        self,
        name: str,
        ip: Optional[str] = None,
        prefs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        POST /pilots

        Backend implementation:
        - If a pilot with this name exists, it updates ip/prefs.
        - Otherwise it creates a new pilot row.
        """
        payload: Dict[str, Any] = {"name": name}
        if ip is not None:
            payload["ip"] = ip
        if prefs is not None:
            payload["prefs"] = self._sanitize_for_json(prefs)
        return self._post("/pilots", payload)

    def get_pilot(self, pilot_id: int) -> Dict[str, Any]:
        """
        GET /pilots/{id}
        """
        return self._get(f"/pilots/{pilot_id}")

    def upsert_pilot_tasks(self, pilot_id: int, tasks: list[dict]):
        """
        POST /pilots/{pilot_id}/tasks

        Sends task capability descriptors reported by the pilot.
        """
        payload = {"tasks": tasks}
        return self._post(f"/pilots/{pilot_id}/tasks", payload)



        # -----------------------
    # SessionRun Endpoints
    # -----------------------

    def create_session_run(self, session_id: int, pilot_id: int) -> Dict[str, Any]:
        payload = {"session_id": session_id, "pilot_id": pilot_id}
        return self._post("/session-runs", payload)

    def get_active_run(self, session_id: int) -> Optional[Dict[str, Any]]:
        # FastAPI can return null JSON => Python None
        return self._get(f"/sessions/{session_id}/active-run")

    def stop_session_run(self, run_id: int) -> Dict[str, Any]:
        return self._post(f"/session-runs/{run_id}/stop", payload={})


    


    def _sanitize_for_json(self, obj):
        """
        Recursively walk obj and replace NaN / +/-inf floats with None,
        because strict JSON (and FastAPI) do not accept them.
        """
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj

        if isinstance(obj, dict):
            return {k: self._sanitize_for_json(v) for k, v in obj.items()}

        if isinstance(obj, list):
            return [self._sanitize_for_json(v) for v in obj]

        # tuples, sets, etc. – convert to list
        if isinstance(obj, (tuple, set)):
            return [self._sanitize_for_json(v) for v in obj]

        # everything else (str, int, bool, None, etc.)
        return obj
    def get_run_by_subject_key(self, subject_key: str):
        return self._get(f"/session-runs/by-subject-key/{subject_key}")
    
    # -----------------------
    # Progress / Steps Endpoints
    # -----------------------

    def increment_trial(self, run_id: int):
        """
        Trigger backend trial increment.
        Backend handles trial number + graduation logic.
        """
        return self._post(f"/runs/{run_id}/progress/increment", payload={})

    def advance_step(self, run_id: int):
        """
        Backend advances to next step, resets trial counter, loads graduation rules.
        """
        return self._post(f"/runs/{run_id}/progress/advance_step", payload={})

    def get_run(self, run_id: int):
        """
        Fetch a single SessionRun row.
        """
        return self._get(f"/session-runs/{run_id}")
    def mark_run_running(self, run_id: int) -> Dict[str, Any]:
        """
        Mark a SessionRun as RUNNING.
        This is called by the orchestrator AFTER sending START to the Pi.
        """
        return self._post(f"/session-runs/{run_id}/mark-running", payload={})
        
    def complete_session_run(self, run_id: int):
        return self._post(f"/session-runs/{run_id}/complete", {})

    def mark_run_error(self, run_id: int, error_type: str, error_message: str):
        url = f"{self.base_url}/session-runs/{run_id}/error"
        resp = requests.post(url, headers=self.headers, params={
            "error_type": error_type,
            "error_message": error_message,
        })
        resp.raise_for_status()
        return resp.json()

    def get_run_with_progress(self, run_id: int):
        return self._get(f"/session-runs/{run_id}/with-progress")

















