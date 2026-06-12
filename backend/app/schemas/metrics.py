"""
Pydantic schemas for SystemMetric — request validation + response serialisation.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


# ── Inbound (agent → API) ─────────────────────────────────────────────────────

class MetricCreate(BaseModel):
    """Validates the JSON body from the monitoring agent."""

    cpu_percent:  float = Field(..., ge=0, le=100, description="CPU utilisation %")
    cpu_count:    Optional[int]   = None
    cpu_freq_mhz: Optional[float] = None

    ram_total_gb: Optional[float] = None
    ram_used_gb:  Optional[float] = None
    ram_percent:  float = Field(..., ge=0, le=100)

    disk_total_gb: Optional[float] = None
    disk_used_gb:  Optional[float] = None
    disk_percent:  float = Field(..., ge=0, le=100)
    disk_read_mb:  Optional[float] = None
    disk_write_mb: Optional[float] = None

    net_bytes_sent_mb: Optional[float] = None
    net_bytes_recv_mb: Optional[float] = None
    net_packets_sent:  Optional[int]   = None
    net_packets_recv:  Optional[int]   = None

    hostname: Optional[str] = None
    platform: Optional[str] = None
    top_processes: Optional[List[dict]] = []


# ── Outbound (API → client) ───────────────────────────────────────────────────

class MetricResponse(MetricCreate):
    """Full metric row as returned by POST /api/metrics/ and GET /api/metrics/{id}."""
    id:         int
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricSummary(BaseModel):
    """
    Lightweight projection for history and sparkline endpoints.
    Keeps the response payload small (no process list).
    """
    cpu_percent:       float
    ram_percent:       float
    disk_percent:      float
    disk_read_mb:      Optional[float] = None   # Disk I/O chart
    disk_write_mb:     Optional[float] = None   # Disk I/O chart
    net_bytes_recv_mb: Optional[float] = None
    net_bytes_sent_mb: Optional[float] = None
    created_at:        datetime

    model_config = {"from_attributes": True}



# ── Aggregation response ──────────────────────────────────────────────────────

class MetricAverages(BaseModel):
    avg_cpu:      float
    avg_ram:      float
    avg_disk:     float
    max_cpu:      float
    max_ram:      float
    min_cpu:      float
    min_ram:      float
    sample_count: int
    period_hours: int


class HourlyBucket(BaseModel):
    """One data point in the hourly-aggregated chart."""
    hour:       datetime
    avg_cpu:    float
    avg_ram:    float
    avg_disk:   float
    max_cpu:    float
    max_ram:    float
    sample_count: int


# ── Paginated response wrapper ────────────────────────────────────────────────

class PaginatedMetrics(BaseModel):
    total:   int
    page:    int
    size:    int
    items:   List[MetricSummary]
