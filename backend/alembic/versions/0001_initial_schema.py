"""Initial schema — system_metrics, anomalies, alerts

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision      = "0001"
down_revision = None
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── system_metrics ───────────────────────────────────────────────────────
    op.create_table(
        "system_metrics",
        sa.Column("id",                sa.Integer(),            nullable=False),
        sa.Column("cpu_percent",       sa.Float(),              nullable=False),
        sa.Column("cpu_count",         sa.Integer(),            nullable=True),
        sa.Column("cpu_freq_mhz",      sa.Float(),              nullable=True),
        sa.Column("ram_total_gb",      sa.Float(),              nullable=True),
        sa.Column("ram_used_gb",       sa.Float(),              nullable=True),
        sa.Column("ram_percent",       sa.Float(),              nullable=False),
        sa.Column("disk_total_gb",     sa.Float(),              nullable=True),
        sa.Column("disk_used_gb",      sa.Float(),              nullable=True),
        sa.Column("disk_percent",      sa.Float(),              nullable=False),
        sa.Column("disk_read_mb",      sa.Float(),              nullable=True),
        sa.Column("disk_write_mb",     sa.Float(),              nullable=True),
        sa.Column("net_bytes_sent_mb", sa.Float(),              nullable=True),
        sa.Column("net_bytes_recv_mb", sa.Float(),              nullable=True),
        sa.Column("net_packets_sent",  sa.Integer(),            nullable=True),
        sa.Column("net_packets_recv",  sa.Integer(),            nullable=True),
        sa.Column("hostname",          sa.String(255),          nullable=True),
        sa.Column("platform",          sa.String(100),          nullable=True),
        sa.Column("top_processes",     postgresql.JSONB(),      nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_created_at_desc", "system_metrics", [sa.text("created_at DESC")])
    op.create_index("ix_metrics_hostname_time",   "system_metrics", ["hostname", sa.text("created_at DESC")])
    op.create_index("ix_system_metrics_hostname",  "system_metrics", ["hostname"])

    # ── anomalies ────────────────────────────────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column("id",                 sa.Integer(),  nullable=False),
        sa.Column("metric_type",        sa.String(50), nullable=False),
        sa.Column("anomaly_score",      sa.Float(),    nullable=False),
        sa.Column("cpu_percent",        sa.Float(),    nullable=True),
        sa.Column("ram_percent",        sa.Float(),    nullable=True),
        sa.Column("disk_percent",       sa.Float(),    nullable=True),
        sa.Column("net_bytes_recv_mb",  sa.Float(),    nullable=True),
        sa.Column("net_bytes_sent_mb",  sa.Float(),    nullable=True),
        sa.Column("description",        sa.String(500), nullable=True),
        sa.Column("severity",           sa.String(20), server_default="medium"),
        sa.Column("is_resolved",        sa.Boolean(),  server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomalies_created_at", "anomalies", [sa.text("created_at DESC")])
    op.create_index("ix_anomalies_severity",   "anomalies", ["severity"])

    # ── alerts ───────────────────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id",              sa.Integer(),   nullable=False),
        sa.Column("alert_type",      sa.String(50),  nullable=False),
        sa.Column("message",         sa.String(500), nullable=False),
        sa.Column("metric_value",    sa.Float(),     nullable=False),
        sa.Column("threshold_value", sa.Float(),     nullable=False),
        sa.Column("severity",        sa.String(20),  server_default="warning"),
        sa.Column("is_read",         sa.Boolean(),   server_default="false"),
        sa.Column("is_resolved",     sa.Boolean(),   server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at",     sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_created_at", "alerts", [sa.text("created_at DESC")])
    op.create_index("ix_alerts_is_read",    "alerts", ["is_read"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("anomalies")
    op.drop_table("system_metrics")
