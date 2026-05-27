-- CloudPulse PostgreSQL Schema
-- Run once when setting up the database for the first time.
-- SQLAlchemy will also auto-create these via create_tables() on startup.

-- =============================================
-- Table 1: system_metrics
-- Stores every metric snapshot from the agent
-- =============================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id              SERIAL PRIMARY KEY,

    -- CPU
    cpu_percent     FLOAT       NOT NULL,
    cpu_count       INTEGER,
    cpu_freq_mhz    FLOAT,

    -- RAM
    ram_total_gb    FLOAT,
    ram_used_gb     FLOAT,
    ram_percent     FLOAT       NOT NULL,

    -- Disk
    disk_total_gb   FLOAT,
    disk_used_gb    FLOAT,
    disk_percent    FLOAT       NOT NULL,
    disk_read_mb    FLOAT,
    disk_write_mb   FLOAT,

    -- Network
    net_bytes_sent_mb   FLOAT,
    net_bytes_recv_mb   FLOAT,
    net_packets_sent    INTEGER,
    net_packets_recv    INTEGER,

    -- System info
    hostname        VARCHAR(255),
    platform        VARCHAR(100),

    -- Top processes snapshot (JSON array)
    top_processes   JSONB       DEFAULT '[]',

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index on created_at for fast time-range queries
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON system_metrics(created_at DESC);

-- =============================================
-- Table 2: anomalies
-- AI-detected metric anomalies (Isolation Forest)
-- =============================================
CREATE TABLE IF NOT EXISTS anomalies (
    id              SERIAL PRIMARY KEY,
    metric_type     VARCHAR(50)  NOT NULL,   -- cpu, ram, disk, network, multi
    anomaly_score   FLOAT        NOT NULL,   -- negative = more anomalous
    cpu_percent     FLOAT,
    ram_percent     FLOAT,
    disk_percent    FLOAT,
    net_bytes_recv_mb   FLOAT,
    net_bytes_sent_mb   FLOAT,
    description     VARCHAR(500),
    severity        VARCHAR(20)  DEFAULT 'medium',  -- low/medium/high/critical
    is_resolved     BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_created_at ON anomalies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity   ON anomalies(severity);

-- =============================================
-- Table 3: alerts
-- Threshold-based alerts (CPU > 85%, RAM > 85%)
-- =============================================
CREATE TABLE IF NOT EXISTS alerts (
    id              SERIAL PRIMARY KEY,
    alert_type      VARCHAR(50)  NOT NULL,   -- cpu_high, ram_high, disk_high
    message         VARCHAR(500) NOT NULL,
    metric_value    FLOAT        NOT NULL,   -- value that triggered alert
    threshold_value FLOAT        NOT NULL,   -- configured threshold
    severity        VARCHAR(20)  DEFAULT 'warning',  -- warning/critical
    is_read         BOOLEAN      DEFAULT FALSE,
    is_resolved     BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_is_read    ON alerts(is_read);

-- =============================================
-- Sample view: daily metric averages
-- =============================================
CREATE OR REPLACE VIEW daily_metric_averages AS
SELECT
    DATE_TRUNC('hour', created_at)  AS hour,
    AVG(cpu_percent)::NUMERIC(5,2)  AS avg_cpu,
    AVG(ram_percent)::NUMERIC(5,2)  AS avg_ram,
    AVG(disk_percent)::NUMERIC(5,2) AS avg_disk,
    MAX(cpu_percent)::NUMERIC(5,2)  AS max_cpu,
    MAX(ram_percent)::NUMERIC(5,2)  AS max_ram,
    COUNT(*)                        AS sample_count
FROM system_metrics
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;
