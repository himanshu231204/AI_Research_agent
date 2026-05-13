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
from starlette.middleware.base import BaseHTTPMiddleware

from api.config import get_settings
from api.routes import health, research, websocket, memory, models
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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
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


app = create_app()

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
