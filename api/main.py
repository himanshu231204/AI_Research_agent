"""
FastAPI Application for Research OS.

Provides REST API, WebSocket, and health endpoints.
"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import get_settings
from api.routes import health, research, websocket, memory, models
from api.middleware.rate_limit import RateLimitMiddleware
from observability.langsmith import configure_langsmith
from models.registry import initialize_model_registry


# Configure logging with custom formatter to handle missing request_id
class SafeFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = "N/A"
        return super().format(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
)
logger = logging.getLogger(__name__)

# Apply custom formatter to root handlers
for handler in logging.root.handlers:
    handler.setFormatter(
        SafeFormatter("%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s")
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request logging."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Log incoming request
        logger.info(
            f"INCOMING_REQUEST",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown",
            },
        )

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log completed request
            logger.info(
                f"REQUEST_COMPLETE",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"REQUEST_ERROR",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    configure_langsmith(settings)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Startup
    logger.info("Initializing services...")

    # Initialize model registry
    try:
        await initialize_model_registry()
        logger.info("Model registry initialized")
    except Exception as e:
        logger.error(f"Failed to initialize model registry: {e}")

    yield

    # Shutdown
    logger.info("Shutting down services...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous AI Research Operating System",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Rate limiting middleware
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests_per_minute,
            burst=settings.rate_limit_burst,
            enabled=settings.rate_limit_enabled,
        )

    # CORS middleware with security best practices
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
        max_age=600,  # Cache preflight for 10 minutes
    )

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(
        research.router,
        prefix=settings.api_v1_prefix,
        tags=["Research"],
    )
    # WebSocket is at root level for direct access
    app.include_router(websocket.router, prefix="", tags=["WebSocket"])
    app.include_router(
        memory.router,
        prefix=settings.api_v1_prefix,
        tags=["Memory & RAG"],
    )
    app.include_router(
        models.router,
        prefix=settings.api_v1_prefix,
        tags=["Models & Routing"],
    )

    return app


# Add exception handlers after app creation
def add_exception_handlers(app: FastAPI):
    """Add global exception handlers for consistent error responses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions with proper error format."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.warning(
            f"HTTPException: {exc.status_code} - {exc.detail}",
            extra={"request_id": request_id, "status_code": exc.status_code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "request_id": request_id,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle ValueError exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(f"ValueError: {str(exc)}", extra={"request_id": request_id})
        return JSONResponse(
            status_code=400,
            content={
                "error": str(exc),
                "status_code": 400,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions - prevents leaking internal errors."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={"request_id": request_id, "exception_type": type(exc).__name__},
            exc_info=True,
        )
        # Don't expose internal error details to clients in production
        settings = get_settings()
        error_message = (
            "An internal error occurred"
            if settings.environment.lower() == "production"
            else str(exc)
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": error_message,
                "status_code": 500,
                "request_id": request_id,
            },
        )


app = create_app()
add_exception_handlers(app)

# Initialize Prometheus metrics instrumentation
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
