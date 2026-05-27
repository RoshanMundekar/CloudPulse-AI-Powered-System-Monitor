"""
Network Collector — bandwidth usage since system boot (cumulative counters).
"""
import psutil


def collect_network() -> dict:
    net = psutil.net_io_counters()
    return {
        "net_bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 3),
        "net_bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 3),
        "net_packets_sent": net.packets_sent,
        "net_packets_recv": net.packets_recv,
    }
