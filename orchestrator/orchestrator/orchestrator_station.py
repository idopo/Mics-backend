import time
import threading
import queue
import copy
import logging
from typing import Dict, Any

from .mics.mics_api_client import MicsApiClient
from .data_handlers.ElasticSearchDateHandler import ElasticSearchDataHandler
from .networking.message import Message
from .state import OrchestratorState

logger = logging.getLogger("orchestrator.station")


class OrchestratorStation:
    """
    Runtime execution engine.
    - Receives messages from RouterGateway
    - Talks to backend via MicsApiClient
    - Owns ES handlers
    """

    def __init__(self, config, gateway, state: OrchestratorState):
        self.config = config
        self.gateway = gateway
        self.state = state

        self.api = MicsApiClient(
            config.require("MICS_API_URL"),
            config.require("MICS_API_TOKEN"),
            logger=logger,
        )

        # ES handlers per subject_key
        self.subjects_data_handlers: Dict[str, ElasticSearchDataHandler] = {}

        # Queues
        self.data_queue = queue.Queue(maxsize=50_000)
        self.trial_queue = queue.Queue(maxsize=50_000)

        for _ in range(4):
            threading.Thread(target=self._data_worker, daemon=True).start()

        threading.Thread(target=self._trial_worker, daemon=True).start()

    # =====================================================
    # ZMQ HANDLERS (called by RouterGateway)
    # =====================================================

    def on_handshake(self, msg: Message):
        payload = msg.value or {}
        pilot = payload.get("pilot") or msg.sender

        if not pilot:
            logger.warning("HANDSHAKE missing pilot: %r", payload)
            return

        self.state.update_handshake(pilot, payload)
        logger.info("HANDSHAKE from %s", pilot)

        try:
            self.api.create_or_update_pilot(
                name=pilot,
                ip=payload.get("ip"),
                prefs=payload.get("prefs", {}) or {},
            )
        except Exception as e:
            logger.error("Backend sync failed for pilot %s: %s", pilot, e)

    def on_state(self, msg: Message):
        self.state.set_state(msg.sender, msg.value)
        logger.debug("STATE %s -> %s", msg.sender, msg.value)

    def on_ping(self, msg: Message):
        self.state.update_ping(msg.sender)

    def on_data(self, msg: Message):
        try:
            self.data_queue.put_nowait(copy.deepcopy(msg.value))
        except queue.Full:
            logger.warning("DATA queue full, dropping message")

    def on_inc_trial(self, msg: Message):
        try:
            self.trial_queue.put_nowait(msg.value)
        except queue.Full:
            logger.warning("TRIAL queue full, dropping event")

    # =====================================================
    # HTTP CONTROL (called by FastAPI)
    # =====================================================

    def start_run(self, run_id: int):
        run = self.api.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        if run.get("status") != "pending":
            raise ValueError(f"Run {run_id} is not pending")

        pilot = self.api.get_pilot(run["pilot_id"])
        pilot_name = pilot["name"]

        if not self.state.is_connected(pilot_name):
            raise ValueError(f"Pilot {pilot_name} is not connected")

        task = self._build_first_step_task(run)

        logger.info("Starting run %s on pilot %s", run_id, pilot_name)
        self.gateway.send(pilot_name, "START", task)

    def stop_run(self, run_id: int):
        run = self.api.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        pilot = self.api.get_pilot(run["pilot_id"])
        pilot_name = pilot["name"]

        logger.info("Stopping run %s on pilot %s", run_id, pilot_name)
        self.gateway.send(pilot_name, "STOP")
        self.api.stop_session_run(run_id)

    # =====================================================
    # WORKERS
    # =====================================================

    def _data_worker(self):
        while True:
            value = self.data_queue.get()
            try:
                self._handle_data(value)
            except Exception:
                logger.exception("DATA worker error")
            finally:
                self.data_queue.task_done()

    def _handle_data(self, value: dict):
        subject = value.get("subject")
        if not subject:
            return

        handler = self.subjects_data_handlers.get(subject)
        if not handler:
            handler = ElasticSearchDataHandler()
            handler.prepare_run()
            self.subjects_data_handlers[subject] = handler

        handler.save(value)

    def _trial_worker(self):
        while True:
            value = self.trial_queue.get()
            try:
                self._handle_inc_trial(value)
            except Exception:
                logger.exception("TRIAL worker error")
            finally:
                self.trial_queue.task_done()

    def _handle_inc_trial(self, value: dict):
        subject_key = value.get("subject")
        if not subject_key:
            return

        run = self.api.get_run_by_subject_key(subject_key)
        if not run or run.get("status") != "running":
            return

        resp = self.api.increment_trial(run["id"])
        if resp.get("should_graduate"):
            self._advance_run_step(run)

    # =====================================================
    # INTERNAL FLOW
    # =====================================================

    def _advance_run_step(self, run: dict):
        pilot = self.api.get_pilot(run["pilot_id"])
        pilot_name = pilot["name"]

        self.gateway.send(pilot_name, "STOP")
        self._wait_for_idle(pilot_name)

        resp = self.api.advance_step(run["id"])
        if resp.get("finished"):
            self.api.stop_session_run(run["id"])

    def _wait_for_idle(self, pilot: str, timeout: float = 15.0):
        start = time.time()
        while time.time() - start < timeout:
            snap = self.state.get_pilot(pilot) or {}
            if snap.get("state") == "IDLE":
                return
            time.sleep(0.1)

    # =====================================================
    # TASK BUILDERS
    # =====================================================

    def _build_first_step_task(self, run: dict) -> dict:
        """
        Build initial START payload for Pi.
        """
        session_id = run["session_id"]
        subject_key = run["subject_key"]

        session = self.api.get_session_detail(session_id)
        runs = self.api.get_subject_runs_for_session(session_id)

        proto_run = runs[0]
        protocol = self.api.get_protocol(proto_run["protocol_id"])
        step = protocol["steps"][0]

        task = dict(step.get("params") or {})
        task["task_type"] = step["task_type"]
        task["step_name"] = step["step_name"]
        task["subject"] = subject_key
        task["step"] = 0
        task["current_trial"] = 0
        task["session"] = session_id

        return task
