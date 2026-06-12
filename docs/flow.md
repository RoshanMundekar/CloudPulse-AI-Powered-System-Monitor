# CloudPulse — Complete Code Analysis & Flow Documentation
> **Purpose**: This document explains every file in the project — why it exists, what it does, and how all pieces connect together.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture Diagram](#2-system-architecture-diagram)
3. [End-to-End Data Flow](#3-end-to-end-data-flow)
4. [Backend — File-by-File Analysis](#4-backend--file-by-file-analysis)
   - [Entry Point & Configuration](#41-entry-point--configuration)
   - [Database Layer](#42-database-layer)
   - [ORM Models](#43-orm-models)
   - [Pydantic Schemas](#44-pydantic-schemas)
   - [API Routers](#45-api-routers)
   - [Service Layer](#46-service-layer)
   - [AI / ML Layer](#47-ai--ml-layer)
   - [Utilities](#48-utilities)
5. [Agent — File-by-File Analysis](#5-agent--file-by-file-analysis)
6. [Frontend — File-by-File Analysis](#6-frontend--file-by-file-analysis)
   - [Entry Point & App Shell](#61-entry-point--app-shell)
   - [Global State (Context)](#62-global-state-context)
   - [Custom Hooks](#63-custom-hooks)
   - [API Service Layer](#64-api-service-layer)
   - [Pages](#65-pages)
   - [Components](#66-components)
7. [Database Schema](#7-database-schema)
8. [API Reference — All Endpoints](#8-api-reference--all-endpoints)
9. [WebSocket Protocol](#9-websocket-protocol)
10. [AI/ML Pipeline Deep Dive](#10-aiml-pipeline-deep-dive)
11. [Redis Caching Strategy](#11-redis-caching-strategy)
12. [Docker & Deployment](#12-docker--deployment)
13. [Tech Stack Summary](#13-tech-stack-summary)

---

## 1. Project Overview

**CloudPulse** is a real-time AI-powered system monitoring application. It collects live CPU, RAM, Disk, Network, and Process data from the host machine every 5 seconds, stores it in PostgreSQL, detects anomalies using a machine learning model (Isolation Forest), and displays everything on a live React dashboard using WebSockets.

### What Problem Does It Solve?
- Traditional system monitors only show **current** usage — no history, no intelligence.
- CloudPulse adds **AI anomaly detection**: it learns what "normal" looks like and alerts when behavior is unusual.
- **Real-time updates** via WebSocket mean no page refreshes needed — the dashboard updates itself every 5 seconds.

---

## 2. System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         HOST MACHINE (Windows/Linux)                      │
│                                                                            │
│   CPU% | RAM% | Disk% | Network MB/s | Top Processes                      │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │  psutil reads OS metrics every 5 seconds
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    MONITORING AGENT  (agent/)                              │
│                                                                            │
│  monitor.py → collect_all_metrics() → send_metrics() → HTTP POST          │
│  collectors/: cpu | ram | disk | network | process                         │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │  POST /api/metrics/  (JSON body)
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND  (backend/app/)                         │
│                                                                            │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐   │
│  │  REST Routers   │   │  WebSocket /ws   │   │  ML Anomaly Engine   │   │
│  │  /api/metrics   │   │  (live feed)     │   │  Isolation Forest    │   │
│  │  /api/alerts    │   └────────┬─────────┘   └──────────┬───────────┘   │
│  │  /api/anomalies │            │                         │               │
│  │  /api/ml        │            │ ◄── Redis pub/sub ──────┘               │
│  └────────┬────────┘            │                                         │
│           │                     │                                         │
│  ┌────────▼─────────────────────▼──────────────────────────────────────┐ │
│  │                      Services Layer                                  │ │
│  │  metrics_service | alert_service | anomaly_service | redis_service   │ │
│  └────────────────────────────┬─────────────────────────────────────────┘ │
└───────────────────────────────┼──────────────────────────────────────────┘
                                │
          ┌─────────────────────┼────────────────────────┐
          ▼                     ▼                         ▼
┌──────────────────┐  ┌──────────────────┐   ┌─────────────────────────┐
│   PostgreSQL 16  │  │    Redis 7        │   │   WebSocket Broadcast   │
│  system_metrics  │  │  latest_metric   │   │   to all browsers        │
│  anomalies       │  │  metric_history  │   └──────────┬──────────────┘
│  alerts          │  │  pub/sub channel │              │
└──────────────────┘  └──────────────────┘              ▼
                                             ┌──────────────────────────┐
                                             │  REACT DASHBOARD (Vite)  │
                                             │                          │
                                             │  Dashboard | Analytics   │
                                             │  Alerts    | Processes   │
                                             └──────────────────────────┘
```

---

## 3. End-to-End Data Flow

This describes exactly what happens when the agent sends one metric reading:

```
STEP 1: Agent collects metrics (agent/monitor.py)
        cpu=45.2%, ram=67.1%, disk=52%, net_recv=120MB, net_sent=30MB
        top_processes=[{pid:1234, name:"chrome", cpu:12.4%}, ...]

STEP 2: Agent POSTs to backend (agent/sender.py)
        POST http://localhost:8000/api/metrics/
        Body: { "cpu_percent": 45.2, "ram_percent": 67.1, ... }

STEP 3: Backend receives (backend/app/routers/metrics.py)
        → validates JSON with Pydantic (MetricCreate schema)
        → calls metrics_service.save_metric(db, payload)

STEP 4: Persistence (backend/app/services/metrics_service.py)
        → INSERT INTO system_metrics (...) VALUES (...)
        → redis_service.cache_metric_batch(payload)
           - SETEX cloudpulse:metric:latest 10 <json>  (10s TTL cache)
           - LPUSH cloudpulse:metric:history <json>    (rolling list)
           - LTRIM cloudpulse:metric:history 0 59      (keep latest 60)

STEP 5: Concurrent checks (backend/app/routers/metrics.py)
        asyncio.gather runs BOTH at the same time:
        A) alert_service.check_and_create_alerts()
           → if cpu_percent >= 85%: INSERT INTO alerts(...)
        B) anomaly_detector.predict(metric_dict)
           → Isolation Forest scores the data point
           → if is_anomaly: INSERT INTO anomalies(...)

STEP 6: Broadcast to WebSocket clients (background task)
        ws_manager.broadcast({
          "type": "metric",
          "data": { cpu_percent, ram_percent, ... },
          "alerts": [...],   # if any new alerts
          "anomaly": {...}   # if anomaly detected
        })

STEP 7: React Dashboard receives WebSocket message
        MetricsContext.onMetric(data)
        → setCurrent(data)         ← updates all metric cards instantly
        → setHistory(prev + data)  ← chart gains one new point
        → lastUpdated = now        ← header shows "updated just now"

STEP 8: Components re-render
        MetricCard shows new CPU %
        LiveChart adds new point to the area chart
        AlertsPanel shows new alert (if any)
        AnomalyFeed shows new anomaly (if any)
```

---

## 4. Backend — File-by-File Analysis

### 4.1 Entry Point & Configuration

---

#### `backend/app/main.py` — FastAPI Application Entry Point

**Why it exists**: This is the heart of the backend. It creates the FastAPI app, registers all routes, starts background tasks, and manages startup/shutdown.

**What it does**:
```python
# Creates the FastAPI application
app = create_app()

# Startup sequence (runs before accepting requests):
await create_tables()          # Create DB tables if missing
await redis_service.connect()  # Connect to Redis
ws_manager.start_heartbeat()   # Start WebSocket ping loop
asyncio.create_task(retrain_model_task())   # ML retraining loop
asyncio.create_task(pubsub_broadcaster())  # Redis → WebSocket relay
asyncio.create_task(retention_cleanup_task())  # Purge old data
```

**Key functions**:

| Function | Purpose |
|----------|---------|
| `lifespan()` | Async context manager — startup + shutdown sequence |
| `pubsub_broadcaster()` | Subscribes to Redis channel, relays messages to all WebSocket clients |
| `retention_cleanup_task()` | Runs every 6 hours, deletes metrics older than 7 days |
| `create_app()` | Factory function — creates FastAPI, adds CORS, middleware, all routers |

**Why `pubsub_broadcaster` instead of direct broadcast?**
> If we had 3 backend instances (for scalability), each only handles some HTTP requests. Without pub/sub, only the instance that received the POST would broadcast. Publishing to Redis means ALL instances relay the update to ALL their WebSocket clients.

---

#### `backend/app/config.py` — Application Settings

**Why it exists**: Centralizes all configuration. Instead of hardcoding database URLs or thresholds everywhere, they live here and can be overridden by `.env` file.

```python
class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://..."  # Async DB connection
    REDIS_URL: str = "redis://localhost:6379/"
    CPU_ALERT_THRESHOLD: float = 85.0    # Alert when CPU > 85%
    RAM_ALERT_THRESHOLD: float = 85.0
    DISK_ALERT_THRESHOLD: float = 90.0
    MODEL_CONTAMINATION: float = 0.05   # 5% of data expected to be anomalous
    MODEL_RETRAIN_INTERVAL: int = 3600  # Retrain every 60 minutes
    AGENT_API_KEY: str = ""             # Optional security key
```

**`@lru_cache()`** on `get_settings()` means Settings is only parsed once from `.env`, not on every request.

---

#### `backend/app/dependencies.py` — Reusable FastAPI Dependencies

**Why it exists**: Avoids repeating `Depends(get_db)` in every route function. Creates typed aliases.

```python
# Instead of writing this in every route:
db: AsyncSession = Depends(get_db)

# You write this (same effect, cleaner):
DBSession = Annotated[AsyncSession, Depends(get_db)]
```

| Dependency | What it provides |
|------------|-----------------|
| `DBSession` | One async database session per request, auto-commits/rollbacks |
| `Pagination` | `page` and `size` query parameters with offset calculation |
| `AgentAuth` | Validates `X-Agent-Key` header (optional security) |

---

#### `backend/app/middleware.py` — Custom HTTP Middleware

**Why it exists**: Adds cross-cutting concerns (timing, logging) to every request without modifying any route handler.

```python
class RequestTimingMiddleware:
    # Adds header: X-Process-Time: 12.34ms
    # Lets you see slow queries in browser DevTools > Network tab

class RequestLoggingMiddleware:
    # Logs: POST /api/metrics/ 201 12.3ms
    # Skips /health and /ws to avoid log noise
```

---

#### `backend/app/exceptions.py` — Global Exception Handlers

**Why it exists**: Without this, every error returns FastAPI's default format. This makes ALL errors return a consistent JSON shape:
```json
{ "error": "validation_error", "detail": "cpu_percent: must be <= 100", "path": "/api/metrics/" }
```

Handles: `RequestValidationError` (bad input), `SQLAlchemyError` (DB issues), `ValueError`, and any other `Exception`.

---

### 4.2 Database Layer

---

#### `backend/app/database.py` — Async Database Engine

**Why it exists**: Sets up the SQLAlchemy async engine and session factory. This is the bridge between Python and PostgreSQL.

**Key design decisions**:
```python
create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,        # Keep 10 connections open always (fast reuse)
    max_overflow=20,     # Allow 20 extra under high load
    pool_pre_ping=True,  # Test connection before use (avoids stale errors)
    pool_recycle=1800,   # Replace connections every 30 min
)
```

**`get_db()` — The Request Lifecycle**:
```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session       # Route handler runs here
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback() # Auto-rollback on error
            raise
        finally:
            await session.close()   # Always close
```
Every HTTP request gets its own database session, automatically cleaned up.

---

### 4.3 ORM Models

These are Python classes that map to PostgreSQL tables. SQLAlchemy reads/writes rows using these.

---

#### `backend/app/models/metrics.py` — SystemMetric Model

**Maps to table**: `system_metrics`

**Why each column exists**:
```python
class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True)  # Unique row ID

    # CPU columns — from psutil.cpu_percent(), cpu_count(), cpu_freq()
    cpu_percent  = Column(Float, nullable=False)  # REQUIRED for anomaly detection
    cpu_count    = Column(Integer, nullable=True)  # For display in dashboard
    cpu_freq_mhz = Column(Float,   nullable=True)  # Current clock speed

    # RAM columns — from psutil.virtual_memory()
    ram_total_gb = Column(Float, nullable=True)   # For "X / Y GB" display
    ram_used_gb  = Column(Float, nullable=True)
    ram_percent  = Column(Float, nullable=False)   # REQUIRED

    # Disk columns — from psutil.disk_usage() and disk_io_counters()
    disk_total_gb = Column(Float, nullable=True)
    disk_used_gb  = Column(Float, nullable=True)
    disk_percent  = Column(Float, nullable=False)  # REQUIRED
    disk_read_mb  = Column(Float, nullable=True)   # I/O throughput
    disk_write_mb = Column(Float, nullable=True)

    # Network — from psutil.net_io_counters()
    net_bytes_sent_mb = Column(Float,   nullable=True)  # REQUIRED for ML
    net_bytes_recv_mb = Column(Float,   nullable=True)

    hostname = Column(String(255), nullable=True, index=True)  # For multi-host future
    platform = Column(String(100), nullable=True)

    top_processes = Column(JSON, default=list)  # Snapshot of running processes

    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**Composite Indexes** (speed up queries):
```python
Index("ix_metrics_created_at_desc", created_at.desc())    # Fast time-range queries
Index("ix_metrics_hostname_time", "hostname", created_at.desc())  # Multi-host filter
```

**`to_summary_dict()`** — Returns a lightweight dict for Redis and WebSocket (excludes large fields):
```python
def to_summary_dict(self):
    return {
        "cpu_percent": self.cpu_percent,
        "ram_percent": self.ram_percent,
        # ... just the fields the dashboard needs
    }
```

---

#### `backend/app/models/anomalies.py` — Anomaly Model

**Maps to table**: `anomalies`

```python
class Anomaly(Base):
    metric_type   = Column(String(50))   # "cpu_percent" (which feature triggered it)
    anomaly_score = Column(Float)        # e.g. -0.45 (more negative = worse)
    cpu_percent   = Column(Float)        # Snapshot values at time of anomaly
    ram_percent   = Column(Float)
    disk_percent  = Column(Float)
    description   = Column(String(500)) # "Anomaly [cpu_percent] — cpu=94.2% (z=3.8)"
    severity      = Column(String(20))  # "low" / "medium" / "high" / "critical"
    is_resolved   = Column(Boolean, default=False)  # User can mark as resolved
```

---

#### `backend/app/models/alerts.py` — Alert Model

**Maps to table**: `alerts`

```python
class Alert(Base):
    alert_type      = Column(String(50))   # "cpu_high", "ram_high", "disk_high"
    message         = Column(String(500)) # "CPU Usage is critically high: 92.1%"
    metric_value    = Column(Float)       # 92.1 (actual value)
    threshold_value = Column(Float)       # 85.0 (configured limit)
    severity        = Column(String(20))  # "warning" (85-95%) or "critical" (>95%)
    is_read         = Column(Boolean, default=False)   # Badge counter uses this
    is_resolved     = Column(Boolean, default=False)
    resolved_at     = Column(DateTime, nullable=True)  # Set when resolved
```

---

### 4.4 Pydantic Schemas

Pydantic schemas serve two purposes:
1. **Input validation** — reject bad data before it reaches the database
2. **Response serialization** — control exactly what JSON is sent back to clients

---

#### `backend/app/schemas/metrics.py`

```python
class MetricCreate(BaseModel):
    """Validates the JSON body from the monitoring agent."""
    cpu_percent:  float = Field(..., ge=0, le=100)  # MUST be 0-100
    ram_percent:  float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)
    # Optional fields:
    cpu_count:    Optional[int] = None
    hostname:     Optional[str] = None
    top_processes: Optional[List[dict]] = []

class MetricResponse(MetricCreate):
    """Same as MetricCreate, but adds id and created_at (returned after saving)."""
    id: int
    created_at: datetime

class MetricSummary(BaseModel):
    """Lightweight version for history queries — no process list."""
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    net_bytes_recv_mb: float
    net_bytes_sent_mb: float
    created_at: datetime

class MetricAverages(BaseModel):
    """Response for /api/metrics/averages"""
    avg_cpu: float
    avg_ram: float
    max_cpu: float
    min_cpu: float
    sample_count: int
    period_hours: int

class HourlyBucket(BaseModel):
    """One data point per hour — for Analytics bar chart."""
    hour: datetime
    avg_cpu: float
    avg_ram: float
    avg_disk: float
    max_cpu: float
    sample_count: int
```

---

#### `backend/app/schemas/ml.py`

```python
class PredictionRequest(BaseModel):
    """Input for /api/ml/predict — test the AI from Swagger UI."""
    cpu_percent: float = Field(..., ge=0, le=100)
    ram_percent: float = Field(..., ge=0, le=100)
    disk_percent: float = Field(..., ge=0, le=100)
    net_bytes_recv_mb: float = Field(default=0.0)
    net_bytes_sent_mb: float = Field(default=0.0)

class PredictionResponse(BaseModel):
    """AI prediction result with explanation."""
    is_anomaly: bool         # True if flagged as anomaly
    anomaly_score: float     # -0.45 (negative = anomalous)
    severity: str            # normal/low/medium/high/critical
    dominant_feature: str    # "cpu_percent" (what triggered it)
    top_features: list[FeatureContribution]  # Per-feature breakdown

class FeatureContribution(BaseModel):
    """Explains WHY something was flagged as anomalous."""
    feature: str       # "cpu_percent"
    contribution: float  # 0.72 (72% of the anomaly was due to CPU)
    value: float       # 94.2 (actual CPU value)
    z_score: float     # 3.8 (3.8 standard deviations from normal)
```

---

### 4.5 API Routers

Routers define HTTP endpoints. Each router handles one domain area.

---

#### `backend/app/routers/metrics.py` — Metrics API

**Base path**: `/api/metrics`

**Most important endpoint — POST / (Ingest from Agent)**:
```
POST /api/metrics/
↓ Validates JSON with MetricCreate schema
↓ Saves to PostgreSQL
↓ Concurrently:
   ├── Checks alert thresholds (alert_service)
   └── Runs AI anomaly detection (anomaly_detector.predict)
↓ Builds broadcast payload
↓ ws_manager.broadcast() → all WebSocket clients get update
↓ Returns 201 with saved metric
```

All endpoints:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/metrics/` | POST | Ingest metric from agent |
| `/api/metrics/latest` | GET | Latest snapshot (Redis cached, <1ms) |
| `/api/metrics/sparkline` | GET | Last 60 points from Redis for mini-charts |
| `/api/metrics/averages?hours=24` | GET | Avg/min/max CPU, RAM, Disk |
| `/api/metrics/buckets?hours=24` | GET | Hourly aggregated data for bar charts |
| `/api/metrics/history?hours=1` | GET | Time-series for line charts |
| `/api/metrics/` | GET | Paginated list with `page` and `size` |
| `/api/metrics/{id}` | GET | Single metric detail |
| `/api/metrics/purge?days=7` | DELETE | Admin: delete old data |

---

#### `backend/app/routers/alerts.py` — Alerts API

**Base path**: `/api/alerts`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/alerts/` | GET | List alerts (optional `?unread_only=true`) |
| `/api/alerts/count` | GET | Unread count for badge in sidebar |
| `/api/alerts/{id}` | PATCH | Mark as read or resolved |
| `/api/alerts/mark-all-read` | POST | Dismiss all alerts at once |

---

#### `backend/app/routers/anomalies.py` — Anomalies API

**Base path**: `/api/anomalies`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/anomalies/` | GET | List anomalies `?hours=24` |
| `/api/anomalies/count` | GET | Count in last hour (for dashboard badge) |
| `/api/anomalies/{id}` | PATCH | Mark anomaly as resolved |

---

#### `backend/app/routers/ml.py` — Machine Learning API

**Base path**: `/api/ml`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ml/status` | GET | Model version, training date, feature stats |
| `/api/ml/retrain` | POST | Manually trigger retraining (protected) |
| `/api/ml/predict` | POST | Test AI on custom input values |
| `/api/ml/anomalies/stats` | GET | Anomaly distribution by severity + type |

**`/api/ml/predict` — Used for Teacher Demonstration**:
```bash
# Send this to Swagger UI at http://localhost:8000/docs
POST /api/ml/predict
{
  "cpu_percent": 95.0,
  "ram_percent": 92.0,
  "disk_percent": 45.0,
  "net_bytes_recv_mb": 0.0,
  "net_bytes_sent_mb": 0.0
}

# Response:
{
  "is_anomaly": true,
  "anomaly_score": -0.4821,
  "severity": "high",
  "dominant_feature": "cpu_percent",
  "top_features": [
    { "feature": "cpu_percent", "contribution": 0.72, "z_score": 3.8 },
    { "feature": "cpu_ram_pressure", "contribution": 0.20, "z_score": 2.1 }
  ],
  "message": "Anomaly detected — cpu_percent is the primary driver (score=-0.4821)"
}
```

---

#### `backend/app/routers/websocket.py` — WebSocket Endpoint

**Endpoint**: `ws://localhost:8000/ws`

**Connection lifecycle**:
```
Browser connects → ws_manager.connect(ws) assigns UUID "a1b2c3d4"
                 → Sends latest cached metric immediately (no empty chart)
                 → Loop:
                   - Client sends "pong" → record_pong() (heartbeat response)
                   - Client sends "ping" → server sends "pong" (keepalive)
                   - Server pushes "metric" every 5s via pubsub_broadcaster
Browser disconnects → ws_manager.disconnect(id) removes from pool
```

---

#### `backend/app/routers/system.py` — Health & System Info

| Endpoint | Purpose |
|----------|---------|
| `/health` | Liveness probe — Docker health check, returns 200 if alive |
| `/api/system/info` | Full status: DB health, Redis health, WS connections, ML status |

---

### 4.6 Service Layer

Services contain the **business logic**. Routers call services; services call models and Redis.

---

#### `backend/app/services/metrics_service.py` — Metrics Business Logic

**Why a service layer?** Keeps routers thin. If the database query changes, only the service changes — not every router.

Key methods:
```python
async def save_metric(db, data):
    # 1. Insert to PostgreSQL
    metric = SystemMetric(**data.model_dump())
    db.add(metric)
    await db.flush()  # Get ID without committing

    # 2. Cache in Redis (one pipeline round-trip)
    await redis_service.cache_metric_batch(metric.to_summary_dict())
    return metric

async def get_latest(db):
    # Redis-first: check cache first (sub-1ms)
    cached = await redis_service.get_latest_metric()
    if cached:
        return cached   # Cache hit — no DB query needed!

    # Cache miss: query PostgreSQL (happens rarely)
    return await db.execute(
        select(SystemMetric).order_by(desc(SystemMetric.created_at)).limit(1)
    )

async def get_hourly_buckets(db, hours=24):
    # Uses PostgreSQL DATE_TRUNC — server-side aggregation, very fast
    result = await db.execute(text("""
        SELECT
            DATE_TRUNC('hour', created_at) AS hour,
            AVG(cpu_percent)::FLOAT        AS avg_cpu,
            ...
        FROM system_metrics
        WHERE created_at >= :since
        GROUP BY DATE_TRUNC('hour', created_at)
    """))
```

---

#### `backend/app/services/alert_service.py` — Alert Business Logic

**How threshold checking works**:
```python
async def check_and_create_alerts(db, metric):
    checks = [
        ("cpu_high",  "CPU Usage",  metric["cpu_percent"],  85.0, "warning"/"critical"),
        ("ram_high",  "RAM Usage",  metric["ram_percent"],  85.0, ...),
        ("disk_high", "Disk Usage", metric["disk_percent"], 90.0, "critical"),
    ]

    for alert_type, label, value, threshold, severity in checks:
        if value >= threshold:
            # DEDUPLICATION: Was the same alert fired in the last 5 minutes?
            existing = await db.execute(
                select(Alert)
                .where(Alert.alert_type == alert_type)
                .where(Alert.is_resolved == False)
                .where(Alert.created_at >= now - 5 minutes)
            )
            if existing.scalar_one_or_none():
                continue  # Skip — already alerted recently

            # Create new alert
            alert = Alert(alert_type=alert_type, message=f"{label}: {value:.1f}%", ...)
            db.add(alert)
```

**Deduplication** is critical — without it, a CPU stuck at 90% would create thousands of alerts in a few hours.

---

#### `backend/app/services/anomaly_service.py` — Anomaly Business Logic

```python
async def save_anomaly(db, metric, score, details):
    # Convert score to severity
    severity = _score_to_severity(score)
    # Scores: < -0.6 = critical, < -0.4 = high, < -0.2 = medium, else low

    # Which feature caused the anomaly?
    metric_type = details.get("dominant_feature")  # e.g. "cpu_percent"

    # Build human-readable description
    description = _build_description(metric, details)
    # "Anomaly [cpu_percent] — cpu_percent=94.2% (z=3.8), ram_percent=57.1% (z=0.3)"

    anomaly = Anomaly(metric_type=metric_type, anomaly_score=score, ...)
    db.add(anomaly)
    await db.flush()  # Get ID
    return anomaly
```

---

#### `backend/app/services/redis_service.py` — Redis Cache Service

**Why Redis?** PostgreSQL queries take ~50ms. Redis returns in <1ms. For the dashboard that refreshes every 5s, this matters.

**Redis Key Layout**:
```
cloudpulse:metric:latest     → JSON string (TTL=10s)  — latest metric snapshot
cloudpulse:metric:history    → List<JSON> (max 60)    — sparkline data
cloudpulse:counter:alerts    → Integer                — alert count
cloudpulse:counter:anomalies → Integer                — anomaly count
cloudpulse:pubsub            → Pub/Sub channel        — metric broadcast
```

**Efficient batch write** (1 Redis round-trip instead of 3):
```python
async def cache_metric_batch(data):
    serialised = json.dumps(data)
    pipe = self._client.pipeline(transaction=False)
    pipe.setex(KEY_LATEST,   TTL,    serialised)  # Store latest
    pipe.lpush(KEY_HISTORY,  serialised)           # Prepend to history
    pipe.ltrim(KEY_HISTORY,  0, 59)                # Keep only 60 items
    await pipe.execute()  # ONE network call for all three!
```

---

### 4.7 AI / ML Layer

---

#### `backend/app/ml/anomaly_detector.py` — Isolation Forest Engine

**Why Isolation Forest?**
- Works **unsupervised** — no need to label data as "normal" or "anomalous"
- Intuition: anomalies are **easier to isolate** in a random decision tree (fewer splits needed)
- Handles **multi-dimensional** data: CPU, RAM, Disk, Network all at once
- Fast to predict (microseconds per data point)

**Feature Engineering** — why we add derived features:
```python
RAW_FEATURES = [
    "cpu_percent",        # 0-100%
    "ram_percent",        # 0-100%
    "disk_percent",       # 0-100%
    "net_bytes_recv_mb",  # MB cumulative
    "net_bytes_sent_mb",  # MB cumulative
]

ENGINEERED_FEATURES = [
    # Captures "system under load" when neither CPU nor RAM alone crosses threshold
    "cpu_ram_pressure": (cpu + ram) / 2.0,

    # Detects DDoS or large file transfers even if individual metrics look normal
    "net_total_mb": recv + sent,
]
```

**Why StandardScaler (normalization)?**
```
Without scaling:
  net_bytes_recv_mb = 1500 MB  ← dominates!
  cpu_percent       = 45       ← appears small

With StandardScaler (mean=0, std=1):
  net_bytes_recv_mb → 0.8  (normalized)
  cpu_percent       → 1.2  (normalized)
  Now all features are on the same scale — fair comparison!
```

**Training**:
```python
def train(self, data: list[dict]):
    X_raw    = self._build_matrix(data)     # (N × 7) matrix
    X_scaled = StandardScaler().fit_transform(X_raw)

    model = IsolationForest(
        n_estimators=150,         # 150 trees (more = more stable)
        contamination=0.05,       # Expect 5% of data to be anomalous
        random_state=42,          # Reproducible results
        n_jobs=-1,                # Use all CPU cores
    )
    model.fit(X_scaled)

    # Save to disk: model.pkl + scaler.pkl + manifest.json
```

**Prediction with Explanation**:
```python
def predict(self, metric):
    enriched = _engineer(metric)          # Add derived features
    X_scaled = scaler.transform([enriched])

    label = model.predict(X_scaled)[0]    # -1 = anomaly, +1 = normal
    score = model.score_samples(X_scaled)[0]  # More negative = more anomalous

    # Per-feature contribution (for explainability):
    abs_z = |X_scaled[0]|                 # Absolute z-scores
    norm  = abs_z / sum(abs_z)            # Normalize to sum=1

    details = {
        "contributions": { "cpu_percent": 0.72, "ram_percent": 0.12, ... },
        "z_scores": { "cpu_percent": 3.8, ... },
        "dominant_feature": "cpu_percent",  # Feature with highest contribution
    }

    return (label == -1), score, details
```

---

#### `backend/app/ml/model_trainer.py` — Background Retraining

**Why retrain periodically?**
> The Isolation Forest learns "normal" from historical data. As usage patterns change (new services, time-of-day traffic), the model becomes stale. Retraining keeps it current.

**Why `run_in_executor`?**
```python
# IsolationForest.fit() is CPU-bound (C code under the hood)
# Running it directly would BLOCK the event loop for ~0.5 seconds
# This means: no WebSocket updates, no HTTP responses for 0.5s!

# Instead, run it in a thread pool — event loop stays free:
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, anomaly_detector.train, data)
```

**Retraining flow**:
```
1. Wait 60 seconds (app startup settles)
2. Loop:
   a. Query last 24h of metrics from PostgreSQL
   b. Convert ORM objects to plain dicts
   c. Run anomaly_detector.train(data) in thread pool
   d. Sleep MODEL_RETRAIN_INTERVAL seconds (default: 1 hour)
   e. Repeat
```

---

### 4.8 Utilities

---

#### `backend/app/utils/websocket_manager.py` — WebSocket Connection Pool

**Why a manager class?** Multiple routes need to broadcast to clients. A singleton manager centralizes this.

**Key features**:
```python
class WebSocketManager:
    _connections: dict[str, WSConnection]  # id → connection object
    _lock: asyncio.Lock                    # Thread-safe add/remove

    async def broadcast(data):
        # Sends to ALL clients CONCURRENTLY (not one-by-one!)
        tasks = [_safe_send(id, conn, message) for id, conn in snapshot]
        await asyncio.gather(*tasks, return_exceptions=True)
        # If one client fails, others still get the message

    async def _heartbeat_loop():
        # Every 20 seconds:
        # 1. Send {"type": "ping"} to each client
        # 2. If client hasn't responded in 30s, disconnect them (stale connection)
```

**Per-connection metadata**:
```python
@dataclass
class WSConnection:
    ws: WebSocket
    id: str = uuid4()[:8]          # Short ID like "a1b2c3d4"
    connected_at: datetime
    last_pong_at: datetime          # Updated when client responds to ping
    alive: bool = True
```

---

## 5. Agent — File-by-File Analysis

The agent is a separate Python program that runs on the monitored machine. Its only job is to collect system metrics and send them to the backend.

---

#### `agent/monitor.py` — Main Agent Loop

**Why it exists**: Orchestrates the collection and sending cycle.

```python
async def run_agent():
    while True:
        start = datetime.now()

        # Collect all metrics
        metrics = collect_all_metrics()
        # Returns: { cpu_percent, ram_percent, disk_percent,
        #            net_bytes_recv_mb, top_processes, hostname, ... }

        # Send to backend
        success = await send_metrics(metrics)

        # Print status line for monitoring
        print(f"[10:30:05] Cycle #42 | CPU: 45.1% | RAM: 67.2% | Send: OK")

        # Wait to maintain 5-second interval (subtracting collection time)
        sleep_time = max(0, COLLECT_INTERVAL - elapsed)
        await asyncio.sleep(sleep_time)
```

---

#### `agent/collectors/cpu_collector.py`

```python
def collect_cpu():
    freq = psutil.cpu_freq()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),  # 1-second sample (more accurate)
        "cpu_count":   psutil.cpu_count(logical=True),  # Total logical cores
        "cpu_freq_mhz": round(freq.current, 1) if freq else None,
    }
```
**`interval=1`**: psutil measures CPU over 1 second — more accurate than instantaneous.

---

#### `agent/collectors/ram_collector.py`

```python
def collect_ram():
    mem = psutil.virtual_memory()
    return {
        "ram_total_gb": round(mem.total / (1024**3), 2),  # Bytes → GB
        "ram_used_gb":  round(mem.used  / (1024**3), 2),
        "ram_percent":  mem.percent,
    }
```

---

#### `agent/collectors/disk_collector.py`

```python
def collect_disk():
    usage = psutil.disk_usage("/")  # Root partition
    io    = psutil.disk_io_counters()  # Cumulative read/write since boot
    return {
        "disk_total_gb": round(usage.total / (1024**3), 2),
        "disk_used_gb":  round(usage.used  / (1024**3), 2),
        "disk_percent":  usage.percent,
        "disk_read_mb":  round(io.read_bytes  / (1024**2), 3) if io else None,
        "disk_write_mb": round(io.write_bytes / (1024**2), 3) if io else None,
    }
```

---

#### `agent/collectors/network_collector.py`

```python
def collect_network():
    net = psutil.net_io_counters()  # Cumulative since system boot
    return {
        "net_bytes_sent_mb": round(net.bytes_sent / (1024**2), 3),
        "net_bytes_recv_mb": round(net.bytes_recv / (1024**2), 3),
        "net_packets_sent":  net.packets_sent,
        "net_packets_recv":  net.packets_recv,
    }
```

**Note**: These are cumulative counters since boot. The ML model uses them directly — relative changes over time reveal spikes.

---

#### `agent/collectors/process_collector.py`

```python
def collect_processes(top_n=10):
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            procs.append({
                "pid": proc.info["pid"],
                "name": proc.info["name"] or "unknown",
                "cpu_percent": round(proc.info["cpu_percent"] or 0, 2),
                "memory_percent": round(proc.info["memory_percent"] or 0, 2),
                "status": proc.info["status"] or "unknown",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue  # Process died or no permission — skip silently

    # Sort by CPU descending, return top N
    return sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:top_n]
```

---

#### `agent/sender.py` — HTTP POST with Retry

```python
async def send_metrics(data):
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, 4):  # Try 3 times
            try:
                response = await client.post(API_ENDPOINT, json=data)
                if response.status_code == 201:
                    return True  # Success!
            except httpx.ConnectError:
                print(f"Connection failed (attempt {attempt}/3). Is backend running?")
            except httpx.TimeoutException:
                print(f"Request timed out (attempt {attempt}/3).")

            if attempt < 3:
                await asyncio.sleep(2.0)  # Wait 2s before retry
    return False
```

**Why retry?** If the backend restarts (Docker restart), the agent would permanently fail without retry logic. With 3 retries and 2s delay, the agent handles brief backend downtime gracefully.

---

## 6. Frontend — File-by-File Analysis

The frontend is a React 18 single-page application built with Vite.

---

### 6.1 Entry Point & App Shell

---

#### `frontend/src/main.jsx` — React Entry Point

```jsx
// This is the first file that runs in the browser
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>  {/* Catches bugs in development */}
    <App />
  </React.StrictMode>
)
```

---

#### `frontend/src/App.jsx` — App Shell & Routing

```jsx
export default function App() {
  return (
    <BrowserRouter>       {/* Enables URL-based navigation */}
      <MetricsProvider>   {/* Global state — wraps everything */}
        <ToastContainer /> {/* Fixed toast layer above everything */}

        <div className="flex min-h-screen">
          <Sidebar />       {/* Left navigation — always visible */}
          <div className="flex flex-col flex-1">
            <Routes>
              <Route path="/"          element={<Dashboard />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts"    element={<Alerts />}    />
              <Route path="/processes" element={<Processes />} />
            </Routes>
          </div>
        </div>
      </MetricsProvider>
    </BrowserRouter>
  )
}
```

**Why `MetricsProvider` wraps everything?** It holds the WebSocket connection and live data. All child components (Sidebar, Header, all pages) can access this data without prop drilling.

---

### 6.2 Global State (Context)

---

#### `frontend/src/context/MetricsContext.jsx` — Global Real-Time State

**Why it exists**: Multiple components need the same live data (Sidebar shows CPU bars, Dashboard shows charts, Header shows WS status). Instead of passing props through many levels, all components subscribe to this context.

**State managed**:
```jsx
const [current,       setCurrent]       // Latest metric snapshot
const [history,       setHistory]       // Last 60 metric readings (for charts)
const [wsStatus,      setWsStatus]      // "connected" | "disconnected" | "error"
const [alertCount,    setAlertCount]    // Unread alerts count (badge)
const [anomalyCount,  setAnomalyCount]  // Anomalies in last hour (badge)
const [recentAnomalies, setRecentAnomalies]  // Latest WS anomaly events
const [toasts,        setToasts]        // Active toast notifications
const [lastUpdated,   setLastUpdated]   // Timestamp of last metric
const [initialized,   setInitialized]   // Shows skeletons until first load
```

**Bootstrap (on page load)**:
```jsx
useEffect(() => {
  async function bootstrap() {
    // Fetch BOTH simultaneously (not sequentially)
    const [latest, hist] = await Promise.all([
      getLatestMetric(),    // GET /api/metrics/latest (Redis cached)
      getMetricHistory(1),  // GET /api/metrics/history?hours=1
    ])

    setCurrent(latest.data)   // Charts have data immediately!
    setHistory(hist.data)     // Chart isn't empty on first load
  }
  bootstrap()
}, [])
```

**WebSocket handlers**:
```jsx
handlers = {
  onMetric: (data) => {
    setCurrent(data)             // All MetricCards update
    setHistory(prev =>           // LiveChart gains one point
      [...prev, {...data}].slice(-60)  // Keep max 60 points
    )
    setLastUpdated(new Date())   // Header shows "updated just now"
  },

  onAnomaly: (data) => {
    setRecentAnomalies(prev => [data, ...prev].slice(0, 10))
    setAnomalyCount(c => c + 1)  // Badge increments
    addToast('danger', 'Anomaly Detected', data.description)  // Popup!
  },
}
```

---

### 6.3 Custom Hooks

---

#### `frontend/src/hooks/useWebSocket.js` — WebSocket Hook

**Why a custom hook?** Encapsulates WebSocket lifecycle (connect, retry, heartbeat, cleanup) so any component can use it with just `useWebSocket(handlers)`.

**Key bug fix it solves**:
```jsx
// ❌ WRONG (original bug): handlers change on every render
// → useEffect re-runs → socket reconnects on every render!
useWebSocket({ onMetric: (data) => setCurrent(data) })

// ✅ FIX: Store handlers in a ref
const handlersRef = useRef(handlers)
useEffect(() => { handlersRef.current = handlers })
// Ref updates silently without causing re-renders or effect re-runs
```

**Exponential backoff reconnection**:
```js
ws.onclose = () => {
    // 1st retry: wait 1s
    // 2nd retry: wait 2s
    // 3rd retry: wait 4s
    // ... up to 30s maximum
    const delay = Math.min(1000 * 2 ** retriesRef.current, 30_000)
    retriesRef.current++
    reconnectRef.current = setTimeout(connect, delay)
}
```

**Client-side keepalive** (18-second ping to stay under server's 20-second cull window):
```js
ws.onopen = () => {
    pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 18_000)
}
```

---

### 6.4 API Service Layer

---

#### `frontend/src/services/api.js` — All REST API Calls

**Why a centralized service?** All API calls in one place means changing the base URL only requires editing one file.

```js
const api = axios.create({
    baseURL: '/api',       // Vite proxy handles: /api/* → http://localhost:8000
    timeout: 10_000,       // 10 second timeout
})

// All endpoints:
export const getLatestMetric   = () => api.get('/metrics/latest')
export const getMetricHistory  = (hours, limit) => api.get(`/metrics/history?hours=${hours}&limit=${limit}`)
export const getMetricBuckets  = (hours) => api.get(`/metrics/buckets?hours=${hours}`)
export const getMetricAverages = (hours) => api.get(`/metrics/averages?hours=${hours}`)

export const getAlerts         = (unreadOnly) => api.get(`/alerts/?unread_only=${unreadOnly}`)
export const getAlertCount     = () => api.get('/alerts/count')
export const updateAlert       = (id, data) => api.patch(`/alerts/${id}`, data)
export const markAllAlertsRead = () => api.post('/alerts/mark-all-read')

export const getAnomalies      = (hours) => api.get(`/anomalies/?hours=${hours}`)
export const getAnomalyCount   = (hours) => api.get(`/anomalies/count?hours=${hours}`)
export const resolveAnomaly    = (id) => api.patch(`/anomalies/${id}`, { is_resolved: true })
```

**Vite Proxy** (`vite.config.js`): In development, Vite forwards `/api/*` calls to `http://localhost:8000`, avoiding CORS issues.

---

### 6.5 Pages

---

#### `frontend/src/pages/Dashboard.jsx` — Main Real-Time View

**Layout** (6 sections):
```
① Anomaly Banner     — Red pulsing bar if AI detected anomalies this hour
② System Status Bar  — Hostname | Platform | WS Status | Uptime
③ 4 Metric Cards     — CPU, RAM, Disk, Disk I/O (each with ring + sparkline)
④ CPU + RAM Charts   — Side-by-side area charts with threshold line
⑤ Disk + Network     — Disk area chart + Network dual-line chart
⑥ Alerts + Anomalies — AlertsPanel (left) | AnomalyFeed (right)
```

**Skeleton loading** (shows shimmer while data loads):
```jsx
{!initialized ? (
  <div className="grid grid-cols-4 gap-3">
    {[...Array(4)].map((_, i) => <Skeleton.Card key={i} />)}
  </div>
) : (
  <div className="grid grid-cols-4 gap-3">
    {cards.map(card => <MetricCard {...card} history={history} />)}
  </div>
)}
```

---

#### `frontend/src/pages/Analytics.jsx` — Historical Data Explorer

**Features**:
- Time range selector: 30m / 1h / 6h / 24h / 7d
- Stat cards: Avg CPU, Peak CPU, Avg RAM, Peak RAM, Avg Disk
- Multi-line chart: CPU + RAM + Disk on same chart
- Bar chart: Network Inbound vs Outbound
- Bar chart: Disk Read vs Write

**Data loading with time range**:
```jsx
const load = useCallback(async () => {
    setLoading(true)
    const [h, a] = await Promise.all([
        getMetricHistory(hours),    // GET /api/metrics/history?hours=X
        getMetricAverages(hours),   // GET /api/metrics/averages?hours=X
    ])
    setHistory(h.data)
    setAvgs(a.data)
    setLoading(false)
}, [hours])

useEffect(() => { load() }, [load])  // Re-runs whenever hours changes
```

---

#### `frontend/src/pages/Alerts.jsx` — Alert Management

**Filter system**:
```jsx
const FILTERS = ['all', 'unread', 'active', 'critical']

const counts = {
    all:      alerts.length,
    unread:   alerts.filter(a => !a.is_read).length,
    active:   alerts.filter(a => !a.is_resolved).length,
    critical: alerts.filter(a => a.severity === 'critical').length,
}

// Auto-reload when WebSocket brings new alert
useEffect(() => {
    if (alertCount > prevCount.current) load()
    prevCount.current = alertCount
}, [alertCount, load])
```

---

#### `frontend/src/pages/Processes.jsx` — Live Process Table

**Client-side sort + search**:
```jsx
const processes = useMemo(() => {
    return [...(current.top_processes || [])]
        .filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
        .sort((a, b) => sortDir === 'desc' ? b[sortKey] - a[sortKey] : a[sortKey] - b[sortKey])
}, [current.top_processes, search, sortKey, sortDir])
// useMemo only recomputes when top_processes, search, or sort changes
```

**Search highlight** — highlights matching text in process names:
```jsx
function Highlight({ text, query }) {
    const idx = text.toLowerCase().indexOf(query.toLowerCase())
    return (
        <>
            {text.slice(0, idx)}
            <mark className="bg-indigo-500/30">{text.slice(idx, idx + query.length)}</mark>
            {text.slice(idx + query.length)}
        </>
    )
}
```

---

### 6.6 Components

---

#### `components/Dashboard/MetricCard.jsx` — Animated Metric Card

**SVG Progress Ring** (drawn in pure SVG math):
```jsx
const r = 34
const circumference = 2 * Math.PI * r   // Full circle length ≈ 213.6

// To show 45% filled:
const offset = circumference - (45/100) * circumference  // 117.5
// SVG uses strokeDashoffset to "trim" how much of the ring is visible
```

**Trend detection** (compares last 5 vs previous 5 readings):
```jsx
const recent = history.slice(-5)   // Latest 5
const older  = history.slice(-10, -5)  // 5 before that
const diff = avg(recent) - avg(older)
if (diff > 1.5)  return 'up'    // CPU trending up → red arrow
if (diff < -1.5) return 'down'  // CPU dropping → green arrow
return 'stable'
```

---

#### `components/Dashboard/LiveChart.jsx` — Real-Time Area Chart

Uses **Recharts** library. Key features:
- `isAnimationActive={false}` — disables animation for fast updates (smoother)
- Dynamic color: green → amber → red as value crosses thresholds
- `ReferenceLine y={85}` — dashed red line at alert threshold
- Custom tooltip showing exact value + unit

---

#### `components/Dashboard/NetworkCard.jsx` — Network I/O Chart

Shows two overlapping area charts:
- **Blue**: Inbound MB (download)
- **Purple**: Outbound MB (upload)
- Displays current recv/sent in header

---

#### `components/Dashboard/SystemStatus.jsx` — System Info Bar

Shows: Hostname | Platform | WS Status | Uptime (seconds since page load).

---

#### `components/Alerts/AlertsPanel.jsx` — Alert Feed

- Loads alerts on mount and when `alertCount` increases
- Each `AlertRow` shows severity badge + message + relative time
- Dismiss button: `PATCH /api/alerts/{id}` → marks read + resolved

---

#### `components/Anomalies/AnomalyFeed.jsx` — AI Anomaly Feed

- Initial load: `GET /api/anomalies/?hours=24`
- Real-time: listens to `recentAnomalies` from MetricsContext (WebSocket)
- Merges without duplicates using Set of IDs
- Color-coded by severity: red (critical) → orange (high) → amber (medium) → yellow (low)

---

#### `components/Layout/Sidebar.jsx` — Navigation Sidebar

- NavLink active state applies highlight + left accent bar
- **Live mini-stats** (when connected): small CPU/RAM/Disk bars update every 5s
- Badge counts on nav items: Alerts badge (red) + Dashboard anomaly badge (yellow)
- WS status indicator: green pulse (connected), yellow (connecting), red (error)

---

#### `components/Layout/Header.jsx` — Page Header

- "Updated X seconds ago" — uses `formatDistanceToNow` from date-fns, ticks every second
- Bell icon with red badge for unread alerts
- Refresh button triggers page-specific data reload
- Clock showing current local time

---

#### `components/ui/Skeleton.jsx` — Loading Placeholders

```jsx
// Three variants:
<Skeleton className="h-8 w-32" />          // Custom shimmer div
<Skeleton.Card rows={4} />                  // Card placeholder
<Skeleton.Chart height={300} />            // Chart placeholder
<Skeleton.Row />                            // Table row placeholder
```

Uses CSS animation `shimmer` that slides a gradient across the element.

---

#### `components/ui/ToastContainer.jsx` — Notification Toasts

Fixed position (top-right corner), renders from `MetricsContext.toasts`:
- `danger` — red (anomaly detected)
- `warning` — amber (new alert)
- `info` — indigo
- `success` — green

Auto-dismisses after 5 seconds (set in `addToast()`).

---

## 7. Database Schema

Three tables, all in PostgreSQL 16:

```sql
-- Table 1: Every metric reading from the agent (one row per 5 seconds)
CREATE TABLE system_metrics (
    id              SERIAL PRIMARY KEY,
    cpu_percent     FLOAT NOT NULL,
    cpu_count       INTEGER,
    cpu_freq_mhz    FLOAT,
    ram_total_gb    FLOAT,
    ram_used_gb     FLOAT,
    ram_percent     FLOAT NOT NULL,
    disk_total_gb   FLOAT,
    disk_used_gb    FLOAT,
    disk_percent    FLOAT NOT NULL,
    disk_read_mb    FLOAT,
    disk_write_mb   FLOAT,
    net_bytes_sent_mb   FLOAT,
    net_bytes_recv_mb   FLOAT,
    net_packets_sent    INTEGER,
    net_packets_recv    INTEGER,
    hostname        VARCHAR(255),
    platform        VARCHAR(100),
    top_processes   JSONB DEFAULT '[]',   -- JSON array of process dicts
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
-- Index ensures fast "WHERE created_at >= 1 hour ago" queries
CREATE INDEX idx_metrics_created_at ON system_metrics(created_at DESC);

-- Table 2: AI-detected anomalies
CREATE TABLE anomalies (
    id              SERIAL PRIMARY KEY,
    metric_type     VARCHAR(50),    -- Which feature caused it
    anomaly_score   FLOAT,          -- -0.45 (more negative = worse)
    cpu_percent     FLOAT,          -- Values at time of detection
    ram_percent     FLOAT,
    disk_percent    FLOAT,
    net_bytes_recv_mb FLOAT,
    net_bytes_sent_mb FLOAT,
    description     VARCHAR(500),   -- Human-readable explanation
    severity        VARCHAR(20) DEFAULT 'medium',
    is_resolved     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Table 3: Threshold-based alerts
CREATE TABLE alerts (
    id              SERIAL PRIMARY KEY,
    alert_type      VARCHAR(50),    -- cpu_high, ram_high, disk_high
    message         VARCHAR(500),   -- "CPU Usage is critically high: 92.1%"
    metric_value    FLOAT,          -- 92.1
    threshold_value FLOAT,          -- 85.0
    severity        VARCHAR(20) DEFAULT 'warning',
    is_read         BOOLEAN DEFAULT FALSE,
    is_resolved     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);
```

**Retention**: Background task deletes `system_metrics` rows older than 7 days (runs every 6 hours).

---

## 8. API Reference — All Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/metrics/` | AgentKey | Ingest metric from agent |
| `GET` | `/api/metrics/latest` | No | Latest metric (Redis) |
| `GET` | `/api/metrics/sparkline` | No | Last 60 points (Redis) |
| `GET` | `/api/metrics/averages?hours=24` | No | Avg/min/max stats |
| `GET` | `/api/metrics/buckets?hours=24` | No | Hourly chart data |
| `GET` | `/api/metrics/history?hours=1&limit=300` | No | Time-series data |
| `GET` | `/api/metrics/?page=1&size=50` | No | Paginated list |
| `GET` | `/api/metrics/{id}` | No | Single row |
| `DELETE` | `/api/metrics/purge?days=7` | No | Delete old rows |
| `GET` | `/api/alerts/` | No | All alerts |
| `GET` | `/api/alerts/count` | No | Unread count |
| `PATCH` | `/api/alerts/{id}` | No | Update alert |
| `POST` | `/api/alerts/mark-all-read` | No | Dismiss all |
| `GET` | `/api/anomalies/` | No | All anomalies |
| `GET` | `/api/anomalies/count?hours=1` | No | Recent count |
| `PATCH` | `/api/anomalies/{id}` | No | Resolve anomaly |
| `GET` | `/api/ml/status` | No | Model info |
| `POST` | `/api/ml/retrain` | AgentKey | Trigger retraining |
| `POST` | `/api/ml/predict` | No | Test AI inference |
| `GET` | `/api/ml/anomalies/stats?hours=24` | No | Distribution stats |
| `GET` | `/health` | No | Liveness probe |
| `GET` | `/api/system/info` | No | Deep health check |
| `WS` | `/ws` | No | Live WebSocket feed |

---

## 9. WebSocket Protocol

**Server → Client messages**:
```json
// Every 5 seconds (when agent sends a metric)
{ "type": "metric",
  "data": { "cpu_percent": 45.2, "ram_percent": 67.1, "disk_percent": 52.0,
            "net_bytes_recv_mb": 124.5, "net_bytes_sent_mb": 34.2,
            "top_processes": [...], "created_at": "2026-06-13T00:30:00Z" },
  "alerts": [{ "type": "cpu_high", "message": "CPU: 92.1%", "severity": "critical" }],
  "anomaly": { "id": 42, "score": -0.482, "severity": "high", "dominant_feature": "cpu_percent" }
}

// Every 20 seconds (heartbeat)
{ "type": "ping" }

// After client sends "ping"
{ "type": "pong" }

// On WebSocket connect (immediate initial data)
{ "type": "metric", "data": { ... } }  // Latest from Redis
```

**Client → Server messages**:
```
"pong"   — Response to server's ping (heartbeat)
"ping"   — Client-initiated keepalive (server responds "pong")
```

---

## 10. AI/ML Pipeline Deep Dive

### How Isolation Forest Works (Simplified)

```
Training data: 500 normal readings + 25 anomalous readings

Step 1: Build 150 random trees
        Each tree tries to ISOLATE each data point
        by randomly choosing a feature and a split value

Step 2: Anomalies need FEWER splits to isolate
        (they're far from the "crowd" of normal points)

Step 3: Average path length across all 150 trees
        Short path → anomaly (easy to isolate)
        Long path  → normal (hard to isolate)

Step 4: Convert to score: -0.5 to +0.1
        < -0.2 → anomaly
        > -0.2 → normal
```

### Severity Mapping

| Score Range | Severity | Meaning |
|-------------|----------|---------|
| > -0.2 | Low | Slightly unusual |
| -0.2 to -0.4 | Medium | Notable deviation |
| -0.4 to -0.6 | High | Significant anomaly |
| < -0.6 | Critical | Extreme outlier |

### Training Data Flow

```
GET /api/metrics/history (last 24h from PostgreSQL)
        ↓
Convert ORM rows to plain dicts
        ↓
_engineer() adds cpu_ram_pressure + net_total_mb (7 features total)
        ↓
StandardScaler: normalize each feature to mean=0, std=1
        ↓
IsolationForest.fit(X_scaled) → 150 trees, contamination=5%
        ↓
Save model.pkl + scaler.pkl + manifest.json to disk
        ↓
Model ready for predictions (loaded automatically on restart)
```

---

## 11. Redis Caching Strategy

```
Request flow for GET /api/metrics/latest:

Browser → GET /api/metrics/latest
          ↓
          Check Redis: GET cloudpulse:metric:latest
          ↓
          Cache HIT? → Return JSON immediately (<1ms)
          ↓
          Cache MISS? → Query PostgreSQL (~50ms)
                        → Store in Redis: SETEX ... 10 <json>
                        → Return JSON

Cache expires after 10 seconds (REDIS_CACHE_TTL=10)
Agent sends new data every 5 seconds → cache always fresh
```

**Sparkline history** (rolling list):
```
Redis List: [newest, ..., oldest]  (max 60 items)

On each new metric:
LPUSH cloudpulse:metric:history <new_json>  → add to front
LTRIM cloudpulse:metric:history 0 59        → keep only 60

Reading: LRANGE ... 0 -1 → then reverse for chronological order
```

**Pub/Sub for WebSocket scaling**:
```
Agent POSTs → Backend Instance 1
Instance 1: PUBLISH cloudpulse:pubsub <metric_json>
             ↓
All Instances subscribe and receive the message
             ↓
Each instance broadcasts to its own WebSocket clients
             ↓
All browsers receive the update (regardless of which instance handled POST)
```

---

## 12. Docker & Deployment

**`docker-compose.yml`** — starts all 4 services with one command:

```yaml
services:
  postgres:   # PostgreSQL database
    image: postgres:16-alpine
    ports: ["5432:5432"]
    healthcheck: pg_isready  # Backend waits for this before starting

  redis:      # Redis cache + pub/sub
    image: redis:7-alpine
    ports: ["6379:6379"]

  backend:    # FastAPI application
    build: ./backend/
    ports: ["8000:8000"]
    depends_on:
      postgres: {condition: service_healthy}  # Wait for DB
      redis:    {condition: service_healthy}  # Wait for Redis

  agent:      # Monitoring agent
    build: . (agent/Dockerfile)
    network_mode: host    # MUST use host networking to read HOST machine metrics
    depends_on: [backend]

  frontend:   # React + Nginx
    build: ./frontend/
    ports: ["80:80"]
    depends_on: [backend]
```

**Why `network_mode: host` for agent?** Without host networking, the agent runs inside a Docker container and would report the CONTAINER's metrics (nearly zero CPU/RAM), not the host machine's metrics.

---

## 13. Tech Stack Summary

| Layer | Technology | Version | Why Chosen |
|-------|-----------|---------|------------|
| **OS Metrics** | psutil | 5.x | Cross-platform (Windows/Linux/Mac), comprehensive |
| **Agent HTTP** | httpx | 0.27 | Async HTTP client with retry support |
| **Backend** | FastAPI | 0.110 | Fast, async, auto-generates Swagger docs |
| **ORM** | SQLAlchemy (async) | 2.x | Type-safe, async, supports all major DBs |
| **Database** | PostgreSQL 16 | 16 | ACID, JSONB, DATE_TRUNC for aggregation |
| **Cache/PubSub** | Redis 7 | 7 | Sub-millisecond reads, built-in pub/sub |
| **AI/ML** | scikit-learn | 1.4 | Isolation Forest, StandardScaler |
| **Validation** | Pydantic | 2.x | Fast validation, auto-generates OpenAPI schema |
| **Settings** | pydantic-settings | 2.x | `.env` file support |
| **Frontend** | React 18 | 18 | Component model, hooks, context |
| **Build tool** | Vite | 5 | Fast HMR, dev proxy, optimized builds |
| **Styling** | Tailwind CSS | 3.4 | Utility classes, dark mode, responsive |
| **Charts** | Recharts | 2.10 | React-native charts, responsive |
| **HTTP client** | Axios | 1.6 | Interceptors, timeout, consistent API |
| **Icons** | Lucide React | 0.344 | Consistent, lightweight SVG icons |
| **Dates** | date-fns | 3.3 | Lightweight date formatting |
| **Container** | Docker + Compose | 3.9 | One-command deployment |

---

*Document generated for CloudPulse v1.0.0 — AI-Powered System Monitor*
*Author: CloudPulse Project | Last updated: June 2026*
