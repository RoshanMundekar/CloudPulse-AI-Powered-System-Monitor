from app.routers.metrics   import router as metrics_router
from app.routers.alerts    import router as alerts_router
from app.routers.anomalies import router as anomalies_router
from app.routers.websocket import router as ws_router
from app.routers.system    import router as system_router
from app.routers.ml        import router as ml_router

__all__ = [
    "metrics_router",
    "alerts_router",
    "anomalies_router",
    "ws_router",
    "system_router",
    "ml_router",
]
