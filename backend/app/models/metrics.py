"""
SystemMetric — one row per monitoring agent collection cycle (every 5 s).

Index strategy:
  - created_at DESC  → time-range queries (history, averages)
  - (hostname, created_at) → future multi-host filtering
"""
from sqlalchemy import (
    Column, Integer, Float, String, DateTime, JSON, Index
)
from sqlalchemy.sql import func
from app.database import Base


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # ── CPU ──────────────────────────────────────────────────────────────────
    cpu_percent  = Column(Float,   nullable=False)
    cpu_count    = Column(Integer, nullable=True)
    cpu_freq_mhz = Column(Float,   nullable=True)

    # ── Memory / RAM ─────────────────────────────────────────────────────────
    ram_total_gb = Column(Float, nullable=True)
    ram_used_gb  = Column(Float, nullable=True)
    ram_percent  = Column(Float, nullable=False)

    # ── Disk ─────────────────────────────────────────────────────────────────
    disk_total_gb = Column(Float, nullable=True)
    disk_used_gb  = Column(Float, nullable=True)
    disk_percent  = Column(Float, nullable=False)
    disk_read_mb  = Column(Float, nullable=True)
    disk_write_mb = Column(Float, nullable=True)

    # ── Network ──────────────────────────────────────────────────────────────
    net_bytes_sent_mb = Column(Float,   nullable=True)
    net_bytes_recv_mb = Column(Float,   nullable=True)
    net_packets_sent  = Column(Integer, nullable=True)
    net_packets_recv  = Column(Integer, nullable=True)

    # ── System info ──────────────────────────────────────────────────────────
    hostname = Column(String(255), nullable=True, index=True)
    platform = Column(String(100), nullable=True)

    # ── Top processes snapshot ────────────────────────────────────────────────
    top_processes = Column(JSON, default=list, nullable=True)

    # ── Timestamp ────────────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Composite indexes ────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_metrics_created_at_desc", created_at.desc()),
        Index("ix_metrics_hostname_time",   "hostname", created_at.desc()),
    )

    def to_summary_dict(self) -> dict:
        """Lightweight dict used for Redis caching and WS broadcasts."""
        return {
            "cpu_percent":        self.cpu_percent,
            "ram_percent":        self.ram_percent,
            "disk_percent":       self.disk_percent,
            "net_bytes_recv_mb":  self.net_bytes_recv_mb  or 0,
            "net_bytes_sent_mb":  self.net_bytes_sent_mb  or 0,
            "disk_read_mb":       self.disk_read_mb        or 0,
            "disk_write_mb":      self.disk_write_mb       or 0,
            "top_processes":      self.top_processes       or [],
            "created_at":         self.created_at.isoformat() if self.created_at else None,
        }
