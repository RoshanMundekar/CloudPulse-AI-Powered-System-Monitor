"""
Anomaly Model — stores AI-detected anomalies from Isolation Forest.
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)

    # Which metric triggered the anomaly
    metric_type = Column(String(50), nullable=False)  # cpu, ram, disk, network

    # Anomaly score from Isolation Forest (-1 = anomaly, closer to -1 = more anomalous)
    anomaly_score = Column(Float, nullable=False)

    # The actual metric values at time of anomaly
    cpu_percent = Column(Float)
    ram_percent = Column(Float)
    disk_percent = Column(Float)
    net_bytes_recv_mb = Column(Float)
    net_bytes_sent_mb = Column(Float)

    # Human-readable description
    description = Column(String(500))

    # Severity: low, medium, high, critical
    severity = Column(String(20), default="medium")

    # Whether user has acknowledged/resolved this anomaly
    is_resolved = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
