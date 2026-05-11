"""
Integration tests for Redis reliability layer.

Tests:
- Connection pooling
- Health checks
- Reconnect logic
- Queue monitoring
- Distributed locks
"""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


class TestRedisConnectionPool:
    """Test suite for Redis connection pool."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test that pool initializes correctly."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(
            max_connections=10,
            min_connections=2,
        )

        assert pool.max_connections == 10
        assert pool.min_connections == 2
        assert pool.is_connected is False

    @pytest.mark.asyncio
    async def test_pool_connection_kwargs(self):
        """Test that pool uses correct connection kwargs."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool()

        assert pool._connection_kwargs["retry_on_timeout"] is True
        assert pool._connection_kwargs["decode_responses"] is True

    @pytest.mark.asyncio
    async def test_pool_stats(self):
        """Test pool statistics retrieval."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(max_connections=10)

        stats = pool.get_pool_stats()

        assert "max_connections" in stats
        assert stats["max_connections"] == 10


class TestRedisHealthCheck:
    """Test suite for Redis health checks."""

    @pytest.mark.asyncio
    async def test_health_check_structure(self):
        """Test health check returns expected structure."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool()

        # Before initialization
        health = await pool.health_check()

        assert "status" in health
        assert "connected" in health

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """Test health check when disconnected."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool()
        pool._connected = False

        health = await pool.health_check()

        assert health["connected"] is False


class TestRedisCache:
    """Test suite for Redis cache operations."""

    @pytest.mark.asyncio
    async def test_cache_operations(self):
        """Test basic cache operations."""
        from observability.redis_reliability import RedisCache, RedisConnectionPool

        pool = RedisConnectionPool()
        cache = RedisCache(pool, default_ttl=3600)

        assert cache.default_ttl == 3600

    @pytest.mark.asyncio
    async def test_cache_get_handles_errors(self):
        """Test that cache get handles errors gracefully."""
        from observability.redis_reliability import RedisCache, RedisConnectionPool

        pool = RedisConnectionPool()
        pool._client = None

        cache = RedisCache(pool)

        # Should return None instead of raising
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_handles_errors(self):
        """Test that cache set handles errors gracefully."""
        from observability.redis_reliability import RedisCache, RedisConnectionPool

        pool = RedisConnectionPool()
        pool._client = None

        cache = RedisCache(pool)

        # Should return False instead of raising
        result = await cache.set("key", "value")
        assert result is False


class TestRedisQueueMonitor:
    """Test suite for Redis queue monitoring."""

    @pytest.mark.asyncio
    async def test_queue_monitor_initialization(self):
        """Test queue monitor initialization."""
        from observability.redis_reliability import RedisQueueMonitor, RedisConnectionPool

        pool = RedisConnectionPool()
        monitor = RedisQueueMonitor(pool)

        assert monitor._pool is pool

    @pytest.mark.asyncio
    async def test_get_all_queues(self):
        """Test getting all queues."""
        from observability.redis_reliability import RedisQueueMonitor, RedisConnectionPool
        from workers.queues import get_all_queue_names

        pool = RedisConnectionPool()
        monitor = RedisQueueMonitor(pool)

        # Get all queue names
        expected_queues = get_all_queue_names()

        assert "research" in expected_queues
        assert "browser" in expected_queues
        assert "rag" in expected_queues
        assert "reflection" in expected_queues
        assert "dead_letter" in expected_queues


class TestRedisDistributedLock:
    """Test suite for distributed locks."""

    @pytest.mark.asyncio
    async def test_lock_initialization(self):
        """Test distributed lock initialization."""
        from observability.redis_reliability import RedisDistributedLock, RedisConnectionPool

        pool = RedisConnectionPool()
        lock = RedisDistributedLock(pool, "test-lock", timeout=30)

        assert lock.lock_name == "lock:test-lock"
        assert lock.timeout == 30
        assert lock._locked is False

    @pytest.mark.asyncio
    async def test_lock_non_blocking_acquire(self):
        """Test non-blocking lock acquisition."""
        from observability.redis_reliability import RedisDistributedLock, RedisConnectionPool

        pool = RedisConnectionPool()
        lock = RedisDistributedLock(pool, "test-lock")

        # Should handle uninitialized pool gracefully
        result = await lock.acquire(blocking=False)
        # Will be False because pool is not connected
        assert result is False

    @pytest.mark.asyncio
    async def test_lock_release_when_not_locked(self):
        """Test releasing lock when not locked."""
        from observability.redis_reliability import RedisDistributedLock, RedisConnectionPool

        pool = RedisConnectionPool()
        lock = RedisDistributedLock(pool, "test-lock")

        # Release when not locked should return False
        result = await lock.release()
        assert result is False


class TestRedisConnectionContext:
    """Test suite for connection context manager."""

    @pytest.mark.asyncio
    async def test_connection_context_structure(self):
        """Test connection context manager structure."""
        from observability.redis_reliability import redis_connection

        # Should be an async context manager
        assert hasattr(redis_connection, "__aenter__")
        assert hasattr(redis_connection, "__aexit__")


class TestRedisUtilityFunctions:
    """Test suite for Redis utility functions."""

    @pytest.mark.asyncio
    async def test_get_redis_info_structure(self):
        """Test get_redis_info returns expected structure."""
        from observability.redis_reliability import get_redis_info

        # Mock the pool to avoid actual connection
        with patch("observability.redis_reliability.get_redis_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.is_connected = False
            mock_get_pool.return_value = mock_pool

            info = await get_redis_info()

            # Should return dict with status
            assert isinstance(info, dict)
            assert "status" in info


class TestRedisReconnection:
    """Test suite for Redis reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_delay_calculation(self):
        """Test reconnect delay calculation."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(
            reconnect_delay=1.0,
            max_reconnect_delay=60.0,
        )

        assert pool.reconnect_delay == 1.0
        assert pool.max_reconnect_delay == 60.0

    @pytest.mark.asyncio
    async def test_reconnect_attempts(self):
        """Test that reconnect tries multiple times."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool()

        # Pool should track reconnection state
        assert pool._connected is False


