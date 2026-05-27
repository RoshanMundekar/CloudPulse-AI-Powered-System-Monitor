"""
CloudPulse — Custom Middleware

1. RequestTimingMiddleware  — adds X-Process-Time header to every response
2. RequestLoggingMiddleware — structured access logs (method, path, status, ms)

Both are lightweight async middleware that add zero blocking.
"""
import time
import logging
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("cloudpulse.http")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Adds 'X-Process-Time: <ms>' header to every HTTP response.
    Useful for debugging slow queries from the browser Network tab.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured access log:  POST /api/metrics/ 201 12.34ms
    Skips /health and /ws to avoid log noise.
    """
    SKIP_PATHS = {"/health", "/ws", "/"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        log.info(
            "%s %s %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


def register_middleware(app: FastAPI) -> None:
    """Register all middleware in the correct order (outermost first)."""
    # Logging wraps Timing (so the logged time includes the timing header write)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestTimingMiddleware)
