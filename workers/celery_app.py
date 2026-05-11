"""
Celery application configuration for Research OS.

Configures:
- Redis broker
- Result backend
- Queue definitions
- Retry configuration
- Task tracking
"""

import logging

from celery import Celery
from celery.signals import worker_init, worker_shutdown

from api.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create Celery app
celery_app = Celery(
    "research_os",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.research",
        "workers.tasks.browser",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes hard limit
    task_soft_time_limit=300,  # 5 minutes soft limit
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Broker
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    # Worker
    worker_max_tasks_per_child=100,
    worker_disable_rate_limits=True,
    # Task routing
    task_routes={
        "workers.tasks.research.*": {"queue": "research"},
        "workers.tasks.browser.*": {"queue": "browser"},
    },
    # Beat schedule (for periodic tasks)
    beat_schedule={},
)


@worker_init.connect
def on_worker_init(**kwargs):
    """Called when worker starts."""
    logger.info("Celery worker initialized")


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Called when worker stops."""
    logger.info("Celery worker shutting down")


# Import tasks after app configuration
from workers.tasks import research, browser  # noqa: F401, E402
