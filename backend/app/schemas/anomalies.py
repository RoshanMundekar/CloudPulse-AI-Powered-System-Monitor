"""
Pydantic schemas for Anomaly model.
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AnomalyResponse(BaseModel):
    id: int
    metric_type: str
    anomaly_score: float
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    disk_percent: Optional[float]
    net_bytes_recv_mb: Optional[float]
    net_bytes_sent_mb: Optional[float]
    description: Optional[str]
    severity: str
    is_resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnomalyUpdate(BaseModel):
    is_resolved: bool
