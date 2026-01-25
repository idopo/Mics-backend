# orchestrator/main.py
import time
import logging
import threading
import uvicorn
from elasticsearch import Elasticsearch

from orchestrator.config import Config
from orchestrator.RouterGateway import RouterGateway
from orchestrator.orchestrator_station import OrchestratorStation
from orchestrator.state import OrchestratorState
from orchestrator.api import create_api
import os
import redis


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

# ---- Redis (runtime state store - not used yet) ----
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

try:
    redis_client = redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    redis_client.ping()
    logger.info("Connected to Redis at %s", REDIS_URL)
except Exception as e:
    logger.error("Failed to connect to Redis at %s: %s", REDIS_URL, e)
    raise


# ---- Shared state (single instance) ----
state = OrchestratorState()

# ---- Transport ----
gateway = RouterGateway(
    id=config.require("NAME"),
    listen_port=int(config.require("MSGPORT")),
    listens={},
    log=logger,
)

es_client = Elasticsearch(
    [{"host": "132.77.73.217", "port": 9200, "scheme": "http"}],
    max_retries=1,
    retry_on_timeout=False,
)


# ---- Logic ----
station = OrchestratorStation(config, gateway, state, es_client,redis_client=redis_client)

# ---- Wire message keys ----
gateway.listens.update({
    "HANDSHAKE": station.on_handshake,
    "STATE": station.on_state,
    "PING": station.on_ping,
    "DATA": station.on_data,
    "CONTINUOUS": station.on_data,
    "STREAM": station.on_data,
    "INC_TRIAL_COUNTER": station.on_inc_trial,
    "TASK_ERROR": station.on_task_error,
})

# ---- Start ZMQ ----
gateway.start()

# ---- Start API ----
app = create_api(state, station)

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")

threading.Thread(target=run_api, daemon=True).start()

def heartbeat():
    while True:
        snap = state.snapshot()
        for pilot, info in snap.items():
            # TEMP: handshake-only mode, no staleness warnings
            pass
        time.sleep(5)


threading.Thread(target=heartbeat, daemon=True).start()

logger.info("Orchestrator running")

while True:
    time.sleep(1)
