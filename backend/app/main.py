"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, init_db
from app.utils.logger import logger
from app.services.extraction_job_service import ExtractionJobService
from app.routers import (
    ingestion,
    multi_source,
    extraction,
    investigations,
    evaluation,
    reference_data,
    enrichment,
    discovery,
    commerce_output,
    catalog,
    dashboard,
)


# Initialize database tables and additive migrations before serving requests.
init_db()


def _allowed_origins() -> list[str]:
    """Build the list of allowed frontend origins."""
    configured = [
        origin.strip().rstrip("/")
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ]

    if settings.frontend_url:
        configured.append(
            settings.frontend_url.strip().rstrip("/")
        )

    # Production Vercel frontend
    configured.append(
        "https://frontend-pxznmj097-navika-m.vercel.app"
    )

    return list(dict.fromkeys(configured))

_docs_url = "/docs" if settings.enable_docs else None
_redoc_url = "/redoc" if settings.enable_docs else None
_openapi_url = "/openapi.json" if settings.enable_docs else None


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    debug=settings.debug,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
    ],
)


# ---------------------------------------------------------------------------
# Request logging
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled request error request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise

    duration_ms = (perf_counter() - started) * 1000

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    return response


# ---------------------------------------------------------------------------
# Global exception handling
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def safe_unhandled_exception_handler(
    request: Request,
    exc: Exception,
):
    """Return a useful generic error without exposing stack traces or secrets."""

    request_id = request.headers.get("X-Request-ID") or "unknown"

    logger.exception(
        "Unhandled application exception request_id=%s path=%s",
        request_id,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected server error occurred.",
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s",
        settings.api_title,
        settings.api_version,
    )

    logger.info(
        "Environment: %s",
        settings.environment,
    )

    logger.info(
        "Database configured: %s",
        settings.database_url.split(":", 1)[0],
    )

    # Recover queued/interrupted background extraction tasks.
    ExtractionJobService.recover_pending_tasks()

    yield

    logger.info(
        "Shutting down %s",
        settings.api_title,
    )


app.router.lifespan_context = lifespan


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Existing Phase 1–10 routers remain registered unchanged.
app.include_router(ingestion.router)
app.include_router(multi_source.router)
app.include_router(extraction.router)
app.include_router(investigations.router)
app.include_router(evaluation.router)
app.include_router(reference_data.router)
app.include_router(enrichment.router)
app.include_router(discovery.router)
app.include_router(commerce_output.router)
app.include_router(catalog.router)
app.include_router(dashboard.router)


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Production health check including database reachability."""

    database_status = "healthy"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unhealthy"

    overall = (
        "healthy"
        if database_status == "healthy"
        else "degraded"
    )

    return {
        "status": overall,
        "service": settings.api_title,
        "version": settings.api_version,
        "environment": settings.environment,
        "database": database_status,
        "discovery_provider": (
            settings.discovery_provider
            if settings.discovery_provider != "none"
            else "not_configured"
        ),
    }


@app.get("/api/v1/health/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe for deployment load balancers and container orchestration."""

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unhealthy",
            },
        )

    return {
        "status": "ready",
        "database": "healthy",
    }


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.api_title}",
        "version": settings.api_version,
        "docs": "/docs" if settings.enable_docs else None,
        "health": "/api/v1/health",
    }


# ---------------------------------------------------------------------------
# Local development entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
