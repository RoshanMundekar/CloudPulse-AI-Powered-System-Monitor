"""
Sample Dataset Generator — 5 realistic anomaly patterns for Isolation Forest training.

Anomaly types injected:
  1. CPU spike      — runaway batch job (CPU 90-100%, everything else normal)
  2. RAM leak       — memory leak growing from 80% → 98% over time
  3. Network flood  — DDoS / large transfer (500-2500 MB/s, CPU moderate)
  4. Disk I/O spike — database backup/compaction (300-900 MB read+write)
  5. Full crisis    — all metrics spike simultaneously (worst-case scenario)

Why 5 patterns?
  A model trained only on "everything is high" learns one kind of anomaly.
  Real-world anomalies are single-dimension (CPU only) or mixed (DDoS: net+cpu).
  Diverse training patterns make the model generalize better.

Run standalone:
  python -m app.ml.sample_data
"""
import asyncio
import random
from datetime import UTC, datetime, timedelta

import numpy as np

from app.database import AsyncSessionLocal, create_tables
from app.models.metrics import SystemMetric


# ── Helper ────────────────────────────────────────────────────────────────────

def _base() -> dict:
    """Common non-metric fields present in every SystemMetric row."""
    return {
        "cpu_count":        8,
        "cpu_freq_mhz":     random.uniform(2400, 3600),
        "ram_total_gb":     16.0,
        "disk_total_gb":    512.0,
        "net_packets_sent": random.randint(100, 5000),
        "net_packets_recv": random.randint(100, 8000),
        "hostname":         "cloudpulse-server",
        "platform":         "Linux",
        "top_processes":    [],
    }


# ── Normal baseline ───────────────────────────────────────────────────────────

def generate_normal_metrics(n: int = 500) -> list[dict]:
    """
    Typical server load: CPU 5-70%, RAM 20-78%, Disk 20-72%.
    Gaussian distributions so the model learns a realistic "normal" cluster.
    """
    data = []
    for _ in range(n):
        cpu  = float(np.clip(np.random.normal(35, 10),  5,  70))
        ram  = float(np.clip(np.random.normal(52, 12), 20,  78))
        disk = float(np.clip(np.random.normal(48,  8), 20,  72))
        data.append({
            **_base(),
            "cpu_percent":       cpu,
            "ram_used_gb":       16.0 * ram / 100,
            "ram_percent":       ram,
            "disk_used_gb":      512.0 * disk / 100,
            "disk_percent":      disk,
            "disk_read_mb":      random.uniform(0, 40),
            "disk_write_mb":     random.uniform(0, 25),
            "net_bytes_sent_mb": random.uniform(0, 8),
            "net_bytes_recv_mb": random.uniform(0, 15),
        })
    return data


# ── Anomaly pattern 1: CPU spike ──────────────────────────────────────────────

def generate_cpu_spike(n: int = 15) -> list[dict]:
    """
    Runaway batch job or crypto miner — CPU pegged at 90-100%
    while RAM and network remain at normal levels.
    """
    return [
        {
            **_base(),
            "cpu_percent":       random.uniform(92, 100),
            "ram_used_gb":       7.5,
            "ram_percent":       random.uniform(44, 56),
            "disk_used_gb":      240,
            "disk_percent":      random.uniform(44, 56),
            "disk_read_mb":      random.uniform(0, 20),
            "disk_write_mb":     random.uniform(0, 10),
            "net_bytes_sent_mb": random.uniform(0, 5),
            "net_bytes_recv_mb": random.uniform(0, 8),
        }
        for _ in range(n)
    ]


# ── Anomaly pattern 2: RAM leak ───────────────────────────────────────────────

def generate_ram_leak(n: int = 15) -> list[dict]:
    """
    Memory leak: RAM climbs from 80% → 98% over time.
    Swap writes increase as physical RAM fills up.
    CPU is elevated because GC and swap thrashing consume cycles.
    """
    data = []
    for i in range(n):
        ram = 80.0 + (i / n) * 18.0       # linear climb: 80% → 98%
        data.append({
            **_base(),
            "cpu_percent":       random.uniform(55, 78),
            "ram_used_gb":       16.0 * ram / 100,
            "ram_percent":       ram,
            "disk_used_gb":      240,
            "disk_percent":      random.uniform(44, 56),
            "disk_read_mb":      random.uniform(0, 30),
            "disk_write_mb":     random.uniform(150, 350),  # swap writes spike
            "net_bytes_sent_mb": random.uniform(0, 5),
            "net_bytes_recv_mb": random.uniform(0, 8),
        })
    return data


