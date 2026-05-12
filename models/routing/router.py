"""
Model routing layer for Research OS.

This module provides:
- Centralized model routing
- Automatic fallback system
- Cost-aware selection
- Workload specialization
- Circuit breaker implementation
- Intelligent retry policies
"""

import logging
import time
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from models.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderStatus,
    LLMResponse,
    StreamingChunk,
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderModelUnavailableError,
)
from models.providers.local import OllamaProvider
from models.providers.cloud import OpenAIProvider, AnthropicProvider, GoogleProvider
from models.routing.gpu_telemetry import log_route_decision, get_gpu_telemetry_logger

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task types for intelligent routing."""

    PLANNING = "planning"
    CODING = "coding"
    REFLECTION = "reflection"
    SUMMARIZATION = "summarization"
    RETRIEVAL = "retrieval"
    GENERAL = "general"
    EMBEDDING = "embedding"


@dataclass
class RoutingPolicy:
    """Routing policy for task type."""

    task_type: TaskType
    primary_model: str
    primary_provider: str
    fallback_chain: List[str]  # List of provider:model
    max_latency_ms: int = 30000
    max_cost: float = 1.0
    temperature: float = 0.7
    max_tokens: Optional[int] = None


# Default routing policies
DEFAULT_ROUTING_POLICIES: Dict[TaskType, RoutingPolicy] = {
    TaskType.PLANNING: RoutingPolicy(
        task_type=TaskType.PLANNING,
        primary_model="qwen3",
        primary_provider="ollama",
        fallback_chain=["openai:gpt-4o", "anthropic:claude-sonnet-4-20250514"],
        max_latency_ms=30000,
        max_cost=0.5,
    ),
    TaskType.CODING: RoutingPolicy(
        task_type=TaskType.CODING,
        primary_model="deepseek-coder",
        primary_provider="ollama",
        fallback_chain=["anthropic:claude-sonnet-4-20250514", "openai:gpt-4o"],
        max_latency_ms=45000,
        max_cost=1.0,
    ),
    TaskType.REFLECTION: RoutingPolicy(
        task_type=TaskType.REFLECTION,
        primary_model="mistral",
        primary_provider="ollama",
        fallback_chain=["google:gemini-2.0-flash", "openai:gpt-4o-mini"],
        max_latency_ms=20000,
        max_cost=0.3,
    ),
    TaskType.SUMMARIZATION: RoutingPolicy(
        task_type=TaskType.SUMMARIZATION,
        primary_model="llama3",
        primary_provider="ollama",
        fallback_chain=["openai:gpt-4o-mini", "anthropic:claude-3-5-sonnet-20240620"],
        max_latency_ms=15000,
        max_cost=0.2,
    ),
    TaskType.RETRIEVAL: RoutingPolicy(
        task_type=TaskType.RETRIEVAL,
        primary_model="qwen3",
        primary_provider="ollama",
        fallback_chain=["openai:gpt-4o-mini"],
        max_latency_ms=10000,
        max_cost=0.1,
    ),
    TaskType.GENERAL: RoutingPolicy(
        task_type=TaskType.GENERAL,
        primary_model="qwen3",
        primary_provider="ollama",
        fallback_chain=["openai:gpt-4o", "anthropic:claude-sonnet-4-20250514"],
        max_latency_ms=30000,
        max_cost=0.5,
    ),
    TaskType.EMBEDDING: RoutingPolicy(
        task_type=TaskType.EMBEDDING,
        primary_model="nomic-embed-text",
        primary_provider="ollama",
        fallback_chain=["openai:text-embedding-3-small"],
        max_latency_ms=10000,
        max_cost=0.05,
    ),
}


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a provider."""

    provider_name: str
    state: str = "closed"  # closed, open, half_open
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    # Configuration
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: int = 60

    def record_success(self) -> None:
        """Record successful request."""
        self.success_count += 1
        self.last_success_time = datetime.utcnow()

        if self.state == "half_open" and self.success_count >= self.success_threshold:
            self.state = "closed"
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"Circuit breaker closed for {self.provider_name}")

    def record_failure(self) -> None:
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == "closed" and self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened for {self.provider_name}")

        elif self.state == "half_open":
            self.state = "open"
            self.success_count = 0
            logger.warning(f"Circuit breaker reopened for {self.provider_name}")

    def can_attempt(self) -> bool:
        """Check if request can be attempted."""
        if self.state == "closed":
            return True

        if self.state == "open":
            if self.last_failure_time:
                time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.timeout_seconds:
                    self.state = "half_open"
                    self.success_count = 0
                    return True
            return False

        # half_open
        return True

    def should_reset(self) -> bool:
        """Check if circuit breaker should be reset."""
        if self.state == "open" and self.last_failure_time:
            time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
            return time_since_failure >= self.timeout_seconds
        return False


