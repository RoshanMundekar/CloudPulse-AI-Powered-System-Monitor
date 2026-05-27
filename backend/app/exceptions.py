"""
CloudPulse — Global Exception Handlers

Registers FastAPI exception handlers so every error returns
a consistent JSON envelope instead of FastAPI's default format.

Response shape:
  { "error": "<short code>", "detail": "<message>", "path": "/api/..." }
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging

log = logging.getLogger("cloudpulse.exceptions")


def _body(error: str, detail: str, request: Request) -> dict:
    return {"error": error, "detail": detail, "path": request.url.path}


def register_exception_handlers(app: FastAPI) -> None:
    """Call this once in main.py after creating the app."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # Flatten pydantic errors into a readable list
        errors = [
            f"{' → '.join(str(l) for l in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body("validation_error", "; ".join(errors), request),
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(request: Request, exc: SQLAlchemyError):
        log.error(f"DB error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_body("database_error", "A database error occurred.", request),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_body("bad_request", str(exc), request),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        log.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body("internal_error", "An unexpected error occurred.", request),
        )
