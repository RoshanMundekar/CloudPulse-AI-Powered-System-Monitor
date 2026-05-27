"""
Alerts Router — CRUD for threshold-based alerts.

GET  /api/alerts/          → list all (or unread-only)
GET  /api/alerts/count     → unread count badge
PATCH /api/alerts/{id}     → mark read / resolve
POST /api/alerts/mark-all-read → bulk dismiss
"""
from fastapi import APIRouter, Query, Path, HTTPException
from app.dependencies import DBSession
from app.schemas.alerts import AlertResponse, AlertUpdate
from app.services.alert_service import alert_service

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    db:          DBSession,
    unread_only: bool = Query(default=False),
    limit:       int  = Query(default=50, ge=1, le=200),
):
    return await alert_service.get_alerts(db, unread_only=unread_only, limit=limit)


@router.get("/count")
async def unread_count(db: DBSession):
    count = await alert_service.get_unread_count(db)
    return {"unread_count": count}


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    db:       DBSession,
    data:     AlertUpdate,
    alert_id: int = Path(..., gt=0),
):
    alert = await alert_service.update_alert(db, alert_id, data)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/mark-all-read")
async def mark_all_read(db: DBSession):
    await alert_service.mark_all_read(db)
    return {"status": "ok"}
