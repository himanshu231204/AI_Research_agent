"""
MCP Base Transport - Abstract transport interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    """Transport types"""

    HTTP = "http"
    STDIO = "stdio"
    WEBSOCKET = "websocket"
    SSE = "sse"


class TransportState(str, Enum):
    """Transport connection states"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass(frozen=True)
class TransportConfig:
    """Transport configuration"""

    transport_type: TransportType = TransportType.HTTP
    url: str = ""
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = field(default_factory=dict)
    # Stdio specific
    command: str = ""
    args: tuple = field(default_factory=tuple)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    # Connection pool
    max_connections: int = 10
    keep_alive: bool = True


@dataclass
class TransportResult:
    """Result of transport operation"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    latency: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTransport(ABC):
    """Abstract base class for MCP transports"""

    def __init__(self, config: TransportConfig):
        self.config = config
        self.state = TransportState.DISCONNECTED
        self._connection_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._request_count: int = 0
        self._error_count: int = 0

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection"""
        pass

    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> TransportResult:
        """Send message and wait for response"""
        pass

    @abstractmethod
    async def send_async(self, message: Dict[str, Any]) -> str:
        """Send message without waiting for response (fire and forget)"""
        pass

    @abstractmethod
    async def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message (for streaming transports)"""
        pass

    async def health_check(self) -> bool:
        """Check if transport is healthy"""
        try:
            result = await self.send({"method": "ping", "params": {}})
            return result.success
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if transport is connected"""
        return self.state == TransportState.CONNECTED

    def get_stats(self) -> Dict[str, Any]:
        """Get transport statistics"""
        return {
            "state": self.state.value,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._request_count, 1),
            "connection_time": self._connection_time.isoformat() if self._connection_time else None,
            "last_error": self._last_error,
        }

    async def _retry_with_backoff(
        self, operation, max_retries: Optional[int] = None, retry_delay: Optional[float] = None
    ):
        """Execute operation with exponential backoff retry"""
        max_retries = max_retries or self.config.max_retries
        retry_delay = retry_delay or self.config.retry_delay

        last_error = None
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        raise last_error

    def _update_stats(self, success: bool) -> None:
        """Update transport statistics"""
        self._request_count += 1
        if not success:
            self._error_count += 1
