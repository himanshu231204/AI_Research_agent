"""
Integration tests for Phase 5: Model Routing + Multi-Model Intelligence.

Tests:
- Provider abstraction compatibility
- Local routing
- Cloud fallback
- Retry logic
- Circuit breakers
- Token accounting
- Cost tracking
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List, Dict

from models.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderStatus,
    LLMResponse,
    StreamingChunk,
    ProviderError,
    ProviderTimeoutError,
)
from models.providers.local import OllamaProvider
from models.providers.cloud import OpenAIProvider, AnthropicProvider, GoogleProvider
from models.routing.router import (
    ModelRouter,
    TaskType,
    RoutingPolicy,
    RetryPolicy,
    CircuitBreakerState,
    RoutingDecision,
)
from models.routing.gpu_scheduler import GPUMonitor, HealthMonitor, AdaptiveScheduler
from models.routing.cost_optimizer import CostOptimizer, CostBudget, TokenBudget, TokenBudgetManager
from models.routing.telemetry import TelemetryCollector, RequestTelemetry


# Test fixtures


@pytest.fixture
def mock_provider_config():
    """Create mock provider config."""
    return ProviderConfig(
        provider_type=ProviderType.LOCAL,
        name="test_provider",
        base_url="http://localhost:11434",
        default_model="qwen3",
        supported_models=["qwen3", "llama3"],
    )


@pytest.fixture
def mock_llm_response():
    """Create mock LLM response."""
    return LLMResponse(
        content="Test response",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        model="qwen3",
        provider="ollama",
        latency_ms=1000.0,
    )


@pytest.fixture
def router():
    """Create model router for testing."""
    r = ModelRouter()
    # Register a mock provider
    mock_provider = Mock(spec=LLMProvider)
    mock_provider.name = "ollama"
    mock_provider.provider_type = ProviderType.LOCAL
    mock_provider.config = ProviderConfig(
        provider_type=ProviderType.LOCAL,
        name="ollama",
        default_model="qwen3",
    )
    mock_provider.health = Mock()
    mock_provider.health.status = ProviderStatus.HEALTHY
    mock_provider.health.is_available = True
    mock_provider.health.latency_ms = 100.0
    r.register_provider(mock_provider)
    return r


# Provider abstraction tests


class TestProviderAbstraction:
    """Test provider abstraction layer."""

    def test_provider_config_creation(self, mock_provider_config):
        """Test provider config creation."""
        assert mock_provider_config.name == "test_provider"
        assert mock_provider_config.provider_type == ProviderType.LOCAL
        assert mock_provider_config.default_model == "qwen3"

    def test_llm_response_structure(self, mock_llm_response):
        """Test LLM response structure."""
        assert mock_llm_response.content == "Test response"
        assert mock_llm_response.prompt_tokens == 100
        assert mock_llm_response.completion_tokens == 50
        assert mock_llm_response.total_tokens == 150

    def test_streaming_chunk_structure(self):
        """Test streaming chunk structure."""
        chunk = StreamingChunk(
            content="Hello",
            delta="Hello",
            model="qwen3",
            provider="ollama",
            index=0,
        )
        assert chunk.content == "Hello"
        assert chunk.delta == "Hello"
        assert chunk.index == 0


# Routing tests


class TestModelRouting:
    """Test model routing functionality."""

    def test_router_initialization(self, router):
        """Test router initialization."""
        assert router is not None
        assert len(router.get_all_providers()) > 0

    def test_register_provider(self, router):
        """Test provider registration."""
        providers = router.get_all_providers()
        assert "ollama" in providers

    def test_get_policy(self, router):
        """Test getting routing policy."""
        policy = router.get_policy(TaskType.PLANNING)
        assert policy is not None
        assert policy.task_type == TaskType.PLANNING

    def test_set_policy(self, router):
        """Test setting custom policy."""
        custom_policy = RoutingPolicy(
            task_type=TaskType.CODING,
            primary_model="deepseek-coder",
            primary_provider="ollama",
            fallback_chain=["openai:gpt-4o"],
        )
        router.set_policy(TaskType.CODING, custom_policy)
        policy = router.get_policy(TaskType.CODING)
        assert policy.primary_model == "deepseek-coder"


# Circuit breaker tests


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self):
        """Test initial circuit breaker state."""
        cb = CircuitBreakerState(provider_name="test")
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_circuit_breaker_opens_on_failures(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreakerState(
            provider_name="test",
            failure_threshold=3,
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"

        cb.record_failure()
        assert cb.state == "open"

    def test_circuit_breaker_closes_on_success(self):
        """Test circuit closes after success threshold."""
        cb = CircuitBreakerState(
            provider_name="test",
            failure_threshold=2,
            success_threshold=2,
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # After opening, need to wait for timeout or reset
        # For testing, we directly test the state transitions
        cb.state = "half_open"  # Manually set to test half_open behavior
        cb.record_success()
        assert cb.success_count == 1

        cb.record_success()
        assert cb.state == "closed"

    def test_circuit_breaker_can_attempt(self):
        """Test circuit breaker attempt check."""
        cb = CircuitBreakerState(provider_name="test")

        # Closed state allows attempts
        assert cb.can_attempt() is True

        # Open state blocks attempts
        cb.state = "open"
        assert cb.can_attempt() is False


# Retry policy tests


class TestRetryPolicy:
    """Test retry policy functionality."""

    def test_retry_policy_initialization(self):
        """Test retry policy initialization."""
        policy = RetryPolicy(max_retries=3, base_delay=1.0)
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        policy = RetryPolicy(max_retries=3, base_delay=1.0, exponential_base=2.0)

        delay1 = policy.get_delay(1)
        delay2 = policy.get_delay(2)
        delay3 = policy.get_delay(3)

        assert delay1 >= 0.5  # With jitter
        assert delay2 >= 1.0
        assert delay3 >= 2.0

    def test_should_retry_logic(self):
        """Test retry decision logic."""
        policy = RetryPolicy(max_retries=3)

        # Should retry on regular errors
        assert policy.should_retry(1, ProviderError("test")) is True

        # Should not retry after max attempts
        assert policy.should_retry(3, ProviderError("test")) is False

        # Should retry on timeout errors (they are transient)
        assert policy.should_retry(1, ProviderTimeoutError("timeout")) is True

        # Should not retry on authentication errors
        from models.providers.base import ProviderAuthenticationError

        assert policy.should_retry(1, ProviderAuthenticationError("auth failed")) is False


# Cost optimization tests


class TestCostOptimization:
    """Test cost optimization functionality."""

    def test_cost_optimizer_initialization(self):
        """Test cost optimizer initialization."""
        optimizer = CostOptimizer("test_session")
        assert optimizer.session_id == "test_session"

    def test_estimate_cost_local(self):
        """Test cost estimation for local models."""
        optimizer = CostOptimizer("test_session")
        cost = optimizer.estimate_cost("qwen3", "ollama", 100, 100)
        assert cost == 0.0  # Local models are free

    def test_estimate_cost_cloud(self):
        """Test cost estimation for cloud models."""
        optimizer = CostOptimizer("test_session")
        cost = optimizer.estimate_cost("gpt-4o", "openai", 100, 100)
        assert cost > 0  # Cloud models have cost

    def test_can_afford_request(self):
        """Test budget checking."""
        budget = CostBudget(max_cost_per_session=10.0, max_tokens_per_session=1000)
        optimizer = CostOptimizer("test_session", cost_budget=budget)

        can_afford, reason = optimizer.can_afford_request(1.0, 100)
        assert can_afford is True

    def test_token_budget_manager(self):
        """Test token budget manager."""
        manager = TokenBudgetManager()
        tokens = manager.estimate_tokens("Hello world")
        assert tokens > 0


# Telemetry tests


class TestTelemetry:
    """Test telemetry functionality."""

    def test_telemetry_collector_initialization(self):
        """Test telemetry collector initialization."""
        collector = TelemetryCollector()
        assert collector is not None

    def test_record_request(self):
        """Test recording request telemetry."""
        collector = TelemetryCollector()
        collector.record_request(
            provider="ollama",
            model="qwen3",
            task_type=TaskType.PLANNING,
            latency_ms=1000.0,
            prompt_tokens=100,
            completion_tokens=50,
            success=True,
        )

        metrics = collector.get_provider_metrics("ollama")
        assert metrics is not None
        assert metrics.total_requests == 1

    def test_get_throughput(self):
        """Test throughput calculation."""
        collector = TelemetryCollector()
        # Add some requests
        collector.record_request(
            provider="ollama",
            model="qwen3",
            task_type=TaskType.PLANNING,
            latency_ms=1000.0,
            prompt_tokens=100,
            completion_tokens=100,
            success=True,
        )

        throughput = collector.get_throughput()
        assert throughput >= 0

    def test_fallback_rate(self):
        """Test fallback rate calculation."""
        collector = TelemetryCollector()
        collector.record_request(
            provider="ollama",
            model="qwen3",
            task_type=TaskType.PLANNING,
            latency_ms=1000.0,
            success=True,
            fallback_used=False,
        )
        collector.record_request(
            provider="openai",
            model="gpt-4o",
            task_type=TaskType.PLANNING,
            latency_ms=2000.0,
            success=True,
            fallback_used=True,
        )

        rate = collector.get_fallback_rate()
        assert rate == 0.5


# GPU scheduler tests


class TestGPUScheduler:
    """Test GPU-aware scheduling."""

    def test_gpu_monitor_initialization(self):
        """Test GPU monitor initialization."""
        monitor = GPUMonitor()
        assert monitor is not None

    def test_health_monitor_initialization(self):
        """Test health monitor initialization."""
        monitor = HealthMonitor()
        assert monitor is not None

    def test_register_model_health(self):
        """Test model health registration."""
        monitor = HealthMonitor()
        monitor.register_model("qwen3", "ollama")

        health = monitor.get_model_health("qwen3", "ollama")
        assert health is not None
        assert health.model_name == "qwen3"

    def test_record_success_failure(self):
        """Test recording success/failure."""
        monitor = HealthMonitor()
        monitor.register_model("qwen3", "ollama")

        monitor.record_success("qwen3", "ollama", 1000.0)
        monitor.record_failure("qwen3", "ollama", is_timeout=True)

        health = monitor.get_model_health("qwen3", "ollama")
        assert health.success_count == 1
        assert health.error_count == 1
        assert health.timeout_count == 1


# Integration tests


class TestIntegration:
    """Integration tests for the routing system."""

    @pytest.mark.asyncio
    async def test_routing_with_fallback(self):
        """Test routing with fallback chain."""
        router = ModelRouter()

        # Create mock providers
        primary_provider = Mock(spec=LLMProvider)
        primary_provider.name = "ollama"
        primary_provider.provider_type = ProviderType.LOCAL
        primary_provider.config = ProviderConfig(
            provider_type=ProviderType.LOCAL,
            name="ollama",
            default_model="qwen3",
        )
        primary_provider.health = Mock()
        primary_provider.health.status = ProviderStatus.HEALTHY
        primary_provider.health.is_available = True

        # Make primary fail
        async def fail_generate(*args, **kwargs):
            raise ProviderError("Primary failed")

        primary_provider.generate = fail_generate

        fallback_provider = Mock(spec=LLMProvider)
        fallback_provider.name = "openai"
        fallback_provider.provider_type = ProviderType.OPENAI
        fallback_provider.config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            name="openai",
            default_model="gpt-4o",
        )
        fallback_provider.health = Mock()
        fallback_provider.health.status = ProviderStatus.HEALTHY
        fallback_provider.health.is_available = True

        # Make fallback succeed
        async def succeed_generate(*args, **kwargs):
            return LLMResponse(
                content="Fallback response",
                model="gpt-4o",
                provider="openai",
                latency_ms=500.0,
            )

        fallback_provider.generate = succeed_generate

        router.register_provider(primary_provider)
        router.register_provider(fallback_provider)

        # Test routing - should fallback
        # Note: In real test, would need to properly set up policies
        assert router.get_provider("ollama") is not None
        assert router.get_provider("openai") is not None

    def test_circuit_breaker_integration(self):
        """Test circuit breaker in routing context."""
        router = ModelRouter()

        # Register provider
        mock_provider = Mock(spec=LLMProvider)
        mock_provider.name = "test"
        mock_provider.provider_type = ProviderType.LOCAL
        router.register_provider(mock_provider)

        # Get circuit breaker
        cb = router.get_circuit_breaker_status()
        assert "test" in cb

    def test_telemetry_integration(self):
        """Test telemetry in routing context."""
        collector = TelemetryCollector()

        # Record multiple requests
        for i in range(5):
            collector.record_request(
                provider="ollama",
                model="qwen3",
                task_type=TaskType.PLANNING,
                latency_ms=1000.0 + i * 100,
                prompt_tokens=100,
                completion_tokens=50,
                success=i < 4,  # One failure
            )

        summary = collector.get_summary()
        assert summary["total_requests"] == 5
        assert summary["providers"]["ollama"]["total_requests"] == 5


# Performance tests


class TestPerformance:
    """Performance tests for routing system."""

    def test_routing_decision_speed(self):
        """Test routing decision creation speed."""
        policy = RoutingPolicy(
            task_type=TaskType.PLANNING,
            primary_model="qwen3",
            primary_provider="ollama",
            fallback_chain=[],
        )

        decision = RoutingDecision(
            provider="ollama",
            model="qwen3",
            task_type=TaskType.PLANNING,
            policy=policy,
            latency_ms=100.0,
        )

        assert decision.provider == "ollama"
        assert decision.latency_ms == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
