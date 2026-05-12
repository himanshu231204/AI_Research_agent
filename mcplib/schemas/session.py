"""
MCP Session Schema - Session management for MCP connections
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid


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


@dataclass
class SessionPool:
    """Pool of MCP sessions"""

    sessions: Dict[str, MCPSession] = field(default_factory=dict)
    max_sessions: int = 10
    session_timeout: int = 300

    def add_session(self, session: MCPSession) -> None:
        """Add session to pool"""
        self.sessions[session.id] = session

    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def get_session_by_server(self, server_name: str) -> Optional[MCPSession]:
        """Get active session by server name"""
        for session in self.sessions.values():
            if session.server_name == server_name and session.is_active():
                return session
        return None

    def remove_session(self, session_id: str) -> Optional[MCPSession]:
        """Remove session from pool"""
        return self.sessions.pop(session_id, None)

    def get_active_sessions(self) -> List[MCPSession]:
        """Get all active sessions"""
        return [s for s in self.sessions.values() if s.is_active()]

    def cleanup_idle_sessions(self) -> List[str]:
        """Remove idle sessions beyond timeout"""
        now = datetime.utcnow()
        removed = []

        for session_id, session in list(self.sessions.items()):
            if session.status == SessionStatus.IDLE and session.last_activity:
                idle_time = (now - session.last_activity).total_seconds()
                if idle_time > self.session_timeout:
                    self.sessions.pop(session_id, None)
                    removed.append(session_id)

        return removed
