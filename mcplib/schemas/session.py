"""
MCP Session Schema - Session management for MCP connections

Uses Redis-backed storage for persistence across restarts.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid
import json

from memory.session_store import get_session_store, RedisSessionStore

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """MCP session status"""

    PENDING = "pending"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ACTIVE = "active"
    IDLE = "idle"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass(frozen=True)
class MCPSession:
    """MCP Session representation"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    server_name: str = ""
    server_url: str = ""
    status: SessionStatus = SessionStatus.PENDING
    capabilities: tuple = field(default_factory=tuple)
    tools: tuple = field(default_factory=tuple)
    resources: tuple = field(default_factory=tuple)
    prompts: tuple = field(default_factory=tuple)
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """Check if session is active"""
        return self.status in (SessionStatus.CONNECTED, SessionStatus.ACTIVE, SessionStatus.IDLE)

    def update_activity(self) -> "MCPSession":
        """Create new session with updated activity timestamp"""
        return MCPSession(
            id=self.id,
            server_name=self.server_name,
            server_url=self.server_url,
            status=self.status,
            capabilities=self.capabilities,
            tools=self.tools,
            resources=self.resources,
            prompts=self.prompts,
            connected_at=self.connected_at,
            last_activity=datetime.utcnow(),
            error=self.error,
            metadata=self.metadata,
        )

    def with_status(self, status: SessionStatus, error: Optional[str] = None) -> "MCPSession":
        """Create new session with updated status"""
        return MCPSession(
            id=self.id,
            server_name=self.server_name,
            server_url=self.server_url,
            status=status,
            capabilities=self.capabilities,
            tools=self.tools,
            resources=self.resources,
            prompts=self.prompts,
            connected_at=self.connected_at,
            last_activity=self.last_activity,
            error=error,
            metadata=self.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage."""
        return {
            "id": self.id,
            "server_name": self.server_name,
            "server_url": self.server_url,
            "status": self.status.value,
            "capabilities": list(self.capabilities),
            "tools": list(self.tools),
            "resources": list(self.resources),
            "prompts": list(self.prompts),
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPSession":
        """Create session from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            server_name=data.get("server_name", ""),
            server_url=data.get("server_url", ""),
            status=SessionStatus(data.get("status", "pending")),
            capabilities=tuple(data.get("capabilities", [])),
            tools=tuple(data.get("tools", [])),
            resources=tuple(data.get("resources", [])),
            prompts=tuple(data.get("prompts", [])),
            connected_at=datetime.fromisoformat(data["connected_at"])
            if data.get("connected_at")
            else None,
            last_activity=datetime.fromisoformat(data["last_activity"])
            if data.get("last_activity")
            else None,
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class SessionPool:
    """
    Pool of MCP sessions with Redis-backed storage.

    Uses Redis for persistent storage to prevent data loss on restart.
    """

    def __init__(self, max_sessions: int = 10, session_timeout: int = 300):
        """
        Initialize session pool.

        Args:
            max_sessions: Maximum number of sessions
            session_timeout: Session timeout in seconds
        """
        self._store: RedisSessionStore = get_session_store()
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout

    async def add_session(self, session: MCPSession) -> bool:
        """
        Add session to pool (persists to Redis).

        Args:
            session: Session to add

        Returns:
            True if added successfully
        """
        try:
            session_data = session.to_dict()
            return await self._store.create(session.id, session_data)
        except Exception as e:
            logger.error(f"Failed to add session {session.id}: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[MCPSession]:
        """
        Get session by ID (from Redis).

        Args:
            session_id: Session ID

        Returns:
            MCPSession or None
        """
        try:
            session_data = await self._store.get(session_id)
            if session_data:
                return MCPSession.from_dict(session_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def get_session_by_server(self, server_name: str) -> Optional[MCPSession]:
        """
        Get active session by server name.

        Args:
            server_name: Server name

        Returns:
            MCPSession or None
        """
        try:
            session_ids = await self._store.list_sessions()
            for session_id in session_ids:
                session = await self.get_session(session_id)
                if session and session.server_name == server_name and session.is_active():
                    return session
            return None
        except Exception as e:
            logger.error(f"Failed to get session by server {server_name}: {e}")
            return None

    async def remove_session(self, session_id: str) -> bool:
        """
        Remove session from pool (deletes from Redis).

        Args:
            session_id: Session ID

        Returns:
            True if removed successfully
        """
        try:
            return await self._store.delete(session_id)
        except Exception as e:
            logger.error(f"Failed to remove session {session_id}: {e}")
            return False

    async def get_active_sessions(self) -> List[MCPSession]:
        """
        Get all active sessions.

        Returns:
            List of active MCPSession objects
        """
        try:
            session_ids = await self._store.list_sessions()
            active_sessions = []

            for session_id in session_ids:
                session = await self.get_session(session_id)
                if session and session.is_active():
                    active_sessions.append(session)

            return active_sessions
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []

    async def cleanup_idle_sessions(self) -> List[str]:
        """
        Remove idle sessions beyond timeout.

        Returns:
            List of removed session IDs
        """
        try:
            session_ids = await self._store.list_sessions()
            removed = []
            now = datetime.utcnow()

            for session_id in session_ids:
                session = await self.get_session(session_id)
                if session and session.status == SessionStatus.IDLE and session.last_activity:
                    idle_time = (now - session.last_activity).total_seconds()
                    if idle_time > self.session_timeout:
                        await self.remove_session(session_id)
                        removed.append(session_id)

            return removed
        except Exception as e:
            logger.error(f"Failed to cleanup idle sessions: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for session pool.

        Returns:
            Health status dictionary
        """
        return await self._store.health_check()
