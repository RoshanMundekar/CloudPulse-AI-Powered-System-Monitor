"""
Sender — POST collected metrics to the FastAPI backend.
Uses httpx for async HTTP calls with retry logic.
"""
import httpx
import asyncio
from agent.config import BACKEND_URL

API_ENDPOINT = f"{BACKEND_URL}/api/metrics/"

# Retry settings: try 3 times with 2s between attempts
MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def send_metrics(data: dict) -> bool:
    """
    Send metric JSON to the backend.
    Returns True on success, False after all retries fail.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.post(API_ENDPOINT, json=data)
                if response.status_code == 201:
                    return True
                print(f"[Sender] HTTP {response.status_code}: {response.text[:200]}")
            except httpx.ConnectError:
                print(f"[Sender] Connection failed (attempt {attempt}/{MAX_RETRIES}). "
                      f"Is the backend running at {BACKEND_URL}?")
            except httpx.TimeoutException:
                print(f"[Sender] Request timed out (attempt {attempt}/{MAX_RETRIES}).")
            except Exception as e:
                print(f"[Sender] Unexpected error: {e}")

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

    return False
