"""
CloudPulse — WebSocket Connection Manager

Improvements over the original:
- asyncio.gather() for concurrent broadcasting (O(1) perceived latency vs O(n) sequential)
- Per-connection metadata: id, connected_at, last_ping_at
- Heartbeat task: pings every client every 20 s, culls non-responding ones
- Thread-safe disconnect via asyncio.Lock
- connection_info() for the /health endpoint
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from fastapi import WebSocket

log = logging.getLogger("cloudpulse.ws")

HEARTBEAT_INTERVAL = 20    # seconds between server → client pings
PONG_TIMEOUT       = 10    # seconds to wait for client pong before culling


@dataclass
class WSConnection:
    ws: WebSocket
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    connected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_pong_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    alive: bool = True


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, WSConnection] = {}   # id → WSConnection
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start_heartbeat(self) -> None:
        """Call once at app startup to begin the background heartbeat loop."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            log.info("[WS] Heartbeat task started.")

    def stop_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    # ── Connect / disconnect ─────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> WSConnection:
        await ws.accept()
        conn = WSConnection(ws=ws)
        async with self._lock:
            self._connections[conn.id] = conn
        log.info(f"[WS] Client {conn.id} connected. Total: {len(self._connections)}")
        return conn

    async def disconnect(self, conn_id: str) -> None:
        async with self._lock:
            conn = self._connections.pop(conn_id, None)
        if conn:
            conn.alive = False
            log.info(f"[WS] Client {conn_id} disconnected. Total: {len(self._connections)}")

    # ── Send helpers ─────────────────────────────────────────────────────────

    async def send_to(self, conn_id: str, data: dict) -> bool:
        """Send to one specific client. Returns False if send failed."""
        async with self._lock:
            conn = self._connections.get(conn_id)
        if not conn:
            return False
        try:
            await conn.ws.send_text(json.dumps(data, default=str))
            return True
        except Exception:
            await self.disconnect(conn_id)
            return False

    async def broadcast(self, data: dict) -> None:
        """
        Fan-out to all connected clients concurrently.
        asyncio.gather collects failures without raising — dead sockets
        are removed as side-effects inside _safe_send.
        """
        async with self._lock:
            snapshot = list(self._connections.items())

        if not snapshot:
            return

        message = json.dumps(data, default=str)
        tasks = [self._safe_send(cid, conn, message) for cid, conn in snapshot]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, conn_id: str, conn: WSConnection, message: str) -> None:
        try:
            await conn.ws.send_text(message)
        except Exception:
            await self.disconnect(conn_id)

    # ── Heartbeat ────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """
        Every HEARTBEAT_INTERVAL seconds, send a ping to every client.
        Clients that haven't responded within PONG_TIMEOUT get culled.
        """
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            async with self._lock:
                snapshot = list(self._connections.items())

            now = datetime.now(timezone.utc)
            for conn_id, conn in snapshot:
                # Cull if last pong is too old (means the previous ping was ignored)
                age = (now - conn.last_pong_at).total_seconds()
                if age > HEARTBEAT_INTERVAL + PONG_TIMEOUT:
                    log.warning(f"[WS] Culling stale client {conn_id} (no pong for {age:.0f}s)")
                    await self.disconnect(conn_id)
                    continue

                # Send ping
                try:
                    await conn.ws.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    await self.disconnect(conn_id)

    def record_pong(self, conn_id: str) -> None:
        """Called by the WebSocket router when a client sends 'pong'."""
        conn = self._connections.get(conn_id)
        if conn:
            conn.last_pong_at = datetime.now(timezone.utc)

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def connection_info(self) -> list[dict]:
        """Summary of all active connections (for /health endpoint)."""
        now = datetime.now(timezone.utc)
        return [
            {
                "id": cid,
                "connected_seconds": (now - conn.connected_at).seconds,
                "last_pong_seconds_ago": (now - conn.last_pong_at).seconds,
            }
            for cid, conn in self._connections.items()
        ]


ws_manager = WebSocketManager()
