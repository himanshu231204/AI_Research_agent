"""
Health check endpoints for Research OS.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, Any]


class ServiceHealth(BaseModel):
    """Individual service health status."""

    status: str
    latency_ms: float | None = None
    error: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Main health check endpoint.

    Returns overall system health status.
    """
    from api.config import get_settings

    settings = get_settings()

    # Check services
    services = await check_services()

    # Determine overall status
    overall_status = "healthy"
    if any(s.status == "unhealthy" for s in services.values()):
        overall_status = "degraded"
    if all(s.status == "unhealthy" for s in services.values()):
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.app_version,
        environment=settings.environment,
        services=services,
    )


@router.get("/health/live")
async def liveness() -> Dict[str, str]:
    """Liveness probe for container orchestration."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> Dict[str, Any]:
    """Readiness probe for container orchestration."""
    services = await check_services()

    ready = all(s.status != "unhealthy" for s in services.values())

    return {
        "ready": ready,
        "services": services,
    }


async def check_services() -> Dict[str, Any]:
    """Check health of all dependent services."""
    from api.config import get_settings

    settings = get_settings()
    services: Dict[str, Any] = {}

    # Check Redis
    services["redis"] = await check_redis(settings)

    # Check PostgreSQL
    services["postgres"] = await check_postgres(settings)

    # Check Ollama
    services["ollama"] = await check_ollama(settings)

    return services


async def check_redis(settings) -> ServiceHealth:
    """Check Redis connectivity."""
    import redis.asyncio as redis

    start = time.perf_counter()
    try:
        client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            socket_timeout=2,
        )
        await client.ping()
        await client.aclose()
        latency = (time.perf_counter() - start) * 1000
        return ServiceHealth(status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        return ServiceHealth(status="unhealthy", error=str(e))


async def check_postgres(settings) -> ServiceHealth:
    """Check PostgreSQL connectivity."""
    import asyncpg

    start = time.perf_counter()
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            timeout=2,
        )
        await conn.close()
        latency = (time.perf_counter() - start) * 1000
        return ServiceHealth(status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        return ServiceHealth(status="unhealthy", error=str(e))


async def check_ollama(settings) -> ServiceHealth:
    """Check Ollama connectivity."""
    import httpx

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                latency = (time.perf_counter() - start) * 1000
                return ServiceHealth(status="healthy", latency_ms=round(latency, 2))
            return ServiceHealth(status="unhealthy", error=f"Status: {response.status_code}")
    except Exception as e:
        return ServiceHealth(status="unhealthy", error=str(e))
