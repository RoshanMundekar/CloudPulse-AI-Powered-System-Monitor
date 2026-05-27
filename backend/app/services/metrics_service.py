"""
CloudPulse — Metrics Service

Handles:
  - Persisting metrics to PostgreSQL (async)
  - Updating Redis cache in one pipeline call
  - Time-range history queries
  - Aggregation (averages, min/max, hourly buckets)
  - Pagination for the /api/metrics/ list endpoint
  - Data retention cleanup
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, text
from datetime import datetime, timedelta, timezone
from app.models.metrics import SystemMetric
from app.schemas.metrics import MetricCreate, MetricAverages, HourlyBucket
from app.services.redis_service import redis_service
import logging

log = logging.getLogger("cloudpulse.metrics_svc")


class MetricsService:

    # ── Write path ────────────────────────────────────────────────────────────

    async def save_metric(self, db: AsyncSession, data: MetricCreate) -> SystemMetric:
        """
        1. Insert row into PostgreSQL
        2. Cache latest + push to sparkline list (single Redis pipeline)
        """
        metric = SystemMetric(**data.model_dump())
        db.add(metric)
        await db.flush()      # get the auto-generated id without a full commit
        await db.refresh(metric)

        # Build the cache payload using the model helper
        payload = metric.to_summary_dict()

        # Single pipeline call: setex + lpush + ltrim
        await redis_service.cache_metric_batch(payload)

        return metric

    # ── Read path — latest ────────────────────────────────────────────────────

    async def get_latest(self, db: AsyncSession) -> dict | SystemMetric | None:
        """
        Redis-first read.  Falls back to DB only if the cache is cold
        (first request, or Redis restarted with empty cache).
        """
        cached = await redis_service.get_latest_metric()
        if cached:
            return cached

        result = await db.execute(
            select(SystemMetric).order_by(desc(SystemMetric.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    # ── Read path — history ───────────────────────────────────────────────────

    async def get_history(
        self,
        db: AsyncSession,
        hours: int = 1,
        limit: int = 500,
        offset: int = 0,
        hostname: str | None = None,
    ) -> list[SystemMetric]:
        """
        Returns metric rows in chronological order for chart rendering.
        Supports optional hostname filter for future multi-host scenarios.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            select(SystemMetric)
            .where(SystemMetric.created_at >= since)
            .order_by(desc(SystemMetric.created_at))
            .offset(offset)
            .limit(limit)
        )
        if hostname:
            query = query.where(SystemMetric.hostname == hostname)

        result = await db.execute(query)
        rows = result.scalars().all()
        return list(reversed(rows))    # oldest first for Recharts

    async def count_in_window(self, db: AsyncSession, hours: int) -> int:
        """Total samples in the last N hours — used for pagination metadata."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(func.count(SystemMetric.id))
            .where(SystemMetric.created_at >= since)
        )
        return result.scalar_one() or 0

    # ── Read path — single row ────────────────────────────────────────────────

    async def get_by_id(self, db: AsyncSession, metric_id: int) -> SystemMetric | None:
        result = await db.execute(
            select(SystemMetric).where(SystemMetric.id == metric_id)
        )
        return result.scalar_one_or_none()

    # ── Aggregation: averages ─────────────────────────────────────────────────

    async def get_averages(self, db: AsyncSession, hours: int = 24) -> MetricAverages:
        """
        Single-query aggregation:  avg, min, max for CPU and RAM,
        avg for disk, total sample count.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(
                func.avg(SystemMetric.cpu_percent).label("avg_cpu"),
                func.avg(SystemMetric.ram_percent).label("avg_ram"),
                func.avg(SystemMetric.disk_percent).label("avg_disk"),
                func.max(SystemMetric.cpu_percent).label("max_cpu"),
                func.max(SystemMetric.ram_percent).label("max_ram"),
                func.min(SystemMetric.cpu_percent).label("min_cpu"),
                func.min(SystemMetric.ram_percent).label("min_ram"),
                func.count(SystemMetric.id).label("sample_count"),
            ).where(SystemMetric.created_at >= since)
        )
        row = result.one()
        return MetricAverages(
            avg_cpu      = round(row.avg_cpu      or 0, 2),
            avg_ram      = round(row.avg_ram      or 0, 2),
            avg_disk     = round(row.avg_disk     or 0, 2),
            max_cpu      = round(row.max_cpu      or 0, 2),
            max_ram      = round(row.max_ram      or 0, 2),
            min_cpu      = round(row.min_cpu      or 0, 2),
            min_ram      = round(row.min_ram      or 0, 2),
            sample_count = row.sample_count or 0,
            period_hours = hours,
        )

    # ── Aggregation: hourly buckets ────────────────────────────────────────────

    async def get_hourly_buckets(
        self, db: AsyncSession, hours: int = 24
    ) -> list[HourlyBucket]:
        """
        Groups metrics into 1-hour buckets with avg/max.
        Useful for the Analytics page bar chart that shows 24 bars.

        Uses PostgreSQL DATE_TRUNC — this is a native SQL aggregation,
        not Python-level grouping, so it's very fast even on large tables.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            text("""
                SELECT
                    DATE_TRUNC('hour', created_at)  AS hour,
                    AVG(cpu_percent)::FLOAT         AS avg_cpu,
                    AVG(ram_percent)::FLOAT         AS avg_ram,
                    AVG(disk_percent)::FLOAT        AS avg_disk,
                    MAX(cpu_percent)::FLOAT         AS max_cpu,
                    MAX(ram_percent)::FLOAT         AS max_ram,
                    COUNT(*)                        AS sample_count
                FROM system_metrics
                WHERE created_at >= :since
                GROUP BY DATE_TRUNC('hour', created_at)
                ORDER BY hour ASC
            """),
            {"since": since},
        )
        rows = result.fetchall()
        return [
            HourlyBucket(
                hour         = row.hour,
                avg_cpu      = round(row.avg_cpu  or 0, 2),
                avg_ram      = round(row.avg_ram  or 0, 2),
                avg_disk     = round(row.avg_disk or 0, 2),
                max_cpu      = round(row.max_cpu  or 0, 2),
                max_ram      = round(row.max_ram  or 0, 2),
                sample_count = row.sample_count or 0,
            )
            for row in rows
        ]

    # ── Sparkline (Redis) ─────────────────────────────────────────────────────

    async def get_sparkline(self) -> list[dict]:
        """Last 60 snapshots from Redis — no DB touch."""
        return await redis_service.get_metric_history()

    # ── Data retention ────────────────────────────────────────────────────────

    async def purge_old_metrics(self, db: AsyncSession, older_than_days: int = 7) -> int:
        """
        Deletes rows older than N days.
        Call this from a scheduled background task to keep the table lean.
        Returns the number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        result = await db.execute(
            text("DELETE FROM system_metrics WHERE created_at < :cutoff RETURNING id"),
            {"cutoff": cutoff},
        )
        deleted = len(result.fetchall())
        await db.commit()
        log.info(f"Purged {deleted} metric rows older than {older_than_days} days.")
        return deleted


metrics_service = MetricsService()
