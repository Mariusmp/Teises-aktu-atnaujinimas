import json
import asyncio
import queue
import os
import sys
import secrets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

import TA_update_web

security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    app_password = os.getenv("APP_PASSWORD")
    if app_password is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_PASSWORD environment variable not set",
        )

    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, app_password)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


def scheduled_update_task():
    print("Running scheduled automated update task...")
    TA_update_web.stop_event.clear()
    TA_update_web.logger.q = queue.Queue()
    TA_update_web.logger.results = []
    TA_update_web.main()
    print("Scheduled automated update task finished.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()

    cron_day = os.getenv("CRON_DAY", "1")
    cron_hour = os.getenv("CRON_HOUR", "9")
    cron_minute = os.getenv("CRON_MINUTE", "0")

    trigger = CronTrigger(day=cron_day, hour=cron_hour, minute=cron_minute)
    scheduler.add_job(scheduled_update_task, trigger)
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

if os.getenv("APP_PASSWORD") is None:
    print("ERROR: APP_PASSWORD environment variable must be set.")
    sys.exit(1)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(verify_credentials)])
async def get(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"token": os.getenv("APP_PASSWORD")})


@app.post("/stop")
async def stop_update(token: str = Query(None)):
    app_password = os.getenv("APP_PASSWORD")
    if token is None or not app_password or not secrets.compare_digest(token, app_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    TA_update_web.request_stop()
    return JSONResponse({"status": "stopping"})


async def _listen_ws_stop(websocket: WebSocket):
    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                payload = json.loads(raw_msg)
                if payload.get("action") == "stop":
                    TA_update_web.request_stop()
            except Exception:
                if raw_msg.strip().lower() == "stop":
                    TA_update_web.request_stop()
    except (WebSocketDisconnect, Exception):
        pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    if token is None or not secrets.compare_digest(token, os.getenv("APP_PASSWORD")):
        await websocket.close(code=1008, reason="Policy Violation")
        return

    await websocket.accept()

    TA_update_web.logger.q = queue.Queue()
    TA_update_web.logger.results = []
    TA_update_web.run_update_thread()

    listener_task = asyncio.create_task(_listen_ws_stop(websocket))

    try:
        while True:
            msg = await asyncio.to_thread(TA_update_web.logger.q.get)
            await websocket.send_text(json.dumps(msg))
            if msg.get("type") == "done":
                break

        await websocket.send_text(json.dumps({"type": "final_results", "data": TA_update_web.logger.results}))

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        listener_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    app_host = os.getenv("APP_HOST", "127.0.0.1")
    app_port = int(os.getenv("APP_PORT", 8000))
    app_reload_str = os.getenv("APP_RELOAD", "False").lower()
    app_reload = app_reload_str in ["true", "1", "t", "yes"]
    app_log_level = os.getenv("APP_LOG_LEVEL", "info")

    uvicorn.run(
        "app:app",
        host=app_host,
        port=app_port,
        reload=app_reload,
        log_level=app_log_level
    )
