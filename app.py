import json
import asyncio
import queue
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import TA_update_web

app = FastAPI()

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
