"""
GPU telemetry and structured logging for Research OS.

Provides:
- GPU state change tracking
- Inference mode logging
- Routing decision logging
- Health status change detection
"""

import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class InferenceMode(Enum):
    """GPU inference mode."""

    NVIDIA = "nvidia"
    AMD = "amd"
    CPU = "cpu"
    UNKNOWN = "unknown"


class GPUState(Enum):
    """GPU state."""

    AVAILABLE = "available"
    BUSY = "busy"
    SATURATED = "saturated"
    UNAVAILABLE = "unavailable"
    CPU_MODE = "cpu_mode"
    ERROR = "error"


@dataclass
class GPUStateChange:
    """Record of a GPU state change."""

    timestamp: datetime
    from_state: Optional[GPUState]
    to_state: GPUState
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """Structured routing decision log."""

    timestamp: datetime
    task_type: str
    selected_provider: str
    selected_model: str
    inference_mode: InferenceMode
    latency_ms: float
    fallback_used: bool
    fallback_chain: List[str]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "task_type": self.task_type,
            "provider": self.selected_provider,
            "model": self.selected_model,
            "inference_mode": self.inference_mode.value,
            "latency_ms": self.latency_ms,
            "fallback_used": self.fallback_used,
            "fallback_chain": self.fallback_chain,
            "error": self.error,
        }


