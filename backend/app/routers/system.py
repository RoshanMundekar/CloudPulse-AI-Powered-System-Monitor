"""
System Router — health check and live system info.

GET /health         → liveness probe (used by Docker health checks)
GET /api/system/info → deep health: DB, Redis, WS connection count, ML status
"""
from fastapi import APIRouter
from app.database import check_db_health
from app.services.redis_service import redis_service
from app.utils.websocket_manager import ws_manager
from app.ml.anomaly_detector import anomaly_detector
from app.config import settings
import platform, psutil
from datetime import datetime, timezone

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness probe")
async def health():
    """
    Minimal health check — returns 200 if the process is running.
    Used by Docker HEALTHCHECK and load balancers.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/system/info", summary="Deep system status")
async def system_info():
    """
    Returns the health status of every subsystem.
    Used by the dashboard header and ops teams.
    """
    db_status    = await check_db_health()
    redis_status = await redis_service.health_check()

    return {
        "app": {
            "name":    settings.APP_NAME,
            "version": settings.APP_VERSION,
            "debug":   settings.DEBUG,
        },
        "database":     db_status,
        "redis":        redis_status,
        "websocket": {
            "active_connections": ws_manager.connection_count,
            "connections":        ws_manager.connection_info(),
        },
        "ml_model": {
            "trained":     anomaly_detector.is_trained,
            "contamination": settings.MODEL_CONTAMINATION,
        },
        "host": {
            "platform":  platform.system(),
            "cpu_count": psutil.cpu_count(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
