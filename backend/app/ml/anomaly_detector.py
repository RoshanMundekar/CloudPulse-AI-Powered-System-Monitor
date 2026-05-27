"""
AI Anomaly Detector — Isolation Forest with feature engineering and explanation.

How Isolation Forest works:
  - Builds a forest of random binary trees that try to isolate each data point
  - Anomalies require fewer splits to isolate (shorter path length in the tree)
  - score_samples() returns negative values for anomalies; closer to 0 = more normal
  - contamination = expected fraction of outliers in training data (tunable)

Feature engineering beyond raw metrics:
  - cpu_ram_pressure: average CPU+RAM load — captures "system under stress" pattern
    where neither metric alone crosses the threshold but together signal a problem
  - net_total_mb: total inbound + outbound throughput — catches DDoS / large transfers

Per-feature contributions:
  After scaling, each feature's value is a z-score (standard deviations from mean).
  We take |z-score| for each feature and normalize them to sum to 1.
  This gives a 0-1 weight showing which feature drove the anomaly the most.
"""
import json
import os
import pickle
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.config import settings

# ── File paths (relative to backend/ working directory) ───────────────────────
_ML_DIR       = "app/ml"
MODEL_PATH    = f"{_ML_DIR}/model.pkl"
SCALER_PATH   = f"{_ML_DIR}/scaler.pkl"
MANIFEST_PATH = f"{_ML_DIR}/manifest.json"

# ── Feature definitions ───────────────────────────────────────────────────────
RAW_FEATURES = [
    "cpu_percent",
    "ram_percent",
    "disk_percent",
    "net_bytes_recv_mb",
    "net_bytes_sent_mb",
]
ENGINEERED_FEATURES = [
    "cpu_ram_pressure",  # (cpu + ram) / 2 — combined load pressure
    "net_total_mb",      # recv + sent — total throughput
]
ALL_FEATURES = RAW_FEATURES + ENGINEERED_FEATURES


def _engineer(raw: dict) -> dict:
    """Add derived features to a raw metric dict (non-destructive)."""
    cpu  = raw.get("cpu_percent", 0)       or 0
    ram  = raw.get("ram_percent", 0)       or 0
    recv = raw.get("net_bytes_recv_mb", 0) or 0
    sent = raw.get("net_bytes_sent_mb", 0) or 0
    return {
        **raw,
        "cpu_ram_pressure": (cpu + ram) / 2.0,
        "net_total_mb":     recv + sent,
    }


