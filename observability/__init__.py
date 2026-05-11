"""Observability package for Research OS."""

from observability.logging import (
    configure_logging,
    get_logger,
    LoggerMixin,
    add_session_context,
    clear_session_context,
)
from observability.distributed_logging import (
    configure_logging as configure_distributed_logging,
    get_logger as get_distributed_logger,
    LogContext,
    set_session_context,
    clear_session_context as clear_distributed_context,
    generate_correlation_id,
    log_task_dispatch,
    log_task_result,
    log_workflow_start,
    log_workflow_end,
    log_agent_execution,
    CeleryTaskLogger,
    set_worker_name,
)
from observability.metrics import (
    MetricsCollector,
    get_metrics_collector,
    track_agent_execution,
    track_request_latency,
)
from observability.redis_reliability import (
    RedisConnectionPool,
    RedisCache,
    RedisQueueMonitor,
    RedisDistributedLock,
    redis_connection,
    get_redis_pool,
    close_redis_pool,
    get_redis_info,
    clear_redis_keys,
)
from observability.token_tracking import (
    TokenTracker,
    TokenUsage,
    ModelPricing,
    TokenUsageMiddleware,
    get_token_tracker,
    clear_token_tracker,
    record_token_usage,
    format_state_token_usage,
    update_state_token_usage,
    estimate_workflow_cost,
    get_model_pricing,
)

__all__ = [
    # Logging
    "configure_logging",
    "configure_distributed_logging",
    "get_logger",
    "get_distributed_logger",
    "LoggerMixin",
    "add_session_context",
    "clear_session_context",
    "clear_distributed_context",
    # Distributed logging
    "LogContext",
    "set_session_context",
    "generate_correlation_id",
    "log_task_dispatch",
    "log_task_result",
    "log_workflow_start",
    "log_workflow_end",
    "log_agent_execution",
    "CeleryTaskLogger",
    "set_worker_name",
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    "track_agent_execution",
    "track_request_latency",
    # Redis reliability
    "RedisConnectionPool",
    "RedisCache",
    "RedisQueueMonitor",
    "RedisDistributedLock",
    "redis_connection",
    "get_redis_pool",
    "close_redis_pool",
    "get_redis_info",
    "clear_redis_keys",
    # Token tracking
    "TokenTracker",
    "TokenUsage",
    "ModelPricing",
    "TokenUsageMiddleware",
    "get_token_tracker",
    "clear_token_tracker",
    "record_token_usage",
    "format_state_token_usage",
    "update_state_token_usage",
    "estimate_workflow_cost",
    "get_model_pricing",
]
