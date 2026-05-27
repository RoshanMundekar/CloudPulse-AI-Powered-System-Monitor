"""
WebSocket Router — /ws endpoint

Flow:
  1. Client connects → ws_manager registers it, returns WSConnection
  2. Server immediately sends the latest cached metric (so charts aren't empty)
  3. Loop: client messages are read; 'pong' updates the heartbeat timestamp
  4. WebSocketDisconnect → client is deregistered
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.utils.websocket_manager import ws_manager
from app.services.redis_service import redis_service
import logging

log = logging.getLogger("cloudpulse.ws_router")

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    The browser opens: ws://localhost:8000/ws

    Message types the server sends:
      { "type": "metric",  "data": {...} }   → every 5 s from agent
      { "type": "anomaly", "data": {...} }   → when AI detects anomaly
      { "type": "ping" }                     → heartbeat (every 20 s)

    Messages the client should send:
      "pong"   → heartbeat response (keeps connection alive)
      "ping"   → client keepalive (server responds with pong)
    """
    conn = await ws_manager.connect(ws)

    # Send the latest cached metric immediately on connect
    # so the dashboard renders populated charts, not empty placeholders
    latest = await redis_service.get_latest_metric()
    if latest:
        await ws_manager.send_to(conn.id, {"type": "metric", "data": latest})
        log.debug(f"[WS] Sent initial metric to {conn.id}")

    try:
        while True:
            raw = await ws.receive_text()

            if raw == "pong":
                # Client is responding to our server-side ping
                ws_manager.record_pong(conn.id)

            elif raw == "ping":
                # Client-initiated keepalive — respond immediately
                await ws_manager.send_to(conn.id, {"type": "pong"})

    except WebSocketDisconnect:
        await ws_manager.disconnect(conn.id)
    except Exception as exc:
        log.warning(f"[WS] Unexpected error for {conn.id}: {exc}")
        await ws_manager.disconnect(conn.id)
