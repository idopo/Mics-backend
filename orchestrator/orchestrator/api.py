from fastapi import FastAPI, HTTPException
from orchestrator.state import OrchestratorState
from orchestrator.orchestrator_station import OrchestratorStation
from datetime import datetime, timezone
import json
PILOT_TIMEOUT_SEC = 15

def create_api(state: OrchestratorState, station: OrchestratorStation):
    app = FastAPI(title="Orchestrator API")

    # -------------------------
    # Pilot visibility
    # -------------------------
    # @app.get("/pilots/live")
    # def list_live_pilots():
    #     """
    #     Live connectivity view (from orchestrator state, NOT DB)
    #     """
    #     return state.snapshot()




    @app.get("/pilots/live")
    def list_live_pilots():
        out = {}
        now = datetime.now(timezone.utc)

        for key in station.redis.scan_iter("pilot:*"):
            pilot_key = key.split("pilot:", 1)[1]
            data = station.redis.hgetall(key)

            updated_at = data.get("updated_at")
            connected = False

            if updated_at:
                try:
                    ts = datetime.fromisoformat(updated_at)
                    connected = (now - ts).total_seconds() < PILOT_TIMEOUT_SEC
                except Exception:
                    connected = False

            active_run = data.get("active_run")
            if active_run:
                try:
                    active_run = json.loads(active_run)
                except Exception:
                    active_run = None

            out[pilot_key] = {
                "connected": connected,
                "state": data.get("state", "UNKNOWN"),
                "active_run": active_run,
                "updated_at": updated_at,
            }

        return out


    # -------------------------
    # Run control
    # -------------------------
    @app.post("/runs/{run_id}/start")
    def start_run(run_id: int):
        """
        Start a backend-created run on its assigned pilot.
        """
        try:
            station.start_run(run_id)
            return {"ok": True, "run_id": run_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/runs/{run_id}/stop")
    def stop_run(run_id: int):
        """
        Stop a running run.
        """
        try:
            station.stop_run(run_id)
            return {"ok": True, "run_id": run_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            # 🔑 STOP is best-effort at orchestrator level
            # Backend is authoritative
            raise HTTPException(
                status_code=500,
                detail=f"Run {run_id} stop partially failed: {e}",
            )

    return app
