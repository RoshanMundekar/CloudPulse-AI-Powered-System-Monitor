# CloudPulse — AI Model Documentation
## How the Machine Learning Model Works

> **For teacher presentation** — explains the full ML pipeline used in CloudPulse,
> from raw sensor data to anomaly detection, in plain language with code references.

---

## 📋 Table of Contents

1. [What Problem Does the Model Solve?](#1-what-problem-does-the-model-solve)
2. [Algorithm — Isolation Forest](#2-algorithm--isolation-forest)
3. [Input Features](#3-input-features)
4. [Feature Engineering](#4-feature-engineering)
5. [Data Normalization (StandardScaler)](#5-data-normalization-standardscaler)
6. [Training Process — Step by Step](#6-training-process--step-by-step)
7. [Automatic Retraining](#7-automatic-retraining)
8. [Prediction Process — Step by Step](#8-prediction-process--step-by-step)
9. [Anomaly Score → Severity Mapping](#9-anomaly-score--severity-mapping)
10. [Explainability — Which Feature Caused It?](#10-explainability--which-feature-caused-it)
11. [Model Persistence](#11-model-persistence)
12. [Where to See It in Action](#12-where-to-see-it-in-action)
13. [Key Configuration Parameters](#13-key-configuration-parameters)
14. [Limitations & Improvements](#14-limitations--improvements)

---

## 1. What Problem Does the Model Solve?

Traditional monitoring tools only alert when a **fixed threshold** is crossed:
```
if cpu_percent > 85%:  → fire alert
```

**Problems with this approach:**
- What if CPU is 80% AND RAM is 82% AND disk reads are spiking? No single threshold catches this.
- What if the server normally runs at 70% CPU (it's a busy server)? 80% is fine — but an alert fires anyway.
- What if something unusual happens at 40% CPU because of a rare combination of factors?

**CloudPulse uses Isolation Forest (unsupervised ML) to learn what "normal" looks like
for this specific machine and detect unusual patterns — even if no single metric
crosses a threshold.**

---

## 2. Algorithm — Isolation Forest

**File**: [`backend/app/ml/anomaly_detector.py`](../backend/app/ml/anomaly_detector.py)

**Library**: `scikit-learn` → `sklearn.ensemble.IsolationForest`

### Core Idea — Intuition

Imagine putting all your data points in a room and randomly dividing the room with walls:

```
Normal data points (clustered together):
  → Need MANY walls to isolate one point (they're packed together)
  → Long path through the "tree" → NORMAL

Anomalous data points (far from the group):
  → Only need FEW walls to isolate them (they're already alone)
  → Short path through the "tree" → ANOMALY
```

### How a Single Tree Works

```
Step 1: Pick a random feature (e.g., cpu_percent)
Step 2: Pick a random split value (e.g., 50%)
Step 3: Divide data into two groups: cpu < 50% and cpu >= 50%
Step 4: Repeat on each group until every point is isolated

Result: Count how many splits it took to isolate each point.
        Fewer splits = more anomalous.
```

### The Full Forest (150 Trees)

```
IsolationForest(n_estimators=150, contamination=0.05)

- Builds 150 random trees independently
- For each data point, averages the path length across all 150 trees
- Converts average path length to an anomaly score:
    score ≈ -0.5 to +0.1
    More negative → shorter average path → more anomalous
```

**Why 150 trees?** More trees = more stable, consistent predictions. Fewer trees = faster but noisier.

**Why unsupervised?** We don't have labeled data saying "this reading was an anomaly".
The model discovers anomalies purely from data structure — no human labeling needed.

---

## 3. Input Features

The model uses **7 features** per data point (5 raw + 2 engineered):

| # | Feature | Source | Description |
|---|---------|--------|-------------|
| 1 | `cpu_percent` | `psutil.cpu_percent()` | Overall CPU usage (0–100%) |
| 2 | `ram_percent` | `psutil.virtual_memory().percent` | RAM usage (0–100%) |
| 3 | `disk_percent` | `psutil.disk_usage("/").percent` | Disk storage used (0–100%) |
| 4 | `net_bytes_recv_mb` | `psutil.net_io_counters().bytes_recv` | Network received (MB, cumulative) |
| 5 | `net_bytes_sent_mb` | `psutil.net_io_counters().bytes_sent` | Network sent (MB, cumulative) |
| 6 | `cpu_ram_pressure` | *engineered* | `(cpu + ram) / 2` — combined load |
| 7 | `net_total_mb` | *engineered* | `recv + sent` — total throughput |

```python
# From anomaly_detector.py
RAW_FEATURES = [
    "cpu_percent",
    "ram_percent",
    "disk_percent",
    "net_bytes_recv_mb",
    "net_bytes_sent_mb",
]
ENGINEERED_FEATURES = [
    "cpu_ram_pressure",   # (cpu + ram) / 2.0
    "net_total_mb",       # recv + sent
]
ALL_FEATURES = RAW_FEATURES + ENGINEERED_FEATURES   # 7 total
```

---

## 4. Feature Engineering

**Feature engineering** means creating new features from existing ones to capture patterns
that raw data misses.

### Feature 1: `cpu_ram_pressure = (cpu_percent + ram_percent) / 2`

**Why it's needed:**

```
Scenario: CPU = 75%, RAM = 78%
Threshold check: Neither exceeds 85% → no alert ❌

But TOGETHER, the system is clearly under heavy stress.
cpu_ram_pressure = (75 + 78) / 2 = 76.5

The model sees this combined pressure and can flag it as unusual
if the machine normally runs at cpu_ram_pressure ≈ 30%.
```

### Feature 2: `net_total_mb = net_bytes_recv_mb + net_bytes_sent_mb`

**Why it's needed:**

```
Scenario: A DDoS attack sends huge inbound traffic.
  net_bytes_recv_mb suddenly jumps from 500 MB to 50,000 MB
  
Separately: recv=50000, sent=30  → maybe only recv looks odd
Together:   net_total_mb=50030   → clearly anomalous total throughput

Also catches large file uploads/downloads that may indicate data exfiltration.
```

```python
# From anomaly_detector.py
def _engineer(raw: dict) -> dict:
    cpu  = raw.get("cpu_percent", 0)       or 0
    ram  = raw.get("ram_percent", 0)       or 0
    recv = raw.get("net_bytes_recv_mb", 0) or 0
    sent = raw.get("net_bytes_sent_mb", 0) or 0
    return {
        **raw,
        "cpu_ram_pressure": (cpu + ram) / 2.0,
        "net_total_mb":     recv + sent,
    }
```

---

## 5. Data Normalization (StandardScaler)

**Problem without normalization:**

```
Feature values on completely different scales:
  cpu_percent        = 45.2        (range: 0–100)
  net_bytes_recv_mb  = 1,523.8     (range: 0–50,000+)

Without scaling, the model sees net_bytes_recv_mb as 33x more important
simply because its numbers are bigger — that's WRONG.
```

**Solution: StandardScaler (Z-score normalization)**

```python
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_raw)
# Each feature now has mean=0 and std=1

# Formula for each value:
# z = (x - mean) / standard_deviation
```

**After scaling:**
```
Before:                          After:
  cpu_percent        = 45.2   →    cpu_percent        = +0.3  (slightly above average)
  net_bytes_recv_mb  = 1523   →    net_bytes_recv_mb  = -0.1  (close to average)
  
Now all features are on equal footing — fair comparison!
```

The scaler remembers the **mean and standard deviation** from training data
and uses the same values to scale new incoming data at prediction time.

---

## 6. Training Process — Step by Step

**File**: [`backend/app/ml/anomaly_detector.py`](../backend/app/ml/anomaly_detector.py) → `train()` method

### Visual Flow

```
PostgreSQL database
(last 24 hours of data, e.g. 17,280 rows at 5s intervals)
           │
           ▼
  _do_retrain() in model_trainer.py
  Fetch all rows as Python dicts:
  [
    {"cpu_percent": 45.2, "ram_percent": 67.1, ...},
    {"cpu_percent": 43.0, "ram_percent": 65.8, ...},
    ...17,280 more rows...
  ]
           │
           ▼
  _build_matrix(data)
  Apply _engineer() to each row → adds 2 derived features
  Build NumPy array of shape (17280, 7)

  [[45.2, 67.1, 52.0, 120.5, 30.2, 56.15, 150.7],
   [43.0, 65.8, 52.0, 121.0, 30.5, 54.40, 151.5],
   ...
  ]
           │
           ▼
  StandardScaler.fit_transform(X_raw)
  Compute mean and std per column
  Transform: X_scaled = (X_raw - mean) / std
  Shape: still (17280, 7) but now all values near 0

  [[ 0.3,  0.4, -0.1,  0.2,  0.1,  0.35, 0.22],
   [ 0.2,  0.3, -0.1,  0.2,  0.1,  0.25, 0.22],
   ...
  ]
           │
           ▼
  IsolationForest(
      n_estimators=150,      ← 150 random decision trees
      contamination=0.05,    ← expect 5% of data is anomalous
      random_state=42,       ← reproducible results
      n_jobs=-1,             ← use all CPU cores
  ).fit(X_scaled)

  Result: 150 trained trees stored in memory
           │
           ▼
  Compute scores on training data:
  scores = model.score_samples(X_scaled)
  Stats: mean=-0.12, std=0.08, min=-0.65, max=0.04

  Save to disk:
  ├── app/ml/model.pkl     ← the trained IsolationForest
  ├── app/ml/scaler.pkl    ← the fitted StandardScaler
  └── app/ml/manifest.json ← metadata (when trained, how many samples, etc.)
```

### Minimum Data Requirement

```python
if len(data) < 50:
    return {"status": "skipped", "reason": "Need ≥50 samples to train"}
```

With the agent sending data every 5 seconds, 50 samples = **4 minutes 10 seconds** of uptime.

---

## 7. Automatic Retraining

**File**: [`backend/app/ml/model_trainer.py`](../backend/app/ml/model_trainer.py)

The model is NOT a static file — it **retrains automatically every hour** while the app runs.

### Background Loop

```python
async def retrain_model_task():
    await asyncio.sleep(60)      # Wait 60 seconds for app to settle on startup
    
    while True:
        result = await trigger_retrain()   # Train on latest 24h data
        log.info(f"Auto-retrain complete: {result}")
        await asyncio.sleep(3600)          # Sleep 1 hour, then retrain again
```

This loop starts when FastAPI starts (`lifespan` in `main.py`) and runs forever.

### Why Retrain Every Hour?

```
Hour 0:  Model trained on normal daytime usage (CPU ≈ 45% average)
Hour 8:  Office hours end → CPU drops to 10% average
Hour 9:  Retraining happens → model updates its idea of "normal" to 10% CPU
Hour 10: A rogue process spikes CPU to 40% overnight
         Old model: 40% is normal ❌ (it learned daytime patterns)
         New model: 40% is anomalous ✅ (it learned overnight patterns)
```

### Concurrency Safety

```python
_retrain_lock = asyncio.Lock()   # Only ONE retrain at a time

async def trigger_retrain():
    if _retrain_lock.locked():
        return {"status": "already_running"}  # Don't stack two retrains
    
    async with _retrain_lock:
        result = await _do_retrain()
    return result
```

### Why Thread Pool? (`run_in_executor`)

```python
# Problem: IsolationForest.fit() is CPU-bound Python/C code
# If run directly in async function, it BLOCKS the event loop for ~0.5 seconds
# During that 0.5s: no WebSocket messages, no HTTP responses → bad!

# Solution: run it in a separate thread
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, anomaly_detector.train, data)
#                                   ^^^^  use default ThreadPoolExecutor
# The event loop stays responsive while training happens in a thread
```

---

## 8. Prediction Process — Step by Step

**File**: [`backend/app/ml/anomaly_detector.py`](../backend/app/ml/anomaly_detector.py) → `predict()` method

This runs on **every metric** the agent sends (every 5 seconds).

```
Agent sends: { cpu_percent: 94.2, ram_percent: 88.1, disk_percent: 52.0, ... }
                           │
                           ▼
         Step 1: Feature engineering
         _engineer(metric) → adds cpu_ram_pressure=91.15, net_total_mb=...

         Step 2: Build matrix
         X_raw = [[94.2, 88.1, 52.0, 120.5, 30.2, 91.15, 150.7]]
         Shape: (1, 7)

         Step 3: Scale using TRAINING scaler (same mean/std from training!)
         X_scaled = scaler.transform(X_raw)
         Result:  [[3.8, 2.9, -0.1, 0.2, 0.1, 3.4, 0.2]]
         (CPU z-score = 3.8 → 3.8 standard deviations above normal!)

         Step 4: IsolationForest.predict()
         label = model.predict(X_scaled)[0]
         Result: -1  (-1 = anomaly, +1 = normal)

         Step 5: Get anomaly score
         score = model.score_samples(X_scaled)[0]
         Result: -0.482

         Step 6: Compute per-feature contributions
         abs_z = |X_scaled[0]| = [3.8, 2.9, 0.1, 0.2, 0.1, 3.4, 0.2]
         total = sum(abs_z)     = 10.7
         norm  = abs_z / total  = [0.355, 0.271, 0.009, ...]
         
         dominant_feature = "cpu_percent" (highest normalized contribution)

         Step 7: Return result
         (is_anomaly=True, score=-0.482, details={
           "dominant_feature": "cpu_percent",
           "contributions": {"cpu_percent": 0.355, "ram_percent": 0.271, ...},
           "z_scores": {"cpu_percent": 3.8, "ram_percent": 2.9, ...},
         })
```

---

## 9. Anomaly Score → Severity Mapping

**File**: [`backend/app/services/anomaly_service.py`](../backend/app/services/anomaly_service.py)

The raw score (e.g. `-0.482`) is converted to a human-readable severity level:

```python
def _score_to_severity(score: float) -> str:
    if score < -0.6:  return "critical"   # Extreme outlier
    if score < -0.4:  return "high"       # Significant anomaly
    if score < -0.2:  return "medium"     # Notable deviation
    return "low"                           # Slightly unusual
```

### Severity Scale

```
Score:   -0.8      -0.6      -0.4      -0.2       0.0      +0.1
          |---------|---------|---------|---------|---------|
          CRITICAL   HIGH      MEDIUM    LOW       NORMAL
                                                   (not saved)
```

| Severity | Score Range | Meaning |
|----------|-------------|---------|
| **Critical** | < -0.6 | Extreme, very rare behavior |
| **High** | -0.6 to -0.4 | Significant deviation from normal |
| **Medium** | -0.4 to -0.2 | Notable but not extreme |
| **Low** | > -0.2 (anomaly) | Slightly unusual, watch closely |
| Normal | > -0.2 (normal) | Not saved — expected behavior |

---

## 10. Explainability — Which Feature Caused It?

This is the **most important part** for real-world usefulness. Instead of just saying
"anomaly detected", CloudPulse explains WHY.

### The Math

After scaling, each feature's value IS a z-score:
```
z-score = (actual_value - mean_during_training) / std_during_training
```

Example:
```
Training mean CPU  = 42.0%,  std = 8.5%
Current CPU        = 94.2%

z-score = (94.2 - 42.0) / 8.5 = +6.1  ← 6.1 standard deviations above normal!
```

### Contribution Calculation

```python
abs_z = numpy.abs(X_scaled[0])        # absolute z-scores for each feature
total = abs_z.sum()                    # total "strangeness"
norm  = abs_z / total                  # each feature's share (sums to 1.0)

# Result:
contributions = {
    "cpu_percent":      0.72,   # 72% of the anomaly was due to CPU
    "cpu_ram_pressure": 0.18,   # 18% due to combined CPU+RAM pressure
    "ram_percent":      0.07,   # 7%  due to RAM
    "disk_percent":     0.02,   # 2%  due to disk
    "net_bytes_recv_mb":0.01,   # 1%  due to network
    ...
}
dominant_feature = "cpu_percent"        # The main culprit
```

### What Gets Saved to Database

```python
description = "Anomaly [cpu_percent] — cpu_percent=94.2% (z=6.1), ram_percent=88.1% (z=2.9)"
```

This appears in:
- The **AnomalyFeed** on the dashboard
- The **Toast notification** that pops up
- The **`/api/ml/predict`** response for teacher demonstration

---

## 11. Model Persistence

The model is saved to disk after every training so it survives backend restarts.

```
backend/app/ml/
├── model.pkl       ← serialized IsolationForest (pickle format)
├── scaler.pkl      ← serialized StandardScaler (pickle format)
└── manifest.json   ← training metadata
```

### `manifest.json` — What's Inside

```json
{
  "version": "2.0",
  "trained_at": "2026-06-13T01:00:00+00:00",
  "sample_count": 17280,
  "contamination": 0.05,
  "n_estimators": 150,
  "features": ["cpu_percent", "ram_percent", "disk_percent", ...],
  "feature_means": {
    "cpu_percent": 42.1,
    "ram_percent": 65.3,
    ...
  },
  "feature_stds": {
    "cpu_percent": 8.5,
    "ram_percent": 4.2,
    ...
  },
  "score_mean": -0.121,
  "score_std":  0.083,
  "score_min":  -0.641,
  "score_max":  0.041
}
```

### Load on Startup

```python
def _load_model(self):
    if os.path.exists("app/ml/model.pkl"):
        self.model  = pickle.load(open("app/ml/model.pkl",  "rb"))
        self.scaler = pickle.load(open("app/ml/scaler.pkl", "rb"))
        self.is_trained = True
        print("Loaded model v2.0 trained at 2026-06-13...")
    else:
        print("No saved model — will train after data arrives.")
```

---

## 12. Where to See It in Action

### Option 1: Swagger UI (Best for Teacher Demo)

Open: **`http://localhost:8000/docs`**

**Test the model with custom values:**
```
POST /api/ml/predict
{
  "cpu_percent": 95.0,
  "ram_percent": 92.0,
  "disk_percent": 45.0,
  "net_bytes_recv_mb": 0.0,
  "net_bytes_sent_mb": 0.0
}
```

**Expected response:**
```json
{
  "is_anomaly": true,
  "anomaly_score": -0.482,
  "severity": "high",
  "dominant_feature": "cpu_percent",
  "top_features": [
    { "feature": "cpu_percent",      "contribution": 0.72, "z_score": 3.8 },
    { "feature": "cpu_ram_pressure", "contribution": 0.20, "z_score": 2.1 }
  ]
}
```

**Check model status:**
```
GET /api/ml/status
```
Returns when it was trained, how many samples, feature statistics.

### Option 2: Live Dashboard

1. Open `http://localhost:5173`
2. Click **Dashboard** in the sidebar
3. Any detected anomaly appears in the **"AI Anomaly Feed"** panel (bottom right)
4. A **red toast notification** pops up in the top-right corner

### Option 3: Backend Logs

```bash
[AnomalyDetector] Loaded model v2.0 trained at 2026-06-13T00:00:00
[Trainer] Fetching training data...
[Trainer] Training on 17280 samples...
[Trainer] Auto-retrain complete: {'status': 'trained', 'samples': 17280, 'score_mean': -0.121}
```

---

## 13. Key Configuration Parameters

Set in `backend/app/config.py` or `.env`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MODEL_CONTAMINATION` | `0.05` | Expected anomaly rate (5% = 1 anomaly per 20 readings) |
| `MODEL_RETRAIN_INTERVAL` | `3600` | Retrain every 3600 seconds (1 hour) |

### Effect of `contamination` parameter

```
contamination=0.01  → very strict, only 1% of data flagged → fewer false alarms
contamination=0.05  → balanced (default), 5% flagged     ← used in CloudPulse
contamination=0.15  → sensitive, 15% flagged → more detections, more false alarms

Too low  = misses real anomalies (undersensitive)
Too high = cries wolf constantly (oversensitive)
```

---

## 14. Limitations & Improvements

### Current Limitations

| Limitation | Impact |
|------------|--------|
| Cumulative network counters | `net_bytes_recv_mb` grows since boot — model sees increasing baseline |
| Single-host only | No multi-machine comparison |
| No time-of-day awareness | Doesn't know "60% CPU is normal at 9am, anomalous at 3am" |
| 5% contamination is fixed | Should ideally be tuned to the specific machine |

### Possible Improvements (Future Work)

1. **Delta network I/O** — use `recv_now - recv_5s_ago` instead of cumulative totals
2. **Time features** — add `hour_of_day` and `day_of_week` as features
3. **Online learning** — update model incrementally without full retraining
4. **Multiple algorithms** — compare with LSTM Autoencoder or One-Class SVM
5. **User feedback loop** — let users mark false positives to improve the model

---

## Summary — The Full ML Pipeline

```
Every 5 seconds:
  Agent → psutil → 5 raw metrics

Each metric → Backend:
  Step 1: Engineer features (+2) → 7-dimensional vector
  Step 2: StandardScaler.transform() → z-scores (mean=0, std=1)
  Step 3: IsolationForest.predict() → label (-1 or +1)
  Step 4: IsolationForest.score_samples() → score (-0.8 to +0.1)
  Step 5: Per-feature contribution = |z-score| / sum(|z-scores|)
  Step 6: If anomaly → save to DB + broadcast via WebSocket + toast

Every hour (background):
  Query 24h data → StandardScaler.fit() + IsolationForest.fit()
  → Better "normal" definition → more accurate future detections

On startup:
  Load model.pkl + scaler.pkl from disk → ready immediately
```

---

*CloudPulse AI Module — Isolation Forest Anomaly Detection*
*Algorithm: scikit-learn IsolationForest | Features: 7 (5 raw + 2 engineered)*
*Training: Automatic hourly retraining on last 24h of data*
