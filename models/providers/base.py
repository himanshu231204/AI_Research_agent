"""
Provider abstraction layer for Research OS.

This module defines the base LLM provider interface that all
providers (local and cloud) must implement. This ensures
the platform never directly depends on specific SDKs.

Architecture:
- LLMProvider: Abstract base class for all LLM providers
- ProviderConfig: Configuration dataclass for provider settings
- ProviderHealth: Health status for monitoring
- StreamingResponse: Unified streaming response format
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncGenerator, Callable
from datetime import datetime
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Types of LLM providers."""

    LOCAL = "local"  # Ollama, LM Studio, etc.
    OPENAI = "openai"  # OpenAI API
    ANTHROPIC = "anthropic"  # Anthropic API
    GOOGLE = "google"  # Google Gemini
    OPENROUTER = "openrouter"  # OpenRouter aggregator
    CUSTOM = "custom"  # Custom endpoint


class ProviderStatus(Enum):
    """Provider health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    # Provider identification
    provider_type: ProviderType
    name: str

    # Connection settings
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = 120

    # Model settings
    default_model: str = ""
    supported_models: List[str] = field(default_factory=list)

    # Performance settings
    max_retries: int = 3
    retry_delay: float = 1.0
    max_concurrent_requests: int = 10

    # Cost settings (per 1M tokens)
    prompt_cost: float = 0.0
    completion_cost: float = 0.0

    # Local-specific settings
    gpu_enabled: bool = True
    gpu_memory_threshold: float = 0.9  # 90% VRAM usage threshold


@dataclass
class ProviderHealth:
    """Health status for a provider."""

    provider_name: str
    status: ProviderStatus
    last_check: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    total_requests: int = 0

    # Local-specific metrics
    gpu_available: bool = True
    gpu_memory_percent: float = 0.0
    active_models: List[str] = field(default_factory=list)

    # Circuit breaker state
    circuit_open: bool = False
    circuit_open_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def is_available(self) -> bool:
        """Check if provider is available."""
        return (
            self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
            and not self.circuit_open
        )


@dataclass
class LLMResponse:
    """Unified LLM response format."""

    # Content
    content: str

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Metadata
    model: str = ""
    provider: str = ""
    finish_reason: str = ""

    # Timing
    latency_ms: float = 0.0

    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Calculate total tokens."""
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class StreamingChunk:
    """Streaming response chunk."""

    content: str
    delta: str = ""
    model: str = ""
    provider: str = ""
    index: int = 0
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers (local and cloud) must implement this interface.
    This ensures the platform never directly depends on specific SDKs
    and supports easy provider switching and fallback.
    """

    def __init__(self, config: ProviderConfig):
        """
        Initialize provider with configuration.

        Args:
            config: Provider configuration
        """
        self.config = config
        self._health = ProviderHealth(
            provider_name=config.name,
            status=ProviderStatus.UNKNOWN,
        )
        self._semaphore = asyncio.Semaphore(config.max_concurrent_requests)

    @property
    def name(self) -> str:
        """Get provider name."""
        return self.config.name

    @property
    def provider_type(self) -> ProviderType:
        """Get provider type."""
        return self.config.provider_type

    @property
    def health(self) -> ProviderHealth:
        """Get provider health status."""
        return self._health

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate text from prompt.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Stream chat completion.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            StreamingChunk for each token
        """
        pass

    @abstractmethod
    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Optional embedding model override

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is available and healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    async def get_available_models(self) -> List[str]:
        """
        Get list of available models.

        Returns:
            List of model names
        """
        return self.config.supported_models

    def update_health(
        self,
        status: ProviderStatus,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """
        Update provider health status.

        Args:
            status: New health status
            latency_ms: Request latency
            success: Whether request succeeded
        """
        self._health.status = status
        self._health.last_check = datetime.utcnow()
        self._health.latency_ms = latency_ms
        self._health.total_requests += 1

        if success:
            self._health.success_count += 1
        else:
            self._health.error_count += 1

    def is_available(self) -> bool:
        """Check if provider is available for requests."""
        return self._health.is_available

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close provider resources."""
        pass


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class ProviderTimeoutError(ProviderError):
    """Exception for provider timeout errors."""

    pass


class ProviderRateLimitError(ProviderError):
    """Exception for rate limit errors."""

    pass


class ProviderAuthenticationError(ProviderError):
    """Exception for authentication errors."""

    pass


class ProviderModelUnavailableError(ProviderError):
    """Exception for unavailable model errors."""

    pass
