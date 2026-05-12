"""
Model telemetry system for Research OS.

This module provides:
- Token throughput tracking
- Latency monitoring
- Routing decision logging
- Fallback frequency tracking
- GPU usage metrics
- Provider cost tracking
"""

import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from models.routing.router import RoutingDecision, TaskType

logger = logging.getLogger(__name__)


@dataclass
class RequestTelemetry:
    """Telemetry for a single request."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    provider: str = ""
    model: str = ""
    task_type: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = True
    fallback_used: bool = False
    fallback_chain: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ProviderMetrics:
    """Metrics for a provider."""

    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    fallback_count: int = 0
    last_request_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests


class TelemetryCollector:
    """
    Collects and aggregates model telemetry.

    Tracks:
    - tokens/sec
    - latency
    - routing decisions
    - fallback frequency
    - GPU usage
    - provider costs
    """

    def __init__(self, max_history: int = 1000):
        """Initialize telemetry collector."""
        self._max_history = max_history
        self._request_history: deque[RequestTelemetry] = deque(maxlen=max_history)

        # Aggregate metrics
        self._provider_metrics: Dict[str, ProviderMetrics] = {}
        self._task_type_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_requests": 0,
                "total_latency_ms": 0.0,
                "total_tokens": 0,
                "fallback_count": 0,
            }
        )

        # Time windows for rate calculation
        self._window_size = timedelta(minutes=5)
        self._window_requests: deque[RequestTelemetry] = deque(maxlen=self._max_history)

    def record_request(
        self,
        provider: str,
        model: str,
        task_type: TaskType,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        fallback_used: bool = False,
        fallback_chain: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a request for telemetry.

        Args:
            provider: Provider name
            model: Model name
            task_type: Task type
            latency_ms: Request latency
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            cost_usd: Cost in USD
            success: Whether request succeeded
            fallback_used: Whether fallback was used
            fallback_chain: Fallback chain used
            error: Error message if failed
        """
        telemetry = RequestTelemetry(
            provider=provider,
            model=model,
            task_type=task_type.value,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            success=success,
            fallback_used=fallback_used,
            fallback_chain=fallback_chain or [],
            error=error,
        )

        self._request_history.append(telemetry)
        self._window_requests.append(telemetry)

        # Update provider metrics
        if provider not in self._provider_metrics:
            self._provider_metrics[provider] = ProviderMetrics(provider=provider)

        metrics = self._provider_metrics[provider]
        metrics.total_requests += 1
        metrics.total_latency_ms += latency_ms
        metrics.total_tokens += telemetry.total_tokens
        metrics.total_cost_usd += cost_usd
        metrics.last_request_time = datetime.utcnow()

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        if fallback_used:
            metrics.fallback_count += 1

        # Update task type metrics
        task_metrics = self._task_type_metrics[task_type.value]
        task_metrics["total_requests"] += 1
        task_metrics["total_latency_ms"] += latency_ms
        task_metrics["total_tokens"] += telemetry.total_tokens
        if fallback_used:
            task_metrics["fallback_count"] += 1

    def get_provider_metrics(self, provider: str) -> Optional[ProviderMetrics]:
        """Get metrics for a provider."""
        return self._provider_metrics.get(provider)

    def get_all_provider_metrics(self) -> Dict[str, ProviderMetrics]:
        """Get all provider metrics."""
        return self._provider_metrics.copy()

    def get_task_type_metrics(self, task_type: str) -> Dict[str, Any]:
        """Get metrics for a task type."""
        return self._task_type_metrics.get(task_type, {})

    def get_all_task_type_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all task type metrics."""
        return dict(self._task_type_metrics)

    def get_throughput(self, window_minutes: int = 5) -> float:
        """
        Calculate tokens per second throughput.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Tokens per second
        """
        window = timedelta(minutes=window_minutes)
        cutoff = datetime.utcnow() - window

        # Filter requests in window
        window_requests = [r for r in self._window_requests if r.timestamp >= cutoff]

        if not window_requests:
            return 0.0

        total_tokens = sum(r.total_tokens for r in window_requests)
        total_seconds = window.total_seconds()

        return total_tokens / total_seconds if total_seconds > 0 else 0.0

    def get_avg_latency(self, window_minutes: int = 5) -> float:
        """Get average latency over window."""
        window = timedelta(minutes=window_minutes)
        cutoff = datetime.utcnow() - window

        window_requests = [r for r in self._window_requests if r.timestamp >= cutoff]

        if not window_requests:
            return 0.0

        return sum(r.latency_ms for r in window_requests) / len(window_requests)

    def get_fallback_rate(self, window_minutes: int = 5) -> float:
        """Get fallback rate over window."""
        window = timedelta(minutes=window_minutes)
        cutoff = datetime.utcnow() - window

        window_requests = [r for r in self._window_requests if r.timestamp >= cutoff]

        if not window_requests:
            return 0.0

        fallback_count = sum(1 for r in window_requests if r.fallback_used)
        return fallback_count / len(window_requests)

    def get_total_cost(self) -> float:
        """Get total cost across all providers."""
        return sum(m.total_cost_usd for m in self._provider_metrics.values())

    def get_recent_requests(self, count: int = 10) -> List[RequestTelemetry]:
        """Get most recent requests."""
        return list(self._request_history)[-count:]

    def get_summary(self) -> Dict[str, Any]:
        """Get telemetry summary."""
        return {
            "total_requests": len(self._request_history),
            "providers": {
                name: {
                    "total_requests": m.total_requests,
                    "success_rate": m.success_rate,
                    "avg_latency_ms": m.avg_latency_ms,
                    "total_cost_usd": m.total_cost_usd,
                    "fallback_count": m.fallback_count,
                }
                for name, m in self._provider_metrics.items()
            },
            "task_types": dict(self._task_type_metrics),
            "throughput_tokens_per_sec": self.get_throughput(),
            "avg_latency_ms": self.get_avg_latency(),
            "fallback_rate": self.get_fallback_rate(),
            "total_cost_usd": self.get_total_cost(),
        }

    def reset(self) -> None:
        """Reset all telemetry."""
        self._request_history.clear()
        self._window_requests.clear()
        self._provider_metrics.clear()
        self._task_type_metrics.clear()


# Global telemetry collector
_telemetry_collector: Optional[TelemetryCollector] = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get global telemetry collector."""
    global _telemetry_collector
    if _telemetry_collector is None:
        _telemetry_collector = TelemetryCollector()
    return _telemetry_collector


def record_inference_telemetry(
    provider: str,
    model: str,
    task_type: TaskType,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    success: bool = True,
    fallback_used: bool = False,
    fallback_chain: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> None:
    """Convenience function to record inference telemetry."""
    collector = get_telemetry_collector()
    collector.record_request(
        provider=provider,
        model=model,
        task_type=task_type,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        success=success,
        fallback_used=fallback_used,
        fallback_chain=fallback_chain,
        error=error,
    )
