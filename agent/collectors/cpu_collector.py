"""
CPU Collector — gathers CPU usage data using psutil.
"""
import psutil


def collect_cpu() -> dict:
    """
    Returns CPU metrics:
    - percent: overall utilization
    - count: logical core count
    - freq_mhz: current clock speed
    """
    freq = psutil.cpu_freq()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),   # 1-second sample
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(freq.current, 1) if freq else None,
    }
