import json
import asyncio
import queue
import os
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

import TA_update_web

def scheduled_update_task():
    print("Running scheduled automated update task...")
    # Initialize logger so we don't crash the print functions if web_print is called
    TA_update_web.logger.q = queue.Queue()
    TA_update_web.logger.results = []
    TA_update_web.main()
    print("Scheduled automated update task finished.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup background scheduler
    scheduler = BackgroundScheduler()

    # Configure via environment variables with defaults
    cron_day = os.getenv("CRON_DAY", "1")
    cron_hour = os.getenv("CRON_HOUR", "9")
    cron_minute = os.getenv("CRON_MINUTE", "0")

    trigger = CronTrigger(day=cron_day, hour=cron_hour, minute=cron_minute)
    scheduler.add_job(scheduled_update_task, trigger)
    scheduler.start()

    yield

    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Start the update process in a separate thread
    TA_update_web.logger.q = queue.Queue()  # Reset queue for each run
    TA_update_web.logger.results = []
    TA_update_web.run_update_thread()

    try:
        while True:
            try:
                # Use a short timeout so we can yield control back to the event loop
                msg = TA_update_web.logger.q.get(timeout=0.1)
                await websocket.send_text(json.dumps(msg))
                if msg.get("type") == "done":
                    break
            except queue.Empty:
                await asyncio.sleep(0.1)

        # Send final results
        await websocket.send_text(json.dumps({"type": "final_results", "data": TA_update_web.logger.results}))

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
