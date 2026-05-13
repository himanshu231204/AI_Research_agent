"""
Metrics and tracing for Research OS.

Provides:
- Request metrics
- Agent metrics
- Token usage tracking
- LangSmith integration (optional)
"""

from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
import time

from observability.logging import get_logger

logger = get_logger(__name__)


from prometheus_client import Counter, Gauge

# Prometheus metrics
ROUTING_REQUESTS = Counter('model_routing_requests_total', 'Total model routing requests', ['provider'])
ROUTING_FALLBACKS = Counter('model_routing_fallbacks_total', 'Total model routing fallbacks', ['provider'])
CIRCUIT_BREAKER_STATE = Gauge('model_circuit_breaker_state', 'Circuit breaker state (0=closed,1=open,2=half_open)', ['provider'])

class MetricsCollector:
    """
    Collects and tracks metrics for the research system.

    Tracks:
    - Request latency
    - Agent execution time
    - Token usage
    - Task completion
    """

    def __init__(self):
        self._metrics: Dict[str, Any] = {
            "requests": 0,
            "errors": 0,
            "latencies": [],
            "agent_executions": {},
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    def record_request(self, latency: float) -> None:
        """Record a request and its latency."""
        self._metrics["requests"] += 1
        self._metrics["latencies"].append(latency)

    def record_error(self) -> None:
        """Record an error."""
        self._metrics["errors"] += 1

    def record_agent_execution(self, agent_name: str, latency: float) -> None:
        """Record agent execution time."""
        if agent_name not in self._metrics["agent_executions"]:
            self._metrics["agent_executions"][agent_name] = {
                "count": 0,
                "total_latency": 0.0,
                "errors": 0,
            }

        self._metrics["agent_executions"][agent_name]["count"] += 1
        self._metrics["agent_executions"][agent_name]["total_latency"] += latency

    def record_token_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record token usage."""
        self._metrics["token_usage"]["prompt_tokens"] += prompt_tokens
        self._metrics["token_usage"]["completion_tokens"] += completion_tokens
        self._metrics["token_usage"]["total_tokens"] += prompt_tokens + completion_tokens

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        avg_latency = 0.0
        if self._metrics["latencies"]:
            avg_latency = sum(self._metrics["latencies"]) / len(self._metrics["latencies"])

        return {
            "requests": self._metrics["requests"],
            "errors": self._metrics["errors"],
            "error_rate": self._metrics["errors"] / max(self._metrics["requests"], 1),
            "avg_latency_ms": avg_latency * 1000,
            "agent_executions": self._metrics["agent_executions"],
            "token_usage": self._metrics["token_usage"],
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics = {
            "requests": 0,
            "errors": 0,
            "latencies": [],
            "agent_executions": {},
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }


# Global metrics collector
_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics


@asynccontextmanager
async def track_agent_execution(agent_name: str):
    """
    Context manager to track agent execution time.

    Usage:
        async with track_agent_execution("planner"):
            # agent code here
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        latency = time.perf_counter() - start_time
        _metrics.record_agent_execution(agent_name, latency)
        logger.debug(
            "agent_execution",
            agent=agent_name,
            latency_ms=latency * 1000,
        )


def track_request_latency(func):
    """
    Decorator to track request latency.

    Usage:
        @track_request_latency
        async def my_function():
            pass
    """

    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            _metrics.record_request(time.perf_counter() - start_time)
            return result
        except Exception:
            _metrics.record_error()
            _metrics.record_request(time.perf_counter() - start_time)
            raise

    return wrapper
