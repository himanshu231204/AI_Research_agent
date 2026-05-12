"""
GPU-aware scheduling and health monitoring for Research OS.

This module provides:
- GPU monitoring and metrics
- Health status tracking
- Model availability checks
- Load balancing across models
- Adaptive inference strategies
"""

import logging
import time
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from models.providers.local import OllamaProvider

logger = logging.getLogger(__name__)


class GPUStatus(Enum):
    """GPU availability status."""

    AVAILABLE = "available"
    BUSY = "busy"
    SATURATED = "saturated"
    UNAVAILABLE = "unavailable"


@dataclass
class GPUMetrics:
    """GPU metrics snapshot."""

    timestamp: datetime = field(default_factory=datetime.utcnow)
    gpu_available: bool = False
    gpu_count: int = 0
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0
    active_models: List[str] = field(default_factory=list)
    queue_length: int = 0

    @property
    def is_saturated(self) -> bool:
        """Check if GPU is saturated."""
        return self.memory_percent > 90

    @property
    def is_busy(self) -> bool:
        """Check if GPU is busy."""
        return self.memory_percent > 70


@dataclass
class ModelHealth:
    """Health status for a model."""

    model_name: str
    provider: str
    available: bool = True
    last_check: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    timeout_count: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.error_count
        if total == 0:
            return 1.0
        return self.success_count / total


class GPUMonitor:
    """
    GPU monitoring and metrics collection.

    Monitors:
    - VRAM usage
    - Queue latency
    - Active inference jobs
    - Model load
    """

    def __init__(self, ollama_provider: Optional[OllamaProvider] = None):
        """Initialize GPU monitor."""
        self._ollama = ollama_provider
        self._metrics_history: List[GPUMetrics] = []
        self._max_history = 100

    async def get_current_metrics(self) -> GPUMetrics:
        """Get current GPU metrics."""
        try:
            if self._ollama:
                gpu_info = await self._ollama.get_gpu_info()

                return GPUMetrics(
                    gpu_available=gpu_info.get("gpu_available", False),
                    active_models=[gpu_info.get("model", "")] if gpu_info.get("model") else [],
                    memory_used_mb=gpu_info.get("size", 0) / (1024 * 1024),
                )

        except Exception as e:
            logger.warning(f"Failed to get GPU metrics: {e}")

        return GPUMetrics()

    async def check_availability(
        self,
        model: str,
        memory_threshold: float = 0.9,
    ) -> tuple[bool, str]:
        """
        Check if model is available for inference.

        Args:
            model: Model name
            memory_threshold: Memory usage threshold

        Returns:
            Tuple of (available, reason)
        """
        metrics = await self.get_current_metrics()

        if not metrics.gpu_available:
            return False, "GPU not available"

        if metrics.is_saturated:
            return False, f"GPU saturated ({metrics.memory_percent:.1f}% memory)"

        # Check if model is already loaded
        if model in metrics.active_models:
            return True, "Model already loaded"

        # Check if there's enough memory for new model
        # Estimate ~4GB per model
        estimated_model_memory = 4 * 1024  # MB
        available_memory = metrics.memory_total_mb - metrics.memory_used_mb

        if available_memory < estimated_model_memory:
            return False, f"Insufficient memory (available: {available_memory:.0f}MB)"

        return True, "Available"

    async def get_load_info(self) -> Dict[str, Any]:
        """Get current load information."""
        metrics = await self.get_current_metrics()

        return {
            "gpu_available": metrics.gpu_available,
            "memory_percent": metrics.memory_percent,
            "is_saturated": metrics.is_saturated,
            "is_busy": metrics.is_busy,
            "active_models": metrics.active_models,
            "queue_length": metrics.queue_length,
        }


