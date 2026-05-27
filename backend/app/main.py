"""
CloudPulse — FastAPI Application Entry Point

Startup sequence:
  1. Create DB tables (idempotent)
  2. Connect Redis
  3. Start WS heartbeat task
  4. Start ML model retraining loop
  5. Start Redis pub/sub listener (broadcasts to WS clients)

Shutdown sequence:
  Cancel all background tasks → disconnect Redis → dispose DB engine
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables, dispose_engine
from app.services.redis_service import redis_service, PUBSUB_CHANNEL
from app.utils.websocket_manager import ws_manager
from app.ml.model_trainer import retrain_model_task
from app.middleware import register_middleware
from app.exceptions import register_exception_handlers
from app.routers import (
    metrics_router,
    alerts_router,
    anomalies_router,
    ws_router,
    system_router,
    ml_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cloudpulse")


# ── Background tasks ──────────────────────────────────────────────────────────

async def pubsub_broadcaster() -> None:
    """
    Subscribes to the Redis pub/sub channel and re-broadcasts every
    published message to all connected WebSocket clients.

    Why pub/sub instead of broadcasting directly in the metrics router?
    → With multiple backend instances (horizontal scaling), only the instance
      that received the POST would broadcast. Publishing to Redis ensures
      ALL instances relay the update to THEIR WebSocket clients.
    → Even with a single instance, this decouples ingestion from delivery.
    """
    pubsub = redis_service.get_pubsub()
    await pubsub.subscribe(PUBSUB_CHANNEL)
    log.info(f"[PubSub] Subscribed to channel '{PUBSUB_CHANNEL}'")

    try:
        async for message in pubsub.listen():
            if message and message.get("type") == "message":
                try:
                    data = json.loads(message["data"])
                    await ws_manager.broadcast(data)
                except (json.JSONDecodeError, Exception) as exc:
                    log.warning(f"[PubSub] Bad message: {exc}")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(PUBSUB_CHANNEL)
        await pubsub.aclose()
        log.info("[PubSub] Unsubscribed and closed.")


async def retention_cleanup_task() -> None:
    """
    Runs every 6 hours and deletes metric rows older than 7 days.
    Prevents the system_metrics table from growing without bound.
    """
    from app.database import AsyncSessionLocal
    from app.services.metrics_service import metrics_service

    while True:
        await asyncio.sleep(6 * 3600)       # wait 6 hours
        async with AsyncSessionLocal() as db:
            try:
                deleted = await metrics_service.purge_old_metrics(db, older_than_days=7)
                log.info(f"[Retention] Purged {deleted} old metric rows.")
            except Exception as exc:
                log.error(f"[Retention] Purge failed: {exc}")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────────────────
    log.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ...")

    await create_tables()
    log.info("Database tables ready.")

    await redis_service.connect()
    log.info("Redis connected.")

    ws_manager.start_heartbeat()

    background_tasks = [
        asyncio.create_task(retrain_model_task(),   name="ml-retrainer"),
        asyncio.create_task(pubsub_broadcaster(),   name="pubsub-broadcaster"),
        asyncio.create_task(retention_cleanup_task(), name="retention-cleanup"),
    ]
    log.info(f"Background tasks started: {[t.get_name() for t in background_tasks]}")

    yield   # ← application handles requests here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    log.info("Shutting down ...")
    ws_manager.stop_heartbeat()

    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)

    await redis_service.disconnect()
    await dispose_engine()
    log.info("Shutdown complete.")


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="CloudPulse API",
        description=(
            "AI-Powered System Monitoring Platform — "
            "real-time metrics, WebSocket live feed, anomaly detection."
        ),
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow the React dev server and production domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Timing + access-log middleware
    register_middleware(app)

    # Global exception handlers
    register_exception_handlers(app)

    # Routers
    app.include_router(system_router)    # /health and /api/system/info
    app.include_router(metrics_router)
    app.include_router(alerts_router)
    app.include_router(anomalies_router)
    app.include_router(ml_router)        # /api/ml/status, /predict, /retrain, /anomalies/stats
    app.include_router(ws_router)

    return app


app = create_app()
