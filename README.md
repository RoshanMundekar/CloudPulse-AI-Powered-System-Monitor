# CloudPulse — AI-Powered System Monitor
###  Real-Time System Monitoring with AI Anomaly Detection

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SYSTEM RESOURCES                             │
│          CPU  │  RAM  │  Disk  │  Network  │  Processes             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ psutil (every 5s)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MONITORING AGENT (Python)                       │
│  collectors/cpu  │  ram  │  disk  │  network  │  process            │
│  sender.py → POST /api/metrics/                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP POST JSON
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Python)                         │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────┐   │
│  │  REST APIs   │   │  WebSocket   │   │   AI/ML Engine        │   │
│  │  /api/       │   │  /ws         │   │   Isolation Forest    │   │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬───────────┘   │
│         │                  │                        │               │
│  ┌──────▼───────────────────▼────────────────────── ▼───────────┐  │
│  │                    Services Layer                             │  │
│  │  metrics_service │ alert_service │ anomaly_service           │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
└──────────────────────────── │ ──────────────────────────────────────┘
                              │
         ┌────────────────────┼─────────────────────┐
         ▼                    ▼                      ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│   PostgreSQL    │  │      Redis       │  │   Alert Engine      │
│  system_metrics │  │  latest_metric   │  │  CPU > 85%          │
│  anomalies      │  │  metric_history  │  │  RAM > 85%          │
│  alerts         │  │  (TTL 10s)       │  │  Disk > 90%         │
└─────────────────┘  └──────────────────┘  └─────────────────────┘
                                                      │
                                   WebSocket broadcast│
                                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REACT DASHBOARD (Vite + Tailwind)                │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │
│  │  Dashboard  │  │  Analytics  │  │   Alerts    │  │Processes │  │
│  │  Live Cards │  │  Historical │  │   Panel     │  │  Table   │  │
│  │  Charts     │  │  Charts     │  │             │  │          │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
CloudPulse/
│
├── backend/                    ← FastAPI application
│   ├── app/
│   │   ├── main.py             ← FastAPI app entry point
│   │   ├── config.py           ← Environment settings
│   │   ├── database.py         ← SQLAlchemy async engine
│   │   ├── models/             ← SQLAlchemy ORM models
│   │   │   ├── metrics.py      ← system_metrics table
│   │   │   ├── anomalies.py    ← anomalies table
│   │   │   └── alerts.py       ← alerts table
│   │   ├── schemas/            ← Pydantic validation schemas
│   │   ├── routers/            ← API route handlers
│   │   │   ├── metrics.py      ← POST /api/metrics/
│   │   │   ├── alerts.py       ← GET/PATCH /api/alerts/
│   │   │   ├── anomalies.py    ← GET /api/anomalies/
│   │   │   └── websocket.py    ← WebSocket /ws
│   │   ├── services/           ← Business logic layer
│   │   │   ├── metrics_service.py
│   │   │   ├── alert_service.py
│   │   │   ├── anomaly_service.py
│   │   │   └── redis_service.py
│   │   ├── ml/                 ← AI/ML components
│   │   │   ├── anomaly_detector.py  ← Isolation Forest model
│   │   │   ├── model_trainer.py     ← Background retraining
│   │   │   └── sample_data.py       ← Demo data generator
│   │   └── utils/
│   │       ├── websocket_manager.py ← WS connection pool
│   │       └── helpers.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── agent/                      ← Monitoring agent
│   ├── monitor.py              ← Main loop
│   ├── config.py               ← Agent settings
│   ├── sender.py               ← HTTP POST with retry
│   ├── collectors/             ← One module per resource
│   │   ├── cpu_collector.py
│   │   ├── ram_collector.py
│   │   ├── disk_collector.py
│   │   ├── network_collector.py
│   │   └── process_collector.py
│   └── requirements.txt
│
├── frontend/                   ← React SPA
│   ├── src/
│   │   ├── context/
│   │   │   └── MetricsContext.jsx  ← Global live-data state
│   │   ├── hooks/
│   │   │   └── useWebSocket.js     ← WS hook with reconnect
│   │   ├── services/
│   │   │   └── api.js              ← Axios REST calls
│   │   ├── components/
│   │   │   ├── Layout/             ← Sidebar, Header
│   │   │   ├── Dashboard/          ← MetricCard, LiveChart
│   │   │   ├── Alerts/             ← AlertsPanel
│   │   │   └── Processes/          ← ProcessTable
│   │   └── pages/
│   │       ├── Dashboard.jsx
│   │       ├── Analytics.jsx
│   │       ├── Alerts.jsx
│   │       └── Processes.jsx
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
│
├── database/
│   └── init.sql                ← PostgreSQL schema
│
├── docker-compose.yml          ← One-command full stack launch
├── .env.example                ← Environment template
└── README.md
```

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Redis 7
- Docker & Docker Compose (optional)

---

### Option A — Docker (Recommended)

```bash
# 1. Clone / enter project
cd CloudPulse

# 2. Copy env file
cp .env.example .env

# 3. Launch everything
docker-compose up --build

