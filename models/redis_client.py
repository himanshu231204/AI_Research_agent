"""
Redis Client for Research OS.

Async Redis client for:
- Session cache
- Memory storage
- Queue management
- Pub/sub
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from api.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Async Redis client wrapper.

    Provides:
    - Connection pooling
    - Automatic reconnection
    - JSON serialization
    - Convenience methods
    """

    _instance: Optional["RedisClient"] = None
    _redis: Optional[Redis] = None

    def __init__(self):
        """Initialize Redis client."""
        self.settings = get_settings()
        self._connected = False

    @classmethod
    async def get_redis(cls) -> Redis:
        """
        Get or create Redis connection.

        Returns:
            Redis connection
        """
        if cls._redis is None or not cls._redis.connection:
            settings = get_settings()

            cls._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
            )

            # Test connection
            try:
                await cls._redis.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                raise

        return cls._redis

    @classmethod
    async def close(cls) -> None:
        """Close Redis connection."""
        if cls._redis:
            await cls._redis.close()
            cls._redis = None
            logger.info("Redis connection closed")

    @classmethod
    async def health_check(cls) -> bool:
        """Check Redis health."""
        try:
            redis = await cls.get_redis()
            await redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Convenience functions
async def get_redis() -> Redis:
    """Get Redis connection."""
    return await RedisClient.get_redis()


async def close_redis() -> None:
    """Close Redis connection."""
    await RedisClient.close()
