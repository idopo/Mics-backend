# orchestrator/main.py
import time
import logging
import threading
import uvicorn

from orchestrator.config import Config
from orchestrator.RouterGateway import RouterGateway
from orchestrator.orchestrator_station import OrchestratorStation
from orchestrator.state import OrchestratorState
from orchestrator.api import create_api

CONFIG_PATH = "/orchestrator/orchestrator/prefs.json"

config = Config(CONFIG_PATH)

logging.basicConfig(
    level=getattr(logging, config.get("LOGLEVEL", "INFO")),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("orchestrator.main")

logger.info(
    "Starting orchestrator NAME=%s MSGPORT=%s",
    config.require("NAME"),
    config.require("MSGPORT"),
)

# ---- Shared state (single instance) ----
state = OrchestratorState()

# ---- Transport ----
gateway = RouterGateway(
    id=config.require("NAME"),
    listen_port=int(config.require("MSGPORT")),
    listens={},
    log=logger,
)

# ---- Logic ----
station = OrchestratorStation(config, gateway, state)

# ---- Wire message keys ----
gateway.listens.update({
    "HANDSHAKE": station.on_handshake,
    "STATE": station.on_state,
    "PING": station.on_ping,
    "DATA": station.on_data,
    "CONTINUOUS": station.on_data,
    "STREAM": station.on_data,
    "INC_TRIAL_COUNTER": station.on_inc_trial,
})

# ---- Start ZMQ ----
gateway.start()

# ---- Start API ----
app = create_api(state, station)

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")

threading.Thread(target=run_api, daemon=True).start()

# ---- Liveness watchdog (logs only) ----
def heartbeat():
    while True:
        snap = state.snapshot()
        for pilot, info in snap.items():
            if not info["connected"] and info["last_seen_sec"] is not None and info["last_seen_sec"] > 10:
                logger.warning("Pilot stale: %s age=%.1f", pilot, info["last_seen_sec"])
        time.sleep(5)

threading.Thread(target=heartbeat, daemon=True).start()

logger.info("Orchestrator running")

while True:
    time.sleep(1)
