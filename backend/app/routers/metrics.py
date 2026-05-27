"""
Metrics Router — all /api/metrics/* endpoints.

POST  /api/metrics/            → ingest from agent (save + alert + AI + broadcast)
GET   /api/metrics/latest      → latest snapshot (Redis cached)
GET   /api/metrics/            → paginated history list
GET   /api/metrics/{id}        → single metric detail
GET   /api/metrics/history     → flat list for chart rendering
GET   /api/metrics/sparkline   → last 60 points from Redis
GET   /api/metrics/averages    → avg/min/max aggregation
GET   /api/metrics/buckets     → hourly aggregated data
DELETE /api/metrics/purge      → data retention cleanup (admin)
"""
import asyncio
from fastapi import APIRouter, Depends, Query, Path, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import DBSession, Pagination, AgentAuth
from app.schemas.metrics import (
    MetricCreate, MetricResponse, MetricSummary,
    MetricAverages, HourlyBucket, PaginatedMetrics,
)
from app.services.metrics_service import metrics_service
from app.services.alert_service import alert_service
from app.services.anomaly_service import anomaly_service
from app.ml.anomaly_detector import anomaly_detector
from app.utils.websocket_manager import ws_manager

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=MetricResponse, status_code=201)
async def ingest_metric(
    payload:    MetricCreate,
    background: BackgroundTasks,
    db:         DBSession,
    _auth:      AgentAuth,
):
    """
    Called by the monitoring agent every 5 seconds.

    Pipeline (all async, non-blocking):
      1. Persist to PostgreSQL
      2. Threshold-based alert check
      3. AI anomaly detection (Isolation Forest)
      4. WebSocket broadcast to all dashboard clients
    """
    # ── 1. Persist ────────────────────────────────────────────────────────────
    metric = await metrics_service.save_metric(db, payload)
    metric_dict = payload.model_dump()

    # ── 2 & 3 run concurrently — they are independent ─────────────────────────
    alert_task   = asyncio.create_task(
        alert_service.check_and_create_alerts(db, metric_dict)
    )
    anomaly_task = asyncio.create_task(
        _run_anomaly_check(db, metric_dict)
    )
    new_alerts, anomaly_payload = await asyncio.gather(alert_task, anomaly_task)

    # ── 4. Build broadcast payload ────────────────────────────────────────────
    broadcast = {
        "type": "metric",
        "data": metric.to_summary_dict(),
    }
    if new_alerts:
        broadcast["alerts"] = [
            {"type": a.alert_type, "message": a.message, "severity": a.severity}
            for a in new_alerts
        ]
    if anomaly_payload:
        broadcast["anomaly"] = anomaly_payload

    # Fire-and-forget broadcast — don't block the HTTP response
    background.add_task(ws_manager.broadcast, broadcast)

    return metric


async def _run_anomaly_check(db: AsyncSession, metric_dict: dict) -> dict | None:
    """Helper: run AI detection and persist if anomaly found. Returns payload or None."""
    is_anomaly, score, details = anomaly_detector.predict(metric_dict)
    if not is_anomaly:
        return None
    anomaly = await anomaly_service.save_anomaly(db, metric_dict, score, details)
    return {
        "id":              anomaly.id,
        "score":           score,
        "severity":        anomaly.severity,
        "description":     anomaly.description,
        "dominant_feature": details.get("dominant_feature"),
    }


# ── Latest (Redis cached) ─────────────────────────────────────────────────────

@router.get("/latest")
async def get_latest_metric(db: DBSession):
    """
    Served from Redis cache (sub-millisecond).
    Falls back to PostgreSQL only if cache is empty.
    """
    latest = await metrics_service.get_latest(db)
    if latest is None:
        return {}
    if isinstance(latest, dict):
        return latest
    return latest.to_summary_dict()


# ── Sparkline (Redis) ─────────────────────────────────────────────────────────

@router.get("/sparkline", response_model=list[dict])
async def get_sparkline():
    """Last 60 metric snapshots from Redis. Used for live mini-charts."""
    return await metrics_service.get_sparkline()


# ── Aggregation endpoints ─────────────────────────────────────────────────────

@router.get("/averages", response_model=MetricAverages)
async def get_averages(
    db:    DBSession,
    hours: int = Query(default=24, ge=1, le=168, description="Look-back window in hours"),
):
    """Avg, min, max CPU/RAM/Disk for the given time window."""
    return await metrics_service.get_averages(db, hours=hours)


@router.get("/buckets", response_model=list[HourlyBucket])
async def get_hourly_buckets(
    db:    DBSession,
    hours: int = Query(default=24, ge=1, le=168),
):
    """
    Returns one data point per hour — perfect for the Analytics bar chart.
    Aggregation is done in PostgreSQL with DATE_TRUNC, not in Python.
    """
    return await metrics_service.get_hourly_buckets(db, hours=hours)


# ── History (flat list for charts) ────────────────────────────────────────────

@router.get("/history", response_model=list[MetricSummary])
async def get_history(
    db:       DBSession,
    hours:    int        = Query(default=1,   ge=1, le=168),
    limit:    int        = Query(default=300, ge=1, le=1000),
    hostname: str | None = Query(default=None),
):
    """Time-series data in chronological order for Recharts area/line charts."""
    return await metrics_service.get_history(
        db, hours=hours, limit=limit, hostname=hostname
    )


# ── Paginated list ────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedMetrics)
async def list_metrics(
    db:     DBSession,
    params: Pagination,
    hours:  int = Query(default=1, ge=1, le=168),
):
    """
    Paginated list of raw metrics for the table/explorer view.
    Example: GET /api/metrics/?hours=1&page=2&size=20
    """
    total = await metrics_service.count_in_window(db, hours)
    items = await metrics_service.get_history(
        db,
        hours=hours,
        limit=params.limit,
        offset=params.offset,
    )
    return PaginatedMetrics(
        total=total,
        page=params.page,
        size=params.size,
        items=items,
    )


# ── Single row ────────────────────────────────────────────────────────────────

@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric_by_id(
    db:        DBSession,
    metric_id: int = Path(..., gt=0),
):
    metric = await metrics_service.get_by_id(db, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found.")
    return metric


# ── Admin: data retention ─────────────────────────────────────────────────────

@router.delete("/purge", status_code=200)
async def purge_old_metrics(
    db:              DBSession,
    older_than_days: int = Query(default=7, ge=1, le=365),
):
    """
    Deletes metric rows older than N days.
    Run this periodically (e.g. from a cron job) to prevent table bloat.
    """
    deleted = await metrics_service.purge_old_metrics(db, older_than_days)
    return {"deleted": deleted, "older_than_days": older_than_days}
