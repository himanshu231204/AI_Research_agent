"""
Celery application configuration for Research OS.

This is the main entry point for all Celery workers and beat scheduler.
Configures:
- Redis broker with connection pooling
- Result backend with persistence
- Queue definitions with priorities
- Retry configuration
- Task tracking and monitoring
- Health checks
"""

import logging
from typing import Any, Dict, List

from celery import Celery
from celery.signals import (
    worker_init,
    worker_shutdown,
    worker_ready,
    task_prerun,
    task_postrun,
    task_retry,
    task_failure,
    task_success,
)
from kombu import Exchange, Queue as KombuQueue

from api.config import get_settings
from workers.queues import QUEUES, DEFAULT_QUEUE, get_all_queue_names

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create Celery app with explicit broker connection settings
celery_app = Celery(
    "research_os",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.research",
        "workers.tasks.browser",
        "workers.tasks.rag",
        "workers.tasks.reflection",
        "workers.tasks.inference",
    ],
)


def _create_queue_with_priority(
    name: str,
    priority: int,
    exchange: str = "default",
    routing_key: str = None,
) -> KombuQueue:
    """
    Create a queue with custom priority.

    Args:
        name: Queue name
        priority: Priority level (0 = highest)
        exchange: Exchange name
        routing_key: Optional routing key

    Returns:
        KombuQueue instance
    """
    if routing_key is None:
        routing_key = name

    return KombuQueue(
        name,
        exchange=Exchange(exchange, type="direct"),
        routing_key=routing_key,
        priority=priority,
        queue_arguments={
            "x-max-priority": 10,
            "x-message-ttl": 3600000,  # 1 hour TTL
        },
    )


# Build queue list for Celery
_queue_list: List[KombuQueue] = []
for queue_name, config in QUEUES.items():
    _queue_list.append(
        _create_queue_with_priority(
            queue_name,
            config["priority"],
        )
    )

# Celery configuration with all required settings
celery_app.conf.update(
    # Task execution (CRITICAL for reliability)
    task_acks_late=True,  # Acknowledge after task completes
    worker_prefetch_multiplier=1,  # Prefetch 1 task per worker
    task_track_started=True,  # Track when task starts
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=300,  # 5 minutes soft limit
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Broker connection with retry
    broker_connection_retry_on_startup=True,  # CRITICAL
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=10,  # Connection pool size
    broker_heartbeat=60,  # Keepalive heartbeat
    # Result backend
    result_expires=3600,  # 1 hour expiry
    result_persistent=True,
    result_extended=True,  # Extended result info
    # Worker settings
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=True,
    worker_send_task_events=True,  # Enable task events
    worker_pool="prefork",  # Use prefork pool for CPU tasks
    worker_concurrency=2,  # Default concurrency
    # Task routing with custom router
    task_routes={
        "workers.tasks.research.*": {"queue": "research"},
        "workers.tasks.browser.*": {"queue": "browser"},
        "workers.tasks.rag.*": {"queue": "rag"},
        "workers.tasks.reflection.*": {"queue": "reflection"},
        "workers.tasks.inference.*": {"queue": "local_inference"},
    },
    # Queue definitions
    task_default_queue=DEFAULT_QUEUE,
    task_default_exchange="default",
    task_default_routing_key=DEFAULT_QUEUE,
    # Beat schedule (for periodic tasks)
    beat_schedule={},
)


# Register signal handlers for monitoring
@worker_init.connect
def on_worker_init(**kwargs):
    """Called when worker starts."""
    logger.info("Celery worker initializing...")

    # Log queue info
    queues = celery_app.conf.task_queues or []
    queue_names = [q.name for q in queues]
    logger.info(f"Worker will consume from queues: {queue_names}")


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Called when worker is ready to accept tasks."""
    logger.info("Celery worker is ready")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Called when worker stops."""
    logger.info("Celery worker shutting down")


@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    """Called before task execution."""
    logger.debug(f"Task {task_id} ({task.name}) starting")

    # Track task start time in result backend
    from celery.app.control import Inspect

    inspect = Inspect(celery_app)
    stats = inspect.stats()

    if stats:
        logger.debug(f"Worker stats: {stats}")