class AnomalyDetector:
    """
    Isolation Forest wrapper with feature engineering, persistence, and explanation.

    Usage:
        from app.ml.anomaly_detector import anomaly_detector  # singleton
        is_anomaly, score, details = anomaly_detector.predict(metric_dict)
    """

    def __init__(self):
        self.model:      IsolationForest | None = None
        self.scaler:     StandardScaler  | None = None
        self.is_trained: bool = False
        self.metadata:   dict = {}
        self._load_model()

    # ── Public methods ────────────────────────────────────────────────────────

    def train(self, data: list[dict]) -> dict:
        """
        Fit a new Isolation Forest on historical metric data.

        Args:
            data: list of metric dicts with at least the RAW_FEATURES keys.
                  Engineered features are computed automatically.

        Returns:
            stats dict with status, sample count, score distribution.
            Saves model + scaler + manifest to disk on success.
        """
        if len(data) < 50:
            return {
                "status": "skipped",
                "reason": f"Need ≥50 samples to train, got {len(data)}",
            }

        X_raw    = self._build_matrix(data)

        # Fit scaler: transforms each feature to mean=0, std=1
        # Without this, network MB values (0–2000) would dominate CPU % (0–100)
        self.scaler  = StandardScaler()
        X_scaled     = self.scaler.fit_transform(X_raw)

        # n_estimators=150: more trees → more stable predictions
        # n_jobs=-1: use all CPU cores for faster training
        self.model = IsolationForest(
            n_estimators=150,
            contamination=settings.MODEL_CONTAMINATION,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)
        self.is_trained = True

        # Compute score distribution on training data (useful for calibration)
        scores = self.model.score_samples(X_scaled)

        self.metadata = {
            "version":       "2.0",
            "trained_at":    datetime.now(timezone.utc).isoformat(),
            "sample_count":  len(data),
            "contamination": settings.MODEL_CONTAMINATION,
            "n_estimators":  150,
            "features":      ALL_FEATURES,
            "feature_means": dict(zip(ALL_FEATURES, self.scaler.mean_.tolist())),
            "feature_stds":  dict(zip(ALL_FEATURES, self.scaler.scale_.tolist())),
            "score_mean":    float(np.mean(scores)),
            "score_std":     float(np.std(scores)),
            "score_min":     float(np.min(scores)),
            "score_max":     float(np.max(scores)),
        }

        self._save_model()
        self._save_manifest()

        return {
            "status":     "trained",
            "samples":    len(data),
            "score_mean": self.metadata["score_mean"],
            "score_min":  self.metadata["score_min"],
            "trained_at": self.metadata["trained_at"],
        }

    def predict(self, metric: dict) -> tuple[bool, float, dict]:
        """
        Predict whether a metric snapshot is anomalous.

        Returns:
            is_anomaly (bool)  — True if the model flags it as an outlier
            score (float)      — anomaly score; negative = more anomalous
                                  typical range: [-0.8, 0.1]
            details (dict)     — per-feature breakdown:
                  contributions: dict[feature, 0-1 normalized weight]
                  z_scores:      dict[feature, standardized value]
                  values:        dict[feature, original value after engineering]
                  dominant_feature: feature with highest contribution
        """
        if not self.is_trained:
            return False, 0.0, {}

        enriched = _engineer(metric)
        X_raw    = self._build_matrix([enriched])    # shape (1, 7)
        X_scaled = self.scaler.transform(X_raw)       # shape (1, 7)

        label = self.model.predict(X_scaled)[0]                    # -1 or 1
        score = float(self.model.score_samples(X_scaled)[0])

        row   = X_scaled[0]
        abs_z = np.abs(row)
        total = float(abs_z.sum())
        norm  = (abs_z / total) if total > 0 else abs_z

        details = {
            "contributions":    {f: float(norm[i])      for i, f in enumerate(ALL_FEATURES)},
            "z_scores":         {f: float(row[i])       for i, f in enumerate(ALL_FEATURES)},
            "values":           {f: float(X_raw[0][i])  for i, f in enumerate(ALL_FEATURES)},
            "dominant_feature": ALL_FEATURES[int(np.argmax(abs_z))],
        }

        return label == -1, round(score, 6), details

    def get_status(self) -> dict:
        """Serialize current state for the /api/ml/status endpoint."""
        return {
            "is_trained": self.is_trained,
            "metadata":   self.metadata,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_matrix(self, data: list[dict]) -> np.ndarray:
        """
        Build an (N × 7) feature matrix from a list of metric dicts.
        Applies feature engineering to each row automatically.
        """
        rows = []
        for raw in data:
            enriched = _engineer(raw)
            rows.append([enriched.get(f, 0) or 0 for f in ALL_FEATURES])
        return np.array(rows, dtype=float)

    def _load_model(self):
        """Load a previously trained model from disk on startup."""
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            try:
                with open(MODEL_PATH, "rb") as f:
                    self.model = pickle.load(f)
                with open(SCALER_PATH, "rb") as f:
                    self.scaler = pickle.load(f)
                if os.path.exists(MANIFEST_PATH):
                    with open(MANIFEST_PATH) as f:
                        self.metadata = json.load(f)
                self.is_trained = True
                print(
                    f"[AnomalyDetector] Loaded model v{self.metadata.get('version', '?')} "
                    f"trained at {self.metadata.get('trained_at', 'unknown')}"
                )
            except Exception as exc:
                print(f"[AnomalyDetector] Failed to load saved model: {exc}")
        else:
            print("[AnomalyDetector] No saved model — will train after data arrives.")

    def _save_model(self):
        os.makedirs(_ML_DIR, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(SCALER_PATH, "wb") as f:
            pickle.dump(self.scaler, f)

    def _save_manifest(self):
        os.makedirs(_ML_DIR, exist_ok=True)
        with open(MANIFEST_PATH, "w") as f:
            json.dump(self.metadata, f, indent=2, default=str)


# ── Module-level singleton ────────────────────────────────────────────────────
# One instance shared across all FastAPI requests — models are not re-created
# per request (that would be catastrophically slow).
anomaly_detector = AnomalyDetector()
