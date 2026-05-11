"""
Unit tests for configuration loading.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from api.config import Settings, get_settings


class TestSettings:
    """Test suite for Settings class."""

    def test_settings_loads_from_env_vars(self):
        """Test that Settings loads values from environment variables."""
        with patch.dict(
            os.environ,
            {
                "APP_NAME": "Test Research OS",
                "APP_VERSION": "1.0.0",
                "ENVIRONMENT": "production",
                "POSTGRES_HOST": "db.example.com",
                "POSTGRES_PORT": "5433",
                "REDIS_HOST": "redis.example.com",
            },
            clear=False,
        ):
            # Clear cached settings
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.app_name == "Test Research OS"
            assert settings.app_version == "1.0.0"
            assert settings.environment == "production"
            assert settings.postgres_host == "db.example.com"
            assert settings.postgres_port == 5433
            assert settings.redis_host == "redis.example.com"

    def test_defaults_work_when_no_env_vars(self):
        """Test that defaults are applied when no env vars are set."""
        with patch.dict(
            os.environ,
            {},
            clear=False,
        ):
            # Clear cached settings
            get_settings.cache_clear()
            settings = get_settings()

            # Check application defaults
            assert settings.app_name == "Research OS"
            assert settings.app_version == "0.1.0"
            assert settings.environment == "development"

            # Check API defaults
            assert settings.api_host == "0.0.0.0"
            assert settings.api_port == 8000

            # Check database defaults
            assert settings.postgres_host == "localhost"
            assert settings.postgres_port == 5432
            assert settings.postgres_user == "research_os"
            assert settings.postgres_db == "research_os"

            # Check Redis defaults
            assert settings.redis_host == "localhost"
            assert settings.redis_port == 6379
            assert settings.redis_db == 0

    def test_postgres_url_property(self):
        """Test postgres_url property generates correct URL."""
        settings = Settings()
        settings.postgres_host = "localhost"
        settings.postgres_port = 5432
        settings.postgres_user = "testuser"
        settings.postgres_password = "testpass"
        settings.postgres_db = "testdb"

        url = settings.postgres_url

        assert url == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
        assert "localhost" in url
        assert "5432" in url
        assert "testdb" in url

    def test_sync_postgres_url_property(self):
        """Test sync_postgres_url property generates correct URL."""
        settings = Settings()
        settings.postgres_host = "db.example.com"
        settings.postgres_port = 5432
        settings.postgres_user = "admin"
        settings.postgres_password = "secret"
        settings.postgres_db = "production"

        url = settings.sync_postgres_url

        assert url == "postgresql://admin:secret@db.example.com:5432/production"
        assert "postgresql://" in url
        assert "db.example.com" in url

    def test_redis_url_without_password(self):
        """Test redis_url property without password."""
        settings = Settings()
        settings.redis_host = "localhost"
        settings.redis_port = 6379
        settings.redis_password = None
        settings.redis_db = 0

        url = settings.redis_url

        assert url == "redis://localhost:6379/0"
        assert "localhost" in url
        assert "6379" in url

    def test_redis_url_with_password(self):
        """Test redis_url property with password."""
        settings = Settings()
        settings.redis_host = "redis.example.com"
        settings.redis_port = 6380
        settings.redis_password = "secret_password"
        settings.redis_db = 1

        url = settings.redis_url

        assert url == "redis://:secret_password@redis.example.com:6380/1"
        assert "redis.example.com" in url
        assert "6380" in url

    def test_is_production_true(self):
        """Test is_production returns True for production environment."""
        settings = Settings(environment="production")

        assert settings.is_production is True

    def test_is_production_false_for_development(self):
        """Test is_production returns False for development environment."""
        settings = Settings(environment="development")

        assert settings.is_production is False

    def test_is_production_false_for_staging(self):
        """Test is_production returns False for staging environment."""
        settings = Settings(environment="staging")

        assert settings.is_production is False

    def test_is_production_case_insensitive(self):
        """Test is_production handles case insensitively."""
        settings = Settings(environment="PRODUCTION")

        assert settings.is_production is True

    def test_cors_origins_default(self):
        """Test default CORS origins are set."""
        settings = Settings()

        assert isinstance(settings.cors_origins, list)
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://localhost:5173" in settings.cors_origins

    def test_cors_origins_from_env(self):
        """Test CORS origins can be set from environment."""
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "http://example.com,https://app.example.com"},
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert len(settings.cors_origins) == 2
            assert "http://example.com" in settings.cors_origins
            assert "https://app.example.com" in settings.cors_origins

    def test_celery_configuration(self):
        """Test Celery broker and result backend URLs."""
        settings = Settings()

        assert settings.celery_broker_url is not None
        assert settings.celery_result_backend is not None
        assert "redis" in settings.celery_broker_url

    def test_ollama_configuration(self):
        """Test Ollama configuration defaults."""
        settings = Settings()

        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "qwen3"
        assert settings.ollama_timeout == 120

    def test_security_configuration(self):
        """Test security settings are present."""
        settings = Settings()

        assert settings.secret_key is not None
        assert settings.jwt_secret_key is not None
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expiration_minutes == 60

    def test_settings_is_cached(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


class TestSettingsValidation:
    """Test suite for Settings validation."""

    def test_integer_env_vars_parse_correctly(self):
        """Test that integer environment variables are parsed correctly."""
        with patch.dict(
            os.environ,
            {
                "API_PORT": "9000",
                "POSTGRES_PORT": "5433",
                "REDIS_PORT": "6380",
            },
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.api_port == 9000
            assert settings.postgres_port == 5433
            assert settings.redis_port == 6380

    def test_boolean_env_vars_parse_correctly(self):
        """Test that boolean environment variables are parsed correctly."""
        with patch.dict(
            os.environ,
            {"DEBUG": "false", "LANGSMITH_TRACING": "true"},
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

            assert settings.debug is False
            assert settings.langsmith_tracing is True