@task_postrun.connect
def on_task_postrun(task_id, task, *args, **kwargs):
    """Called after task execution."""
    logger.debug(f"Task {task_id} ({task.name}) completed")


@task_retry.connect
def on_task_retry(sender, task, reason, *args, **kwargs):
    """Called when a task is retried."""
    logger.warning(
        f"Task {sender} being retried",
        extra={
            "task_id": sender,
            "task_name": task.name if hasattr(task, "name") else str(task),
            "reason": str(reason),
            "retry_count": kwargs.get("retry_count", 0),
        },
    )


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **other_kwargs):
    """Handle task failure: log and route to dead-letter queue if retries exhausted."""
    logger.error(
        f"Task {task_id} failed",
        extra={
            "task_id": task_id,
            "task_name": sender,
            "exception": str(exception),
            "traceback": str(traceback),
        },
    )
    # If the task has exhausted retries, forward to dead-letter queue
    try:
        # Retrieve max_retries from task config if available
        max_retries = getattr(sender, "max_retries", 0)
        # Celery provides request.retries attribute via kwargs
        retries = kwargs.get("retries", 0)
        if retries >= max_retries:
            # Requeue task to dead_letter with same args for debugging
            dead_letter_queue = "dead_letter"
            logger.warning(
                f"Routing failed task {task_id} to dead-letter queue {dead_letter_queue}",
                extra={"original_task": sender, "queue": dead_letter_queue},
            )
            # Use apply_async to send to dead_letter queue without retry
            sender.apply_async(args=args, kwargs=kwargs, queue=dead_letter_queue, retry=False)
    except Exception as e:
        logger.error(f"Failed to route task {task_id} to dead-letter queue: {e}")
    # Original failure handling continues
    # Note: raising exception is not needed here as Celery already marks task failed


@task_success.connect
def on_task_success(sender, result, **kwargs):
    """Called when a task succeeds."""
    logger.debug(f"Task {sender} succeeded with result")


# Import tasks after app configuration
from workers.tasks import research, browser, rag, reflection  # noqa: F401, E402


def health_check() -> Dict[str, Any]:
    """
    Perform health check on Celery workers.

    Returns:
        Health status dictionary
    """
    from celery.app.control import Inspect

    try:
        inspect = Inspect(celery_app)

        # Check active workers
        stats = inspect.stats()
        active = inspect.active()
        reserved = inspect.reserved()

        # Count workers and tasks
        worker_count = len(stats) if stats else 0

        active_tasks = []
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    active_tasks.append(
                        {
                            "worker": worker,
                            "id": task.get("id"),
                            "name": task.get("name"),
                        }
                    )

        return {
            "status": "healthy" if worker_count > 0 else "no_workers",
            "workers": worker_count,
            "active_tasks": len(active_tasks),
            "reserved_tasks": sum(len(tasks) for tasks in (reserved or {}).values()),
            "timestamp": None,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "workers": 0,
            "active_tasks": 0,
        }


def get_queue_stats() -> Dict[str, Dict[str, Any]]:
    """
    Get statistics for all queues.

    Returns:
        Queue statistics dictionary
    """
    from celery.app.control import Inspect

    try:
        inspect = Inspect(celery_app)
        stats = inspect.stats() or {}

        queue_stats = {}
        for queue_name in get_all_queue_names():
            # Get tasks for this queue from workers
            active = inspect.active() or {}

            # Count tasks for this queue
            task_count = 0
            for worker_tasks in active.values():
                for task in worker_tasks:
                    if queue_name in task.get("name", ""):
                        task_count += 1

            # Estimate based on worker stats
            worker_count = len(stats)

            queue_stats[queue_name] = {
                "active_tasks": task_count,
                "worker_count": worker_count,
                "status": "active" if worker_count > 0 else "inactive",
            }

        return queue_stats

    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {}


# Export queue configuration for workers
__all__ = [
    "celery_app",
    "health_check",
    "get_queue_stats",
]
