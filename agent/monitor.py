"""
CloudPulse Monitoring Agent
============================
Collects system metrics every COLLECT_INTERVAL seconds and POSTs
them to the FastAPI backend.

Run: python -m agent.monitor
"""
import asyncio
import platform
import socket
from datetime import datetime

from agent.collectors.cpu_collector import collect_cpu
from agent.collectors.ram_collector import collect_ram
from agent.collectors.disk_collector import collect_disk
from agent.collectors.network_collector import collect_network
from agent.collectors.process_collector import collect_processes
from agent.sender import send_metrics
from agent.config import COLLECT_INTERVAL, TOP_PROCESSES

HOSTNAME = socket.gethostname()
PLATFORM = platform.system()


def collect_all_metrics() -> dict:
    """
    Merge data from all collectors into one flat dict.
    This becomes the JSON body sent to POST /api/metrics/
    """
    data = {}
    data.update(collect_cpu())
    data.update(collect_ram())
    data.update(collect_disk())
    data.update(collect_network())
    data["top_processes"] = collect_processes(TOP_PROCESSES)
    data["hostname"] = HOSTNAME
    data["platform"] = PLATFORM
    return data


async def run_agent():
    """Main agent loop — collect → send → sleep → repeat."""
    print(f"[Agent] CloudPulse Monitoring Agent started.")
    print(f"[Agent] Hostname: {HOSTNAME} | Platform: {PLATFORM}")
    print(f"[Agent] Sending to backend every {COLLECT_INTERVAL}s...")
    print("-" * 50)

    cycle = 0
    while True:
        cycle += 1
        start = datetime.utcnow()

        metrics = collect_all_metrics()
        success = await send_metrics(metrics)

        elapsed = (datetime.utcnow() - start).total_seconds()
        status = "OK" if success else "FAILED"
        print(
            f"[{start.strftime('%H:%M:%S')}] Cycle #{cycle} | "
            f"CPU: {metrics['cpu_percent']:.1f}% | "
            f"RAM: {metrics['ram_percent']:.1f}% | "
            f"Disk: {metrics['disk_percent']:.1f}% | "
            f"Send: {status} ({elapsed:.2f}s)"
        )

        # Wait remaining time to maintain the interval
        sleep_time = max(0, COLLECT_INTERVAL - elapsed)
        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    asyncio.run(run_agent())
