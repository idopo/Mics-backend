import time
import threading
import queue
import copy
import logging
from typing import Dict, Any
import json
from datetime import datetime, timezone
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

    def __init__(
        self,
        config,
        gateway,
        state: OrchestratorState,
        es_client,
        redis_client=None
    ):
        self.config = config
        self.gateway = gateway
        self.state = state
        self.es_client = es_client
        self.redis = redis_client

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
        threading.Thread(target=self._ping_loop, daemon=True).start()
        for _ in range(4):
            threading.Thread(target=self._data_worker, daemon=True).start()

        threading.Thread(target=self._trial_worker, daemon=True).start()
        # threading.Thread(target=self._run_watchdog, daemon=True).start()

    def _ping_loop(self):
        while True:
            try:
                snapshot = self.state.snapshot()
                for pilot, info in snapshot.items():
                    self.gateway.send(pilot, "PING")
            except Exception:
                logger.exception("Ping loop error")

            time.sleep(10)

    def on_handshake(self, msg: Message):
        payload = msg.value or {}
        pilot = payload.get("pilot") or msg.sender
        tasks = payload.get("tasks")
        self._redis_touch(pilot)


        self.state.update_handshake(pilot, payload)
        logger.info("HANDSHAKE from %s", pilot)

        try:
            pilot_obj = self.api.create_or_update_pilot(
                name=pilot,
                ip=payload.get("ip"),
                prefs=payload.get("prefs", {}) or {},
            )

            
            if tasks:
                self.api.upsert_pilot_tasks(
                    pilot_id=pilot_obj["id"],
                    tasks=tasks,
                )


        except Exception as e:
            logger.error("Backend sync failed for pilot %s: %s", pilot, e)

        

    def _redis_set_active_run(self, pilot_key: str, run: dict | None):
        """
        Mirror active run state to Redis (write-only).
        - Key: pilot:{pilot_key}
        - Fields:
            - active_run -> JSON string (if running)
            - state -> "RUNNING" / "IDLE"
            - updated_at -> isotimestamp
        """
        if not self.redis:
            # Redis not configured — nothing to do
            return

        key = f"pilot:{pilot_key}"
        now = datetime.now(timezone.utc).isoformat()

        try:
            if run is None:
                # remove active_run field and mark idle
                try:
                    # HDEL returns number of fields deleted; ignore result
                    self.redis.hdel(key, "active_run")
                except Exception:
                    # ignore deletion errors, continue to set state
                    logger.debug("Redis HDEL failed for %s", key, exc_info=True)

                # set state and timestamp
                self.redis.hset(
                    key,
                    mapping={
                        "state": "IDLE",
                        "updated_at": now,
                    },
                )
                logger.debug("Redis: set %s -> IDLE", key)
            else:
                # store active_run as JSON and set RUNNING
                self.redis.hset(
                    key,
                    mapping={
                        "active_run": json.dumps(run, default=str),
                        "state": "RUNNING",
                        "updated_at": now,
                    },
                )
                logger.debug("Redis: set %s -> RUNNING (run_id=%s)", key, run.get("id"))
        except Exception:
            logger.exception("Failed writing active_run to Redis for %s", pilot_key)


    def on_state(self, msg: Message):
        self._redis_touch(msg.sender)
        # DO NOT clear active_run here


    def on_ping(self, msg: Message):
        self._redis_touch(msg.sender)

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
        logger.info("Starting run %s", run_id)

        # 1️⃣ Load execution run
        run_meta = self.api.get_run(run_id)
        if not run_meta:
            raise ValueError(f"Run {run_id} not found")

        # 2️⃣ Load backend pilot
        pilot = self.api.get_pilot(run_meta["pilot_id"])
        if not pilot:
            raise RuntimeError(f"Pilot {run_meta['pilot_id']} not found")

        # 🔑 Resolve the orchestrator/ZMQ pilot key
        pilot_key = self.state.resolve_pilot_key(
            db_name=pilot.get("name"),
            ip=pilot.get("ip"),
        )
        logger.info("Resolved pilot key: %s", pilot_key)

        # 3️⃣ Resolve protocol context
        proto_runs = self.api.get_subject_runs_for_session(run_meta["session_id"])
        if not proto_runs:
            raise RuntimeError(f"Session {run_meta['session_id']} has no SubjectProtocolRun")
        protocol_id = proto_runs[0]["protocol_id"]

        # 4️⃣ Load run WITH progress so we can resume if needed
        try:
            run_with_prog = self.api.get_run_with_progress(run_id)
            prog = (run_with_prog or {}).get("progress") or {}
        except Exception:
            logger.exception(
                "Failed to fetch run progress for run %s; falling back to step 0",
                run_id,
            )
            prog = {}

        # 5️⃣ Build the task according to existing progress (resume) or fresh start
        if prog and prog.get("current_step") is not None:
            step_idx = prog["current_step"]
            task = self._build_step_task({**run_meta, "protocol_id": protocol_id}, step_idx=step_idx)
            task["current_trial"] = prog.get("current_trial", 0)
            logger.info(
                "Resuming run %s at step %s trial %s",
                run_id,
                task.get("step"),
                task.get("current_trial"),
            )
        else:
            task = self._build_first_step_task({**run_meta, "protocol_id": protocol_id})
            task["current_trial"] = 0
            logger.info("Starting run %s from step 0", run_id)

        # ✅ Make sure run_id exists in payload (Pi expects it)
        task["run_id"] = run_meta["id"]

        # include pilot + subject keys in payload
        task["pilot"] = pilot.get("name")
        task["subject"] = run_meta.get("subject_key")

        # minimal additions (do not change existing behavior)
        self._attach_session_context(
            task,
            run_meta=run_meta,
            proto_runs=proto_runs,
            progress=prog,
        )
        task["subjects"] = task.get("subjects") or []
        task["session_progress_index"] = task.get("session_progress_index")

        # 6️⃣ Send START to Pi
        try:
            self.gateway.send(pilot_key, "START", task)
            logger.info("START sent to pilot %s for run %s", pilot_key, run_id)
        except Exception as e:
            logger.exception("Failed to send START to pilot %s for run %s: %s", pilot_key, run_id, e)
            try:
                self.api.mark_run_error(run_id, error_type="OrchGatewayError", error_message=str(e))
            except Exception:
                logger.exception("Failed to mark run error in backend after gateway failure for run %s", run_id)

            self.state.set_active_run(pilot_key, None)
            self._redis_set_active_run(pilot_key, None)
            raise

        # 7️⃣ Now mark backend RUNNING
        try:
            self.api.mark_run_running(run_id)
            logger.info("Marked run %s RUNNING in backend", run_id)
        except Exception:
            logger.exception("Failed to mark run %s as RUNNING in backend after sending START", run_id)

        # 8️⃣ Update local state & mirror to Redis
        active_run = {
            "id": run_meta["id"],
            "session_id": run_meta["session_id"],
            "subject_key": run_meta["subject_key"],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        self.state.set_active_run(pilot_key, active_run)

        try:
            self._redis_set_active_run(pilot_key, active_run)
        except Exception:
            logger.exception("Failed updating redis active_run for pilot %s run %s", pilot_key, run_id)

        logger.info("Active run set for %s (run_id=%s)", pilot_key, run_meta["id"])



    def stop_run(self, run_id: int):
        run = self.api.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        pilot = self.api.get_pilot(run["pilot_id"])
        if not pilot:
            raise RuntimeError(f"Pilot {run['pilot_id']} not found")

        pilot_key = self.state.resolve_pilot_key(
            db_name=pilot.get("name"),
            ip=pilot.get("ip"),
        )

        logger.info("Stopping run %s on pilot %s", run_id, pilot_key)

        # 1) Tell Pi to STOP
        try:
            self.gateway.send(pilot_key, "STOP")
            logger.info("STOP sent to pilot %s for run %s", pilot_key, run_id)
        except Exception as e:
            logger.exception("Failed to send STOP to pilot %s for run %s: %s", pilot_key, run_id, e)
            # Best-effort mark error in backend
            try:
                self.api.mark_run_error(run_id, error_type="OrchGatewayError", error_message=str(e))
            except Exception:
                logger.exception("Failed to mark run error in backend after STOP gateway failure for run %s", run_id)
            # Clear local state to avoid dangling UI
            self.state.set_active_run(pilot_key, None)
            self._redis_set_active_run(pilot_key, None)
            raise

        # 2) Mark backend STOPPED (orchestrator wrote DB authoritative)
        try:
            self.api.stop_session_run(run_id)
            logger.info("Marked run %s STOPPED in backend", run_id)
        except Exception:
            logger.exception("Failed to mark run %s STOPPED in backend after sending STOP", run_id)
            # No retries per request — log and continue

        # 3) Clear orchestrator state + Redis mirror
        self.state.set_active_run(pilot_key, None)
        try:
            self._redis_set_active_run(pilot_key, None)
        except Exception:
            logger.exception("Failed to clear redis active_run for pilot %s run %s", pilot_key, run_id)

        logger.info("Active run cleared for %s (run_id=%s)", pilot_key, run_id)





    def on_task_error(self, msg: Message):
        payload = msg.value or {}
        pilot_key = payload.get("pilot") or msg.sender
        subject_key = payload.get("subject")

        logger.error(
            "TASK_ERROR from pilot=%s subject=%s error=%s",
            pilot_key,
            subject_key,
            payload.get("error_message"),
        )

        # 🔑 HARD STOP THE PILOT
        self.gateway.send(pilot_key, "STOP")

        run = None
        if subject_key:
            try:
                run = self.api.get_run_by_subject_key(subject_key)
            except Exception:
                logger.exception("Failed to resolve run for crashed task")

        if not run:
            self.state.set_active_run(pilot_key, None)
            return

        self.api.mark_run_error(
            run["id"],
            error_type="TaskError",
            error_message=payload.get("error_message", ""),
        )

        self.state.set_active_run(pilot_key, None)
        self._redis_set_active_run(pilot_key, None)

    def _apply_overrides(self, task: dict, run_meta: dict, step_idx: int) -> dict:
        ov = run_meta.get("overrides") or {}
        global_ov = ov.get("global") or {}
        steps_ov = ov.get("steps") or {}

        step_ov = steps_ov.get(str(step_idx)) or steps_ov.get(step_idx) or {}

        task.update(global_ov)
        task.update(step_ov)
        return task




    def _resolve_pilot_key(self, pilot_ip: str) -> str:
        """
        Find the orchestrator/ZMQ pilot key (e.g. 'pilot_raspberry_lior')
        corresponding to a backend Pilot (matched by IP).
        """
        for key, info in self.state._pilots.items():
            if info.get("ip") == pilot_ip:
                return key
        raise RuntimeError(f"No orchestrator pilot found with ip={pilot_ip}")

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
            handler = ElasticSearchDataHandler(client=self.es_client)
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

        # ✅ keep gateway routing consistent with start_run()
        pilot_key = self.state.resolve_pilot_key(
            db_name=pilot.get("name"),
            ip=pilot.get("ip"),
        )

        logger.info(
            "Advancing run %s (pilot=%s)",
            run["id"],
            pilot_name,
        )

        # 1️⃣ Stop current task
        self.gateway.send(pilot_key, "STOP")
        self._wait_for_idle(pilot_key)

        # 2️⃣ Advance step in backend FIRST
        resp = self.api.advance_step(run["id"])

        if resp.get("finished"):
            logger.info("Run %s completed", run["id"])
            self.api.complete_session_run(run["id"])
            self.state.set_active_run(pilot_key, None)
            self._redis_set_active_run(pilot_key, None)
            return

        logger.info(
            "Waiting for hardware release (10s) before next step on pilot %s",
            pilot_name,
        )
        time.sleep(10)

        # 3️⃣ Start next step
        next_step_idx = resp["current_step"]
        next_task = self._build_step_task(run, step_idx=next_step_idx)

        # ✅ attach minimal context for Pi (subjects + session_progress_index)
        try:
            run_with_prog = self.api.get_run_with_progress(run["id"])
            prog = (run_with_prog or {}).get("progress") or {}
        except Exception:
            logger.exception(
                "Failed to fetch run progress for run %s in advance; continuing without progress",
                run["id"],
            )
            prog = {}

        try:
            proto_runs = self.api.get_subject_runs_for_session(run["session_id"])
        except Exception:
            logger.exception(
                "Failed to fetch proto_runs for session %s in advance; continuing without subjects",
                run["session_id"],
            )
            proto_runs = None

        self._attach_session_context(
            next_task,
            run_meta=run,
            proto_runs=proto_runs,
            progress=prog,
        )

        next_task["subjects"] = next_task.get("subjects") or []
        next_task["session_progress_index"] = next_task.get("session_progress_index")

        logger.info(
            "Starting step %s for run %s on pilot %s",
            next_step_idx,
            run["id"],
            pilot_name,
        )

        self.gateway.send(pilot_key, "START", next_task)



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
        session_id = run["session_id"]
        subject_key = run["subject_key"]

        runs = self.api.get_subject_runs_for_session(session_id)
        proto_run = runs[0]

        protocol = self.api.get_protocol(proto_run["protocol_id"])
        step_idx = 0  # ✅ ADD THIS
        step = protocol["steps"][step_idx]

        task = dict(step.get("params") or {})
        task["task_type"] = step["task_type"]
        task["step_name"] = step["step_name"]

        pilot = self.api.get_pilot(run["pilot_id"])
        task["pilot"] = pilot["name"]

        task["subject"] = subject_key
        task["step"] = step_idx
        task["current_trial"] = 0
        task["session"] = session_id

        task["run_id"] = run["id"]                 # ✅ ADD THIS (required)
        task["protocol_id"] = proto_run["protocol_id"]  # ✅ optional but useful

        # Apply overrides last
        task = self._apply_overrides(task, run_meta=run, step_idx=step_idx)

        # ✅ recommended: re-assert reserved keys so overrides can't break routing/meta
        task["task_type"] = step["task_type"]
        task["step_name"] = step["step_name"]
        task["pilot"] = pilot["name"]
        task["subject"] = subject_key
        task["session"] = session_id
        task["step"] = step_idx
        task["run_id"] = run["id"]
        task["protocol_id"] = proto_run["protocol_id"]

        return task


    def _build_step_task(self, run: dict, step_idx: int) -> dict:
        session_id = run["session_id"]
        subject_key = run["subject_key"]

        runs = self.api.get_subject_runs_for_session(session_id)
        proto_run = runs[0]

        protocol = self.api.get_protocol(proto_run["protocol_id"])
        step = protocol["steps"][step_idx]

        task = dict(step.get("params") or {})
        task["task_type"] = step["task_type"]
        task["step_name"] = step["step_name"]

        pilot = self.api.get_pilot(run["pilot_id"])
        task["pilot"] = pilot["name"]

        task["subject"] = subject_key
        task["step"] = step_idx
        task["current_trial"] = 0
        task["session"] = session_id

        task["run_id"] = run["id"]                 # ✅ ADD THIS
        task["protocol_id"] = proto_run["protocol_id"]  # ✅ optional

        task = self._apply_overrides(task, run_meta=run, step_idx=step_idx)

        # ✅ recommended protection
        task["task_type"] = step["task_type"]
        task["step_name"] = step["step_name"]
        task["pilot"] = pilot["name"]
        task["subject"] = subject_key
        task["session"] = session_id
        task["step"] = step_idx
        task["run_id"] = run["id"]
        task["protocol_id"] = proto_run["protocol_id"]

        return task


    def _run_watchdog(self):
        logger.info("Run watchdog started")

        while True:
            try:
                snapshot = self.state.snapshot()

                for pilot, info in snapshot.items():
                    run = info.get("active_run")
                    if not run:
                        continue

                    if run.get("status") != "running":
                        continue

                    started_at = run.get("started_at")
                    if not started_at:
                        continue

                    # 🔑 Normalize started_at
                    if isinstance(started_at, str):
                        try:
                            started_at = datetime.fromisoformat(started_at)
                        except Exception:
                            logger.warning(
                                "Watchdog: invalid started_at for run %s: %r",
                                run.get("id"),
                                started_at,
                            )
                            continue

                    elapsed = (datetime.utcnow() - started_at).total_seconds()

                    if elapsed > 30:
                        logger.error(
                            "Watchdog: run %s stuck RUNNING for %.1fs (pilot=%s)",
                            run["id"],
                            elapsed,
                            pilot,
                        )

                        try:
                            self.api.mark_run_error(
                                run["id"],
                                error_type="WatchdogTimeout",
                                error_message=f"Run stuck RUNNING for {elapsed:.1f}s",
                            )
                        except Exception:
                            logger.exception("Watchdog: failed marking run ERROR")

                        self.state.set_active_run(pilot, None)

            except Exception:
                logger.exception("Watchdog loop error")

            time.sleep(5)

    def _redis_touch(self, pilot_key: str):
        if not self.redis:
            return
        try:
            self.redis.hset(
                f"pilot:{pilot_key}",
                mapping={
                    "updated_at": datetime.now(timezone.utc).isoformat()
                },
            )
        except Exception:
            logger.exception("Redis touch failed for %s", pilot_key)

    def _attach_session_context(
        self,
        task: dict,
        *,
        run_meta: dict,
        proto_runs: list | None,
        progress: dict | None,) -> dict:
        """
        Minimal payload additions for Pi:
        - session_progress_index: int | None
        - subjects: [str, ...]
        Always produces:
        task["session_progress_index"] exists (maybe None)
        task["subjects"] exists (list)
        """

        # -----------------------------
        # 1) Normalize progress input
        # -----------------------------
        prog = None
        if progress is None:
            prog = {}
        elif isinstance(progress, dict):
            # if caller accidentally passed the full {"run":..., "progress":...} payload
            if "progress" in progress and isinstance(progress.get("progress"), dict):
                prog = progress["progress"]
            else:
                prog = progress
        else:
            # tolerate objects with attributes
            try:
                prog = {
                    "session_progress_index": getattr(progress, "session_progress_index", None),
                    "current_step": getattr(progress, "current_step", None),
                    "current_trial": getattr(progress, "current_trial", None),
                }
            except Exception:
                prog = {}

        # -----------------------------
        # 2) session_progress_index
        # -----------------------------
        spi = None
        if isinstance(prog, dict):
            # tolerant to different backend field names / migrations
            spi = (
                prog.get("session_progress_index")
                or prog.get("session_run_index")
                or prog.get("run_index")
                or prog.get("index")
            )

        # Force presence (like run_id)
        task["session_progress_index"] = spi

        # -----------------------------
        # 3) subjects list
        # -----------------------------
        subjects: list[str] = []

        if proto_runs:
            for r in proto_runs:
                if r is None:
                    continue

                # tolerate dict rows
                if isinstance(r, dict):
                    name = (
                        r.get("subject_name")
                        or r.get("subject_key")
                        or r.get("subject")
                    )

                    # subject might be nested dict {"name": "..."} or {"key": "..."}
                    if isinstance(name, dict):
                        name = name.get("name") or name.get("key") or name.get("subject_key")

                else:
                    # tolerate objects
                    name = (
                        getattr(r, "subject_name", None)
                        or getattr(r, "subject_key", None)
                        or getattr(r, "subject", None)
                    )
                    if isinstance(name, dict):
                        name = name.get("name") or name.get("key") or name.get("subject_key")

                if name:
                    subjects.append(str(name))

        # De-dup while preserving order
        seen = set()
        subjects = [s for s in subjects if not (s in seen or seen.add(s))]

        # Force presence (never None)
        task["subjects"] = subjects

        return task