class HealthMonitor:
    """
    Model health monitoring system.

    Tracks:
    - Response latency
    - Timeout frequency
    - Provider uptime
    - Token throughput
    - GPU load
    """

    def __init__(self):
        """Initialize health monitor."""
        self._model_health: Dict[str, ModelHealth] = {}
        self._provider_health: Dict[str, Dict[str, Any]] = {}
        self._check_interval = 30  # seconds

    def register_model(self, model_name: str, provider: str) -> None:
        """Register a model for health monitoring."""
        key = f"{provider}:{model_name}"
        if key not in self._model_health:
            self._model_health[key] = ModelHealth(
                model_name=model_name,
                provider=provider,
            )
            logger.info(f"Registered model for health monitoring: {key}")

    def record_success(
        self,
        model_name: str,
        provider: str,
        latency_ms: float,
    ) -> None:
        """Record successful inference."""
        key = f"{provider}:{model_name}"
        if key in self._model_health:
            health = self._model_health[key]
            health.success_count += 1
            health.last_check = datetime.utcnow()
            health.latency_ms = latency_ms

    def record_failure(
        self,
        model_name: str,
        provider: str,
        is_timeout: bool = False,
    ) -> None:
        """Record failed inference."""
        key = f"{provider}:{model_name}"
        if key in self._model_health:
            health = self._model_health[key]
            health.error_count += 1
            health.last_check = datetime.utcnow()

            if is_timeout:
                health.timeout_count += 1

    def get_model_health(self, model_name: str, provider: str) -> Optional[ModelHealth]:
        """Get health status for a model."""
        key = f"{provider}:{model_name}"
        return self._model_health.get(key)

    def get_all_health(self) -> Dict[str, ModelHealth]:
        """Get all model health statuses."""
        return self._model_health.copy()

    def get_unhealthy_models(self) -> List[str]:
        """Get list of unhealthy models."""
        unhealthy = []

        for key, health in self._model_health.items():
            if not health.available or health.success_rate < 0.5:
                unhealthy.append(key)

        return unhealthy

    def get_slow_models(self, threshold_ms: float = 30000) -> List[str]:
        """Get models that are exceeding latency threshold."""
        slow = []

        for key, health in self._model_health.items():
            if health.latency_ms > threshold_ms:
                slow.append(key)

        return slow


class AdaptiveScheduler:
    """
    Adaptive inference scheduler.

    Features:
    - GPU-aware routing
    - Load distribution
    - Automatic model selection
    - Graceful degradation
    """

    def __init__(
        self,
        gpu_monitor: Optional[GPUMonitor] = None,
        health_monitor: Optional[HealthMonitor] = None,
    ):
        """Initialize adaptive scheduler."""
        self._gpu_monitor = gpu_monitor or GPUMonitor()
        self._health_monitor = health_monitor or HealthMonitor()

        # Model preferences by task
        self._model_preferences: Dict[str, List[str]] = {
            "planning": ["qwen3", "llama3"],
            "coding": ["deepseek-coder", "qwen3"],
            "reflection": ["mistral", "llama3"],
            "summarization": ["llama3", "qwen3"],
            "general": ["qwen3", "llama3"],
        }

    def set_model_preferences(self, task_type: str, models: List[str]) -> None:
        """Set model preferences for a task type."""
        self._model_preferences[task_type] = models

    async def select_model(
        self,
        task_type: str,
        prefer_local: bool = True,
    ) -> tuple[str, str, str]:
        """
        Select best model for task.

        Args:
            task_type: Type of task
            prefer_local: Whether to prefer local models

        Returns:
            Tuple of (provider, model, reason)
        """
        # Get available models for task type
        preferred_models = self._model_preferences.get(task_type, ["qwen3"])

        if prefer_local:
            # Try local models first
            for model in preferred_models:
                available, reason = await self._gpu_monitor.check_availability(model)

                if available:
                    # Check health
                    health = self._health_monitor.get_model_health(model, "ollama")
                    if health and health.success_rate >= 0.5:
                        return "ollama", model, reason

            # Fall back to any available local model
            for model in ["qwen3", "llama3", "mistral"]:
                available, reason = await self._gpu_monitor.check_availability(model)
                if available:
                    return "ollama", model, f"Fallback: {reason}"

        # Try cloud models as fallback
        return "cloud", "gpt-4o", "Local models unavailable"

    async def should_use_local(self) -> tuple[bool, str]:
        """
        Determine if local inference should be used.

        Returns:
            Tuple of (should_use_local, reason)
        """
        load_info = await self._gpu_monitor.get_load_info()

        if not load_info["gpu_available"]:
            return False, "GPU not available"

        if load_info["is_saturated"]:
            return False, "GPU saturated"

        if load_info["is_busy"]:
            return False, "GPU busy"

        return True, "GPU available"


# Global instances
_gpu_monitor: Optional[GPUMonitor] = None
_health_monitor: Optional[HealthMonitor] = None
_scheduler: Optional[AdaptiveScheduler] = None


def get_gpu_monitor() -> GPUMonitor:
    """Get global GPU monitor."""
    global _gpu_monitor
    if _gpu_monitor is None:
        _gpu_monitor = GPUMonitor()
    return _gpu_monitor


def get_health_monitor() -> HealthMonitor:
    """Get global health monitor."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor


def get_adaptive_scheduler() -> AdaptiveScheduler:
    """Get global adaptive scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AdaptiveScheduler(get_gpu_monitor(), get_health_monitor())
    return _scheduler
