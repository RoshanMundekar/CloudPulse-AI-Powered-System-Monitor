"""
ML Router — model management and inference endpoints.

GET  /api/ml/status           → model metadata, feature stats, last retrain result
POST /api/ml/retrain          → trigger model retraining (protected, non-blocking)
POST /api/ml/predict          → single-point anomaly inference with feature explanation
GET  /api/ml/anomalies/stats  → anomaly distribution (count by severity and metric type)

Why a dedicated /api/ml router?
  Separating ML concerns from the /api/metrics/* CRUD router keeps each router
  small and focused. The ML router is also useful for viva demonstrations:
  you can call /api/ml/predict from the Swagger UI and see in real time which
  feature (cpu/ram/disk/network) is driving the anomaly detection.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, HTTPException

from app.dependencies import DBSession, AgentAuth
from app.ml.anomaly_detector import anomaly_detector
from app.ml.model_trainer import trigger_retrain, get_last_retrain_result
from app.models.anomalies import Anomaly
from app.schemas.ml import (
    AnomalyStats,
    FeatureContribution,
    ModelStatus,
    PredictionRequest,
    PredictionResponse,
    RetrainResponse,
)
from sqlalchemy import select

router = APIRouter(prefix="/api/ml", tags=["ML / AI"])


@router.get("/status", response_model=ModelStatus)
async def get_model_status():
    """
    Returns current model metadata: version, training timestamp, sample count,
    per-feature means/stds, and the anomaly score distribution from the last training run.
    Also includes the result of the most recent retrain operation.
    """
    status = anomaly_detector.get_status()
    return ModelStatus(
        is_trained=status["is_trained"],
        metadata=status["metadata"] if status["is_trained"] else None,
        last_retrain_result=get_last_retrain_result() or None,
    )


@router.post("/retrain", response_model=RetrainResponse)
async def manual_retrain(_auth: AgentAuth):
    """
    Manually trigger model retraining using the last 24 hours of metric data.

    - Protected by the agent API key (set AGENT_API_KEY env var; empty = open in dev)
    - Returns immediately with "already_running" if a retrain is in progress
    - The actual training happens in a thread pool (non-blocking)
    - After training, the new model is automatically used for all future predictions
    """
    result = await trigger_retrain()
    return RetrainResponse(
        status=result.get("status", "unknown"),
        samples=result.get("samples"),
        elapsed_seconds=result.get("elapsed_seconds"),
        retrained_at=result.get("retrained_at") or result.get("trained_at"),
        message=result.get("reason") or result.get("message"),
    )


@router.post("/predict", response_model=PredictionResponse)
async def predict_anomaly(payload: PredictionRequest):
    """
    Run anomaly detection on a single metric snapshot.

    Returns:
      - is_anomaly: bool
      - anomaly_score: float (negative values indicate anomaly)
      - severity: normal / low / medium / high / critical
      - dominant_feature: which feature contributed most to the anomaly
      - top_features: top 5 feature contributions with z-scores and actual values

    This endpoint is useful for:
      - Testing the model interactively from Swagger UI
      - Viva demonstrations (show which feature triggers the alert)
      - Building a "what-if" tool in the frontend
    """
    if not anomaly_detector.is_trained:
        raise HTTPException(
            status_code=503,
            detail=(
                "Model is not yet trained. "
                "POST metrics to /api/metrics/ first (or run sample_data.py), "
                "then call POST /api/ml/retrain."
            ),
        )

    metric            = payload.model_dump()
    is_anomaly, score, details = anomaly_detector.predict(metric)

    # Map score to human-readable severity (same thresholds as anomaly_service)
    if not is_anomaly:
        severity = "normal"
    elif score > -0.2:
        severity = "low"
    elif score > -0.4:
        severity = "medium"
    elif score > -0.6:
        severity = "high"
    else:
        severity = "critical"

    # Build feature contribution objects for the response
    contributions   = details.get("contributions", {})
    z_scores        = details.get("z_scores", {})
    values          = details.get("values", {})

    sorted_features = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    top_features = [
        FeatureContribution(
            feature=feat,
            contribution=round(contrib, 4),
            value=round(values.get(feat, 0) or 0, 4),
            z_score=round(abs(z_scores.get(feat, 0)), 4),
        )
        for feat, contrib in sorted_features[:5]
    ]

    dominant = details.get("dominant_feature")
    message  = (
        f"Anomaly detected — {dominant} is the primary driver (score={score:.4f})"
        if is_anomaly
        else f"Normal operation (score={score:.4f})"
    )

    return PredictionResponse(
        is_anomaly=is_anomaly,
        anomaly_score=score,
        severity=severity,
        dominant_feature=dominant,
        top_features=top_features,
        message=message,
    )


@router.get("/anomalies/stats", response_model=AnomalyStats)
async def get_anomaly_stats(
    db:    DBSession,
    hours: int = Query(default=24, ge=1, le=168, description="Look-back window in hours"),
):
    """
    Aggregated anomaly statistics for the given time window.
    Returns total count, breakdown by severity (low/medium/high/critical),
    and breakdown by metric type (which feature triggered each anomaly).

    Useful for the Analytics page to show anomaly distribution charts.
    """
    since  =  datetime.now(UTC) - timedelta(hours=hours)
    result = await db.execute(
        select(Anomaly).where(Anomaly.created_at >= since)
    )
    rows = result.scalars().all()

    by_severity: dict[str, int] = {}
    by_type:     dict[str, int] = {}

    for row in rows:
        by_severity[row.severity]   = by_severity.get(row.severity, 0)   + 1
        by_type[row.metric_type]    = by_type.get(row.metric_type, 0)    + 1

    return AnomalyStats(
        total=len(rows),
        by_severity=by_severity,
        by_type=by_type,
        hours=hours,
    )
