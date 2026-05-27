"""
Pydantic schemas for Alert model.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    message: str
    metric_value: float
    threshold_value: float
    severity: str
    is_read: bool
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_resolved: Optional[bool] = None
