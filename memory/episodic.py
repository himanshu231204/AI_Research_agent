"""
Episodic Memory System for Research OS.

Stores:
- Sessions
- Workflows
- Past reports
- User interactions

Uses Redis for fast access and PostgreSQL for persistence.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory.base import (
    MemoryBase,
    MemoryConfig,
    MemoryEntry,
    MemoryType,
)
from models.redis_client import get_redis

logger = logging.getLogger(__name__)


class EpisodicMemory(MemoryBase[MemoryEntry]):
    """
    Episodic memory for storing session history.

    Uses Redis for fast session access and caching.
    Uses PostgreSQL for long-term persistence.
    """

    # Redis key prefixes
    SESSION_KEY = "memory:episodic:session:{session_id}"
    USER_SESSIONS_KEY = "memory:episodic:user:{user_id}:sessions"
    GLOBAL_INDEX_KEY = "memory:episodic:index"

    def __init__(self, config: MemoryConfig):
        """
        Initialize episodic memory.

        Args:
            config: Memory configuration
        """
        super().__init__(config)
        self._redis = None

    async def _get_redis(self):
        """Get Redis client lazily."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    async def store(self, entry: MemoryEntry) -> bool:
        """
        Store an episodic memory entry.

        Args:
            entry: Memory entry to store

        Returns:
            True if stored successfully
        """
        if entry.type != MemoryType.EPISODIC:
            entry.type = MemoryType.EPISODIC

        try:
            redis = await self._get_redis()

            # Store in Redis with session TTL
            session_key = self.SESSION_KEY.format(session_id=entry.session_id or "global")
            entry_data = json.dumps(entry.to_dict())

            await redis.setex(
                session_key,
                self.config.session_ttl,
                entry_data,
            )

            # Index by user if available
            if entry.user_id:
                user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=entry.user_id)
                await redis.sadd(user_sessions_key, entry.id)

            # Global index
            await redis.sadd(self.GLOBAL_INDEX_KEY, entry.id)

            logger.debug(f"Stored episodic memory: {entry.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store episodic memory: {e}")
            return False

    async def retrieve(
        self,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """
        Retrieve episodic memory entries.

        Args:
            query: Text query (not used for episodic, use session_id)
            session_id: Filter by session
            limit: Maximum entries to return
            memory_type: Filter by type

        Returns:
            List of memory entries
        """
        try:
            redis = await self._get_redis()
            entries = []

            if session_id:
                # Get specific session
                session_key = self.SESSION_KEY.format(session_id=session_id)
                entry_data = await redis.get(session_key)

                if entry_data:
                    entry_dict = json.loads(entry_data)
                    entry = MemoryEntry.from_dict(entry_dict)
                    entries.append(entry)

            else:
                # Get from global index
                entry_ids = await redis.srandmember(self.GLOBAL_INDEX_KEY, count=limit)

                for entry_id in entry_ids:
                    # Find entry - in production would use proper key
                    entry_dict = await redis.get(f"memory:episodic:entry:{entry_id}")
                    if entry_dict:
                        entries.append(MemoryEntry.from_dict(json.loads(entry_dict)))

            return entries

        except Exception as e:
            logger.error(f"Failed to retrieve episodic memory: {e}")
            return []

    async def update(self, entry: MemoryEntry) -> bool:
        """
        Update an episodic memory entry.

        Args:
            entry: Updated entry

        Returns:
            True if updated successfully
        """
        entry.updated_at = datetime.utcnow()
        return await self.store(entry)

    async def delete(self, entry_id: str) -> bool:
        """
        Delete an episodic memory entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted successfully
        """
        try:
            redis = await self._get_redis()

            # Remove from global index
            await redis.srem(self.GLOBAL_INDEX_KEY, entry_id)

            # Remove from Redis
            await redis.delete(f"memory:episodic:entry:{entry_id}")

            logger.debug(f"Deleted episodic memory: {entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete episodic memory: {e}")
            return False

    async def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count episodic memory entries."""
        try:
            redis = await self._get_redis()
            return await redis.scard(self.GLOBAL_INDEX_KEY)

        except Exception as e:
            logger.error(f"Failed to count episodic memory: {e}")
            return 0

    async def clear(self, session_id: Optional[str] = None) -> int:
        """
        Clear episodic memory entries.

        Args:
            session_id: Clear entries for specific session

        Returns:
            Number of entries cleared
        """
        try:
            redis = await self._get_redis()
            count = 0

            if session_id:
                session_key = self.SESSION_KEY.format(session_id=session_id)
                count = 1 if await redis.exists(session_key) else 0
                await redis.delete(session_key)

            else:
                # Clear all
                entry_ids = await redis.smembers(self.GLOBAL_INDEX_KEY)
                count = len(entry_ids)

                for entry_id in entry_ids:
                    await redis.delete(f"memory:episodic:entry:{entry_id}")

                await redis.delete(self.GLOBAL_INDEX_KEY)

            logger.info(f"Cleared {count} episodic memory entries")
            return count

        except Exception as e:
            logger.error(f"Failed to clear episodic memory: {e}")
            return 0

    async def health_check(self) -> bool:
        """Check if Redis is available."""
        try:
            redis = await self._get_redis()
            await redis.ping()
            return True

        except Exception as e:
            logger.error(f"Episodic memory health check failed: {e}")
            return False

    # Additional episodic-specific methods

    async def store_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Store complete session data.

        Args:
            session_id: Session identifier
            session_data: Complete session state

        Returns:
            True if stored successfully
        """
        entry = MemoryEntry(
            id=session_id,
            type=MemoryType.EPISODIC,
            content=json.dumps(session_data),
            metadata={
                "session_id": session_id,
                "query": session_data.get("query", ""),
                "status": session_data.get("status", "unknown"),
                "findings_count": len(session_data.get("findings", [])),
            },
            session_id=session_id,
            created_at=datetime.utcnow(),
        )

        return await self.store(entry)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve complete session data.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None
        """
        entries = await self.retrieve(session_id=session_id, limit=1)

        if entries and entries[0].content:
            try:
                return json.loads(entries[0].content)
            except json.JSONDecodeError:
                return None

        return None

    async def list_user_sessions(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[str]:
        """
        List sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum sessions to return

        Returns:
            List of session IDs
        """
        try:
            redis = await self._get_redis()
            user_sessions_key = self.USER_SESSIONS_KEY.format(user_id=user_id)
            return await redis.srandmember(user_sessions_key, count=limit)

        except Exception as e:
            logger.error(f"Failed to list user sessions: {e}")
            return []

    async def store_workflow(
        self,
        session_id: str,
        workflow_id: str,
        workflow_data: Dict[str, Any],
    ) -> bool:
        """
        Store workflow execution data.

        Args:
            session_id: Associated session
            workflow_id: Workflow identifier
            workflow_data: Workflow state

        Returns:
            True if stored successfully
        """
        entry = MemoryEntry(
            id=f"{session_id}:workflow:{workflow_id}",
            type=MemoryType.EPISODIC,
            content=json.dumps(workflow_data),
            metadata={
                "workflow_id": workflow_id,
                "session_id": session_id,
                "node_count": workflow_data.get("node_count", 0),
            },
            session_id=session_id,
        )

        return await self.store(entry)

    async def get_workflow(self, session_id: str, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve workflow execution data.

        Args:
            session_id: Session identifier
            workflow_id: Workflow identifier

        Returns:
            Workflow data or None
        """
        try:
            redis = await self._get_redis()
            key = f"memory:episodic:session:{session_id}:workflow:{workflow_id}"
            data = await redis.get(key)

            if data:
                return json.loads(data)

            return None

        except Exception as e:
            logger.error(f"Failed to get workflow: {e}")
            return None
