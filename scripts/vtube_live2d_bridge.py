"""
VTube Studio Live2D Bridge
Connects to VTube Studio WebSocket API and exposes an HTTP server
so other services can send move/hotkey commands.

Usage:
  python scripts/vtube_live2d_bridge.py

HTTP API (default port 8088):
  POST /move    { posX, posY, rotation, size, relative }
  POST /hotkey  { hotkeyID }
  GET  /hotkeys
  GET  /model
  GET  /health
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

import websockets
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("vtube-bridge")

VTUBE_WS_URL = "ws://0.0.0.0:8001"
PLUGIN_NAME = "Musui Live2D Bridge"
PLUGIN_DEV = "musui"
HTTP_PORT = 8088

# ─── State ────────────────────────────────────────────────────────────────────

class BridgeState:
    ws: websockets.WebSocketClientProtocol | None = None
    authenticated: bool = False
    token: str | None = None
    pending: dict[str, asyncio.Future] = {}
    _lock: asyncio.Lock = None

    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

state = BridgeState()


# ─── VTube Studio WebSocket client ────────────────────────────────────────────

async def send(msg: dict) -> dict | None:
    """Send a message and wait for the matching response."""
    if not state.ws or not state.authenticated:
        raise RuntimeError("Not connected / not authenticated")
    req_id = msg.get("requestID", str(uuid.uuid4()))
    msg["requestID"] = req_id
    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    state.pending[req_id] = fut
    await state.ws.send(json.dumps(msg))
    try:
        return await asyncio.wait_for(fut, timeout=5.0)
    except asyncio.TimeoutError:
        state.pending.pop(req_id, None)
        raise RuntimeError(f"VTube response timeout for requestID={req_id}")


async def reader_loop():
    """Pump incoming messages and resolve pending futures."""
    async for raw in state.ws:
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        req_id = msg.get("requestID")
        if req_id and req_id in state.pending:
            fut = state.pending.pop(req_id)
            if not fut.done():
                fut.set_result(msg)
        else:
            log.debug("unhandled msg type=%s", msg.get("messageType"))


def vtube_msg(message_type: str, data: dict, req_id: str | None = None) -> dict:
    return {
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": req_id or str(uuid.uuid4()),
        "messageType": message_type,
        "data": data,
    }


async def authenticate():
    """Full VTube Studio auth flow: request token → authenticate."""
    # Step 1 — request token
    req_id = "auth-token"
    msg = vtube_msg("AuthenticationTokenRequest", {
        "pluginName": PLUGIN_NAME,
        "pluginDeveloper": PLUGIN_DEV,
        "pluginIcon": "",
    }, req_id)
    state.pending[req_id] = asyncio.get_event_loop().create_future()
    await state.ws.send(json.dumps(msg))
    resp = await asyncio.wait_for(state.pending.pop(req_id), timeout=10.0)
    token = resp.get("data", {}).get("authenticationToken")
    if not token:
        raise RuntimeError("No auth token received — approve plugin in VTube Studio")
    state.token = token
    log.info("Got auth token")

    # Step 2 — authenticate with token
    req_id = "auth-2"
    msg = vtube_msg("AuthenticationRequest", {
        "pluginName": PLUGIN_NAME,
        "pluginDeveloper": PLUGIN_DEV,
        "authenticationToken": token,
    }, req_id)
    state.pending[req_id] = asyncio.get_event_loop().create_future()
    await state.ws.send(json.dumps(msg))
    resp = await asyncio.wait_for(state.pending.pop(req_id), timeout=10.0)
    ok = resp.get("data", {}).get("authenticated", False)
    if not ok:
        raise RuntimeError("Authentication rejected by VTube Studio")
    state.authenticated = True
    log.info("Authenticated with VTube Studio")


async def connect_loop():
    """Keep reconnecting to VTube Studio on disconnect."""
    while True:
        try:
            log.info("Connecting to VTube Studio at %s", VTUBE_WS_URL)
            async with websockets.connect(VTUBE_WS_URL) as ws:
                state.ws = ws
                state.authenticated = False
                await authenticate()
                log.info("Bridge ready — approve plugin popup in VTube Studio if needed")
                await reader_loop()
        except Exception as e:
            log.warning("VTube connection lost: %s — retrying in 5s", e)
            state.ws = None
            state.authenticated = False
        await asyncio.sleep(5)


# ─── HTTP Models ──────────────────────────────────────────────────────────────

class MoveRequest(BaseModel):
    posX: float = Field(0.0, ge=-1.0, le=1.0)
    posY: float = Field(0.0, ge=-1.0, le=1.0)
    rotation: float = Field(0.0, ge=-360.0, le=360.0)
    size: float | None = Field(None, ge=-100.0, le=100.0)
    relative: bool = False
    timeInSeconds: float = Field(0.2, ge=0.0, le=2.0)


class HotkeyRequest(BaseModel):
    hotkeyID: str


# ─── FastAPI app ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(connect_loop())
    yield
    task.cancel()

app = FastAPI(title="VTube Live2D Bridge", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vtube_connected": state.ws is not None and state.authenticated,
        "vtube_url": VTUBE_WS_URL,
    }


@app.post("/move")
async def move_model(req: MoveRequest):
    """Move / reposition the Live2D model."""
    if not state.authenticated:
        raise HTTPException(503, "Not connected to VTube Studio")
    data: dict = {
        "timeInSeconds": req.timeInSeconds,
        "valuesAreRelativeToModel": req.relative,
        "positionX": req.posX,
        "positionY": req.posY,
        "rotation": req.rotation,
    }
    if req.size is not None:
        data["size"] = req.size
    resp = await send(vtube_msg("MoveModelRequest", data))
    return {"success": True, "response": resp}


@app.post("/hotkey")
async def trigger_hotkey(req: HotkeyRequest):
    """Trigger a VTube Studio hotkey by ID."""
    if not state.authenticated:
        raise HTTPException(503, "Not connected to VTube Studio")
    resp = await send(vtube_msg("HotkeyTriggerRequest", {"hotkeyID": req.hotkeyID}))
    return {"success": True, "response": resp}


@app.get("/hotkeys")
async def get_hotkeys():
    """List all hotkeys available in the current model."""
    if not state.authenticated:
        raise HTTPException(503, "Not connected to VTube Studio")
    resp = await send(vtube_msg("HotkeysInCurrentModelRequest", {}))
    return {"hotkeys": resp.get("data", {}).get("availableHotkeys", [])}


@app.get("/model")
async def get_model_info():
    """Get info about the currently loaded model."""
    if not state.authenticated:
        raise HTTPException(503, "Not connected to VTube Studio")
    resp = await send(vtube_msg("CurrentModelRequest", {}))
    return {"model": resp.get("data", {})}


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_level="info")
