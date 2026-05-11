"""
Celery task routing system for Research OS.

This module provides:
- Automatic task routing based on task type
- Priority-based queue assignment
- Retry policy configuration
- Task metadata tracking
"""

import logging
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from celery import Task
from celery.result import AsyncResult

from workers.queues import (
    QUEUES,
    get_queue_config,
    DEFAULT_QUEUE,
    ORCHESTRATION_QUEUE,
    get_dead_letter_queue,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task type enumeration for routing."""

    ORCHESTRATION = "orchestration"
    WEB_SEARCH = "web_search"
    GITHUB_ANALYSIS = "github_analysis"
    PDF_ANALYSIS = "pdf_analysis"
    RAG_EMBEDDING = "rag_embedding"
    RAG_RETRIEVAL = "rag_retrieval"
    REFLECTION = "reflection"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_SCRAPE = "browser_scrape"
    BROWSER_FORM = "browser_form"
    AGGREGATION = "aggregation"
    UNKNOWN = "unknown"


class TaskRouter:
    """
    Central task routing system for Research OS.

    Handles:
    - Queue selection based on task type
    - Priority assignment
    - Retry policy configuration
    - Task correlation
    """

    # Mapping of task types to queues
    TASK_TO_QUEUE_MAP: Dict[TaskType, str] = {
        TaskType.ORCHESTRATION: ORCHESTRATION_QUEUE,
        TaskType.WEB_SEARCH: "research",
        TaskType.GITHUB_ANALYSIS: "research",
        TaskType.PDF_ANALYSIS: "research",
        TaskType.RAG_EMBEDDING: "rag",
        TaskType.RAG_RETRIEVAL: "rag",
        TaskType.REFLECTION: "reflection",
        TaskType.BROWSER_NAVIGATE: "browser",
        TaskType.BROWSER_SCRAPE: "browser",
        TaskType.BROWSER_FORM: "browser",
        TaskType.AGGREGATION: "research",
        TaskType.UNKNOWN: DEFAULT_QUEUE,
    }

    def __init__(self):
        """Initialize the task router."""
        self._task_correlations: Dict[str, Dict[str, Any]] = {}

    def get_queue_for_task(self, task_type: TaskType) -> str:
        """
        Get the queue name for a task type.

        Args:
            task_type: Type of task

        Returns:
            Queue name
        """
        return self.TASK_TO_QUEUE_MAP.get(task_type, DEFAULT_QUEUE)

    def get_retry_config(self, task_type: TaskType) -> Dict[str, Any]:
        """
        Get retry configuration for a task type.

        Args:
            task_type: Type of task

        Returns:
            Retry configuration dict with max_retries, countdown, etc.
        """
        queue_name = self.get_queue_for_task(task_type)
        queue_config = get_queue_config(queue_name)

        return {
            "max_retries": queue_config["max_retries"],
            "countdown": queue_config["default_retry_delay"],
            "time_limit": queue_config["time_limit"],
            "soft_time_limit": queue_config["soft_time_limit"],
        }

    def create_task_metadata(
        self,
        task_type: TaskType,
        session_id: str,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create metadata for task tracking.

        Args:
            task_type: Type of task
            session_id: Session identifier
            workflow_id: Optional workflow identifier
            correlation_id: Optional correlation ID for tracing

        Returns:
            Metadata dictionary
        """
        import uuid

        correlation = correlation_id or str(uuid.uuid4())[:8]

        metadata = {
            "task_type": task_type.value,
            "session_id": session_id,
            "workflow_id": workflow_id or session_id,
            "correlation_id": correlation,
            "queue": self.get_queue_for_task(task_type),
            "retry_config": self.get_retry_config(task_type),
            "enqueued_at": None,  # Will be set at dispatch time
            "started_at": None,
            "completed_at": None,
            "attempts": 0,
        }

        # Store correlation for later lookup
        self._task_correlations[correlation] = metadata

        return metadata

    def update_task_status(
        self,
        correlation_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update task status in tracking.

        Args:
            correlation_id: Task correlation ID
            status: New status (started, completed, failed)
            result: Task result if completed
            error: Error message if failed
        """
        if correlation_id in self._task_correlations:
            self._task_correlations[correlation_id]["status"] = status

            if status == "started":
                self._task_correlations[correlation_id]["started_at"] = None
            elif status == "completed":
                self._task_correlations[correlation_id]["completed_at"] = None
                self._task_correlations[correlation_id]["result"] = result
            elif status == "failed":
                self._task_correlations[correlation_id]["error"] = error

    def get_task_status(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status by correlation ID.

        Args:
            correlation_id: Task correlation ID

        Returns:
            Task status dict or None if not found
        """
        return self._task_correlations.get(correlation_id)

    def resolve_task_type(self, task_name: str) -> TaskType:
        """
        Resolve task name to TaskType.

        Args:
            task_name: Task name (e.g., 'research.web_search')

        Returns:
            TaskType enum value
        """
        task_name_lower = task_name.lower()

        if "orchestration" in task_name_lower:
            return TaskType.ORCHESTRATION
        elif "web_search" in task_name_lower:
            return TaskType.WEB_SEARCH
        elif "github" in task_name_lower:
            return TaskType.GITHUB_ANALYSIS
        elif "pdf" in task_name_lower:
            return TaskType.PDF_ANALYSIS
        elif "embedding" in task_name_lower:
            return TaskType.RAG_EMBEDDING
        elif "retrieval" in task_name_lower or "rag" in task_name_lower:
            return TaskType.RAG_RETRIEVAL
        elif "reflection" in task_name_lower:
            return TaskType.REFLECTION
        elif "navigate" in task_name_lower:
            return TaskType.BROWSER_NAVIGATE
        elif "scrape" in task_name_lower:
            return TaskType.BROWSER_SCRAPE
        elif "form" in task_name_lower:
            return TaskType.BROWSER_FORM
        elif "aggregate" in task_name_lower:
            return TaskType.AGGREGATION
        else:
            return TaskType.UNKNOWN


class RetryPolicy:
    """
    Configurable retry policy for tasks.

    Supports exponential backoff with jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: int = 30,
        max_delay: int = 600,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Exponential multiplier for backoff
            jitter: Whether to add random jitter
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> int:
        """
        Calculate delay for retry attempt.

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds before next retry
        """
        import random

        # Exponential backoff: base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter if enabled (0.5 to 1.5 of delay)
        if self.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay = delay * jitter_factor

        return int(delay)

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """
        Determine if task should be retried.

        Args:
            attempt: Current attempt number
            exception: The exception that was raised

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            return False

        # Don't retry on certain exceptions
        non_retryable = (
            KeyboardInterrupt,
            SystemExit,
            MemoryError,
        )

        return not isinstance(exception, non_retryable)


class PriorityTask(Task):
    """
    Base class for priority-aware tasks.

    Automatically routes to appropriate queue based on task type.
    Supports priority inheritance from task metadata.
    """

    # Override in subclasses
    task_type: TaskType = TaskType.UNKNOWN

    def __init__(self, *args, **kwargs):
        """Initialize priority task."""
        super().__init__(*args, **kwargs)
        self._router = TaskRouter()
        self._metadata = {}

    def set_metadata(self, **kwargs) -> None:
        """Set task metadata for tracking."""
        self._metadata.update(kwargs)

    def get_metadata(self) -> Dict[str, Any]:
        """Get task metadata."""
        return self._metadata.copy()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            f"Task {task_id} failed",
            extra={
                "task_id": task_id,
                "exception": str(exc),
                "task_name": self.name,
                "args": args,
                "kwargs": kwargs,
            },
        )

        # Track failure
        correlation_id = kwargs.get("correlation_id", task_id[:8])
        self._router.update_task_status(correlation_id, "failed", error=str(exc))

        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")

        # Track success
        correlation_id = kwargs.get("correlation_id", task_id[:8])
        self._router.update_task_status(correlation_id, "completed", result=retval)

        super().on_success(retval, task_id, args, kwargs)


def route_task(task_name: str, args: tuple, kwargs: dict) -> str:
    """
    Determine the queue for a task based on routing rules.

    This function is used as the celery task_routing_split task router.

    Args:
        task_name: Name of the task
        args: Task positional arguments
        kwargs: Task keyword arguments

    Returns:
        Queue name to route the task to
    """
    router = TaskRouter()
    task_type = router.resolve_task_type(task_name)
    queue = router.get_queue_for_task(task_type)

    logger.debug(f"Routing task {task_name} to queue {queue}")

    return queue


def get_task_result(task_id: str) -> Optional[AsyncResult]:
    """
    Get AsyncResult for a task.

    Args:
        task_id: Celery task ID

    Returns:
        AsyncResult instance or None
    """
    return AsyncResult(task_id, app=celery_app)


def get_task_info(task_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a task.

    Args:
        task_id: Celery task ID

    Returns:
        Task info dictionary
    """
    result = get_task_result(task_id)

    if result is None:
        return {"status": "unknown", "task_id": task_id}

    return {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "value": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
    }


# Global router instance
_router = TaskRouter()


def get_router() -> TaskRouter:
    """Get the global task router instance."""
    return _router
