"""
Model Trainer — background retraining loop and on-demand retrain trigger.

Why retrain periodically?
  The Isolation Forest learns what "normal" looks like from historical data.
  As system load patterns change (new services, time-of-day traffic, deployments),
  the model's idea of "normal" becomes stale. Hourly retraining keeps it current.

Why run_in_executor?
  IsolationForest.fit() is CPU-bound (scikit-learn uses C extensions).
  Running it directly in an async function would block the entire event loop
  for ~0.5s, freezing all WebSocket connections and HTTP responses.
  run_in_executor() moves it to a thread pool so the loop stays responsive.
"""
import asyncio
import logging
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.ml.anomaly_detector import anomaly_detector
from app.models.metrics import SystemMetric

log = logging.getLogger("cloudpulse.trainer")

# ── State shared between background task and API endpoint ─────────────────────
_retrain_lock         = asyncio.Lock()   # prevents two concurrent retrains
_last_retrain_result: dict = {}


async def retrain_model_task():
    """
    Background coroutine started at FastAPI startup.
    Waits 60s (for the app to settle), then retrains every MODEL_RETRAIN_INTERVAL seconds.
    """
    # Give the app time to start and load existing data before the first retrain
    await asyncio.sleep(60)

    while True:
        result = await trigger_retrain()
        log.info(f"[Trainer] Auto-retrain complete: {result}")
        await asyncio.sleep(settings.MODEL_RETRAIN_INTERVAL)


async def trigger_retrain() -> dict:
    """
    Trigger a model retrain — safe to call from both the background loop and the API.
    Returns immediately (with a "already_running" status) if a retrain is in progress.
    Thread-safe via asyncio.Lock.
    """
    global _last_retrain_result

    if _retrain_lock.locked():
        return {
            "status":  "already_running",
            "message": "Retraining is already in progress — try again shortly.",
        }

    async with _retrain_lock:
        _last_retrain_result = await _do_retrain()

    return _last_retrain_result


async def _do_retrain() -> dict:
    """
    Core retrain logic:
      1. Query last 24h of metrics from PostgreSQL
      2. Run IsolationForest.fit() in a thread pool (non-blocking)
      3. Return training stats
    """
    log.info("[Trainer] Fetching training data...")
    started_at = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        since  =  datetime.now(UTC) - timedelta(hours=24)
        result = await db.execute(
            select(SystemMetric)
            .where(SystemMetric.created_at >= since)
            .order_by(SystemMetric.created_at)
        )
        rows = result.scalars().all()

    # Convert ORM objects to plain dicts (required by anomaly_detector.train)
    data = [
        {
            "cpu_percent":       r.cpu_percent       or 0,
            "ram_percent":       r.ram_percent        or 0,
            "disk_percent":      r.disk_percent       or 0,
            "net_bytes_recv_mb": r.net_bytes_recv_mb  or 0,
            "net_bytes_sent_mb": r.net_bytes_sent_mb  or 0,
        }
        for r in rows
    ]

    log.info(f"[Trainer] Training on {len(data)} samples...")

    # Run the CPU-bound sklearn training in a thread pool
    loop   = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, anomaly_detector.train, data)

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    return {
        **result,
        "elapsed_seconds": round(elapsed, 2),
        "retrained_at":    started_at.isoformat(),
    }


def get_last_retrain_result() -> dict:
    """Return the most recent retrain result dict (read by /api/ml/status)."""
    return _last_retrain_result
