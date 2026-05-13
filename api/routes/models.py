"""
API routes for model management and telemetry.

Endpoints:
- GET /models/status - Get model status
- GET /models/providers - Get provider information
- POST /models/test - Test a model
- GET /telemetry/models - Get model telemetry
- GET /telemetry/costs - Get cost telemetry

Model Selection Endpoints:
- GET /models - Get all available models (local + cloud)
- GET /models/local - Get local Ollama models
- GET /models/cloud - Get cloud models by provider
- GET /providers/status - Get provider health status
- POST /models/select - Select model for session
- GET /models/selection/{session_id} - Get current selection
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from models.providers.base import ProviderStatus
from models.providers.local import OllamaProvider, get_ollama_provider
from models.providers.cloud import OpenAIProvider, AnthropicProvider, GoogleProvider
from models.routing.router import get_model_router, ModelRouter, TaskType
from models.routing.gpu_scheduler import get_gpu_monitor, get_health_monitor
from models.routing.telemetry import get_telemetry_collector
from models.routing.cost_optimizer import get_cost_optimizer, CostBudget
from models.registry import (
    get_model_registry,
    ModelRegistry,
    RoutingMode,
    ModelInfo,
    ProviderStatus as RegistryProviderStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])


# Request/Response models


class ModelTestRequest(BaseModel):
    """Request to test a model."""

    provider: str
    model: str
    prompt: str = "Hello, world!"
    temperature: float = 0.7


class ModelTestResponse(BaseModel):
    """Response from model test."""

    success: bool
    provider: str
    model: str
    latency_ms: float
    content: str
    error: Optional[str] = None


class ProviderInfo(BaseModel):
    """Provider information."""

    name: str
    type: str
    status: str
    available: bool
    models: List[str]
    latency_ms: float = 0.0
    circuit_breaker: Optional[Dict[str, Any]] = None
    # Extended info for local providers
    inference_mode: Optional[str] = None
    gpu_count: Optional[int] = None
    gpu_available: Optional[bool] = None
    memory_total_mb: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    model_loaded: Optional[str] = None


class GPUStatusDetail(BaseModel):
    """Detailed GPU status for frontend display."""

    available: bool
    mode: str  # "nvidia", "amd", "cpu", "unknown"
    status: str  # "available", "busy", "saturated", "unavailable", "cpu_mode"
    gpu_count: int = 0
    memory: Dict[str, float] = {}
    compute_utilization: float = 0.0
    temperature: Optional[float] = None
    driver_version: Optional[str] = None
    model_loaded: Optional[str] = None
    model_size_mb: float = 0.0
    is_saturated: bool = False
    is_busy: bool = False
    display_status: str = ""
    display_icon: str = ""
    last_updated: Optional[str] = None
    error: Optional[str] = None


class ModelStatusResponse(BaseModel):
    """Model status response."""

    timestamp: str
    providers: List[ProviderInfo]
    gpu_status: GPUStatusDetail
    model_health: Dict[str, Any]


class TelemetryResponse(BaseModel):
    """Telemetry response."""

    summary: Dict[str, Any]
    providers: Dict[str, Any]
    task_types: Dict[str, Any]


class CostResponse(BaseModel):
    """Cost response."""

    session_id: str
    total_cost_usd: float
    total_tokens: int
    by_provider: Dict[str, float]
    by_model: Dict[str, float]


# Model Selection Models


class ModelSelectionRequest(BaseModel):
    """Request to select a model for a session."""

    session_id: str
    provider: str = "auto"  # "auto", "ollama", "openai", "anthropic", "google", "groq"
    model: str = ""
    routing_mode: str = "auto"  # "auto", "local_only", "cloud_only", "hybrid"


class ModelSelectionResponse(BaseModel):
    """Response from model selection."""

    success: bool
    provider: str
    model: str
    routing_mode: str
    message: str
    error: Optional[str] = None


class ModelListResponse(BaseModel):
    """Response containing all available models."""

    local: List[Dict[str, Any]]
    cloud: Dict[str, List[Dict[str, Any]]]
    timestamp: str


class LocalModelsResponse(BaseModel):
    """Response for local models."""

    models: List[Dict[str, Any]]
    count: int
    provider: str = "ollama"


class CloudModelsResponse(BaseModel):
    """Response for cloud models."""

    providers: Dict[str, List[Dict[str, Any]]]


class ProviderStatusResponse(BaseModel):
    """Response for provider status."""

    providers: List[Dict[str, Any]]


# Endpoints


@router.get("/status", response_model=ModelStatusResponse)
async def get_model_status():
    """
    Get status of all models and providers.

    Returns:
        Model status with provider info, detailed GPU status, and health
    """
    router = get_model_router()
    gpu_monitor = get_gpu_monitor()
    health_monitor = get_health_monitor()

    providers = []

    # Get Ollama status with detailed GPU info
    try:
        ollama = get_ollama_provider()
        ollama_health = await ollama.health_check()
        available_models = await ollama.get_available_models()

        # Get GPU info from provider
        gpu_info = await ollama.get_gpu_info()

        providers.append(
            ProviderInfo(
                name="ollama",
                type="local",
                status="healthy" if ollama_health else "unhealthy",
                available=ollama_health,
                models=available_models,
                latency_ms=ollama.health.latency_ms,
                inference_mode=gpu_info.get("inference_mode"),
                gpu_count=gpu_info.get("gpu_count", 0),
                gpu_available=gpu_info.get("gpu_available", False),
                memory_total_mb=gpu_info.get("memory_total_mb"),
                memory_used_mb=gpu_info.get("memory_used_mb"),
                memory_percent=gpu_info.get("memory_percent"),
                model_loaded=gpu_info.get("model_loaded"),
            )
        )

        # Update GPU monitor with provider reference
        gpu_monitor.set_ollama_provider(ollama)

        logger.debug(
            f"Ollama status: healthy={ollama_health}, "
            f"models={len(available_models)}, "
            f"gpu_mode={gpu_info.get('inference_mode')}, "
            f"gpu_available={gpu_info.get('gpu_available')}"
        )

    except Exception as e:
        logger.warning(f"Failed to get Ollama status: {e}")
        providers.append(
            ProviderInfo(
                name="ollama",
                type="local",
                status="unavailable",
                available=False,
                models=[],
                inference_mode="unknown",
                gpu_available=False,
            )
        )

    # Get registered cloud providers
    for name, provider in router.get_all_providers().items():
        if name != "ollama":
            providers.append(
                ProviderInfo(
                    name=name,
                    type=provider.provider_type.value,
                    status=provider.health.status.value,
                    available=provider.is_available(),
                    models=provider.config.supported_models,
                    latency_ms=provider.health.latency_ms,
                )
            )

    # Get detailed GPU status
    try:
        detailed_status = await gpu_monitor.get_detailed_status()
        gpu_status = GPUStatusDetail(**detailed_status)
    except Exception as e:
        logger.warning(f"Failed to get detailed GPU status: {e}")
        gpu_status = GPUStatusDetail(
            available=False,
            mode="unknown",
            status="error",
            error=str(e),
            display_status="Error checking GPU status",
            display_icon="error",
        )

    # Get model health
    model_health = {}
    for key, health in health_monitor.get_all_health().items():
        model_health[key] = {
            "available": health.available,
            "success_rate": health.success_rate,
            "latency_ms": health.latency_ms,
            "error_count": health.error_count,
        }

    return ModelStatusResponse(
        timestamp=datetime.utcnow().isoformat(),
        providers=providers,
        gpu_status=gpu_status,
        model_health=model_health,
    )


@router.get("/providers", response_model=List[ProviderInfo])
async def get_providers():
    """
    Get information about all providers.

    Returns:
        List of provider information
    """
    router = get_model_router()
    providers = []

    # Ollama
    try:
        ollama = get_ollama_provider()
        available_models = await ollama.get_available_models()

        providers.append(
            ProviderInfo(
                name="ollama",
                type="local",
                status=ollama.health.status.value,
                available=ollama.is_available(),
                models=available_models,
                latency_ms=ollama.health.latency_ms,
            )
        )
    except Exception as e:
        logger.warning(f"Failed to get Ollama: {e}")

    # Cloud providers
    for name, provider in router.get_all_providers().items():
        if name != "ollama":
            providers.append(
                ProviderInfo(
                    name=name,
                    type=provider.provider_type.value,
                    status=provider.health.status.value,
                    available=provider.is_available(),
                    models=provider.config.supported_models,
                    latency_ms=provider.health.latency_ms,
                    circuit_breaker=router.get_circuit_breaker_status().get(name),
                )
            )

    return providers


@router.post("/test", response_model=ModelTestResponse)
async def test_model(request: ModelTestRequest):
    """
    Test a specific model.

    Args:
        request: Model test request

    Returns:
        Test result
    """
    router = get_model_router()

    try:
        # Get provider
        provider = router.get_provider(request.provider)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider {request.provider} not found")

        # Test the model
        response = await provider.generate(
            prompt=request.prompt,
            temperature=request.temperature,
        )

        return ModelTestResponse(
            success=True,
            provider=request.provider,
            model=request.model,
            latency_ms=response.latency_ms,
            content=response.content[:500],  # Limit response length
        )

    except Exception as e:
        logger.error(f"Model test failed: {e}")
        return ModelTestResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            latency_ms=0,
            content="",
            error=str(e),
        )


@router.post("/circuit-breaker/reset/{provider}")
async def reset_circuit_breaker(provider: str):
    """
    Reset circuit breaker for a provider.

    Args:
        provider: Provider name

    Returns:
        Success message
    """
    router = get_model_router()
    router.reset_circuit_breaker(provider)

    return {"message": f"Circuit breaker reset for {provider}"}


# Telemetry endpoints


@router.get("/telemetry", response_model=TelemetryResponse)
async def get_telemetry():
    """
    Get model telemetry.

    Returns:
        Telemetry summary
    """
    collector = get_telemetry_collector()

    return TelemetryResponse(
        summary=collector.get_summary(),
        providers=collector.get_all_provider_metrics(),
        task_types=collector.get_all_task_type_metrics(),
    )


@router.get("/telemetry/costs", response_model=CostResponse)
async def get_cost_telemetry(session_id: str = "default"):
    """
    Get cost telemetry for a session.

    Args:
        session_id: Session ID

    Returns:
        Cost telemetry
    """
    optimizer = get_cost_optimizer(session_id)
    summary = optimizer.get_session_summary()

    return CostResponse(
        session_id=session_id,
        total_cost_usd=summary["total_cost_usd"],
        total_tokens=summary["total_tokens"],
        by_provider=summary.get("by_model", {}),  # Using by_model as proxy
        by_model=summary.get("by_model", {}),
    )


@router.get("/routing/stats")
async def routing_stats() -> Dict[str, Any]:
    """
    Return detailed routing statistics, circuit breaker status, and fallback counts.
    """
    router = get_model_router()
    return {
        "routing_stats": router.get_routing_stats(),
        "circuit_breakers": router.get_circuit_breaker_status(),
    }


async def get_routing_stats():
    """
    Get routing statistics.

    Returns:
        Routing stats
    """
    router = get_model_router()

    return {
        "routing_stats": router.get_routing_stats(),
        "circuit_breakers": router.get_circuit_breaker_status(),
    }


# Health check endpoint


@router.get("/health")
async def models_health():
    """
    Quick health check for models.

    Returns:
        Health status
    """
    results = {}

    # Check Ollama
    try:
        ollama = get_ollama_provider()
        results["ollama"] = await ollama.health_check()
    except Exception as e:
        results["ollama"] = False

    # Check router providers
    router = get_model_router()
    for name, provider in router.get_all_providers().items():
        if name != "ollama":
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False

    return {
        "healthy": all(results.values()) if results else False,
        "providers": results,
    }


# Dedicated GPU status endpoint


@router.get("/gpu-status")
async def get_gpu_status():
    """
    Get detailed GPU status for monitoring dashboard.

    This endpoint provides comprehensive GPU information including:
    - GPU availability and count
    - Memory usage
    - Inference mode (NVIDIA/AMD/CPU)
    - Loaded models
    - User-friendly status messages

    Returns:
        Detailed GPU status
    """
    gpu_monitor = get_gpu_monitor()

    try:
        ollama = get_ollama_provider()
        gpu_monitor.set_ollama_provider(ollama)

        detailed_status = await gpu_monitor.get_detailed_status()
        return detailed_status

    except Exception as e:
        logger.error(f"Failed to get GPU status: {e}")
        return {
            "available": False,
            "mode": "unknown",
            "status": "error",
            "error": str(e),
            "display_status": "GPU Status Error",
            "display_icon": "error",
        }


# Model Selection Endpoints


@router.get("", response_model=ModelListResponse)
async def get_all_models():
    """
    Get all available models (local + cloud).

    Returns:
        All available models with metadata
    """
    registry = get_model_registry()
    models = await registry.get_available_models()

    return ModelListResponse(**models)


@router.get("/local", response_model=LocalModelsResponse)
async def get_local_models():
    """
    Get dynamically discovered local Ollama models.

    Uses Ollama's /api/tags endpoint to discover installed models.
    No hardcoded model lists.

    Returns:
        List of available local models
    """
    registry = get_model_registry()
    models = await registry.get_local_models()

    return LocalModelsResponse(
        models=[
            {
                "name": m.name,
                "provider": m.provider,
                "model_type": m.model_type.value,
                "is_local": m.is_local,
                "available": m.available,
                "health_status": m.health_status,
                "latency_ms": m.latency_ms,
                "display_name": m.display_name,
                "icon": m.icon,
            }
            for m in models
        ],
        count=len(models),
    )


@router.get("/cloud", response_model=CloudModelsResponse)
async def get_cloud_models():
    """
    Get available cloud models by provider.

    Returns:
        Dict of provider -> models
    """
    registry = get_model_registry()
    cloud_models = await registry.get_cloud_models()

    return CloudModelsResponse(
        providers={
            provider: [
                {
                    "name": m.name,
                    "provider": m.provider,
                    "model_type": m.model_type.value,
                    "is_local": m.is_local,
                    "available": m.available,
                    "health_status": m.health_status,
                    "latency_ms": m.latency_ms,
                    "display_name": m.display_name,
                    "icon": m.icon,
                }
                for m in models
            ]
            for provider, models in cloud_models.items()
        }
    )


@router.get("/providers/status", response_model=ProviderStatusResponse)
async def get_providers_status():
    """
    Get health status of all providers.

    Returns:
        List of provider statuses with health indicators
    """
    registry = get_model_registry()
    statuses = await registry.get_provider_status()

    return ProviderStatusResponse(
        providers=[
            {
                "name": s.name,
                "provider_type": s.provider_type,
                "status": s.status,
                "available": s.available,
                "models": s.models,
                "latency_ms": s.latency_ms,
                "error": s.error,
                "last_check": s.last_check.isoformat() if s.last_check else None,
                "status_icon": s.status_icon,
            }
            for s in statuses
        ]
    )


@router.post("/select", response_model=ModelSelectionResponse)
async def select_model(request: ModelSelectionRequest):
    """
    Select model for a research session.

    Allows users to:
    - Select a specific provider and model
    - Set routing mode (auto, local_only, cloud_only, hybrid)
    - Override automatic routing decisions

    Args:
        request: Model selection request

    Returns:
        Selection result
    """
    # Validate routing mode
    valid_routing_modes = ["auto", "local_only", "cloud_only", "hybrid"]
    if request.routing_mode not in valid_routing_modes:
        return ModelSelectionResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            routing_mode=request.routing_mode,
            message="",
            error=f"Invalid routing_mode. Must be one of: {valid_routing_modes}",
        )

    # Validate provider
    valid_providers = ["auto", "ollama", "openai", "anthropic", "google", "groq"]
    if request.provider not in valid_providers:
        return ModelSelectionResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            routing_mode=request.routing_mode,
            message="",
            error=f"Invalid provider. Must be one of: {valid_providers}",
        )

    registry = get_model_registry()
    result = await registry.select_model(
        session_id=request.session_id,
        provider=request.provider,
        model=request.model,
        routing_mode=request.routing_mode,
    )

    return ModelSelectionResponse(
        success=result["success"],
        provider=result.get("provider", request.provider),
        model=result.get("model", request.model),
        routing_mode=result.get("routing_mode", request.routing_mode),
        message=result.get("message", ""),
        error=result.get("error"),
    )


@router.get("/selection/{session_id}")
async def get_model_selection(session_id: str):
    """
    Get current model selection for a session.

    Args:
        session_id: Session identifier

    Returns:
        Current selection
    """
    registry = get_model_registry()
    selection = await registry.get_user_selection(session_id)

    # Resolve actual model being used
    provider, model = await registry.resolve_model(session_id)

    return {
        "session_id": session_id,
        "selected_provider": selection["provider"],
        "selected_model": selection["model"],
        "routing_mode": selection["routing_mode"],
        "active_provider": provider,
        "active_model": model,
    }


@router.post("/refresh-local")
async def refresh_local_models():
    """
    Manually trigger refresh of local Ollama models.

    Returns:
        Refreshed model list
    """
    registry = get_model_registry()
    models = await registry.refresh_local_models()

    return {
        "success": True,
        "models": [m.name for m in models],
        "count": len(models),
    }
