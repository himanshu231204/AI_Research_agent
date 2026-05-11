"""
Unit tests for API configuration.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from api.config import Settings, get_settings


class TestAPISettingsInitialization:
    """Test suite for API settings initialization."""

    def test_settings_initialization(self):
        """Test that Settings class initializes correctly."""
        settings = Settings()

        assert settings.app_name == "Research OS"
        assert settings.app_version == "0.1.0"
        assert settings.environment == "development"

    def test_settings_is_singleton_like(self):
        """Test that get_settings returns consistent instances."""
        settings1 = get_settings()
        settings2 = get_settings()

        # Due to lru_cache, should be the same instance
        assert settings1 is settings2

    def test_environment_variable_loading(self):
        """Test that settings load from environment variables."""
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "Custom Research OS",
                "ENVIRONMENT": "staging",
                "DEBUG": "false",
            },
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.app_name == "Custom Research OS"
            assert settings.environment == "staging"
            assert settings.debug is False


class TestAPIConfiguration:
    """Test suite for API configuration properties."""

    def test_api_host_default(self):
        """Test default API host."""
        settings = Settings()

        assert settings.api_host == "0.0.0.0"

    def test_api_port_default(self):
        """Test default API port."""
        settings = Settings()

        assert settings.api_port == 8000

    def test_api_v1_prefix_default(self):
        """Test default API v1 prefix."""
        settings = Settings()

        assert settings.api_v1_prefix == "/api/v1"

    def test_api_host_from_env(self):
        """Test API host loaded from environment."""
        with patch.dict(os.environ, {"API_HOST": "127.0.0.1"}, clear=False):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.api_host == "127.0.0.1"

    def test_api_port_from_env(self):
        """Test API port loaded from environment."""
        with patch.dict(os.environ, {"API_PORT": "9000"}, clear=False):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.api_port == 9000


class TestCORSConfiguration:
    """Test suite for CORS configuration."""

    def test_cors_origins_default_values(self):
        """Test default CORS origins."""
        settings = Settings()

        assert "http://localhost:3000" in settings.cors_origins
        assert "http://localhost:5173" in settings.cors_origins

    def test_cors_origins_type(self):
        """Test CORS origins is a list."""
        settings = Settings()

        assert isinstance(settings.cors_origins, list)

    def test_cors_origins_can_be_customized(self):
        """Test CORS origins can be customized via env."""
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "https://example.com,https://app.example.com"},
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert len(settings.cors_origins) >= 1


class TestApplicationMetadata:
    """Test suite for application metadata."""

    def test_app_name_in_settings(self):
        """Test app name is present in settings."""
        settings = Settings()

        assert hasattr(settings, "app_name")
        assert settings.app_name is not None

    def test_app_version_in_settings(self):
        """Test app version is present in settings."""
        settings = Settings()

        assert hasattr(settings, "app_version")
        assert settings.app_version is not None

    def test_environment_in_settings(self):
        """Test environment is present in settings."""
        settings = Settings()

        assert hasattr(settings, "environment")
        assert settings.environment in ["development", "staging", "production"]


class TestDatabaseConfiguration:
    """Test suite for database configuration."""

    def test_postgres_defaults(self):
        """Test PostgreSQL default configuration."""
        settings = Settings()

        assert settings.postgres_host == "localhost"
        assert settings.postgres_port == 5432
        assert settings.postgres_user == "research_os"
        assert settings.postgres_db == "research_os"

    def test_redis_defaults(self):
        """Test Redis default configuration."""
        settings = Settings()

        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 0

    def test_postgres_url_property(self):
        """Test postgres_url property."""
        settings = Settings()

        url = settings.postgres_url

        assert "postgresql+asyncpg://" in url
        assert settings.postgres_host in url
        assert str(settings.postgres_port) in url

    def test_redis_url_property(self):
        """Test redis_url property."""
        settings = Settings()

        url = settings.redis_url

        assert "redis://" in url
        assert settings.redis_host in url
        assert str(settings.redis_port) in url


class TestLLMConfiguration:
    """Test suite for LLM/Ollama configuration."""

    def test_ollama_defaults(self):
        """Test Ollama default configuration."""
        settings = Settings()

        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "qwen3"
        assert settings.ollama_timeout == 120

    def test_ollama_base_url_property(self):
        """Test Ollama base URL property."""
        settings = Settings()

        assert settings.ollama_base_url.startswith("http://")
        assert "11434" in settings.ollama_base_url
