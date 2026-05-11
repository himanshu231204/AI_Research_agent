"""
Unit tests for health endpoints.
"""

from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.routes.health import health_check, liveness, readiness, check_services


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(create_app())

    def test_get_health_returns_200(self):
        """Test that GET /health returns 200 status code."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "0.1.0"
            mock_settings.return_value.environment = "testing"

            mock_check.return_value = {
                "redis": MagicMock(status="healthy", latency_ms=1.0),
                "postgres": MagicMock(status="healthy", latency_ms=1.0),
                "ollama": MagicMock(status="unhealthy", error="Connection refused"),
            }

            response = self.client.get("/health")

            assert response.status_code == 200

    def test_health_response_structure(self):
        """Test that health response has correct structure."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "1.0.0"
            mock_settings.return_value.environment = "development"

            mock_check.return_value = {
                "redis": MagicMock(status="healthy", latency_ms=1.5),
                "postgres": MagicMock(status="healthy", latency_ms=2.0),
                "ollama": MagicMock(status="unhealthy", error="Timeout"),
            }

            response = self.client.get("/health")
            data = response.json()

            # Check required fields
            assert "status" in data
            assert "timestamp" in data
            assert "version" in data
            assert "environment" in data
            assert "services" in data

            # Check types
            assert isinstance(data["status"], str)
            assert isinstance(data["timestamp"], str)
            assert isinstance(data["version"], str)
            assert isinstance(data["environment"], str)
            assert isinstance(data["services"], dict)

    def test_health_status_healthy(self):
        """Test health status is 'healthy' when all services are up."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "1.0.0"
            mock_settings.return_value.environment = "production"

            mock_check.return_value = {
                "redis": MagicMock(status="healthy"),
                "postgres": MagicMock(status="healthy"),
                "ollama": MagicMock(status="healthy"),
            }

            response = self.client.get("/health")
            data = response.json()

            assert data["status"] == "healthy"

    def test_health_status_degraded(self):
        """Test health status is 'degraded' when some services are down."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "1.0.0"
            mock_settings.return_value.environment = "production"

            mock_check.return_value = {
                "redis": MagicMock(status="healthy"),
                "postgres": MagicMock(status="unhealthy", error="Connection refused"),
                "ollama": MagicMock(status="healthy"),
            }

            response = self.client.get("/health")
            data = response.json()

            assert data["status"] == "degraded"

    def test_health_status_unhealthy(self):
        """Test health status is 'unhealthy' when all services are down."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "1.0.0"
            mock_settings.return_value.environment = "production"

            mock_check.return_value = {
                "redis": MagicMock(status="unhealthy", error="Connection refused"),
                "postgres": MagicMock(status="unhealthy", error="Connection refused"),
                "ollama": MagicMock(status="unhealthy", error="Connection refused"),
            }

            response = self.client.get("/health")
            data = response.json()

            assert data["status"] == "unhealthy"

    def test_liveness_endpoint(self):
        """Test liveness probe endpoint."""
        response = self.client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    def test_readiness_endpoint(self):
        """Test readiness probe endpoint."""
        with patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = {
                "redis": MagicMock(status="healthy"),
                "postgres": MagicMock(status="healthy"),
                "ollama": MagicMock(status="healthy"),
            }

            response = self.client.get("/health/ready")

            assert response.status_code == 200
            data = response.json()
            assert "ready" in data
            assert "services" in data


class TestWebSocketRoute:
    """Test suite for WebSocket route existence."""

    def test_websocket_route_exists(self):
        """Test that WebSocket route is registered in the app."""
        app = create_app()

        # Check that websocket router is included
        routes = [route.path for route in app.routes]
        websocket_routes = [r for r in routes if "websocket" in r.lower()]

        # Should have at least one websocket route
        assert len(websocket_routes) > 0 or any("/ws" in r for r in routes)


class TestHealthCheckFunction:
    """Test suite for health check function directly."""

    @pytest.mark.asyncio
    async def test_health_check_returns_health_response(self):
        """Test health_check function returns correct model."""
        with (
            patch("api.routes.health.get_settings") as mock_settings,
            patch("api.routes.health.check_services", new_callable=AsyncMock) as mock_check,
        ):
            mock_settings.return_value.app_version = "0.1.0"
            mock_settings.return_value.environment = "test"

            mock_check.return_value = {
                "redis": MagicMock(status="healthy", latency_ms=1.0),
                "postgres": MagicMock(status="healthy", latency_ms=1.0),
                "ollama": MagicMock(status="healthy", latency_ms=1.0),
            }

            result = await health_check()

            assert result.status == "healthy"
            assert result.version == "0.1.0"
            assert result.environment == "test"
            assert "redis" in result.services
            assert "postgres" in result.services
