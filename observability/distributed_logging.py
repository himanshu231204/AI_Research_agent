"""
Distributed logging for Research OS.

This module provides:
- Structured JSON logging
- Request correlation IDs
- Workflow ID tracking
- Task tracing across workers
- Celery task logging integration
"""

import logging
import sys
import json
import uuid
from typing import Any, Dict, Optional
from datetime import datetime
from contextvars import ContextVar

import structlog

from api.config import get_settings

# Context variables for distributed logging
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_workflow_id: ContextVar[Optional[str]] = ContextVar("workflow_id", default=None)
_task_id: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_worker_name: ContextVar[Optional[str]] = ContextVar("worker_name", default=None)
_current_agent: ContextVar[Optional[str]] = ContextVar("current_agent", default=None)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class StructuredLogRenderer:
    """
    Custom JSON renderer for structured logging with correlation IDs.

    Adds session_id, workflow_id, task_id, worker_name, and agent
    to every log message.
    """

    def __call__(self, logger, method_name, event_dict):
        """
        Render log entry with correlation context.

        Args:
            logger: Logger instance
            method_name: Log method name
            event_dict: Event dictionary

        Returns:
            Rendered log entry
        """
        # Add correlation context
        event_dict["session_id"] = _session_id.get() or "unknown"
        event_dict["workflow_id"] = _workflow_id.get() or "unknown"
        event_dict["task_id"] = _task_id.get() or ""
        event_dict["worker_name"] = _worker_name.get() or ""
        event_dict["current_agent"] = _current_agent.get() or ""
        event_dict["correlation_id"] = _correlation_id.get() or ""

        # Add timestamp
        event_dict["timestamp"] = datetime.utcnow().isoformat()

        # Add host info
        event_dict["host"] = get_hostname()

        # Serialize to JSON
        output = json.dumps(event_dict, default=str)
        return output + "\n"


