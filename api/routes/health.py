"""
Health check and monitoring endpoints for Research OS.

Provides:
- System health checks
- Worker monitoring
- Queue inspection
- Celery worker status
- Redis queue statistics
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

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


class WorkerStatus(BaseModel):
    """Celery worker status."""

    name: str
    status: str
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    uptime_seconds: float
    last_heartbeat: Optional[str] = None


class QueueStatus(BaseModel):
    """Queue status information."""

    name: str
    status: str
    active_tasks: int
    pending_tasks: int
    worker_count: int


class WorkerHealthResponse(BaseModel):
    """Worker monitoring response."""

    timestamp: datetime
    total_workers: int
    workers: List[WorkerStatus]
    queues: List[QueueStatus]
    overall_status: str


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


@router.get("/health/workers", response_model=WorkerHealthResponse)
async def worker_health() -> WorkerHealthResponse:
    """
    Worker health monitoring endpoint.

    Returns status of all Celery workers and queues.
    """
    # Get Celery worker stats
    workers = await get_worker_stats()
    queues = await get_queue_stats()

    # Determine overall status
    overall_status = "healthy"
    if len(workers) == 0:
        overall_status = "no_workers"
    elif any(w.status == "offline" for w in workers):
        overall_status = "degraded"

    return WorkerHealthResponse(
        timestamp=datetime.utcnow(),
        total_workers=len(workers),
        workers=workers,
        queues=queues,
        overall_status=overall_status,
    )


@router.get("/health/queues")
async def queue_health() -> Dict[str, Any]:
    """
    Queue health monitoring endpoint.

    Returns status of all queues.
    """
    queues = await get_queue_stats()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "queues": queues,
        "total_queues": len(queues),
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

    # Check Celery
    services["celery"] = await check_celery(settings)

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


async def check_celery(settings) -> ServiceHealth:
    """Check Celery connectivity."""
    start = time.perf_counter()
    try:
        from celery.app.control import Inspect

        # Try to get worker stats
        inspect = Inspect()
        stats = inspect.stats()

        if stats:
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealth(status="healthy", latency_ms=round(latency, 2))
        else:
            return ServiceHealth(status="degraded", error="No workers registered")
    except Exception as e:
        return ServiceHealth(status="unhealthy", error=str(e))


async def get_worker_stats() -> List[WorkerStatus]:
    """Get statistics from Celery workers."""
    try:
        from celery.app.control import Inspect

        inspect = Inspect()

        # Get worker stats
        stats = inspect.stats() or {}
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}

        workers = []
        for worker_name, worker_stats in stats.items():
            active_tasks = len(active.get(worker_name, []))
            reserved_tasks = len(reserved.get(worker_name, []))

            workers.append(
                WorkerStatus(
                    name=worker_name,
                    status="online",
                    active_tasks=active_tasks,
                    completed_tasks=worker_stats.get("total", {}).get("celery.backend.count", 0),
                    failed_tasks=worker_stats.get("total", {}).get("celery.backend.errors", 0),
                    uptime_seconds=worker_stats.get("uptime", 0),
                    last_heartbeat=worker_stats.get("last_heartbeat"),
                )
            )

        return workers

    except Exception:
        return []


async def get_queue_stats() -> List[QueueStatus]:
    """Get statistics for all queues."""
    from workers.queues import get_all_queue_names, QUEUES

    queues = []

    try:
        from celery.app.control import Inspect

        inspect = Inspect()
        active = inspect.active() or {}

        # Count active tasks per queue
        queue_activity = {}
        for worker_tasks in active.values():
            for task in worker_tasks:
                task_name = task.get("name", "")
                # Infer queue from task name
                if "research" in task_name:
                    queue_activity.setdefault("research", 0)
                    queue_activity["research"] += 1
                elif "browser" in task_name:
                    queue_activity.setdefault("browser", 0)
                    queue_activity["browser"] += 1
                elif "rag" in task_name:
                    queue_activity.setdefault("rag", 0)
                    queue_activity["rag"] += 1
                elif "reflection" in task_name:
                    queue_activity.setdefault("reflection", 0)
                    queue_activity["reflection"] += 1
                elif "high_priority" in task_name or "orchestration" in task_name:
                    queue_activity.setdefault("high_priority", 0)
                    queue_activity["high_priority"] += 1

    except Exception:
        queue_activity = {}

    # Build queue statuses
    for queue_name in get_all_queue_names():
        config = QUEUES[queue_name]

        queues.append(
            QueueStatus(
                name=queue_name,
                status="active" if queue_activity.get(queue_name, 0) > 0 else "idle",
                active_tasks=queue_activity.get(queue_name, 0),
                pending_tasks=0,  # Would need Redis inspection for accurate count
                worker_count=1,  # Estimated
            )
        )

    return queues