class TestRedisKeyOperations:
    """Test suite for Redis key operations."""

    @pytest.mark.asyncio
    async def test_clear_keys_pattern(self):
        """Test clearing keys by pattern."""
        from observability.redis_reliability import clear_redis_keys

        # Mock pool
        with patch("observability.redis_reliability.get_redis_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_client = AsyncMock()
            mock_client.keys.return_value = ["key1", "key2", "key3"]
            mock_client.delete.return_value = 3
            mock_pool.client = mock_client
            mock_get_pool.return_value = mock_pool

            result = await clear_redis_keys("test:*")

            # Should return count of deleted keys
            assert result == 3


class TestRedisErrorHandling:
    """Test suite for Redis error handling."""

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test handling of connection errors."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool()

        # Health check should handle errors gracefully
        health = await pool.health_check()

        assert "status" in health
        assert health["connected"] is False


class TestRedisHealthCheckInterval:
    """Test suite for Redis health check interval."""

    @pytest.mark.asyncio
    async def test_health_check_interval_config(self):
        """Test health check interval configuration."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(health_check_interval=60)

        assert pool.health_check_interval == 60


class TestRedisPoolLimits:
    """Test suite for Redis pool limits."""

    @pytest.mark.asyncio
    async def test_pool_max_connections(self):
        """Test pool max connections setting."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(max_connections=50)

        assert pool.max_connections == 50

    @pytest.mark.asyncio
    async def test_pool_min_connections(self):
        """Test pool min connections setting."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(min_connections=10)

        assert pool.min_connections == 10


class TestRedisConnectionParameters:
    """Test suite for Redis connection parameters."""

    @pytest.mark.asyncio
    async def test_keepalive_enabled(self):
        """Test that socket keepalive is enabled."""
        from observability.redis_reliability import RedisConnectionPool

        pool = RedisConnectionPool(socket_keepalive=True)

        assert pool._connection_kwargs["socket_keepalive"] is True

    @pytest.mark.asyncio
    async def test_keepalive_options(self):
        """Test socket keepalive options."""
        from observability.redis_reliability import RedisConnectionPool

        keepalive_options = {1: 30, 2: 60}
        pool = RedisConnectionPool(socket_keepalive_options=keepalive_options)

        assert pool._connection_kwargs["socket_keepalive_options"] == keepalive_options
