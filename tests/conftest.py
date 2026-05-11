"""
Pytest configuration and shared fixtures for Research OS tests.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest import FixtureRequest

# Mark async tests
mark_asyncio = pytest.mark.asyncio


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    from api.config import Settings

    with patch("api.config.get_settings") as mock_get_settings:
        settings = MagicMock(spec=Settings)
        settings.app_name = "Research OS Test"
        settings.app_version = "0.1.0"
        settings.environment = "testing"
        settings.debug = True
        settings.api_host = "0.0.0.0"
        settings.api_port = 8000
        settings.api_v1_prefix = "/api/v1"
        settings.postgres_host = "localhost"
        settings.postgres_port = 5432
        settings.postgres_user = "test_user"
        settings.postgres_password = "test_password"
        settings.postgres_db = "test_db"
        settings.postgres_url = (
            "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db"
        )
        settings.sync_postgres_url = "postgresql://test_user:test_password@localhost:5432/test_db"
        settings.redis_host = "localhost"
        settings.redis_port = 6379
        settings.redis_password = None
        settings.redis_db = 0
        settings.redis_url = "redis://localhost:6379/0"
        settings.celery_broker_url = "redis://localhost:6379/0"
        settings.celery_result_backend = "redis://localhost:6379/0"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "qwen3"
        settings.is_production = False
        settings.cors_origins = ["http://localhost:3000", "http://localhost:5173"]
        mock_get_settings.return_value = settings
        yield settings


@pytest.fixture
def research_state_factory():
    """Factory fixture for creating test research states."""
    from graphs.state import ResearchState

    def _create_state(
        session_id: str = None,
        query: str = "Test research query",
        reflection_count: int = 0,
        max_reflections: int = 3,
        **kwargs,
    ) -> ResearchState:
        """Create a research state with optional overrides."""
        if session_id is None:
            session_id = str(uuid.uuid4())

        state: ResearchState = {
            "session_id": session_id,
            "query": query,
            "tasks": kwargs.get("tasks", []),
            "active_tasks": kwargs.get("active_tasks", []),
            "completed_tasks": kwargs.get("completed_tasks", []),
            "failed_tasks": kwargs.get("failed_tasks", []),
            "findings": kwargs.get("findings", []),
            "sources": kwargs.get("sources", []),
            "memory_context": kwargs.get("memory_context", {}),
            "reflections": kwargs.get("reflections", []),
            "reflection_count": reflection_count,
            "max_reflections": max_reflections,
            "draft_report": kwargs.get("draft_report", ""),
            "final_report": kwargs.get("final_report", ""),
            "current_agent": kwargs.get("current_agent", ""),
            "next_action": kwargs.get("next_action", "planner"),
            "status": kwargs.get("status", "initiated"),
            "progress": kwargs.get("progress", 0.0),
            "error_state": kwargs.get("error_state", None),
            "requires_human_input": kwargs.get("requires_human_input", False),
            "token_usage": kwargs.get(
                "token_usage",
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            ),
            "metadata": kwargs.get(
                "metadata",
                {"started_at": None, "completed_at": None, "model_used": None},
            ),
        }
        return state

    return _create_state


@pytest.fixture
def temp_session_id() -> str:
    """Generate a temporary session ID for testing."""
    return f"test-session-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mock_redis():
    """Mock Redis connection for tests."""
    mock = MagicMock()
    mock.ping = asyncio.coroutine(lambda: True)
    mock.get = asyncio.coroutine(lambda key: None)
    mock.set = asyncio.coroutine(lambda key, value: True)
    mock.delete = asyncio.coroutine(lambda key: 1)
    mock.close = asyncio.coroutine(lambda: None)
    mock.aclose = asyncio.coroutine(lambda: None)
    return mock


@pytest.fixture
def mock_postgres():
    """Mock PostgreSQL connection for tests."""
    mock = MagicMock()
    mock.fetch = asyncio.coroutine(lambda query, *args: [])
    mock.execute = asyncio.coroutine(lambda query, *args: None)
    mock.close = asyncio.coroutine(lambda: None)
    return mock


@pytest.fixture
def mock_ollama():
    """Mock Ollama client for tests."""
    mock = MagicMock()
    mock.generate = asyncio.coroutine(
        lambda prompt, **kwargs: {"response": "Mock response", "model": "qwen3"}
    )
    return mock


@pytest.fixture
def mock_celery_app():
    """Mock Celery app for tests."""
    mock = MagicMock()
    mock.conf.task_routes = {
        "workers.tasks.research.*": {"queue": "research"},
        "workers.tasks.browser.*": {"queue": "browser"},
    }
    mock.conf.task_serializer = "json"
    mock.conf.broker_url = "redis://localhost:6379/0"
    mock.conf.result_backend = "redis://localhost:6379/0"
    return mock