@dataclass
class RetryPolicy:
    """Retry policy configuration."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        import random

        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay *= random.uniform(0.5, 1.5)

        return delay

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if should retry."""
        if attempt >= self.max_retries:
            return False

        # Don't retry on these exceptions
        non_retryable = (
            ProviderAuthenticationError,
            ProviderModelUnavailableError,
        )

        return not isinstance(error, non_retryable)


@dataclass
class RoutingDecision:
    """Routing decision with metadata."""

    provider: str
    model: str
    task_type: TaskType
    policy: RoutingPolicy
    latency_ms: float = 0.0
    fallback_attempted: bool = False
    fallback_chain: List[str] = field(default_factory=list)
    error: Optional[str] = None


class ModelRouter:
    """
    Central model routing system.

    Features:
    - Intelligent model selection based on task type
    - Automatic fallback on failures
    - Circuit breaker implementation
    - Cost-aware routing
    - GPU-aware scheduling
    """

    def __init__(self):
        """Initialize model router."""
        self._providers: Dict[str, LLMProvider] = {}
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._routing_policies = DEFAULT_ROUTING_POLICIES.copy()
        self._retry_policy = RetryPolicy()

        # Telemetry
        self._routing_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "fallback_count": 0,
                "total_latency_ms": 0.0,
            }
        )

    def register_provider(self, provider: LLMProvider) -> None:
        """
        Register a provider.

        Args:
            provider: LLMProvider instance
        """
        self._providers[provider.name] = provider
        self._circuit_breakers[provider.name] = CircuitBreakerState(
            provider_name=provider.name,
        )
        logger.info(f"Registered provider: {provider.name}")

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Get provider by name."""
        return self._providers.get(name)

    def get_all_providers(self) -> Dict[str, LLMProvider]:
        """Get all registered providers."""
        return self._providers.copy()

    def set_policy(self, task_type: TaskType, policy: RoutingPolicy) -> None:
        """Set routing policy for task type."""
        self._routing_policies[task_type] = policy

    def get_policy(self, task_type: TaskType) -> RoutingPolicy:
        """Get routing policy for task type."""
        return self._routing_policies.get(task_type, DEFAULT_ROUTING_POLICIES[TaskType.GENERAL])

    def _get_circuit_breaker(self, provider_name: str) -> CircuitBreakerState:
        """Get or create circuit breaker for provider."""
        if provider_name not in self._circuit_breakers:
            self._circuit_breakers[provider_name] = CircuitBreakerState(provider_name=provider_name)
        return self._circuit_breakers[provider_name]

    def _parse_provider_model(self, provider_model: str) -> tuple[str, str]:
        """Parse provider:model string."""
        parts = provider_model.split(":")
        if len(parts) == 2:
            return parts[0], parts[1]
        return parts[0], ""

    def _get_inference_mode(self, provider_name: str) -> str:
        """
        Get inference mode for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Inference mode (nvidia, amd, cpu, unknown)
        """
        provider = self.get_provider(provider_name)
        if provider and hasattr(provider, "_health"):
            return getattr(provider._health, "inference_mode", "unknown")
        return "unknown"

    async def route(
        self,
        task_type: TaskType,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """
        Route request to appropriate provider with fallback.

        Args:
            task_type: Type of task
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens

        Returns:
            Tuple of (LLMResponse, RoutingDecision)
        """
        policy = self.get_policy(task_type)
        start_time = time.perf_counter()

        # Try primary provider first
        provider_model = f"{policy.primary_provider}:{policy.primary_model}"
        fallback_chain = []

        try:
            response, decision = await self._try_provider(
                provider_model,
                prompt,
                system,
                temperature,
                max_tokens,
                task_type,
                policy,
            )

            decision.latency_ms = (time.perf_counter() - start_time) * 1000

            # Log routing decision
            inference_mode = self._get_inference_mode(policy.primary_provider)
            log_route_decision(
                task_type=task_type.value,
                provider=policy.primary_provider,
                model=policy.primary_model,
                inference_mode=inference_mode,
                latency_ms=decision.latency_ms,
                fallback_used=False,
            )

            return response, decision

        except Exception as primary_error:
            logger.warning(f"Primary provider failed: {primary_error}")
            fallback_chain.append(provider_model)

            # Try fallback chain
            for fallback in policy.fallback_chain:
                fallback_chain.append(fallback)

                try:
                    response, decision = await self._try_provider(
                        fallback,
                        prompt,
                        system,
                        temperature,
                        max_tokens,
                        task_type,
                        policy,
                    )

                    decision.fallback_attempted = True
                    decision.fallback_chain = fallback_chain
                    decision.latency_ms = (time.perf_counter() - start_time) * 1000

                    self._routing_stats[policy.primary_provider]["fallback_count"] += 1

                    # Log fallback routing decision
                    fallback_provider, fallback_model = self._parse_provider_model(fallback)
                    inference_mode = self._get_inference_mode(fallback_provider)
                    log_route_decision(
                        task_type=task_type.value,
                        provider=fallback_provider,
                        model=fallback_model,
                        inference_mode=inference_mode,
                        latency_ms=decision.latency_ms,
                        fallback_used=True,
                        fallback_chain=fallback_chain,
                    )

                    return response, decision

                except Exception as fallback_error:
                    logger.warning(f"Fallback {fallback} failed: {fallback_error}")
                    continue

        # All providers failed - log error
        latency_ms = (time.perf_counter() - start_time) * 1000
        log_route_decision(
            task_type=task_type.value,
            provider=policy.primary_provider,
            model=policy.primary_model,
            inference_mode=self._get_inference_mode(policy.primary_provider),
            latency_ms=latency_ms,
            fallback_used=True,
            fallback_chain=fallback_chain,
            error=str(primary_error) if "primary_error" in dir() else "All providers failed",
        )
        raise ProviderError(f"All providers failed for task type {task_type.value}")

    async def _try_provider(
        self,
        provider_model: str,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        task_type: TaskType,
        policy: RoutingPolicy,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Try a specific provider."""
        provider_name, model = self._parse_provider_model(provider_model)

        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(provider_name)
        if not circuit_breaker.can_attempt():
            raise ProviderError(f"Circuit breaker open for {provider_name}")

        provider = self.get_provider(provider_name)
        if not provider:
            raise ProviderError(f"Provider {provider_name} not found")

        # Update provider config for this request
        if hasattr(provider, "config"):
            original_model = provider.config.default_model
            provider.config.default_model = model

        try:
            response = await provider.generate(
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Record success
            circuit_breaker.record_success()
            self._update_stats(provider_name, True, response.latency_ms)

            decision = RoutingDecision(
                provider=provider_name,
                model=model,
                task_type=task_type,
                policy=policy,
            )

            return response, decision

        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            self._update_stats(provider_name, False, 0)

            raise

        finally:
            # Restore original model
            if hasattr(provider, "config"):
                provider.config.default_model = original_model

    async def chat(
        self,
        task_type: TaskType,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """
        Route chat request with fallback.

        Args:
            task_type: Type of task
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Max tokens

        Returns:
            Tuple of (LLMResponse, RoutingDecision)
        """
        policy = self.get_policy(task_type)
        start_time = time.perf_counter()

        # Try primary provider first
        provider_model = f"{policy.primary_provider}:{policy.primary_model}"
        fallback_chain = []

        try:
            response, decision = await self._try_chat_provider(
                provider_model,
                messages,
                temperature,
                max_tokens,
                task_type,
                policy,
            )

            decision.latency_ms = (time.perf_counter() - start_time) * 1000
            return response, decision

        except Exception as primary_error:
            logger.warning(f"Primary provider failed: {primary_error}")
            fallback_chain.append(provider_model)

            # Try fallback chain
            for fallback in policy.fallback_chain:
                fallback_chain.append(fallback)

                try:
                    response, decision = await self._try_chat_provider(
                        fallback,
                        messages,
                        temperature,
                        max_tokens,
                        task_type,
                    )

                    decision.fallback_attempted = True
                    decision.fallback_chain = fallback_chain
                    decision.latency_ms = (time.perf_counter() - start_time) * 1000

                    self._routing_stats[policy.primary_provider]["fallback_count"] += 1

                    return response, decision

                except Exception as fallback_error:
                    logger.warning(f"Fallback {fallback} failed: {fallback_error}")
                    continue

        raise ProviderError(f"All providers failed for task type {task_type.value}")

    async def _try_chat_provider(
        self,
        provider_model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        task_type: TaskType,
        policy: RoutingPolicy,
    ) -> tuple[LLMResponse, RoutingDecision]:
        """Try chat with specific provider."""
        provider_name, model = self._parse_provider_model(provider_model)

        circuit_breaker = self._get_circuit_breaker(provider_name)
        if not circuit_breaker.can_attempt():
            raise ProviderError(f"Circuit breaker open for {provider_name}")

        provider = self.get_provider(provider_name)
        if not provider:
            raise ProviderError(f"Provider {provider_name} not found")

        original_model = None
        if hasattr(provider, "config"):
            original_model = provider.config.default_model
            provider.config.default_model = model

        try:
            response = await provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            circuit_breaker.record_success()
            self._update_stats(provider_name, True, response.latency_ms)

            decision = RoutingDecision(
                provider=provider_name,
                model=model,
                task_type=task_type,
                policy=policy,
            )

            return response, decision

        except Exception as e:
            circuit_breaker.record_failure()
            self._update_stats(provider_name, False, 0)
            raise

        finally:
            if original_model and hasattr(provider, "config"):
                provider.config.default_model = original_model

    async def stream(
        self,
        task_type: TaskType,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[tuple[StreamingChunk, RoutingDecision], None]:
        """Stream with routing and fallback."""
        policy = self.get_policy(task_type)
        provider_model = f"{policy.primary_provider}:{policy.primary_model}"

        try:
            provider = self.get_provider(policy.primary_provider)
            if not provider:
                raise ProviderError(f"Provider {policy.primary_provider} not found")

            async for chunk in provider.stream(messages, temperature, max_tokens):
                decision = RoutingDecision(
                    provider=policy.primary_provider,
                    model=policy.primary_model,
                    task_type=task_type,
                    policy=policy,
                )
                yield chunk, decision

        except Exception as e:
            logger.warning(f"Primary streaming failed, trying fallback: {e}")

            for fallback in policy.fallback_chain:
                try:
                    provider = self.get_provider(self._parse_provider_model(fallback)[0])
                    if not provider:
                        continue

                    async for chunk in provider.stream(messages, temperature, max_tokens):
                        provider_name, model = self._parse_provider_model(fallback)
                        decision = RoutingDecision(
                            provider=provider_name,
                            model=model,
                            task_type=task_type,
                            policy=policy,
                            fallback_attempted=True,
                        )
                        yield chunk, decision

                    break

                except Exception as fallback_error:
                    logger.warning(f"Fallback streaming failed: {fallback_error}")
                    continue

    def _update_stats(self, provider_name: str, success: bool, latency_ms: float) -> None:
        """Update routing statistics."""
        stats = self._routing_stats[provider_name]
        stats["total_requests"] += 1

        if success:
            stats["successful_requests"] += 1
            stats["total_latency_ms"] += latency_ms
        else:
            stats["failed_requests"] += 1

    def get_routing_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get routing statistics."""
        return dict(self._routing_stats)

    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get circuit breaker status for all providers."""
        return {
            name: {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "last_failure_time": cb.last_failure_time.isoformat()
                if cb.last_failure_time
                else None,
            }
            for name, cb in self._circuit_breakers.items()
        }

    def reset_circuit_breaker(self, provider_name: str) -> None:
        """Reset circuit breaker for a provider."""
        if provider_name in self._circuit_breakers:
            self._circuit_breakers[provider_name] = CircuitBreakerState(provider_name=provider_name)
            logger.info(f"Circuit breaker reset for {provider_name}")


# Global router instance
_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create global model router."""
    global _router

    if _router is None:
        _router = ModelRouter()

        # Register default providers
        _router.register_provider(OllamaProvider())

    return _router


def initialize_router(
    enable_cloud: bool = False,
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
    google_key: Optional[str] = None,
) -> ModelRouter:
    """
    Initialize model router with providers.

    Args:
        enable_cloud: Whether to enable cloud providers
        openai_key: OpenAI API key
        anthropic_key: Anthropic API key
        google_key: Google API key

    Returns:
        Configured ModelRouter
    """
    router = get_model_router()

    if enable_cloud:
        if openai_key:
            config = ProviderConfig(
                provider_type=ProviderType.OPENAI,
                name="openai",
                api_key=openai_key,
            )
            router.register_provider(OpenAIProvider(config))

        if anthropic_key:
            config = ProviderConfig(
                provider_type=ProviderType.ANTHROPIC,
                name="anthropic",
                api_key=anthropic_key,
            )
            router.register_provider(AnthropicProvider(config))

        if google_key:
            config = ProviderConfig(
                provider_type=ProviderType.GOOGLE,
                name="google",
                api_key=google_key,
            )
            router.register_provider(GoogleProvider(config))

    return router
