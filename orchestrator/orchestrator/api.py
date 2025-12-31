from fastapi import FastAPI, HTTPException
from orchestrator.state import OrchestratorState
from orchestrator.orchestrator_station import OrchestratorStation


def create_api(state: OrchestratorState, station: OrchestratorStation):
    app = FastAPI(title="Orchestrator API")

    # -------------------------
    # Pilot visibility
    # -------------------------
    @app.get("/pilots/live")
    def list_live_pilots():
        """
        Live connectivity view (from orchestrator state, NOT DB)
        """
        return state.snapshot()

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
            raise HTTPException(status_code=500, detail=str(e))

    return app
