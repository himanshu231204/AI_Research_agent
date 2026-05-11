"""
Queue definitions for Research OS distributed worker system.

This module defines all Celery queues with their characteristics:
- Priority levels
- Visibility timeouts
- Retry policies
- Dead letter routing
"""

from typing import Dict, Any


# Queue priority levels (lower = higher priority)
class QueuePriority:
    """Queue priority constants."""

    HIGH = 0
    MEDIUM = 5
    LOW = 10
    BACKGROUND = 15


# Queue definitions with configuration
QUEUES: Dict[str, Dict[str, Any]] = {
    # High Priority Queue - for orchestration and critical tasks
    "high_priority": {
        "priority": QueuePriority.HIGH,
        "max_retries": 5,
        "default_retry_delay": 10,  # seconds
        "time_limit": 300,  # 5 minutes
        "soft_time_limit": 180,  # 3 minutes
        "description": "Critical orchestration and user-facing tasks",
    },
    # Research Queue - for web search, GitHub analysis, PDF processing
    "research": {
        "priority": QueuePriority.MEDIUM,
        "max_retries": 3,
        "default_retry_delay": 30,  # seconds
        "time_limit": 600,  # 10 minutes
        "soft_time_limit": 480,  # 8 minutes
        "description": "Research tasks: web search, GitHub, PDF analysis",
    },
    # Browser Queue - for Playwright automation
    "browser": {
        "priority": QueuePriority.MEDIUM,
        "max_retries": 2,
        "default_retry_delay": 60,  # seconds
        "time_limit": 900,  # 15 minutes
        "soft_time_limit": 720,  # 12 minutes
        "description": "Browser automation and web scraping tasks",
    },
    # RAG Queue - for embedding generation and vector operations
    "rag": {
        "priority": QueuePriority.LOW,
        "max_retries": 3,
        "default_retry_delay": 45,  # seconds
        "time_limit": 450,  # 7.5 minutes
        "soft_time_limit": 360,  # 6 minutes
        "description": "RAG tasks: chunking, embedding, retrieval",
    },
    # Reflection Queue - for reflection/critic agent tasks
    "reflection": {
        "priority": QueuePriority.LOW,
        "max_retries": 2,
        "default_retry_delay": 60,  # seconds
        "time_limit": 300,  # 5 minutes
        "soft_time_limit": 240,  # 4 minutes
        "description": "Reflection and validation tasks",
    },
    # Dead Letter Queue - for failed tasks that exceeded retries
    "dead_letter": {
        "priority": QueuePriority.BACKGROUND,
        "max_retries": 0,  # No retries - already failed
        "default_retry_delay": 0,
        "time_limit": 60,  # 1 minute for logging
        "soft_time_limit": 30,
        "description": "Failed tasks for debugging and recovery",
    },
}


def get_queue_config(queue_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific queue.

    Args:
        queue_name: Name of the queue

    Returns:
        Queue configuration dictionary

    Raises:
        ValueError: If queue doesn't exist
    """
    if queue_name not in QUEUES:
        raise ValueError(f"Unknown queue: {queue_name}")
    return QUEUES[queue_name].copy()


def get_all_queue_names() -> list[str]:
    """Get list of all queue names."""
    return list(QUEUES.keys())


def get_queues_by_priority() -> list[tuple[str, int]]:
    """
    Get queues sorted by priority (highest first).

    Returns:
        List of (queue_name, priority) tuples
    """
    return sorted(QUEUES.items(), key=lambda x: x[1]["priority"])


def is_critical_queue(queue_name: str) -> bool:
    """Check if queue is critical (high priority)."""
    return queue_name == "high_priority"


def get_dead_letter_queue() -> str:
    """Get the dead letter queue name."""
    return "dead_letter"


# Default queue for tasks without explicit routing
DEFAULT_QUEUE = "research"

# Queue for orchestration tasks
ORCHESTRATION_QUEUE = "high_priority"
