"""
Anomalies Router — query and manage AI-detected anomalies.

GET   /api/anomalies/       → paginated list
GET   /api/anomalies/count  → recent anomaly count
PATCH /api/anomalies/{id}   → resolve anomaly
"""
from fastapi import APIRouter, Query, Path, HTTPException
from app.dependencies import DBSession
from app.schemas.anomalies import AnomalyResponse, AnomalyUpdate
from app.services.anomaly_service import anomaly_service

router = APIRouter(prefix="/api/anomalies", tags=["Anomalies"])


@router.get("/", response_model=list[AnomalyResponse])
async def list_anomalies(
    db:    DBSession,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
):
    return await anomaly_service.get_anomalies(db, hours=hours, limit=limit)


@router.get("/count")
async def recent_count(
    db:    DBSession,
    hours: int = Query(default=1, ge=1, le=168),
):
    count = await anomaly_service.get_recent_count(db, hours=hours)
    return {"count": count, "hours": hours}


@router.patch("/{anomaly_id}", response_model=AnomalyResponse)
async def update_anomaly(
    db:         DBSession,
    data:       AnomalyUpdate,
    anomaly_id: int = Path(..., gt=0),
):
    anomaly = await anomaly_service.update_anomaly(db, anomaly_id, data)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly
