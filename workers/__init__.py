"""
Workers module for Research OS distributed execution.

Exports:
- Celery app
- Queue definitions
- Task modules
- Worker utilities
"""

from workers.celery_app import celery_app, health_check, get_queue_stats
from workers.queues import (
    QUEUES,
    get_queue_config,
    get_all_queue_names,
    get_queues_by_priority,
    is_critical_queue,
    get_dead_letter_queue,
    DEFAULT_QUEUE,
    ORCHESTRATION_QUEUE,
)
from workers.routing import (
    TaskRouter,
    TaskType,
    RetryPolicy,
    PriorityTask,
    route_task,
    get_router,
    get_task_result,
    get_task_info,
)

# Import all task modules to register them with Celery
from workers import tasks  # noqa: F401, E402

__all__ = [
    # Celery
    "celery_app",
    "health_check",
    "get_queue_stats",
    # Queues
    "QUEUES",
    "get_queue_config",
    "get_all_queue_names",
    "get_queues_by_priority",
    "is_critical_queue",
    "get_dead_letter_queue",
    "DEFAULT_QUEUE",
    "ORCHESTRATION_QUEUE",
    # Routing
    "TaskRouter",
    "TaskType",
    "RetryPolicy",
    "PriorityTask",
    "route_task",
    "get_router",
    "get_task_result",
    "get_task_info",
    # Tasks
    "tasks",
]