class GPUTelemetryLogger:
    """
    Structured telemetry logger for GPU and routing events.

    Logs structured events for:
    - GPU state changes
    - Inference mode switches
    - Routing decisions
    - Model loading/unloading
    """

    def __init__(self):
        """Initialize telemetry logger."""
        self._state_changes: List[GPUStateChange] = []
        self._routing_decisions: List[RoutingDecision] = []
        self._max_history = 1000
        self._last_gpu_state: Optional[GPUState] = None
        self._last_inference_mode: Optional[InferenceMode] = None

    def log_gpu_check(
        self,
        gpu_available: bool,
        inference_mode: str,
        gpu_count: int,
        memory_percent: float,
        model_loaded: Optional[str],
    ) -> None:
        """
        Log a GPU status check result.

        Args:
            gpu_available: Whether GPU is available
            inference_mode: Mode (nvidia, amd, cpu)
            gpu_count: Number of GPUs detected
            memory_percent: Memory usage percentage
            model_loaded: Currently loaded model
        """
        state = self._determine_state(gpu_available, inference_mode, memory_percent)

        logger.info(
            "GPU status check: available=%s mode=%s count=%d memory=%.1f%% model=%s state=%s",
            gpu_available,
            inference_mode,
            gpu_count,
            memory_percent,
            model_loaded or "none",
            state.value if state else "unknown",
        )

        # Track state changes
        if self._last_gpu_state != state:
            change = GPUStateChange(
                timestamp=datetime.utcnow(),
                from_state=self._last_gpu_state,
                to_state=state or GPUState.UNAVAILABLE,
                reason="GPU check result",
                details={
                    "gpu_available": gpu_available,
                    "inference_mode": inference_mode,
                    "gpu_count": gpu_count,
                    "memory_percent": memory_percent,
                },
            )
            self._state_changes.append(change)
            self._trim_history()

            logger.info(
                "GPU state changed: from=%s to=%s reason=%s",
                self._last_gpu_state.value if self._last_gpu_state else "none",
                state.value if state else "unknown",
                change.reason,
            )

            self._last_gpu_state = state

    def log_routing_decision(
        self,
        task_type: str,
        provider: str,
        model: str,
        inference_mode: str,
        latency_ms: float,
        fallback_used: bool = False,
        fallback_chain: Optional[List[str]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Log a routing decision.

        Args:
            task_type: Type of task being routed
            provider: Selected provider
            model: Selected model
            inference_mode: Inference mode used
            latency_ms: Request latency
            fallback_used: Whether fallback was used
            fallback_chain: Chain of fallback attempts
            error: Error if request failed
        """
        decision = RoutingDecision(
            timestamp=datetime.utcnow(),
            task_type=task_type,
            selected_provider=provider,
            selected_model=model,
            inference_mode=InferenceMode(inference_mode)
            if inference_mode in [e.value for e in InferenceMode]
            else InferenceMode.UNKNOWN,
            latency_ms=latency_ms,
            fallback_used=fallback_used,
            fallback_chain=fallback_chain or [],
            error=error,
        )
        self._routing_decisions.append(decision)
        self._trim_history()

        log_data = decision.to_dict()
        event = log_data.pop("event", "routing_decision")

        if error:
            logger.warning(
                "Routing decision with error: provider=%s model=%s fallback=%s error=%s",
                provider,
                model,
                fallback_used,
                error,
                extra=log_data,
            )
        elif fallback_used:
            logger.info(
                "Routing decision with fallback: provider=%s model=%s latency=%.2fms",
                provider,
                model,
                latency_ms,
                extra=log_data,
            )
        else:
            logger.debug(
                "Routing decision: provider=%s model=%s latency=%.2fms inference=%s",
                provider,
                model,
                latency_ms,
                inference_mode,
                extra=log_data,
            )

    def log_model_load(
        self, model: str, provider: str, success: bool, error: Optional[str] = None
    ) -> None:
        """
        Log model loading event.

        Args:
            model: Model being loaded
            provider: Provider loading the model
            success: Whether load succeeded
            error: Error message if failed
        """
        if success:
            logger.info("Model loaded: model=%s provider=%s", model, provider)
        else:
            logger.warning(
                "Model load failed: model=%s provider=%s error=%s", model, provider, error
            )

    def log_gpu_error(self, error: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log GPU-related error.

        Args:
            error: Error message
            context: Additional context
        """
        logger.error("GPU error: %s context=%s", error, context or {})

    def _determine_state(
        self, gpu_available: bool, inference_mode: str, memory_percent: float
    ) -> Optional[GPUState]:
        """Determine GPU state from metrics."""
        if inference_mode == "cpu":
            return GPUState.CPU_MODE
        if inference_mode == "unknown":
            return GPUState.UNKNOWN
        if not gpu_available:
            return GPUState.UNAVAILABLE
        if memory_percent > 90:
            return GPUState.SATURATED
        if memory_percent > 70:
            return GPUState.BUSY
        return GPUState.AVAILABLE

    def _trim_history(self) -> None:
        """Trim history to max size."""
        if len(self._state_changes) > self._max_history:
            self._state_changes = self._state_changes[-self._max_history :]
        if len(self._routing_decisions) > self._max_history:
            self._routing_decisions = self._routing_decisions[-self._max_history :]

    def get_state_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent state changes."""
        changes = self._state_changes[-limit:]
        return [
            {
                "timestamp": c.timestamp.isoformat(),
                "from_state": c.from_state.value if c.from_state else None,
                "to_state": c.to_state.value,
                "reason": c.reason,
                "details": c.details,
            }
            for c in changes
        ]

    def get_routing_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent routing decisions."""
        return [d.to_dict() for d in self._routing_decisions[-limit:]]


# Global telemetry logger
_telemetry_logger: Optional[GPUTelemetryLogger] = None


def get_gpu_telemetry_logger() -> GPUTelemetryLogger:
    """Get global GPU telemetry logger."""
    global _telemetry_logger
    if _telemetry_logger is None:
        _telemetry_logger = GPUTelemetryLogger()
    return _telemetry_logger


# Convenience functions for inline logging
def log_gpu_status(
    gpu_available: bool,
    inference_mode: str,
    gpu_count: int,
    memory_percent: float,
    model_loaded: Optional[str],
) -> None:
    """Log GPU status check result."""
    get_gpu_telemetry_logger().log_gpu_check(
        gpu_available=gpu_available,
        inference_mode=inference_mode,
        gpu_count=gpu_count,
        memory_percent=memory_percent,
        model_loaded=model_loaded,
    )


def log_route_decision(
    task_type: str,
    provider: str,
    model: str,
    inference_mode: str,
    latency_ms: float,
    fallback_used: bool = False,
    fallback_chain: Optional[List[str]] = None,
    error: Optional[str] = None,
) -> None:
    """Log routing decision."""
    get_gpu_telemetry_logger().log_routing_decision(
        task_type=task_type,
        provider=provider,
        model=model,
        inference_mode=inference_mode,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        fallback_chain=fallback_chain,
        error=error,
    )
