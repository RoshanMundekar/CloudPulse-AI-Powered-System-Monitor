"""
Agent Configuration — load from environment or use defaults.
"""
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "5"))  # seconds
TOP_PROCESSES = int(os.getenv("TOP_PROCESSES", "10"))
