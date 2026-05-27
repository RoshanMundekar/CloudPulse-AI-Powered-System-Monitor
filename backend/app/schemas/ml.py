"""
Pydantic schemas for the ML / AI endpoints (/api/ml/*).
"""
from typing import Optional
from pydantic import BaseModel, Field


class FeatureContribution(BaseModel):
    """Per-feature breakdown of why a data point was flagged as anomalous."""
    feature:      str
    contribution: float   # normalized 0–1: fraction of total deviation this feature caused
    value:        float   # actual (engineered) feature value at prediction time
    z_score:      float   # absolute standard deviations from training mean (higher = more unusual)


class PredictionRequest(BaseModel):
    """Input for the single-point prediction endpoint."""
    cpu_percent:       float = Field(...,        ge=0, le=100, description="CPU utilization %")
    ram_percent:       float = Field(...,        ge=0, le=100, description="RAM utilization %")
    disk_percent:      float = Field(...,        ge=0, le=100, description="Disk utilization %")
    net_bytes_recv_mb: float = Field(default=0.0, ge=0,       description="Inbound MB/s")
    net_bytes_sent_mb: float = Field(default=0.0, ge=0,       description="Outbound MB/s")


class PredictionResponse(BaseModel):
    """Result from /api/ml/predict — includes score, severity, and feature explanation."""
    is_anomaly:       bool
    anomaly_score:    float                    # negative = anomalous (Isolation Forest convention)
    severity:         str                      # normal / low / medium / high / critical
    dominant_feature: Optional[str]           # the feature that contributed most
    top_features:     list[FeatureContribution]  # top 5 features sorted by contribution
    message:          str                      # human-readable summary for dashboards


class ModelMetadata(BaseModel):
    """Training metadata saved in manifest.json and returned by /api/ml/status."""
    version:       str
    trained_at:    str
    sample_count:  int
    contamination: float
    n_estimators:  int
    features:      list[str]
    feature_means: dict[str, float]
    feature_stds:  dict[str, float]
    score_mean:    float
    score_std:     float
    score_min:     float
    score_max:     float


class ModelStatus(BaseModel):
    """Full model status — returned by GET /api/ml/status."""
    is_trained:          bool
    metadata:            Optional[ModelMetadata] = None
    last_retrain_result: Optional[dict]          = None


class RetrainResponse(BaseModel):
    """Result from POST /api/ml/retrain."""
    status:          str
    samples:         Optional[int]   = None
    elapsed_seconds: Optional[float] = None
    retrained_at:    Optional[str]   = None
    message:         Optional[str]   = None


class AnomalyStats(BaseModel):
    """Aggregated anomaly distribution for a time window."""
    total:       int
    by_severity: dict[str, int]   # {"medium": 5, "high": 2, "critical": 1}
    by_type:     dict[str, int]   # {"cpu_percent": 4, "ram_percent": 3, ...}
    hours:       int
