"""Smart Room Cooling — FastAPI backend.

Pipeline per telemetry message from the sensor:
    resolve control state -> publish AC state -> log to SQLite -> broadcast to dashboards
Dashboard commands arrive over the same WebSocket and drive manual override.
"""
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from . import db
from .control import ControlState
from .mqtt_client import MqttBridge
from .ws_manager import WSManager

control = ControlState()
ws_manager = WSManager()
bridge: MqttBridge | None = None


async def handle_telemetry(env: dict) -> None:
    """Called for every environment message published by the sensor."""
    merged, comfort = control.resolve(env)
    if bridge:
        bridge.publish_ac(control.ac_state())      # let the room/AC respond
    db.log_telemetry(merged, comfort.state)
    await ws_manager.broadcast(merged)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bridge
    db.init()
    loop = asyncio.get_running_loop()
    bridge = MqttBridge(loop, handle_telemetry)
    bridge.start()
    yield
    bridge.stop()


app = FastAPI(title="SmartCool Backend", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mqtt_connected": bool(bridge and bridge.connected)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            if msg.get("type") == "command":
                cmd = msg.get("cmd", "")
                control.apply_command(cmd)
                db.log_event(f"Manual: {cmd}")
                if bridge:
                    bridge.publish_ac(control.ac_state())
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


@app.get("/api/telemetry")
async def api_telemetry(limit: int = 200):
    return db.recent_telemetry(limit)


@app.get("/api/events")
async def api_events(limit: int = 100):
    return db.recent_events(limit)


@app.get("/api/stats")
async def api_stats():
    return db.stats()


# Serve the dashboard at / (index.html). Mounted last so routes win.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
