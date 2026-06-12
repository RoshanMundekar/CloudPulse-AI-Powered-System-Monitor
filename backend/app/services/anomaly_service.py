"""
Anomaly Service — persists and queries AI-detected anomalies.

save_anomaly() accepts the full `details` dict from anomaly_detector.predict()
so it can:
  - set metric_type to the dominant feature (e.g. "cpu_percent", "net_total_mb")
  - build a richer description showing per-feature z-scores for the viva log
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomalies import Anomaly
from app.schemas.anomalies import AnomalyUpdate


def _score_to_severity(score: float) -> str:
    """
    Map Isolation Forest score to a human-readable severity level.
    Scores are negative; more negative = more anomalous.
    Thresholds tuned to match ~5% contamination rate (default settings).
    """
    if score < -0.6:
        return "critical"
    if score < -0.4:
        return "high"
    if score < -0.2:
        return "medium"
    return "low"


def _build_description(metric: dict, details: dict) -> str:
    """
    Build a human-readable description listing the top 3 contributing features
    with their actual values and z-scores.

    Example output:
      "Anomaly — cpu_percent=94.2% (z=3.8), ram_percent=57.1% (z=0.3), net_total_mb=0.0 (z=0.1)"
    """
    contribs = details.get("contributions", {})
    z_scores = details.get("z_scores", {})
    values   = details.get("values", {})

    top = sorted(contribs.items(), key=lambda x: x[1], reverse=True)[:3]

    parts = []
    for feat, _ in top:
        val = values.get(feat, metric.get(feat, 0) or 0)
        z   = abs(z_scores.get(feat, 0))
        # Format as percentage for utilization features, plain for MB features
        if feat.endswith("_percent") or feat == "cpu_ram_pressure":
            parts.append(f"{feat}={val:.1f}% (z={z:.2f})")
        else:
            parts.append(f"{feat}={val:.1f} (z={z:.2f})")

    dominant = details.get("dominant_feature", "multi")
    return f"Anomaly [{dominant}] — " + ", ".join(parts)


class AnomalyService:

    async def save_anomaly(
        self,
        db:     AsyncSession,
        metric: dict,
        score:  float,
        details: dict,
    ) -> Anomaly:
        """
        Persist a detected anomaly with enriched metadata.

        Args:
            metric:  raw metric dict (with cpu_percent, ram_percent, etc.)
            score:   anomaly score from Isolation Forest (negative = anomalous)
            details: the full details dict returned by anomaly_detector.predict()
                     containing contributions, z_scores, values, dominant_feature
        """
        severity     = _score_to_severity(score)
        metric_type  = details.get("dominant_feature") or "multi"
        description  = _build_description(metric, details)

        anomaly = Anomaly(
            metric_type=metric_type,
            anomaly_score=round(score, 6),
            cpu_percent=metric.get("cpu_percent"),
            ram_percent=metric.get("ram_percent"),
            disk_percent=metric.get("disk_percent"),
            net_bytes_recv_mb=metric.get("net_bytes_recv_mb"),
            net_bytes_sent_mb=metric.get("net_bytes_sent_mb"),
            description=description,
            severity=severity,
        )
        db.add(anomaly)
        await db.flush()    # assigns anomaly.id without committing
        await db.refresh(anomaly)
        return anomaly

    async def get_anomalies(
        self, db: AsyncSession, hours: int = 24, limit: int = 100
    ) -> list[Anomaly]:
        since  =  datetime.now(UTC)- timedelta(hours=hours)
        result = await db.execute(
            select(Anomaly)
            .where(Anomaly.created_at >= since)
            .order_by(desc(Anomaly.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def update_anomaly(
        self, db: AsyncSession, anomaly_id: int, data: AnomalyUpdate
    ) -> Anomaly | None:
        result  = await db.execute(select(Anomaly).where(Anomaly.id == anomaly_id))
        anomaly = result.scalar_one_or_none()
        if not anomaly:
            return None
        anomaly.is_resolved = data.is_resolved
        await db.flush()
        await db.refresh(anomaly)
        return anomaly

    async def get_recent_count(self, db: AsyncSession, hours: int = 1) -> int:
        since  =  datetime.now(UTC) - timedelta(hours=hours)
        result = await db.execute(
            select(func.count()).select_from(Anomaly).where(Anomaly.created_at >= since)
        )
        return result.scalar_one()


anomaly_service = AnomalyService()
