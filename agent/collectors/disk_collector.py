"""
Disk Collector — storage utilization and I/O throughput.
"""
import psutil


def collect_disk() -> dict:
    usage = psutil.disk_usage("/")
    io = psutil.disk_io_counters()
    return {
        "disk_total_gb": round(usage.total / (1024 ** 3), 2),
        "disk_used_gb": round(usage.used / (1024 ** 3), 2),
        "disk_percent": usage.percent,
        "disk_read_mb": round(io.read_bytes / (1024 ** 2), 3) if io else None,
        "disk_write_mb": round(io.write_bytes / (1024 ** 2), 3) if io else None,
    }
