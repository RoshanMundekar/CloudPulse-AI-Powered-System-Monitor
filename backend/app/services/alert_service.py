"""
Alert Service — checks metric thresholds and creates alerts.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from datetime import datetime, timedelta
from app.models.alerts import Alert
from app.schemas.alerts import AlertUpdate
from app.config import settings


class AlertService:

    async def check_and_create_alerts(
        self, db: AsyncSession, metric: dict
    ) -> list[Alert]:
        """
        Called every time a new metric arrives.
        Creates alert rows when any metric exceeds its threshold.
        """
        new_alerts = []

        checks = [
            ("cpu_high", "CPU Usage", metric.get("cpu_percent", 0),
             settings.CPU_ALERT_THRESHOLD, "warning" if metric.get("cpu_percent", 0) < 95 else "critical"),
            ("ram_high", "RAM Usage", metric.get("ram_percent", 0),
             settings.RAM_ALERT_THRESHOLD, "warning" if metric.get("ram_percent", 0) < 95 else "critical"),
            ("disk_high", "Disk Usage", metric.get("disk_percent", 0),
             settings.DISK_ALERT_THRESHOLD, "critical"),
        ]

        for alert_type, label, value, threshold, severity in checks:
            if value >= threshold:
                # Avoid duplicate alerts — skip if same type fired in last 5 min
                existing = await db.execute(
                    select(Alert)
                    .where(Alert.alert_type == alert_type)
                    .where(Alert.is_resolved == False)
                    .where(Alert.created_at >= datetime.utcnow() - timedelta(minutes=5))
                    .limit(1)
                )
                if existing.scalar_one_or_none():
                    continue

                alert = Alert(
                    alert_type=alert_type,
                    message=f"{label} is critically high: {value:.1f}% (threshold: {threshold}%)",
                    metric_value=value,
                    threshold_value=threshold,
                    severity=severity,
                )
                db.add(alert)
                new_alerts.append(alert)

        if new_alerts:
            await db.commit()
            for a in new_alerts:
                await db.refresh(a)

        return new_alerts

    async def get_alerts(
        self, db: AsyncSession, unread_only: bool = False, limit: int = 50
    ) -> list[Alert]:
        query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
        if unread_only:
            query = query.where(Alert.is_read == False)
        result = await db.execute(query)
        return result.scalars().all()

    async def update_alert(
        self, db: AsyncSession, alert_id: int, data: AlertUpdate
    ) -> Alert | None:
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            return None

        if data.is_read is not None:
            alert.is_read = data.is_read
        if data.is_resolved is not None:
            alert.is_resolved = data.is_resolved
            if data.is_resolved:
                alert.resolved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(alert)
        return alert

    async def mark_all_read(self, db: AsyncSession):
        await db.execute(
            update(Alert).where(Alert.is_read == False).values(is_read=True)
        )
        await db.commit()

    async def get_unread_count(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(Alert).where(Alert.is_read == False)
        )
        return len(result.scalars().all())


alert_service = AlertService()
