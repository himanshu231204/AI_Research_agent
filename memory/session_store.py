"""
Redis-based Session Storage for Research OS.

Provides persistent session storage using Redis to prevent data loss on restart.
"""

import json
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

from redis.asyncio import Redis

from models.redis_client import get_redis

logger = logging.getLogger(__name__)

# Session key prefix
SESSION_PREFIX = "session:"
SESSION_TTL = 3600 * 24 * 7  # 7 days default TTL


class RedisSessionStore:
    """
    Redis-backed session storage.

    Features:
    - Persistent storage (survives restarts)
    - Automatic expiration
    - JSON serialization
    - Connection pooling
    """

    def __init__(self, redis: Optional[Redis] = None, default_ttl: int = SESSION_TTL):
        """
        Initialize Redis session store.

        Args:
            redis: Optional Redis connection (will create if not provided)
            default_ttl: Default time-to-live in seconds (default: 7 days)
        """
        self._redis = redis
        self._default_ttl = default_ttl

    async def _get_redis(self) -> Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{SESSION_PREFIX}{session_id}"

    async def create(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Create a new session.

        Args:
            session_id: Session ID
            data: Session data
            ttl: Optional TTL override

        Returns:
            True if created successfully
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            # Add metadata
            session_data = {
                **data,
                "_created_at": datetime.utcnow().isoformat(),
                "_updated_at": datetime.utcnow().isoformat(),
            }

            await redis.set(
                key,
                json.dumps(session_data),
                ex=ttl or self._default_ttl,
            )

            logger.info(f"Created session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            data = await redis.get(key)
            if data:
                # Extend TTL on access
                await redis.expire(key, self._default_ttl)
                return json.loads(data)

            return None

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def update(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID
            data: Data to update (merges with existing)
            ttl: Optional TTL override

        Returns:
            True if updated successfully
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            # Get existing data
            existing = await self.get(session_id)
            if existing:
                # Merge updates
                existing.update(data)
                existing["_updated_at"] = datetime.utcnow().isoformat()
                session_data = existing
            else:
                # Create new session
                session_data = {
                    **data,
                    "_created_at": datetime.utcnow().isoformat(),
                    "_updated_at": datetime.utcnow().isoformat(),
                }

            await redis.set(
                key,
                json.dumps(session_data),
                ex=ttl or self._default_ttl,
            )

            logger.debug(f"Updated session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted successfully
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            result = await redis.delete(key)
            logger.info(f"Deleted session: {session_id}")
            return result > 0

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def exists(self, session_id: str) -> bool:
        """
        Check if session exists.

        Args:
            session_id: Session ID

        Returns:
            True if session exists
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            return await redis.exists(key) > 0

        except Exception as e:
            logger.error(f"Failed to check session {session_id}: {e}")
            return False

    async def list_sessions(self, pattern: str = f"{SESSION_PREFIX}*") -> List[str]:
        """
        List all session IDs.

        Args:
            pattern: Redis key pattern

        Returns:
            List of session IDs
        """
        try:
            redis = await self._get_redis()

            keys = []
            async for key in redis.scan_iter(match=pattern):
                keys.append(key.replace(SESSION_PREFIX, ""))

            return keys

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []

    async def extend_ttl(self, session_id: str, ttl: int) -> bool:
        """
        Extend session TTL.

        Args:
            session_id: Session ID
            ttl: New TTL in seconds

        Returns:
            True if extended successfully
        """
        try:
            redis = await self._get_redis()
            key = self._session_key(session_id)

            return await redis.expire(key, ttl)

        except Exception as e:
            logger.error(f"Failed to extend TTL for {session_id}: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for session store.

        Returns:
            Health status dictionary
        """
        try:
            redis = await self._get_redis()
            await redis.ping()

            # Count sessions
            session_count = len(await self.list_sessions())

            return {
                "status": "healthy",
                "backend": "redis",
                "session_count": session_count,
            }

        except Exception as e:
            logger.error(f"Session store health check failed: {e}")
            return {
                "status": "unhealthy",
                "backend": "redis",
                "error": str(e),
            }


# Global session store instance
_session_store: Optional[RedisSessionStore] = None


def get_session_store() -> RedisSessionStore:
    """
    Get or create global session store.

    Returns:
        RedisSessionStore instance
    """
    global _session_store

    if _session_store is None:
        _session_store = RedisSessionStore()

    return _session_store


# Convenience functions for session operations


async def create_session(
    session_id: str,
    data: Dict[str, Any],
    ttl: Optional[int] = None,
) -> bool:
    """Create a new session."""
    store = get_session_store()
    return await store.create(session_id, data, ttl)


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session data."""
    store = get_session_store()
    return await store.get(session_id)


async def update_session(
    session_id: str,
    data: Dict[str, Any],
    ttl: Optional[int] = None,
) -> bool:
    """Update session data."""
    store = get_session_store()
    return await store.update(session_id, data, ttl)


async def delete_session(session_id: str) -> bool:
    """Delete a session."""
    store = get_session_store()
    return await store.delete(session_id)


async def session_exists(session_id: str) -> bool:
    """Check if session exists."""
    store = get_session_store()
    return await store.exists(session_id)


async def list_all_sessions() -> List[str]:
    """List all session IDs."""
    store = get_session_store()
    return await store.list_sessions()


async def check_session_health() -> Dict[str, Any]:
    """Check session store health."""
    store = get_session_store()
    return await store.health_check()
