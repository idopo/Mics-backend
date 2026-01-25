import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from httpx import ConnectError, ReadTimeout
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os
ORCHESTRATOR_URL = "http://host.docker.internal:9000"


app = FastAPI(title="MICS Web UI")



MICS_API_TOKEN = os.environ.get("MICS_API_TOKEN")
if not MICS_API_TOKEN:
    raise RuntimeError("MICS_API_TOKEN not set")


def backend_client():
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {MICS_API_TOKEN}",
            "Content-Type": "application/json",
        }
    )
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/pilots")
async def get_pilots():
    async with backend_client() as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/pilots/live")
        resp.raise_for_status()
        return resp.json()




@app.websocket("/ws/pilots")
async def pilots_ws(ws: WebSocket):
    await ws.accept()

    try:
        while True:
            try:
                async with backend_client() as client:
                    resp = await client.get(
                        f"{ORCHESTRATOR_URL}/pilots/live",
                        timeout=2.0,
                    )
                    await ws.send_json(resp.json())

            except (ConnectError, ReadTimeout):
                # 🔑 Orchestrator temporarily unavailable
                # Send empty payload → frontend treats as OFFLINE
                await ws.send_json({})

            except Exception as e:
                # Any other unexpected error: log but DO NOT crash WS
                print("pilots_ws error:", repr(e))
                await ws.send_json({})

            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        pass



from pydantic import BaseModel

API_URL = "http://host.docker.internal:8000"  # backend API

class SubjectCreate(BaseModel):
    name: str


@app.get("/subjects-ui", response_class=HTMLResponse)
def subjects_page(request: Request):
    return templates.TemplateResponse("subjects.html", {"request": request})


@app.get("/api/subjects")
async def list_subjects():
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/subjects")
        resp.raise_for_status()
        return resp.json()


@app.post("/api/subjects")
async def create_subject(payload: SubjectCreate):
    async with backend_client() as client:
        resp = await client.post(
            f"{API_URL}/subjects",
            json=payload.dict(),
        )
        if resp.status_code == 400:
            raise HTTPException(400, resp.text)
        resp.raise_for_status()
        return resp.json()



@app.get("/api/protocols")
async def list_protocols():
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/protocols")
        resp.raise_for_status()
        return resp.json()


@app.post("/api/assign-protocol")
async def assign_protocol_ui(payload: dict):
    """
    payload = {
        "protocol_id": int,
        "subjects": [str, str, ...]
    }
    """
    protocol_id = payload["protocol_id"]
    subjects = payload["subjects"]

    async with backend_client() as client:
        # 1) Assign protocol to subjects
        for subj in subjects:
            resp = await client.post(
                f"{API_URL}/subjects/{subj}/assign_protocol",
                json={"protocol_id": protocol_id},
            )
            resp.raise_for_status()

        # 2) 🔥 IMMEDIATELY CREATE SESSION (SERVER-SIDE)
        session_resp = await client.post(f"{API_URL}/sessions/start")
        session_resp.raise_for_status()

        session_data = session_resp.json()

    return {
        "status": "ok",
        "assigned": len(subjects),
        "session": session_data,
    }


@app.get("/subjects/{subject}/sessions-ui", response_class=HTMLResponse)
def subject_sessions_page(subject: str, request: Request):
    return templates.TemplateResponse(
        "subject_sessions.html",
        {"request": request, "subject": subject},
    )


@app.get("/api/subjects/{subject}/sessions")
async def subject_sessions(subject: str):
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/subjects/{subject}/runs")
        resp.raise_for_status()
        return resp.json()

@app.get("/api/sessions/{session_id}")
async def get_session_detail_ui(session_id: int):
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/sessions/{session_id}")
        resp.raise_for_status()
        return resp.json()

@app.get("/api/protocols/{protocol_id}")
async def get_protocol_ui(protocol_id: int):
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/protocols/{protocol_id}")
        resp.raise_for_status()
        return resp.json()




@app.get("/pilots/{pilot_name}/sessions-ui", response_class=HTMLResponse)
def pilot_sessions_page(pilot_name: str, request: Request):
    return templates.TemplateResponse(
        "pilot_sessions.html",
        {"request": request, "pilot": pilot_name},
    )

@app.get("/api/sessions")
async def list_sessions():
    async with backend_client() as client:
        r = await client.get(f"{API_URL}/sessions")
        r.raise_for_status()
        return r.json()

@app.post("/api/sessions/{session_id}/start-on-pilot")
async def start_session_on_pilot(session_id: int, payload: dict):
    pilot_id = payload["pilot_id"]

    async with backend_client() as client:
        run_resp = await client.post(
            f"{API_URL}/session-runs",
            json={"session_id": session_id, "pilot_id": pilot_id},
        )

        if run_resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=run_resp.status_code,
                detail=run_resp.text,
            )

        run_id = run_resp.json()["id"]

    async with httpx.AsyncClient() as orch:
        orch_resp = await orch.post(
            f"{ORCHESTRATOR_URL}/runs/{run_id}/start"
        )

        if orch_resp.status_code >= 400:
            return {
                "status": "error",
                "run_id": run_id,
                "message": "Failed to start run on pilot",
                "orchestrator_status": orch_resp.status_code,
                "orchestrator_error": orch_resp.text,
            }

    return {
        "status": "started",
        "run_id": run_id,
    }


@app.get("/pilots/{pilot_name}/sessions-ui", response_class=HTMLResponse)
def pilot_sessions_ui(pilot_name: str, request: Request):
    return templates.TemplateResponse(
        "pilot_sessions.html",
        {
            "request": request,
            "pilot_name": pilot_name,
        },
    )

@app.get("/api/backend/pilots")
async def list_backend_pilots():
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/pilots")
        resp.raise_for_status()
        return resp.json()



# --------------------------------------------------
# PROTOCOLS
# --------------------------------------------------

@app.get("/protocols-ui", response_class=HTMLResponse)
def protocols_ui(request: Request):
    return templates.TemplateResponse(
        "protocols.html",
        {"request": request},
    )

@app.get("/protocols-create", response_class=HTMLResponse)
def protocols_create_ui(request: Request):
    return templates.TemplateResponse(
        "protocols-create.html",
        {"request": request},
    )


@app.get("/api/tasks/leaf")
async def list_leaf_tasks():
    async with backend_client() as client:
        resp = await client.get(f"{API_URL}/tasks/leaf")
        resp.raise_for_status()
        return resp.json()

@app.post("/api/protocols")
async def create_protocol_ui(payload: dict):
    async with backend_client() as client:
        resp = await client.post(
            f"{API_URL}/protocols",
            json=payload,
        )

        if resp.status_code != 201:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.text,
            )

        return resp.json()


@app.post("/api/session-runs/{run_id}/stop")
async def stop_session_run_ui(run_id: int):
    # 1️⃣ Mark STOPPED in backend (authoritative)
    async with backend_client() as client:
        resp = await client.post(
            f"{API_URL}/session-runs/{run_id}/stop"
        )
        resp.raise_for_status()

    # 2️⃣ Tell orchestrator to stop the Pi
    async with httpx.AsyncClient() as orch:
        orch_resp = await orch.post(
            f"{ORCHESTRATOR_URL}/runs/{run_id}/stop"
        )
        orch_resp.raise_for_status()

    return {"status": "stopped", "run_id": run_id}


@app.get("/api/session-runs/{run_id}/with-progress")
async def get_run_with_progress_ui(run_id: int):
    async with backend_client() as client:
        resp = await client.get(
            f"{API_URL}/session-runs/{run_id}/with-progress"
        )
        resp.raise_for_status()
        return resp.json()







