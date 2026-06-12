"""
Utility helpers used across the backend.
"""
from datetime import UTC, datetime


def utc_now_iso() -> str:
    return  datetime.now(UTC).isoformat() + "Z"


def bytes_to_mb(b: int) -> float:
    return round(b / (1024 * 1024), 3)


def bytes_to_gb(b: int) -> float:
    return round(b / (1024 ** 3), 2)
