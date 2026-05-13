"""
Integration tests for model selection system.

Tests:
- Ollama model discovery
- Provider registry
- Routing selection
- API endpoints
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List

from models.registry import (
    ModelRegistry,
    ModelInfo,
    ProviderStatus,
    RoutingMode,
    ModelType,
)
from models.providers.base import ProviderConfig, ProviderType
from graphs.state import ResearchState, create_initial_state


class TestModelRegistry:
    """Test ModelRegistry functionality."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        return ModelRegistry()

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry):
        """Test registry can be initialized."""
        # Registry should start empty
        assert registry._providers == {}
        assert registry._local_models == []

    @pytest.mark.asyncio
    async def test_refresh_local_models(self, registry):
        """Test dynamic Ollama model discovery."""
        # Mock Ollama provider
        mock_provider = MagicMock()
        mock_provider.get_available_models = AsyncMock(
            return_value=[
                "qwen3",
                "llama3",
                "mistral",
                "deepseek-coder",
                "nomic-embed-text",
            ]
        )
        mock_provider.health.latency_ms = 50.0

        registry._providers["ollama"] = mock_provider

        # Refresh local models
        models = await registry.refresh_local_models()

        # Should discover 5 models
        assert len(models) == 5
        assert all(m.provider == "ollama" for m in models)
        assert all(m.is_local for m in models)

        # Check model types are inferred
        coders = [m for m in models if m.model_type == ModelType.CODING]
        assert len(coders) > 0  # deepseek-coder should be detected

    @pytest.mark.asyncio
    async def test_get_cloud_models(self, registry):
        """Test cloud model retrieval."""
        # Mock cloud providers
        mock_openai = MagicMock()
        mock_openai.config.supported_models = ["gpt-4o", "gpt-4o-mini"]
        mock_openai.is_available = MagicMock(return_value=True)
        mock_openai.health.status.value = "healthy"
        mock_openai.health.latency_ms = 100.0

        mock_anthropic = MagicMock()
        mock_anthropic.config.supported_models = ["claude-sonnet-4-20250514"]
        mock_anthropic.is_available = MagicMock(return_value=True)
        mock_anthropic.health.status.value = "healthy"
        mock_anthropic.health.latency_ms = 150.0

        registry._providers["openai"] = mock_openai
        registry._providers["anthropic"] = mock_anthropic

        # Initialize cloud models
        await registry._initialize_cloud_models()

        # Get cloud models
        cloud = await registry.get_cloud_models()

        assert "openai" in cloud
        assert "anthropic" in cloud
        assert len(cloud["openai"]) == 2
        assert len(cloud["anthropic"]) == 1

    @pytest.mark.asyncio
    async def test_user_selection_storage(self, registry):
        """Test user selection is stored correctly."""
        # Set user selection
        registry.set_user_selection(
            session_id="test-session-123",
            provider="ollama",
            model="qwen3",
            routing_mode="local_only",
        )

        # Get user selection
        selection = registry.get_user_selection("test-session-123")

        assert selection["provider"] == "ollama"
        assert selection["model"] == "qwen3"
        assert selection["routing_mode"] == "local_only"

    @pytest.mark.asyncio
    async def test_model_selection_api(self, registry):
        """Test model selection API."""
        # Mock providers
        mock_provider = MagicMock()
        mock_provider.get_available_models = AsyncMock(return_value=["qwen3"])
        registry._providers["ollama"] = mock_provider

        # Select model
        result = await registry.select_model(
            session_id="test-session",
            provider="ollama",
            model="qwen3",
            routing_mode="local_only",
        )

        assert result["success"] is True
        assert result["provider"] == "ollama"
        assert result["model"] == "qwen3"

    @pytest.mark.asyncio
    async def test_invalid_provider_selection(self, registry):
        """Test selection with invalid provider fails."""
        result = await registry.select_model(
            session_id="test-session",
            provider="invalid_provider",
            model="some-model",
            routing_mode="auto",
        )

        assert result["success"] is False
        assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_resolve_model_auto_mode(self, registry):
        """Test model resolution in auto mode."""
        # Set auto mode
        registry.set_user_selection(
            session_id="test-session",
            provider="auto",
            model="",
            routing_mode="auto",
        )

        # Resolve model
        provider, model = registry.resolve_model("test-session", "general")

        # Should use default routing
        assert provider == "ollama"
        assert model == "qwen3"

    @pytest.mark.asyncio
    async def test_resolve_model_local_only(self, registry):
        """Test model resolution in local_only mode."""
        # Add local models
        registry._local_models = [
            ModelInfo(name="qwen3", provider="ollama", is_local=True),
        ]

        registry.set_user_selection(
            session_id="test-session",
            provider="auto",
            model="",
            routing_mode="local_only",
        )

        provider, model = registry.resolve_model("test-session", "general")

        assert provider == "ollama"
        assert model == "qwen3"

    @pytest.mark.asyncio
    async def test_get_provider_status(self, registry):
        """Test provider status retrieval."""
        # Mock Ollama
        mock_ollama = MagicMock()
        mock_ollama.health_check = AsyncMock(return_value=True)
        mock_ollama.health.latency_ms = 50.0
        registry._providers["ollama"] = mock_ollama

        # Get status
        statuses = await registry.get_provider_status()

        assert len(statuses) >= 1
        ollama_status = next(s for s in statuses if s.name == "ollama")
        assert ollama_status.available is True
        assert ollama_status.status == "healthy"


class TestResearchStateModelSelection:
    """Test ResearchState with model selection fields."""

    def test_create_initial_state_with_model_selection(self):
        """Test initial state includes model selection fields."""
        state = create_initial_state(
            session_id="test-123",
            query="Test query",
            selected_provider="ollama",
            selected_model="qwen3",
            routing_mode="hybrid",
        )

        assert state["selected_provider"] == "ollama"
        assert state["selected_model"] == "qwen3"
        assert state["routing_mode"] == "hybrid"
        assert state["active_provider"] == ""
        assert state["active_model"] == ""
        assert state["fallback_occurred"] is False

    def test_create_initial_state_defaults(self):
        """Test default model selection values."""
        state = create_initial_state(
            session_id="test-123",
            query="Test query",
        )

        assert state["selected_provider"] == "auto"
        assert state["selected_model"] == ""
        assert state["routing_mode"] == "auto"


class TestRoutingModeEnum:
    """Test RoutingMode enum values."""

    def test_routing_modes(self):
        """Test all routing modes are defined."""
        assert RoutingMode.AUTO.value == "auto"
        assert RoutingMode.LOCAL_ONLY.value == "local_only"
        assert RoutingMode.CLOUD_ONLY.value == "cloud_only"
        assert RoutingMode.HYBRID.value == "hybrid"


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_display_name(self):
        """Test display name formatting."""
        model = ModelInfo(
            name="deepseek-coder",
            provider="ollama",
            is_local=True,
        )

        assert model.display_name == "Deepseek Coder"

    def test_icon_local(self):
        """Test icon for local model."""
        model = ModelInfo(
            name="qwen3",
            provider="ollama",
            is_local=True,
        )

        assert model.icon == "🖥️"

    def test_icon_cloud(self):
        """Test icon for cloud model."""
        model = ModelInfo(
            name="gpt-4o",
            provider="openai",
            is_local=False,
        )

        assert model.icon == "☁️"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
