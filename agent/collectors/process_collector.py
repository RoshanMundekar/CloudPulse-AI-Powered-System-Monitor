"""
Process Collector — top N processes by CPU usage.
"""
import psutil


def collect_processes(top_n: int = 10) -> list[dict]:
    """
    Returns top N processes sorted by CPU percentage.
    Skips processes we can't access (permission denied).
    """
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "unknown",
                "cpu_percent": round(info["cpu_percent"] or 0, 2),
                "memory_percent": round(info["memory_percent"] or 0, 2),
                "status": info["status"] or "unknown",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort by CPU desc, return top N
    procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
    return procs[:top_n]