class ColoredLogRenderer:
    """
    Human-readable log renderer with colors for development.

    Useful for development and debugging.
    """

    # ANSI color codes
    COLORS = {
        "debug": "\033[36m",  # Cyan
        "info": "\033[32m",  # Green
        "warning": "\033[33m",  # Yellow
        "error": "\033[31m",  # Red
        "critical": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __call__(self, logger, method_name, event_dict):
        """Render colored log entry."""
        color = self.COLORS.get(method_name, "")
        reset = self.RESET

        # Extract key fields
        timestamp = event_dict.pop("timestamp", "")
        session_id = event_dict.pop("session_id", "")
        workflow_id = event_dict.pop("workflow_id", "")
        agent = event_dict.pop("current_agent", "")
        msg = event_dict.pop("event", "")

        # Build colored output
        parts = []

        if timestamp:
            parts.append(f"[{timestamp.split('T')[1][:8]}]")

        if agent:
            parts.append(f"{color}[{agent}]{reset}")

        if session_id:
            parts.append(f"[{session_id[:8]}]")

        parts.append(f"{color}{method_name.upper()}{reset}")

        if msg:
            parts.append(msg)

        # Add remaining fields
        extra = ", ".join(f"{k}={v}" for k, v in event_dict.items() if v)
        if extra:
            parts.append(f"({extra})")

        return " ".join(parts) + "\n"


def get_hostname() -> str:
    """Get hostname for logging."""
    import socket

    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def configure_logging(
    environment: str = "development",
    json_format: bool = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        environment: Environment (development, production)
        json_format: Force JSON format (auto-detect based on environment if None)
    """
    settings = get_settings()

    # Auto-detect format based on environment
    if json_format is None:
        json_format = environment == "production" or not settings.debug

    # Configure processors based on format
    if json_format:
        renderer = StructuredLogRenderer()
    else:
        renderer = ColoredLogRenderer()

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    log_level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger with correlation context
    """
    logger = structlog.get_logger(name)

    # Bind context variables if set
    ctx = {}
    if _session_id.get():
        ctx["session_id"] = _session_id.get()
    if _workflow_id.get():
        ctx["workflow_id"] = _workflow_id.get()
    if _task_id.get():
        ctx["task_id"] = _task_id.get()
    if _worker_name.get():
        ctx["worker_name"] = _worker_name.get()
    if _current_agent.get():
        ctx["current_agent"] = _current_agent.get()

    if ctx:
        logger = logger.bind(**ctx)

    return logger


class LogContext:
    """
    Context manager for setting log correlation context.

    Usage:
        with LogContext(session_id="abc", agent="planner"):
            logger.info("Task started")
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        worker_name: Optional[str] = None,
        agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize log context."""
        self.context = {}
        if session_id:
            self.context["session_id"] = session_id
        if workflow_id:
            self.context["workflow_id"] = workflow_id
        if task_id:
            self.context["task_id"] = task_id
        if worker_name:
            self.context["worker_name"] = worker_name
        if agent:
            self.context["current_agent"] = agent
        if correlation_id:
            self.context["correlation_id"] = correlation_id

    def __enter__(self):
        """Enter context - bind variables."""
        for key, value in self.context.items():
            if key == "session_id":
                _session_id.set(value)
            elif key == "workflow_id":
                _workflow_id.set(value)
            elif key == "task_id":
                _task_id.set(value)
            elif key == "worker_name":
                _worker_name.set(value)
            elif key == "current_agent":
                _current_agent.set(value)
            elif key == "correlation_id":
                _correlation_id.set(value)

        # Bind to structlog context vars
        structlog.contextvars.bind_contextvars(**self.context)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - unbind variables."""
        for key in self.context.keys():
            if key == "session_id":
                _session_id.set(None)
            elif key == "workflow_id":
                _workflow_id.set(None)
            elif key == "task_id":
                _task_id.set(None)
            elif key == "worker_name":
                _worker_name.set(None)
            elif key == "current_agent":
                _current_agent.set(None)
            elif key == "correlation_id":
                _correlation_id.set(None)

        structlog.contextvars.clear_contextvars()


def set_session_context(
    session_id: str,
    workflow_id: Optional[str] = None,
) -> None:
    """
    Set session context for all log messages.

    Args:
        session_id: Session identifier
        workflow_id: Optional workflow identifier
    """
    _session_id.set(session_id)
    if workflow_id:
        _workflow_id.set(workflow_id)

    structlog.contextvars.bind_contextvars(
        session_id=session_id,
        workflow_id=workflow_id or "",
    )


def clear_session_context() -> None:
    """Clear session context from log messages."""
    _session_id.set(None)
    _workflow_id.set(None)
    _task_id.set(None)
    _worker_name.set(None)
    _current_agent.set(None)
    _correlation_id.set(None)

    structlog.contextvars.clear_contextvars()


def generate_correlation_id() -> str:
    """
    Generate a unique correlation ID for request tracing.

    Returns:
        Correlation ID (first 8 characters of UUID)
    """
    return str(uuid.uuid4())[:8]


def log_task_dispatch(
    logger: structlog.stdlib.BoundLogger,
    task_name: str,
    correlation_id: str,
    queue: str,
    **kwargs,
) -> None:
    """
    Log task dispatch to Celery worker.

    Args:
        logger: Structured logger
        task_name: Celery task name
        correlation_id: Task correlation ID
        queue: Target queue
        **kwargs: Additional context
    """
    logger.info(
        "task_dispatched",
        event="task_dispatched",
        task_name=task_name,
        correlation_id=correlation_id,
        queue=queue,
        **kwargs,
    )


def log_task_result(
    logger: structlog.stdlib.BoundLogger,
    correlation_id: str,
    status: str,
    duration: float,
    **kwargs,
) -> None:
    """
    Log task result from Celery worker.

    Args:
        logger: Structured logger
        correlation_id: Task correlation ID
        status: Task status (completed, failed)
        duration: Execution duration in seconds
        **kwargs: Additional context
    """
    logger.info(
        "task_result",
        event="task_result",
        correlation_id=correlation_id,
        status=status,
        duration_ms=duration * 1000,
        **kwargs,
    )


def log_workflow_start(
    logger: structlog.stdlib.BoundLogger,
    session_id: str,
    query: str,
    workflow_id: str,
) -> None:
    """
    Log workflow start.

    Args:
        logger: Structured logger
        session_id: Session identifier
        query: Research query
        workflow_id: Workflow identifier
    """
    logger.info(
        "workflow_started",
        event="workflow_started",
        session_id=session_id,
        query_preview=query[:100] if query else "",
        workflow_id=workflow_id,
    )


def log_workflow_end(
    logger: structlog.stdlib.BoundLogger,
    session_id: str,
    workflow_id: str,
    status: str,
    duration: float,
    findings_count: int = 0,
) -> None:
    """
    Log workflow end.

    Args:
        logger: Structured logger
        session_id: Session identifier
        workflow_id: Workflow identifier
        status: Final status
        duration: Total duration in seconds
        findings_count: Number of findings
    """
    logger.info(
        "workflow_completed",
        event="workflow_completed",
        session_id=session_id,
        workflow_id=workflow_id,
        status=status,
        duration_s=duration,
        findings_count=findings_count,
    )


def log_agent_execution(
    logger: structlog.stdlib.BoundLogger,
    agent_name: str,
    session_id: str,
    duration: float,
    tokens_used: int = 0,
) -> None:
    """
    Log agent execution.

    Args:
        logger: Structured logger
        agent_name: Name of the agent
        session_id: Session identifier
        duration: Execution duration in seconds
        tokens_used: Number of tokens consumed
    """
    logger.info(
        "agent_executed",
        event="agent_executed",
        agent=agent_name,
        session_id=session_id,
        duration_ms=duration * 1000,
        tokens_used=tokens_used,
    )


class CeleryTaskLogger:
    """
    Celery task wrapper that adds logging to all tasks.
    """

    @staticmethod
    def setup_task_logging(task_name: str, correlation_id: str) -> None:
        """
        Setup logging context for Celery task.

        Args:
            task_name: Name of the task
            correlation_id: Task correlation ID
        """
        _task_id.set(task_name)
        _correlation_id.set(correlation_id)

        structlog.contextvars.bind_contextvars(
            task_name=task_name,
            correlation_id=correlation_id,
        )

    @staticmethod
    def cleanup_task_logging() -> None:
        """Cleanup logging context after Celery task."""
        _task_id.set(None)
        _correlation_id.set(None)

        structlog.contextvars.clear_contextvars()


# Worker name configuration for Celery
def set_worker_name(name: str) -> None:
    """
    Set the worker name for logging.

    Args:
        name: Worker name
    """
    _worker_name.set(name)
    structlog.contextvars.bind_contextvars(worker_name=name)


# Export common log event types
LOG_EVENTS = {
    "WORKFLOW_START": "workflow_started",
    "WORKFLOW_END": "workflow_completed",
    "TASK_DISPATCH": "task_dispatched",
    "TASK_RESULT": "task_result",
    "TASK_RETRY": "task_retry",
    "TASK_FAILURE": "task_failure",
    "AGENT_START": "agent_started",
    "AGENT_END": "agent_completed",
    "QUEUE_PUBLISH": "queue_published",
    "QUEUE_CONSUME": "queue_consumed",
}
