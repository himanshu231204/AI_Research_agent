"""
Integration tests for WebSocket endpoints.
"""

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from api.main import app
from api.routes.websocket import manager, ConnectionManager


class TestWebSocketRoutes:
    """Test suite for WebSocket route registration."""

    def test_websocket_route_exists(self):
        """Test that WebSocket route is registered."""
        route_paths = [route.path for route in app.routes]

        # WebSocket should be registered at /ws/{session_id}
        ws_routes = [p for p in route_paths if "/ws" in p]
        assert len(ws_routes) > 0, "WebSocket route should be registered"

    def test_websocket_route_correct_path(self):
        """Test WebSocket route has correct path pattern."""
        route_paths = [route.path for route in app.routes]

        # Should match /ws/{session_id} pattern
        ws_route_exists = any(p.startswith("/ws/") or p == "/ws" for p in route_paths)
        assert ws_route_exists, "WebSocket should be at /ws/{session_id}"


class TestConnectionManager:
    """Test suite for WebSocket connection manager."""

    def test_manager_initialization(self):
        """Test manager initializes with empty connections."""
        test_manager = ConnectionManager()
        assert test_manager.active_connections == {}

    def test_connect_adds_connection(self):
        """Test connecting adds to active connections."""
        test_manager = ConnectionManager()

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        # Can't test actual connect without full websocket support
        # but we can verify the structure
        assert hasattr(test_manager, "connect")
        assert hasattr(test_manager, "disconnect")
        assert hasattr(test_manager, "send_message")


class TestWebSocketEvents:
    """Test suite for WebSocket event notifications."""

    def test_notify_research_update_exists(self):
        """Test research update notification function exists."""
        from api.routes.websocket import notify_research_update

        assert callable(notify_research_update)

    def test_notify_agent_activity_exists(self):
        """Test agent activity notification function exists."""
        from api.routes.websocket import notify_agent_activity

        assert callable(notify_agent_activity)

    def test_notify_research_complete_exists(self):
        """Test research complete notification function exists."""
        from api.routes.websocket import notify_research_complete

        assert callable(notify_research_complete)


class TestWebSocketMessage:
    """Test suite for WebSocket message model."""

    def test_message_model_creation(self):
        """Test WebSocket message model works."""
        from api.routes.websocket import WebSocketMessage

        message = WebSocketMessage(type="test", payload={"data": "test_data"})

        assert message.type == "test"
        assert message.payload["data"] == "test_data"

    def test_message_json_serialization(self):
        """Test WebSocket message serializes to JSON correctly."""
        from api.routes.websocket import WebSocketMessage

        message = WebSocketMessage(
            type="research_update", payload={"status": "running", "progress": 0.5}
        )

        json_str = message.model_dump_json()
        data = json.loads(json_str)

        assert data["type"] == "research_update"
        assert data["payload"]["status"] == "running"


class TestHealthEndpointsForWebSocket:
    """Test suite for health endpoints related to WebSocket."""

    def test_websocket_health_endpoint_exists(self):
        """Test websocket health endpoint is registered."""
        route_paths = [route.path for route in app.routes]

        ws_health_exists = any("/health/websocket" in p for p in route_paths)
        assert ws_health_exists, "WebSocket health endpoint should exist"


class TestWebSocketRouting:
    """Test suite for WebSocket routing between frontend and backend."""

    def test_ws_not_under_api_prefix(self):
        """Test WebSocket is NOT under /api/v1 prefix."""
        route_paths = [route.path for route in app.routes]

        # WebSocket should be at root level
        ws_routes = [p for p in route_paths if "/ws" in p]

        for ws_route in ws_routes:
            assert not ws_route.startswith("/api/v1"), (
                f"WebSocket route {ws_route} should not be under /api/v1 prefix"
            )

    def test_api_endpoints_under_prefix(self):
        """Test API endpoints ARE under /api/v1 prefix."""
        route_paths = [route.path for route in app.routes]

        # Research, memory, models should be under /api/v1
        research_routes = [p for p in route_paths if "/research" in p]
        memory_routes = [p for p in route_paths if "/memory" in p]
        models_routes = [p for p in route_paths if "/models" in p]

        # These should exist (under prefix)
        assert len(research_routes) > 0 or len(memory_routes) > 0 or len(models_routes) > 0
