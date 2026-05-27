"""
Alert Model — threshold-based alerts (CPU > 85%, RAM > 85%, etc.)
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)

    # Alert type: cpu_high, ram_high, disk_high, network_spike
    alert_type = Column(String(50), nullable=False)

    # Message shown to user
    message = Column(String(500), nullable=False)

    # Actual value that triggered the alert
    metric_value = Column(Float, nullable=False)

    # Threshold that was breached
    threshold_value = Column(Float, nullable=False)

    # Severity: warning, critical
    severity = Column(String(20), default="warning")

    # Whether alert has been read/dismissed
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
