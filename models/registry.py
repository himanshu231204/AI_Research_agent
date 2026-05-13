"""
Model Registry for Research OS.

Centralized registry that dynamically discovers local Ollama models
and manages cloud providers. Provides a unified interface for model
discovery, health monitoring, and selection.

Architecture:
- ModelRegistry: Central registry for all models
- ModelInfo: Dataclass for model metadata
- ProviderStatus: Health status for providers
- RoutingMode: User-selectable routing modes
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict

from models.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderStatus as BaseProviderStatus,
)
from models.providers.local import OllamaProvider, get_ollama_provider
from models.providers.cloud import (
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
)
from api.config import get_settings

logger = logging.getLogger(__name__)


class RoutingMode(Enum):
    """User-selectable routing modes."""

    AUTO = "auto"  # System chooses best model
    LOCAL_ONLY = "local_only"  # Use only Ollama models
    CLOUD_ONLY = "cloud_only"  # Use only cloud providers
    HYBRID = "hybrid"  # Prefer local, fallback to cloud


class ModelType(Enum):
    """Types of models."""

    CHAT = "chat"  # General chat models
    CODING = "coding"  # Code-specific models
    EMBEDDING = "embedding"  # Embedding models
    REASONING = "reasoning"  # Reasoning models


@dataclass
class ModelInfo:
    """Model information and metadata."""

    name: str
    provider: str
    model_type: ModelType = ModelType.CHAT
    is_local: bool = True
    size_mb: Optional[float] = None
    modified_at: Optional[str] = None
    available: bool = True
    health_status: str = "healthy"
    latency_ms: float = 0.0
    context_length: Optional[int] = None
    description: Optional[str] = None

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.name.replace("-", " ").replace("_", " ").title()

    @property
    def icon(self) -> str:
        """Get icon based on model type."""
        if self.is_local:
            return "🖥️"
        return "☁️"


@dataclass
class ProviderStatus:
    """Provider health status for registry."""

    name: str
    provider_type: str  # "local" or "cloud"
    status: str  # "healthy", "degraded", "offline", "unavailable"
    available: bool
    models: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None
    last_check: Optional[datetime] = None

    @property
    def status_icon(self) -> str:
        """Get status icon."""
        status_map = {
            "healthy": "🟢",
            "degraded": "🟡",
            "offline": "🔴",
            "unavailable": "🔴",
        }
        return status_map.get(self.status, "⚪")


class ModelRegistry:
    """
    Central model registry for Research OS.

    Features:
    - Dynamic Ollama model discovery
    - Cloud provider management
    - Health monitoring
    - User preference storage
    - Routing mode support
    """

    def __init__(self):
        """Initialize model registry."""
        self._providers: Dict[str, LLMProvider] = {}
        self._local_models: List[ModelInfo] = []
        self._cloud_models: Dict[str, List[ModelInfo]] = defaultdict(list)
        self._user_selections: Dict[
            str, Dict[str, str]
        ] = {}  # session_id -> {provider, model, routing_mode}
        self._refresh_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

        # Default cloud models (will be updated from providers)
        self._default_cloud_models = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-5"],
            "anthropic": [
                "claude-opus-4-20250514",
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20240620",
            ],
            "google": ["gemini-2.0-flash", "gemini-2.5-pro"],
            "groq": [
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile",
                "mixtral-8x7b-32768",
            ],
        }

    async def initialize(self) -> None:
        """Initialize registry with providers."""
        settings = get_settings()

        # Register Ollama provider
        try:
            ollama = get_ollama_provider()
            self._providers["ollama"] = ollama
            logger.info("Registered Ollama provider")
        except Exception as e:
            logger.warning(f"Failed to register Ollama: {e}")

        # Register cloud providers if API keys are available
        if settings.openai_api_key:
            try:
                config = ProviderConfig(
                    provider_type=ProviderType.OPENAI,
                    name="openai",
                    base_url="https://api.openai.com/v1",
                    api_key=settings.openai_api_key,
                    default_model="gpt-4o",
                    supported_models=self._default_cloud_models["openai"],
                )
                self._providers["openai"] = OpenAIProvider(config)
                logger.info("Registered OpenAI provider")
            except Exception as e:
                logger.warning(f"Failed to register OpenAI: {e}")

        if settings.anthropic_api_key:
            try:
                config = ProviderConfig(
                    provider_type=ProviderType.ANTHROPIC,
                    name="anthropic",
                    base_url="https://api.anthropic.com/v1",
                    api_key=settings.anthropic_api_key,
                    default_model="claude-sonnet-4-20250514",
                    supported_models=self._default_cloud_models["anthropic"],
                )
                self._providers["anthropic"] = AnthropicProvider(config)
                logger.info("Registered Anthropic provider")
            except Exception as e:
                logger.warning(f"Failed to register Anthropic: {e}")

        if settings.google_api_key:
            try:
                config = ProviderConfig(
                    provider_type=ProviderType.GOOGLE,
                    name="google",
                    base_url="https://generativelanguage.googleapis.com/v1beta",
                    api_key=settings.google_api_key,
                    default_model="gemini-2.0-flash",
                    supported_models=self._default_cloud_models["google"],
                )
                self._providers["google"] = GoogleProvider(config)
                logger.info("Registered Google provider")
            except Exception as e:
                logger.warning(f"Failed to register Google: {e}")

        if settings.groq_api_key:
            try:
                config = ProviderConfig(
                    provider_type=ProviderType.OPENROUTER,
                    name="groq",
                    base_url="https://api.groq.com/openai/v1",
                    api_key=settings.groq_api_key,
                    default_model="llama-3.3-70b-versatile",
                    supported_models=self._default_cloud_models["groq"],
                )
                self._providers["groq"] = GroqProvider(config)
                logger.info("Registered Groq provider")
            except Exception as e:
                logger.warning(f"Failed to register Groq: {e}")

        # Initial model discovery
        await self.refresh_local_models()
        await self._initialize_cloud_models()

    async def _initialize_cloud_models(self) -> None:
        """Initialize cloud model lists from providers."""
        for provider_name, provider in self._providers.items():
            if provider_name == "ollama":
                continue

            models = []
            for model_name in provider.config.supported_models:
                # Determine model type
                model_type = self._infer_model_type(model_name)

                model_info = ModelInfo(
                    name=model_name,
                    provider=provider_name,
                    model_type=model_type,
                    is_local=False,
                    available=provider.is_available(),
                    health_status=provider.health.status.value,
                    latency_ms=provider.health.latency_ms,
                )
                models.append(model_info)

            self._cloud_models[provider_name] = models

    def _infer_model_type(self, model_name: str) -> ModelType:
        """Infer model type from model name."""
        model_lower = model_name.lower()

        if any(kw in model_lower for kw in ["coder", "code", "dev"]):
            return ModelType.CODING
        elif any(kw in model_lower for kw in ["embed", "embedding"]):
            return ModelType.EMBEDDING
        elif any(kw in model_lower for kw in ["reason", "think", "o1", "o3"]):
            return ModelType.REASONING

        return ModelType.CHAT

    async def refresh_local_models(self) -> List[ModelInfo]:
        """
        Dynamically discover installed Ollama models.

        Uses Ollama's /api/tags endpoint to get the list of
        downloaded models.

        Returns:
            List of discovered ModelInfo
        """
        async with self._lock:
            ollama = self._providers.get("ollama")

            if not ollama:
                logger.warning("Ollama provider not available")
                return []

            try:
                # Get available models from Ollama
                available_models = await ollama.get_available_models()

                # Convert to ModelInfo objects
                self._local_models = []

                for model_name in available_models:
                    # Determine model type
                    model_type = self._infer_model_type(model_name)

                    model_info = ModelInfo(
                        name=model_name,
                        provider="ollama",
                        model_type=model_type,
                        is_local=True,
                        available=True,
                        health_status="healthy",
                        latency_ms=ollama.health.latency_ms,
                    )
                    self._local_models.append(model_info)

                logger.info(f"Discovered {len(self._local_models)} local models")
                return self._local_models

            except Exception as e:
                logger.error(f"Failed to refresh local models: {e}")
                return self._local_models

    async def get_local_models(self) -> List[ModelInfo]:
        """
        Get list of available local models.

        Returns:
            List of local ModelInfo
        """
        if not self._local_models:
            await self.refresh_local_models()
        return self._local_models

    async def get_cloud_models(self) -> Dict[str, List[ModelInfo]]:
        """
        Get list of available cloud models by provider.

        Returns:
            Dict of provider -> List[ModelInfo]
        """
        # Update availability based on provider health
        for provider_name, provider in self._providers.items():
            if provider_name == "ollama":
                continue

            for model in self._cloud_models.get(provider_name, []):
                model.available = provider.is_available()
                model.health_status = provider.health.status.value
                model.latency_ms = provider.health.latency_ms

        return self._cloud_models

    async def get_available_models(self) -> Dict[str, Any]:
        """
        Get all available models with metadata.

        Returns:
            Dict with local and cloud models
        """
        local = await self.get_local_models()
        cloud = await self.get_cloud_models()

        return {
            "local": [self._model_to_dict(m) for m in local],
            "cloud": {
                provider: [self._model_to_dict(m) for m in models]
                for provider, models in cloud.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _model_to_dict(self, model: ModelInfo) -> Dict[str, Any]:
        """Convert ModelInfo to dictionary."""
        return {
            "name": model.name,
            "provider": model.provider,
            "model_type": model.model_type.value,
            "is_local": model.is_local,
            "size_mb": model.size_mb,
            "available": model.available,
            "health_status": model.health_status,
            "latency_ms": model.latency_ms,
            "context_length": model.context_length,
            "description": model.description,
            "display_name": model.display_name,
            "icon": model.icon,
        }

    async def get_provider_status(self) -> List[ProviderStatus]:
        """
        Get health status of all providers.

        Returns:
            List of ProviderStatus
        """
        statuses = []

        # Check Ollama
        ollama = self._providers.get("ollama")
        if ollama:
            try:
                is_healthy = await ollama.health_check()
                statuses.append(
                    ProviderStatus(
                        name="ollama",
                        provider_type="local",
                        status="healthy" if is_healthy else "offline",
                        available=is_healthy,
                        models=[m.name for m in self._local_models],
                        latency_ms=ollama.health.latency_ms,
                        last_check=datetime.utcnow(),
                    )
                )
            except Exception as e:
                statuses.append(
                    ProviderStatus(
                        name="ollama",
                        provider_type="local",
                        status="unavailable",
                        available=False,
                        models=[],
                        error=str(e),
                        last_check=datetime.utcnow(),
                    )
                )
        else:
            statuses.append(
                ProviderStatus(
                    name="ollama",
                    provider_type="local",
                    status="unavailable",
                    available=False,
                    models=[],
                    error="Provider not registered",
                    last_check=datetime.utcnow(),
                )
            )

        # Check cloud providers
        for provider_name, provider in self._providers.items():
            if provider_name == "ollama":
                continue

            try:
                is_healthy = await provider.health_check()
                statuses.append(
                    ProviderStatus(
                        name=provider_name,
                        provider_type="cloud",
                        status="healthy" if is_healthy else "degraded",
                        available=is_healthy,
                        models=provider.config.supported_models,
                        latency_ms=provider.health.latency_ms,
                        last_check=datetime.utcnow(),
                    )
                )
            except Exception as e:
                statuses.append(
                    ProviderStatus(
                        name=provider_name,
                        provider_type="cloud",
                        status="offline",
                        available=False,
                        models=provider.config.supported_models,
                        error=str(e),
                        last_check=datetime.utcnow(),
                    )
                )

        return statuses

    async def set_user_selection(
        self,
        session_id: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        routing_mode: Optional[str] = None,
    ) -> None:
        """
        Store user model selection for a session (thread-safe).

        Args:
            session_id: Session identifier
            provider: Selected provider
            model: Selected model
            routing_mode: Selected routing mode
        """
        async with self._lock:
            if session_id not in self._user_selections:
                self._user_selections[session_id] = {
                    "provider": "auto",
                    "model": "",
                    "routing_mode": "auto",
                }

            if provider is not None:
                self._user_selections[session_id]["provider"] = provider
            if model is not None:
                self._user_selections[session_id]["model"] = model
            if routing_mode is not None:
                self._user_selections[session_id]["routing_mode"] = routing_mode

            logger.info(f"User selection for {session_id}: {self._user_selections[session_id]}")

    async def get_user_selection(self, session_id: str) -> Dict[str, str]:
        """
        Get user model selection for a session (thread-safe).

        Args:
            session_id: Session identifier

        Returns:
            Dict with provider, model, routing_mode
        """
        async with self._lock:
            return self._user_selections.get(
                session_id,
                {"provider": "auto", "model": "", "routing_mode": "auto"},
            ).copy()

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Get provider by name."""
        return self._providers.get(name)

    def get_all_providers(self) -> Dict[str, LLMProvider]:
        """Get all registered providers."""
        return self._providers.copy()

    async def select_model(
        self,
        session_id: str,
        provider: str,
        model: str,
        routing_mode: str = "auto",
    ) -> Dict[str, Any]:
        """
        Select model for a session (thread-safe).

        Args:
            session_id: Session identifier
            provider: Provider name
            model: Model name
            routing_mode: Routing mode

        Returns:
            Selection result
        """
        async with self._lock:
            # Validate provider
            if provider != "auto" and provider not in self._providers:
                return {
                    "success": False,
                    "error": f"Provider {provider} not available",
                }

            # Validate model for selected provider
            if provider != "auto" and model:
                provider_models = []
                if provider == "ollama":
                    provider_models = [m.name for m in self._local_models]
                else:
                    # Cloud models are stored as ModelInfo objects
                    cloud_models = self._cloud_models.get(provider, [])
                    provider_models = [m.name if hasattr(m, "name") else m for m in cloud_models]

                if provider_models and model not in provider_models:
                    return {
                        "success": False,
                        "error": f"Model {model} not available for {provider}",
                    }

            # Store selection
            if session_id not in self._user_selections:
                self._user_selections[session_id] = {
                    "provider": "auto",
                    "model": "",
                    "routing_mode": "auto",
                }

            self._user_selections[session_id]["provider"] = provider
            self._user_selections[session_id]["model"] = model
            self._user_selections[session_id]["routing_mode"] = routing_mode

            return {
                "success": True,
                "provider": provider,
                "model": model,
                "routing_mode": routing_mode,
                "message": f"Model selection updated: {provider}/{model}",
            }

    async def resolve_model(
        self,
        session_id: str,
        task_type: str = "general",
    ) -> tuple[str, str]:
        """
        Resolve the actual model to use based on user selection and routing mode (thread-safe).

        Args:
            session_id: Session identifier
            task_type: Type of task (planning, coding, etc.)

        Returns:
            Tuple of (provider, model)
        """
        async with self._lock:
            selection = self._user_selections.get(
                session_id,
                {"provider": "auto", "model": "", "routing_mode": "auto"},
            ).copy()

            provider = selection["provider"]
            model = selection["model"]
            routing_mode = selection["routing_mode"]

            # Auto mode - use routing logic
            if provider == "auto" or routing_mode == "auto":
                return self._auto_route(task_type)

            # Local only mode
            if routing_mode == "local_only":
                if self._local_models:
                    return ("ollama", self._local_models[0].name)
                return self._auto_route(task_type)

            # Cloud only mode
            if routing_mode == "cloud_only":
                cloud_providers = {k: v for k, v in self._providers.items() if k != "ollama"}
                if cloud_providers:
                    first_provider = list(cloud_providers.keys())[0]
                    provider_obj = cloud_providers[first_provider]
                    return (first_provider, provider_obj.config.default_model)
                return self._auto_route(task_type)

            # Hybrid mode - prefer local, fallback to cloud
            if routing_mode == "hybrid":
                if self._local_models:
                    return ("ollama", self._local_models[0].name)
                return self._auto_route(task_type)

            # Explicit provider/model selection
            if provider and model:
                return (provider, model)

            # Fallback to auto routing
            return self._auto_route(task_type)

    def _auto_route(self, task_type: str) -> tuple[str, str]:
        """Auto-route based on task type."""
        # Default routing based on task type
        task_routing = {
            "planning": ("ollama", "qwen3"),
            "coding": ("ollama", "deepseek-coder"),
            "reflection": ("ollama", "mistral"),
            "summarization": ("ollama", "llama3"),
            "general": ("ollama", "qwen3"),
        }

        return task_routing.get(task_type, ("ollama", "qwen3"))


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get or create global model registry."""
    global _registry

    if _registry is None:
        _registry = ModelRegistry()

    return _registry


async def initialize_model_registry() -> ModelRegistry:
    """Initialize and return the model registry."""
    registry = get_model_registry()
    await registry.initialize()
    return registry