# Dashboard → http://localhost:80
# API docs  → http://localhost:8000/docs
```

---

### Option B — Manual Setup

#### 1. PostgreSQL
```sql
CREATE DATABASE cloudpulse;
CREATE USER cloudpulse WITH PASSWORD 'cloudpulse123';
GRANT ALL PRIVILEGES ON DATABASE cloudpulse TO cloudpulse;
\c cloudpulse
\i database/init.sql
```

#### 2. Redis
```bash
redis-server   # default port 6379
```

#### 3. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Copy env
copy ..\.env.example .env

# Generate sample data + train model
python -m app.ml.sample_data

# Start API server
uvicorn app.main:app --reload --port 8000
```

#### 4. Monitoring Agent
```bash
cd ..   # back to root
pip install -r agent/requirements.txt
python -m agent.monitor
```

#### 5. Frontend
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## API Documentation

FastAPI auto-generates interactive docs at **http://localhost:8000/docs**

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST   | /api/metrics/ | Ingest metric from agent |
| GET    | /api/metrics/latest | Latest metric (Redis cached) |
| GET    | /api/metrics/history?hours=1 | Historical data |
| GET    | /api/metrics/averages?hours=24 | Avg/max stats |
| GET    | /api/alerts/ | All alerts |
| PATCH  | /api/alerts/{id} | Update alert status |
| POST   | /api/alerts/mark-all-read | Mark all read |
| GET    | /api/anomalies/ | AI-detected anomalies |
| PATCH  | /api/anomalies/{id} | Resolve anomaly |
| WS     | /ws | Live WebSocket feed |

---

## WebSocket Message Format

```json
// Metric update (sent every 5 seconds)
{
  "type": "metric",
  "data": {
    "cpu_percent": 45.2,
    "ram_percent": 63.1,
    "disk_percent": 52.0,
    "net_bytes_recv_mb": 124.5,
    "net_bytes_sent_mb": 34.2,
    "top_processes": [...],
    "created_at": "2026-05-27T10:30:00"
  }
}

// Anomaly detected
{
  "type": "anomaly",
  "data": {
    "id": 42,
    "score": -0.45,
    "severity": "high",
    "description": "Anomaly detected in multi: CPU=97.2%, RAM=92.1%"
  }
}
```

---

## AI/ML — How It Works

### Isolation Forest Algorithm

1. **What it does**: Detects anomalies by isolating data points in random decision trees
2. **Intuition**: Anomalies are isolated faster (fewer splits) than normal points
3. **Score**: Ranges from ~-0.5 (anomaly) to ~+0.5 (normal)
4. **Features used**: CPU%, RAM%, Disk%, Network In/Out MB
5. **Training**: Automatically retrains every 60 minutes using the last 24 hours of data

### Anomaly Score → Severity

| Score Range | Severity |
|-------------|----------|
| > -0.2      | Low      |
| -0.2 to -0.4| Medium   |
| -0.4 to -0.6| High     |
| < -0.6      | Critical |

### Training the Model Manually

```bash
cd backend
# 1. Generate 525 sample records (500 normal + 25 anomalous)
python -m app.ml.sample_data

# 2. Model trains automatically after data insert
# Or trigger from Python:
from app.ml.anomaly_detector import anomaly_detector
```

---

## Viva Questions & Answers

**Q: What is the purpose of Redis in this project?**
A: Redis is used as a caching layer. The latest metric is stored in Redis (TTL=10s) so dashboard API calls are served from memory rather than querying PostgreSQL on every request. This reduces latency from ~50ms to <1ms.

**Q: Why Isolation Forest for anomaly detection?**
A: Isolation Forest is ideal for unsupervised anomaly detection without labeled data. It works by randomly isolating data points — anomalies require fewer splits and thus get lower scores. It handles multi-dimensional data (CPU, RAM, Disk, Network) simultaneously.

**Q: How does real-time monitoring work end-to-end?**
A: The Python agent (psutil) collects metrics every 5 seconds → POSTs to FastAPI → FastAPI saves to PostgreSQL, caches in Redis, runs AI detection, and broadcasts via WebSocket → React dashboard receives the WebSocket message and updates charts instantly.

**Q: What is the role of WebSocket vs REST API?**
A: REST APIs are used for historical data queries (analytics page), CRUD operations on alerts/anomalies. WebSocket is used for live push-updates so the dashboard receives data without polling.

**Q: How are alerts generated?**
A: Rule-based threshold checks run on every incoming metric. If CPU > 85%, RAM > 85%, or Disk > 90%, an alert row is created in PostgreSQL (with deduplication to avoid spam within 5-minute windows).

---

## Tech Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Monitoring | psutil | OS-level metrics |
| Backend | FastAPI + Python | REST + WebSocket API |
| ORM | SQLAlchemy (async) | Database abstraction |
| Database | PostgreSQL | Historical storage |
| Cache | Redis | Live data caching |
| AI/ML | scikit-learn (Isolation Forest) | Anomaly detection |
| Frontend | React 18 + Vite | SPA Dashboard |
| Styling | Tailwind CSS | Dark theme UI |
| Charts | Recharts | Data visualization |
| HTTP | Axios | REST API calls |
| Container | Docker + Compose | Deployment |
