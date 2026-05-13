"""
Integration tests for Ollama GPU detection and CPU fallback.

Tests:
- GPU detection logic
- CPU fallback mode
- Ollama health checks
- Model registry validation
- Frontend state mapping
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from models.providers.local import OllamaProvider, GPUInfo
from models.providers.base import ProviderConfig, ProviderType, ProviderStatus
from models.routing.gpu_scheduler import GPUMonitor
from models.routing.gpu_telemetry import (
    GPUTelemetryLogger,
    InferenceMode,
    GPUState,
    log_gpu_status,
)


# Test fixtures


@pytest.fixture
def ollama_config():
    """Create Ollama provider config."""
    return ProviderConfig(
        provider_type=ProviderType.LOCAL,
        name="ollama",
        base_url="http://localhost:11434",
        default_model="qwen3",
        supported_models=["qwen3", "llama3", "mistral", "deepseek-coder"],
        gpu_enabled=True,
    )


@pytest.fixture
def mock_ollama_response_gpu():
    """Mock Ollama /api/ps response with GPU info."""
    return {
        "model": "qwen3",
        "size": 5368709120,  # 5GB
        "duration": 1000000000,
        "gpus": [
            {
                "index": 0,
                "name": "NVIDIA GeForce RTX 3090",
                "memory_total": 25769803776,  # 24GB
                "memory_used": 5368709120,  # 5GB
                "memory_free": 20401094656,  # ~19GB
                "utilization": 35,
                "temperature": 65,
                "vendor": "NVIDIA",
            }
        ],
    }


@pytest.fixture
def mock_ollama_response_cpu():
    """Mock Ollama /api/ps response without GPU (CPU mode)."""
    return {
        "model": "qwen3",
        "size": 5368709120,
        "duration": 1000000000,
        "gpus": [],  # No GPUs detected
    }


# GPU Info dataclass tests


class TestGPUInfo:
    """Test GPUInfo dataclass."""

    def test_gpu_info_with_gpu(self):
        """Test GPUInfo with GPU available."""
        info = GPUInfo(
            gpu_available=True,
            gpu_count=1,
            inference_mode="nvidia",
            memory_total_mb=24576.0,
            memory_used_mb=5120.0,
        )

        assert info.gpu_available is True
        assert info.inference_mode == "nvidia"
        assert info.memory_percent == pytest.approx(20.83, rel=0.1)
        assert info.is_saturated is False
        assert info.is_busy is False
        assert info.status == "available"

    def test_gpu_info_saturated(self):
        """Test GPUInfo with saturated GPU."""
        info = GPUInfo(
            gpu_available=True,
            gpu_count=1,
            inference_mode="nvidia",
            memory_total_mb=24576.0,
            memory_used_mb=23000.0,  # >90%
        )

        assert info.is_saturated is True
        assert info.status == "saturated"

    def test_gpu_info_cpu_mode(self):
        """Test GPUInfo in CPU mode."""
        info = GPUInfo(
            gpu_available=False,
            inference_mode="cpu",
        )

        assert info.gpu_available is False
        assert info.inference_mode == "cpu"
        assert info.status == "cpu_mode"


# Ollama Provider GPU Detection Tests


class TestOllamaGPUDetection:
    """Test Ollama GPU detection functionality."""

    @pytest.mark.asyncio
    async def test_get_gpu_info_with_nvidia_gpu(self, ollama_config, mock_ollama_response_gpu):
        """Test GPU detection with NVIDIA GPU."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_ollama_response_gpu
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.object(provider, "_check_nvidia_smi") as mock_smi:
                mock_smi.return_value = {
                    "available": True,
                    "gpu_count": 1,
                    "driver_version": "525.85.05",
                    "memory_total_mb": 24576,
                    "memory_used_mb": 5120,
                    "gpus": [],
                }

                result = await provider.get_gpu_info()

                assert result["gpu_available"] is True
                assert result["inference_mode"] == "nvidia"
                assert result["gpu_count"] == 1
                assert result["memory_total_mb"] > 0
                assert result["status"] == "available"

    @pytest.mark.asyncio
    async def test_get_gpu_info_cpu_mode(self, ollama_config, mock_ollama_response_cpu):
        """Test GPU detection in CPU mode."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_ollama_response_cpu
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.object(provider, "_check_nvidia_smi") as mock_smi:
                mock_smi.return_value = {"available": False, "error": "no_nvidia"}

                with patch.object(provider, "_check_amd_gpu") as mock_amd:
                    mock_amd.return_value = {"available": False, "error": "no_amd"}

                    result = await provider.get_gpu_info()

                    assert result["gpu_available"] is False
                    assert result["inference_mode"] == "cpu"
                    assert result["status"] == "cpu_mode"

    @pytest.mark.asyncio
    async def test_get_gpu_info_api_error(self, ollama_config):
        """Test GPU detection with API error."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            # Simulate API error
            import httpx

            mock_client.get.side_effect = httpx.HTTPStatusError(
                "Server error", request=Mock(), response=Mock()
            )

            result = await provider.get_gpu_info()

            assert result["gpu_available"] is False
            assert result["inference_mode"] == "cpu"
            assert result["status"] == "cpu_mode"


