"""
RAM Collector — gathers memory usage data using psutil.
"""
import psutil


def collect_ram() -> dict:
    mem = psutil.virtual_memory()
    return {
        "ram_total_gb": round(mem.total / (1024 ** 3), 2),
        "ram_used_gb": round(mem.used / (1024 ** 3), 2),
        "ram_percent": mem.percent,
    }