# ── Anomaly pattern 3: Network flood ─────────────────────────────────────────

def generate_network_flood(n: int = 15) -> list[dict]:
    """
    DDoS attack or large-file transfer: inbound/outbound network throughput
    500-2500 MB, packet counts in the hundreds of thousands.
    CPU moderately elevated from kernel network processing.
    """
    return [
        {
            **_base(),
            "cpu_percent":       random.uniform(40, 65),
            "ram_used_gb":       9.0,
            "ram_percent":       random.uniform(50, 65),
            "disk_used_gb":      240,
            "disk_percent":      random.uniform(44, 56),
            "disk_read_mb":      random.uniform(0, 20),
            "disk_write_mb":     random.uniform(0, 10),
            "net_bytes_sent_mb": random.uniform(500, 2500),
            "net_bytes_recv_mb": random.uniform(600, 2500),
            "net_packets_sent":  random.randint(200_000, 800_000),
            "net_packets_recv":  random.randint(200_000, 800_000),
        }
        for _ in range(n)
    ]


# ── Anomaly pattern 4: Disk I/O spike ────────────────────────────────────────

def generate_disk_io_spike(n: int = 10) -> list[dict]:
    """
    Database backup, compaction, or log rotation: disk usage near capacity
    (88-97%) with read+write throughput 300-900 MB.
    """
    return [
        {
            **_base(),
            "cpu_percent":       random.uniform(30, 55),
            "ram_used_gb":       8.0,
            "ram_percent":       random.uniform(48, 58),
            "disk_used_gb":      480,
            "disk_percent":      random.uniform(88, 97),
            "disk_read_mb":      random.uniform(300, 900),
            "disk_write_mb":     random.uniform(200, 700),
            "net_bytes_sent_mb": random.uniform(0, 5),
            "net_bytes_recv_mb": random.uniform(0, 8),
        }
        for _ in range(n)
    ]


# ── Anomaly pattern 5: Full crisis ────────────────────────────────────────────

def generate_full_crisis(n: int = 10) -> list[dict]:
    """
    Worst-case: CPU + RAM + Disk + Network all critical simultaneously.
    Simulates a cascading failure or severe resource contention.
    """
    return [
        {
            **_base(),
            "cpu_percent":       random.uniform(90, 100),
            "ram_used_gb":       15.5,
            "ram_percent":       random.uniform(92, 99),
            "disk_used_gb":      490,
            "disk_percent":      random.uniform(90, 98),
            "disk_read_mb":      random.uniform(400, 900),
            "disk_write_mb":     random.uniform(300, 700),
            "net_bytes_sent_mb": random.uniform(500, 1500),
            "net_bytes_recv_mb": random.uniform(600, 2000),
            "net_packets_sent":  random.randint(300_000, 900_000),
            "net_packets_recv":  random.randint(300_000, 900_000),
        }
        for _ in range(n)
    ]


# ── Database insertion ────────────────────────────────────────────────────────

async def insert_sample_data():
    """
    Insert all sample metrics with realistic timestamps spread over 24 hours.
    Shuffles anomalies into the normal data stream (as they'd appear in production).
    """
    await create_tables()

    normal    = generate_normal_metrics(500)
    anomalous = (
        generate_cpu_spike(15)
        + generate_ram_leak(15)
        + generate_network_flood(15)
        + generate_disk_io_spike(10)
        + generate_full_crisis(10)
    )

    all_metrics = normal + anomalous
    random.shuffle(all_metrics)

    now   =  datetime.now(UTC)
    total = len(all_metrics)

    async with AsyncSessionLocal() as db:
        for i, m in enumerate(all_metrics):
            # Spread evenly across the last 24 hours
            timestamp = now - timedelta(seconds=(total - i) * (86400 // total))
            row = SystemMetric(**m, created_at=timestamp)
            db.add(row)
        await db.commit()

    print(
        f"[SampleData] Inserted {total} metrics "
        f"({len(normal)} normal + {len(anomalous)} anomalous across 5 patterns)."
    )
    return all_metrics


if __name__ == "__main__":
    asyncio.run(insert_sample_data())
    print(
        "Done. Trigger model training:\n"
        "  python -c \"import asyncio; from app.ml.model_trainer import trigger_retrain; "
        "asyncio.run(trigger_retrain())\""
    )