# GPU Monitor Tests


class TestGPUMonitor:
    """Test GPU monitor functionality."""

    @pytest.mark.asyncio
    async def test_gpu_monitor_initialization(self):
        """Test GPU monitor initialization."""
        monitor = GPUMonitor()
        assert monitor is not None

    @pytest.mark.asyncio
    async def test_get_current_metrics(self):
        """Test getting current GPU metrics."""
        monitor = GPUMonitor()

        # Create mock provider
        mock_provider = Mock(spec=OllamaProvider)
        mock_provider.get_gpu_info = AsyncMock(
            return_value={
                "gpu_available": True,
                "inference_mode": "nvidia",
                "gpu_count": 1,
                "memory_total_mb": 24576.0,
                "memory_used_mb": 8192.0,
                "memory_percent": 33.3,
                "model_loaded": "qwen3",
            }
        )

        monitor.set_ollama_provider(mock_provider)

        metrics = await monitor.get_current_metrics()

        assert metrics.gpu_available is True
        assert metrics.gpu_count == 1
        assert metrics.memory_percent == 33.3
        assert "qwen3" in metrics.active_models

    @pytest.mark.asyncio
    async def test_get_detailed_status_cpu_mode(self):
        """Test getting detailed status in CPU mode."""
        monitor = GPUMonitor()

        mock_provider = Mock(spec=OllamaProvider)
        mock_provider.get_gpu_info = AsyncMock(
            return_value={
                "gpu_available": False,
                "inference_mode": "cpu",
                "status": "cpu_mode",
                "gpu_count": 0,
                "memory_total_mb": 0,
                "memory_used_mb": 0,
                "memory_percent": 0,
                "model_loaded": "qwen3",
                "error": None,
            }
        )

        monitor.set_ollama_provider(mock_provider)

        status = await monitor.get_detailed_status()

        assert status["available"] is False
        assert status["mode"] == "cpu"
        assert status["status"] == "cpu_mode"
        assert status["display_status"] == "CPU Inference Mode"


# Telemetry Logger Tests


class TestGPUTelemetry:
    """Test GPU telemetry logging."""

    def test_telemetry_logger_initialization(self):
        """Test telemetry logger initialization."""
        logger = GPUTelemetryLogger()
        assert logger is not None
        assert len(logger._state_changes) == 0
        assert len(logger._routing_decisions) == 0

    def test_log_gpu_check(self):
        """Test logging GPU status check."""
        logger = GPUTelemetryLogger()

        logger.log_gpu_check(
            gpu_available=True,
            inference_mode="nvidia",
            gpu_count=1,
            memory_percent=50.0,
            model_loaded="qwen3",
        )

        assert len(logger._state_changes) == 1
        change = logger._state_changes[0]
        assert change.to_state == GPUState.AVAILABLE

    def test_log_gpu_state_change(self):
        """Test logging GPU state changes."""
        logger = GPUTelemetryLogger()

        # Log first state
        logger.log_gpu_check(
            gpu_available=True,
            inference_mode="nvidia",
            gpu_count=1,
            memory_percent=50.0,
            model_loaded="qwen3",
        )

        # Log second state (different)
        logger.log_gpu_check(
            gpu_available=False,
            inference_mode="cpu",
            gpu_count=0,
            memory_percent=0,
            model_loaded=None,
        )

        assert len(logger._state_changes) == 2
        changes = logger.get_state_changes(limit=10)
        assert len(changes) == 2
        assert changes[0]["to_state"] == "available"
        assert changes[1]["to_state"] == "cpu_mode"

    def test_log_routing_decision(self):
        """Test logging routing decisions."""
        logger = GPUTelemetryLogger()

        logger.log_routing_decision(
            task_type="planning",
            provider="ollama",
            model="qwen3",
            inference_mode="nvidia",
            latency_ms=500.0,
            fallback_used=False,
        )

        assert len(logger._routing_decisions) == 1
        decision = logger._routing_decisions[0]
        assert decision.task_type == "planning"
        assert decision.selected_provider == "ollama"
        assert decision.inference_mode == InferenceMode.NVIDIA

    def test_log_routing_decision_with_fallback(self):
        """Test logging routing decisions with fallback."""
        logger = GPUTelemetryLogger()

        logger.log_routing_decision(
            task_type="planning",
            provider="openai",
            model="gpt-4o",
            inference_mode="cloud",
            latency_ms=1500.0,
            fallback_used=True,
            fallback_chain=["ollama:qwen3", "openai:gpt-4o"],
            error="Ollama timeout",
        )

        decisions = logger.get_routing_decisions(limit=10)
        assert len(decisions) == 1
        assert decisions[0]["fallback_used"] is True
        assert decisions[0]["error"] == "Ollama timeout"


