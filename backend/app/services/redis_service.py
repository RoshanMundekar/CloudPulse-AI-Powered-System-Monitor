"""
CloudPulse — Redis Service

Responsibilities:
1. Cache latest metric (TTL-based, sub-1ms reads)
2. Maintain rolling sparkline history (Redis list, max 60 entries)
3. Pub/Sub channel for broadcasting across multiple backend instances
4. Alert / anomaly counters
5. Health probe

Redis key layout:
  cloudpulse:metric:latest      → JSON string, TTL=REDIS_CACHE_TTL
  cloudpulse:metric:history     → List<JSON>, max 60 items
  cloudpulse:counter:alerts     → Integer
  cloudpulse:counter:anomalies  → Integer
  cloudpulse:pubsub             → Pub/Sub channel name
"""
import json
import logging
import redis.asyncio as aioredis
from redis.asyncio.client import PubSub
from app.config import settings

log = logging.getLogger("cloudpulse.redis")

# Centralised key names — change once if you need to rename
_KEY_LATEST  = "cloudpulse:metric:latest"
_KEY_HISTORY = "cloudpulse:metric:history"
_KEY_ALERTS  = "cloudpulse:counter:alerts"
_KEY_ANOM    = "cloudpulse:counter:anomalies"
PUBSUB_CHANNEL = "cloudpulse:pubsub"


class RedisService:
    def __init__(self):
        self._client: aioredis.Redis | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,   # background ping every 30 s
        )
        # Verify the connection works immediately
        await self._client.ping()
        log.info("Redis connected.")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            log.info("Redis disconnected.")

    # ── Metric cache ─────────────────────────────────────────────────────────

    async def set_latest_metric(self, data: dict) -> None:
        """
        Overwrite the latest metric with a TTL.
        Dashboard API calls read this instead of querying PostgreSQL.
        """
        await self._client.setex(
            _KEY_LATEST,
            settings.REDIS_CACHE_TTL,
            json.dumps(data, default=str),
        )

    async def get_latest_metric(self) -> dict | None:
        raw = await self._client.get(_KEY_LATEST)
        return json.loads(raw) if raw else None

    # ── Sparkline rolling list ────────────────────────────────────────────────

    async def push_metric_history(self, data: dict, max_items: int = 60) -> None:
        """
        Prepend to a capped list so index 0 is always the newest entry.
        Uses a pipeline to make the LPUSH + LTRIM atomic.
        """
        pipe = self._client.pipeline(transaction=True)
        pipe.lpush(_KEY_HISTORY, json.dumps(data, default=str))
        pipe.ltrim(_KEY_HISTORY, 0, max_items - 1)
        await pipe.execute()

    async def get_metric_history(self) -> list[dict]:
        """Return history in chronological order (oldest → newest)."""
        items = await self._client.lrange(_KEY_HISTORY, 0, -1)
        parsed = [json.loads(i) for i in items]
        return list(reversed(parsed))   # list is newest-first; reverse for charts

    # ── Pub / Sub  ────────────────────────────────────────────────────────────

    async def publish(self, data: dict) -> int:
        """
        Publish a message on the shared channel.
        Returns the number of subscribers that received it.
        This allows multiple backend instances to broadcast to WebSocket clients.
        """
        return await self._client.publish(
            PUBSUB_CHANNEL, json.dumps(data, default=str)
        )

    def get_pubsub(self) -> PubSub:
        """
        Return a new Pub/Sub handle.
        The caller is responsible for subscribing and closing it.
        """
        return self._client.pubsub(ignore_subscribe_messages=True)

    # ── Counters ─────────────────────────────────────────────────────────────

    async def increment_alert_count(self) -> int:
        return await self._client.incr(_KEY_ALERTS)

    async def increment_anomaly_count(self) -> int:
        return await self._client.incr(_KEY_ANOM)

    async def get_alert_count(self) -> int:
        val = await self._client.get(_KEY_ALERTS)
        return int(val) if val else 0

    async def get_anomaly_count(self) -> int:
        val = await self._client.get(_KEY_ANOM)
        return int(val) if val else 0

    async def reset_counters(self) -> None:
        pipe = self._client.pipeline()
        pipe.delete(_KEY_ALERTS)
        pipe.delete(_KEY_ANOM)
        await pipe.execute()

    # ── Bulk cache op (used by metrics_service) ───────────────────────────────

    async def cache_metric_batch(self, data: dict, max_history: int = 60) -> None:
        """
        Combine set_latest + push_history in one pipeline round-trip.
        Reduces Redis RTTs from 2 to 1 per ingest cycle.
        """
        serialised = json.dumps(data, default=str)
        pipe = self._client.pipeline(transaction=False)
        pipe.setex(_KEY_LATEST, settings.REDIS_CACHE_TTL, serialised)
        pipe.lpush(_KEY_HISTORY, serialised)
        pipe.ltrim(_KEY_HISTORY, 0, max_history - 1)
        await pipe.execute()

    # ── Health check ─────────────────────────────────────────────────────────

    async def health_check(self) -> dict:
        try:
            pong = await self._client.ping()
            info = await self._client.info("memory")
            return {
                "status": "ok",
                "ping": pong,
                "used_memory_human": info.get("used_memory_human"),
            }
        except Exception as exc:
            log.error(f"Redis health check failed: {exc}")
            return {"status": "error", "detail": str(exc)}


redis_service = RedisService()
