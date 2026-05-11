"""
Redis reliability layer for Research OS.

This module provides:
- Connection pooling
- Health checks
- Reconnect logic
- Retry resilience
- Redis monitoring hooks
- Queue inspection utilities
"""

import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import redis.exceptions as redis_exceptions

from api.config import get_settings

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class RedisConnectionPool:
    """
    Redis connection pool manager with reliability features.

    Features:
    - Connection pooling
    - Automatic reconnection
    - Health monitoring
    - Connection validation
    """

    def __init__(
        self,
        max_connections: int = 20,
        min_connections: int = 5,
        socket_keepalive: bool = True,
        socket_keepalive_options: Optional[Dict[int, int]] = None,
        health_check_interval: int = 30,  # seconds
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ):
        """
        Initialize Redis connection pool.

        Args:
            max_connections: Maximum connections in pool
            min_connections: Minimum connections to maintain
            socket_keepalive: Enable TCP keepalive
            socket_keepalive_options: TCP keepalive options
            health_check_interval: Interval for health checks
            reconnect_delay: Initial reconnect delay
            max_reconnect_delay: Maximum reconnect delay
        """
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.health_check_interval = health_check_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        self._pool: Optional[aioredis.ConnectionPool] = None
        self._client: Optional[aioredis.Redis] = None
        self._connected = False
        self._last_health_check: Optional[datetime] = None
        self._health_check_task: Optional[asyncio.Task] = None

        # Connection options
        self._connection_kwargs = {
            "socket_keepalive": socket_keepalive,
            "socket_keepalive_options": socket_keepalive_options,
            "retry_on_timeout": True,
            "decode_responses": True,
        }

    async def initialize(self) -> None:
        """
        Initialize the connection pool.

        Creates the pool and establishes connections.
        """
        try:
            # Build Redis URL
            redis_url = settings.redis_url

            # Create connection pool
            self._pool = aioredis.ConnectionPool.from_url(
                redis_url,
                max_connections=self.max_connections,
                **self._connection_kwargs,
            )

            # Create client
            self._client = aioredis.Redis(connection_pool=self._pool)

            # Test connection
            await self._client.ping()

            self._connected = True
            logger.info(
                f"Redis connection pool initialized: {self.max_connections} max connections"
            )

            # Start health check background task
            self._start_health_check()

        except Exception as e:
            logger.error(f"Failed to initialize Redis connection pool: {e}")
            self._connected = False
            raise

    async def close(self) -> None:
        """Close the connection pool and all connections."""
        self._connected = False

        # Stop health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close pool
        if self._pool:
            await self._pool.disconnect()
            self._pool = None

        self._client = None
        logger.info("Redis connection pool closed")

    async def _start_health_check(self) -> None:
        """Start background health check task."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._connected:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Redis connection.

        Returns:
            Health status dictionary
        """
        if not self._client:
            return {
                "status": "disconnected",
                "connected": False,
            }

        try:
            start = datetime.utcnow()
            await self._client.ping()
            latency = (datetime.utcnow() - start).total_seconds()

            self._last_health_check = datetime.utcnow()

            # Get additional info
            info = await self._client.info()
            db_info = info.get("db", {})

            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": latency * 1000,
                "last_check": self._last_health_check.isoformat(),
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "db_keys": db_info,
            }

        except redis_exceptions.ConnectionError as e:
            logger.warning(f"Redis connection failed: {e}")
            self._connected = False
            return {
                "status": "disconnected",
                "connected": False,
                "error": str(e),
            }

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "error",
                "connected": self._connected,
                "error": str(e),
            }

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to Redis.

        Returns:
            True if reconnection successful
        """
        delay = self.reconnect_delay

        for attempt in range(10):
            try:
                logger.info(f"Attempting Redis reconnection (attempt {attempt + 1})")

                if self._client:
                    await self._client.ping()

                self._connected = True
                logger.info("Redis reconnection successful")
                return True

            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")

                # Exponential backoff
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.max_reconnect_delay)

        logger.error("Redis reconnection failed after 10 attempts")
        return False

    @property
    def client(self) -> aioredis.Redis:
        """Get Redis client."""
        if not self._client:
            raise RuntimeError("Redis connection pool not initialized")
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        if not self._pool:
            return {"status": "not_initialized"}

        return {
            "max_connections": self.max_connections,
            "current_connections": self._pool.max_connections,
            "connected": self._connected,
            "last_health_check": self._last_health_check.isoformat()
            if self._last_health_check
            else None,
        }


class RedisCache:
    """
    Redis-based cache with automatic retry and expiration.
    """

    def __init__(self, pool: RedisConnectionPool, default_ttl: int = 3600):
        """
        Initialize Redis cache.

        Args:
            pool: Redis connection pool
            default_ttl: Default time-to-live in seconds
        """
        self._pool = pool
        self.default_ttl = default_ttl

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            client = self._pool.client
            value = await client.get(key)
            return value
        except Exception as e:
            logger.error(f"Cache get failed for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful
        """
        try:
            client = self._pool.client
            ttl = ttl or self.default_ttl
            await client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Cache set failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            client = self._pool.client
            await client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete failed for {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            client = self._pool.client
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists check failed for {key}: {e}")
            return False


class RedisQueueMonitor:
    """
    Monitor Redis queues and Celery tasks.
    """

    def __init__(self, pool: RedisConnectionPool):
        """
        Initialize queue monitor.

        Args:
            pool: Redis connection pool
        """
        self._pool = pool

    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """
        Get information about a specific queue.

        Args:
            queue_name: Name of the queue

        Returns:
            Queue information
        """
        try:
            client = self._pool.client

            # Get queue length
            queue_key = f"celery.{queue_name}.size"
            size = await client.get(queue_key)

            # Get pending tasks
            pending_key = f"celery.{queue_name}.pending"
            pending = await client.zcard(pending_key) if await client.exists(pending_key) else 0

            return {
                "queue": queue_name,
                "size": int(size) if size else 0,
                "pending": pending,
                "status": "active" if self._pool.is_connected else "inactive",
            }

        except Exception as e:
            logger.error(f"Failed to get queue info for {queue_name}: {e}")
            return {
                "queue": queue_name,
                "error": str(e),
            }

    async def get_all_queues(self) -> List[Dict[str, Any]]:
        """Get information about all queues."""
        from workers.queues import get_all_queue_names

        queues = []
        for queue_name in get_all_queue_names():
            info = await self.get_queue_info(queue_name)
            queues.append(info)

        return queues

    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Get all keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "celery:*")

        Returns:
            List of matching keys
        """
        try:
            client = self._pool.client
            keys = await client.keys(pattern)
            return keys
        except Exception as e:
            logger.error(f"Failed to get keys by pattern {pattern}: {e}")
            return []


class RedisDistributedLock:
    """
    Distributed lock implementation using Redis.
    """

    def __init__(self, pool: RedisConnectionPool, lock_name: str, timeout: int = 30):
        """
        Initialize distributed lock.

        Args:
            pool: Redis connection pool
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
        """
        self._pool = pool
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self._locked = False

    async def acquire(self, blocking: bool = True, blocking_timeout: int = 10) -> bool:
        """
        Acquire the lock.

        Args:
            blocking: Whether to block until lock is acquired
            blocking_timeout: Maximum time to wait

        Returns:
            True if lock acquired
        """
        import uuid

        lock_value = str(uuid.uuid4())
        client = self._pool.client

        if not blocking:
            result = await client.set(
                self.lock_name,
                lock_value,
                nx=True,
                ex=self.timeout,
            )
            self._locked = result is not None
            return self._locked

        # Blocking acquire with retry
        start = datetime.utcnow()
        while (datetime.utcnow() - start).total_seconds() < blocking_timeout:
            result = await client.set(
                self.lock_name,
                lock_value,
                nx=True,
                ex=self.timeout,
            )

            if result:
                self._locked = True
                return True

            await asyncio.sleep(0.1)

        return False

    async def release(self) -> bool:
        """Release the lock."""
        if not self._locked:
            return False

        try:
            client = self._pool.client
            await client.delete(self.lock_name)
            self._locked = False
            return True
        except Exception as e:
            logger.error(f"Failed to release lock {self.lock_name}: {e}")
            return False


@asynccontextmanager
async def redis_connection():
    """
    Context manager for Redis connection.

    Usage:
        async with redis_connection() as client:
            await client.get("key")
    """
    pool = RedisConnectionPool()
    await pool.initialize()

    try:
        yield pool.client
    finally:
        await pool.close()


# Global connection pool instance
_global_pool: Optional[RedisConnectionPool] = None


async def get_redis_pool() -> RedisConnectionPool:
    """
    Get the global Redis connection pool.

    Returns:
        Redis connection pool
    """
    global _global_pool

    if _global_pool is None:
        _global_pool = RedisConnectionPool()
        await _global_pool.initialize()

    return _global_pool


async def close_redis_pool() -> None:
    """Close the global Redis connection pool."""
    global _global_pool

    if _global_pool:
        await _global_pool.close()
        _global_pool = None


# Utility functions


async def get_redis_info() -> Dict[str, Any]:
    """
    Get Redis server information.

    Returns:
        Redis server info
    """
    pool = await get_redis_pool()
    client = pool.client

    try:
        info = await client.info()
        return {
            "version": info.get("redis_version"),
            "mode": info.get("redis_mode"),
            "uptime": info.get("uptime_in_days"),
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "status": "connected" if pool.is_connected else "disconnected",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def clear_redis_keys(pattern: str) -> int:
    """
    Clear all keys matching a pattern.

    Args:
        pattern: Key pattern

    Returns:
        Number of keys deleted
    """
    pool = await get_redis_pool()
    client = pool.client

    try:
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0
    except Exception as e:
        logger.error(f"Failed to clear keys with pattern {pattern}: {e}")
        return 0