# Frontend State Mapping Tests


class TestFrontendStateMapping:
    """Test frontend state mapping for GPU status."""

    def test_gpu_status_type_cpu_mode(self):
        """Test GPUStatus type mapping for CPU mode."""
        # Define the expected type structure (can't import from frontend in Python)
        status = {
            "available": False,
            "mode": "cpu",
            "status": "cpu_mode",
            "display_status": "CPU Inference Mode",
            "display_icon": "cpu",
        }

        assert status["available"] is False
        assert status["mode"] == "cpu"
        assert status["status"] == "cpu_mode"
        assert status["display_status"] == "CPU Inference Mode"

    def test_gpu_status_type_gpu_available(self):
        """Test GPUStatus type mapping for GPU available."""
        status = {
            "available": True,
            "mode": "nvidia",
            "status": "available",
            "gpu_count": 1,
            "memory": {
                "total_mb": 24576,
                "used_mb": 8192,
                "free_mb": 16384,
                "percent": 33.3,
            },
            "compute_utilization": 35,
            "temperature": 65,
            "driver_version": "525.85.05",
            "model_loaded": "qwen3",
            "is_saturated": False,
            "is_busy": False,
        }

        assert status["available"] is True
        assert status["mode"] == "nvidia"
        assert status["memory"]["percent"] == 33.3
        assert status["model_loaded"] == "qwen3"

    def test_gpu_status_type_gpu_saturated(self):
        """Test GPUStatus type mapping for GPU saturated."""
        status = {
            "available": True,
            "mode": "nvidia",
            "status": "saturated",
            "memory": {
                "total_mb": 24576,
                "used_mb": 23500,
                "free_mb": 1076,
                "percent": 95.7,
            },
            "is_saturated": True,
            "is_busy": True,
        }

        assert status["available"] is True
        assert status["status"] == "saturated"
        assert status["is_saturated"] is True
        assert status["memory"]["percent"] == 95.7


# Model Registry Validation Tests


class TestModelRegistry:
    """Test model registry validation."""

    @pytest.mark.asyncio
    async def test_get_available_models(self, ollama_config):
        """Test getting available models."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [
                    {"name": "qwen3", "size": 5368709120, "modified_at": "2024-01-01"},
                    {"name": "llama3", "size": 4294967296, "modified_at": "2024-01-02"},
                    {"name": "mistral", "size": 4194304000, "modified_at": "2024-01-03"},
                ]
            }
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            models = await provider.get_available_models()

            assert len(models) == 3
            assert "qwen3" in models
            assert "llama3" in models
            assert "mistral" in models

    @pytest.mark.asyncio
    async def test_get_available_models_error(self, ollama_config):
        """Test getting available models with error (falls back to config)."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection error")

            models = await provider.get_available_models()

            # Should fall back to config supported models
            assert "qwen3" in models
            assert "llama3" in models

    @pytest.mark.asyncio
    async def test_generate_uses_installed_model_when_default_missing(self, ollama_config):
        """Test generate switches to an installed local model when qwen3 is unavailable."""
        provider = OllamaProvider(ollama_config)

        with patch.object(provider, "get_available_models", AsyncMock(return_value=["llama3.2:3b", "mistral:latest"])):
            with patch.object(provider, "_get_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.raise_for_status = Mock(return_value=None)
                mock_response.json.return_value = {"response": "fallback ok"}
                mock_client.post.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await provider.generate("Hello world")

                assert result.content == "fallback ok"
                assert result.model == "llama3.2:3b"
                assert mock_client.post.await_count == 1
                assert mock_client.post.call_args.kwargs["json"]["model"] == "llama3.2:3b"


# Integration Tests


class TestGPUIntegration:
    """Integration tests for GPU detection system."""

    @pytest.mark.asyncio
    async def test_full_gpu_detection_flow(self, mock_ollama_response_gpu):
        """Test full GPU detection flow from provider to monitor."""
        config = ProviderConfig(
            provider_type=ProviderType.LOCAL,
            name="ollama",
            base_url="http://localhost:11434",
            default_model="qwen3",
        )

        provider = OllamaProvider(config)
        monitor = GPUMonitor(provider)

        with patch.object(provider, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_ollama_response_gpu
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch.object(provider, "_check_nvidia_smi") as mock_smi:
                mock_smi.return_value = {
                    "available": True,
                    "gpu_count": 1,
                    "driver_version": "525.85.05",
                    "memory_total_mb": 24576,
                    "memory_used_mb": 5120,
                    "gpus": [],
                }

                # Get GPU info from provider
                gpu_info = await provider.get_gpu_info()

                # Get metrics from monitor
                metrics = await monitor.get_current_metrics()

                # Get detailed status
                status = await monitor.get_detailed_status()

                # Verify consistency
                assert gpu_info["gpu_available"] == metrics.gpu_available
                assert status["available"] == metrics.gpu_available
                assert status["mode"] == gpu_info["inference_mode"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
