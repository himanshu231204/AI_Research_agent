"""
Models package for Research OS.

Provides:
- Provider abstraction layer
- Local model infrastructure (Ollama)
- Cloud model providers (OpenAI, Anthropic, Google)
- Model routing with fallback
- Cost optimization
- GPU-aware scheduling
- Telemetry
"""

# Base provider classes
from models.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderStatus,
    ProviderHealth,
    LLMResponse,
    StreamingChunk,
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderModelUnavailableError,
)

# Local provider
from models.providers.local import (
    OllamaProvider,
    get_ollama_provider,
    create_ollama_provider,
)

# Cloud providers
from models.providers.cloud import (
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
    create_openai_provider,
    create_anthropic_provider,
    create_google_provider,
    create_groq_provider,
)

# Routing
from models.routing.router import (
    ModelRouter,
    get_model_router,
    initialize_router,
    TaskType,
    RoutingPolicy,
    RetryPolicy,
    CircuitBreakerState,
    RoutingDecision,
)

# GPU scheduling
from models.routing.gpu_scheduler import (
    GPUMonitor,
    HealthMonitor,
    AdaptiveScheduler,
    get_gpu_monitor,
    get_health_monitor,
    get_adaptive_scheduler,
)

# Cost optimization
from models.routing.cost_optimizer import (
    CostOptimizer,
    CostBudget,
    TokenBudget,
    TokenBudgetManager,
    PromptOptimizer,
    get_cost_optimizer,
    get_token_budget_manager,
)

# Telemetry
from models.routing.telemetry import (
    TelemetryCollector,
    RequestTelemetry,
    ProviderMetrics,
    get_telemetry_collector,
    record_inference_telemetry,
)

# Legacy compatibility
from models.ollama_client import OllamaClient, OllamaError, OllamaTimeoutError

__all__ = [
    # Base
    "LLMProvider",
    "ProviderConfig",
    "ProviderType",
    "ProviderStatus",
    "ProviderHealth",
    "LLMResponse",
    "StreamingChunk",
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderRateLimitError",
    "ProviderAuthenticationError",
    "ProviderModelUnavailableError",
    # Local
    "OllamaProvider",
    "get_ollama_provider",
    "create_ollama_provider",
    # Cloud
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    "create_openai_provider",
    "create_anthropic_provider",
    "create_google_provider",
    # Routing
    "ModelRouter",
    "get_model_router",
    "initialize_router",
    "TaskType",
    "RoutingPolicy",
    "RetryPolicy",
    "CircuitBreakerState",
    "RoutingDecision",
    # GPU
    "GPUMonitor",
    "HealthMonitor",
    "AdaptiveScheduler",
    "get_gpu_monitor",
    "get_health_monitor",
    "get_adaptive_scheduler",
    # Cost
    "CostOptimizer",
    "CostBudget",
    "TokenBudget",
    "TokenBudgetManager",
    "PromptOptimizer",
    "get_cost_optimizer",
    "get_token_budget_manager",
    # Telemetry
    "TelemetryCollector",
    "RequestTelemetry",
    "ProviderMetrics",
    "get_telemetry_collector",
    "record_inference_telemetry",
    # Legacy
    "OllamaClient",
    "OllamaError",
    "OllamaTimeoutError",
]
