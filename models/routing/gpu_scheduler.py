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
    - CPU fallback detection
    """

    def __init__(self, ollama_provider: Optional[OllamaProvider] = None):
        """Initialize GPU monitor."""
        self._ollama = ollama_provider
        self._metrics_history: List[GPUMetrics] = []
        self._max_history = 100
        self._last_gpu_check: Optional[datetime] = None
        self._cache_duration = 5  # seconds

    def set_ollama_provider(self, ollama_provider: OllamaProvider) -> None:
        """Set or update the Ollama provider reference."""
        self._ollama = ollama_provider
        logger.debug("Ollama provider set for GPU monitor")

    async def get_current_metrics(self) -> GPUMetrics:
        """Get current GPU metrics with proper CPU fallback handling."""
        try:
            if self._ollama:
                gpu_info = await self._ollama.get_gpu_info()

                # Log detailed GPU status
                logger.info(
                    f"GPU Monitor: mode={gpu_info.get('inference_mode', 'unknown')}, "
                    f"available={gpu_info.get('gpu_available', False)}, "
                    f"count={gpu_info.get('gpu_count', 0)}, "
                    f"memory={gpu_info.get('memory_used_mb', 0):.0f}/{gpu_info.get('memory_total_mb', 0):.0f}MB, "
                    f"model={gpu_info.get('model_loaded', 'none')}"
                )

                return GPUMetrics(
                    gpu_available=gpu_info.get("gpu_available", False),
                    gpu_count=gpu_info.get("gpu_count", 0),
                    memory_total_mb=gpu_info.get("memory_total_mb", 0.0),
                    memory_used_mb=gpu_info.get("memory_used_mb", 0.0),
                    memory_percent=gpu_info.get("memory_percent", 0.0),
                    active_models=[gpu_info.get("model_loaded")]
                    if gpu_info.get("model_loaded")
                    else [],
                    queue_length=gpu_info.get("queue_length", 0),
                )

        except Exception as e:
            logger.warning(f"Failed to get GPU metrics: {e}")

        return GPUMetrics()

    async def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed GPU/inference status for frontend display.

        Returns comprehensive status suitable for dashboard display.
        """
        try:
            if self._ollama:
                gpu_info = await self._ollama.get_gpu_info()

                status = gpu_info.get("status", "unavailable")
                inference_mode = gpu_info.get("inference_mode", "unknown")

                return {
                    "available": gpu_info.get("gpu_available", False),
                    "mode": inference_mode,
                    "status": status,
                    "gpu_count": gpu_info.get("gpu_count", 0),
                    "memory": {
                        "total_mb": gpu_info.get("memory_total_mb", 0),
                        "used_mb": gpu_info.get("memory_used_mb", 0),
                        "free_mb": gpu_info.get("memory_free_mb", 0),
                        "percent": gpu_info.get("memory_percent", 0),
                    },
                    "compute_utilization": gpu_info.get("compute_utilization", 0),
                    "temperature": gpu_info.get("temperature"),
                    "driver_version": gpu_info.get("driver_version"),
                    "model_loaded": gpu_info.get("model_loaded"),
                    "model_size_mb": gpu_info.get("model_size_bytes", 0) / (1024 * 1024),
                    "is_saturated": gpu_info.get("is_saturated", False),
                    "is_busy": gpu_info.get("is_busy", False),
                    "gpus": gpu_info.get("gpus", []),
                    "last_updated": gpu_info.get("last_updated"),
                    # User-friendly messages
                    "display_status": self._get_display_status(status, inference_mode, gpu_info),
                    "display_icon": self._get_display_icon(status, inference_mode),
                }

        except Exception as e:
            logger.error(f"Failed to get detailed GPU status: {e}")
            return {
                "available": False,
                "mode": "unknown",
                "status": "error",
                "error": str(e),
                "display_status": "Error checking GPU status",
                "display_icon": "error",
            }

    def _get_display_status(self, status: str, inference_mode: str, gpu_info: Dict) -> str:
        """Generate user-friendly display status."""
        if inference_mode == "cpu":
            return "CPU Inference Mode"
        if inference_mode == "amd":
            if status == "available":
                return f"AMD GPU Available ({gpu_info.get('gpu_count', 0)})"
            return "AMD GPU Unavailable"
        if inference_mode == "nvidia":
            if status == "saturated":
                return f"GPU Saturated ({gpu_info.get('memory_percent', 0):.0f}%)"
            if status == "busy":
                return f"GPU Busy ({gpu_info.get('memory_percent', 0):.0f}%)"
            if status == "available":
                return "GPU Available"
            return "GPU Unavailable"
        return "GPU Status Unknown"

    def _get_display_icon(self, status: str, inference_mode: str) -> str:
        """Get icon identifier for frontend."""
        if inference_mode == "cpu":
            return "cpu"
        if status in ("saturated", "busy"):
            return "busy"
        if status == "available":
            return "available"
        return "unavailable"

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
            "planning": ["mistral:latest", "llama2:latest "],
            "coding": ["llama2:latest ", "qwen2.5-coder:7b"],
            "reflection": ["mistral:latest", "llama2:latest "],
            "summarization": ["llama3", "qwen2.5-coder:7b"],
            "general": ["mistral:latest", "llama2:latest "],
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
