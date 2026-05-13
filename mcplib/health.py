"""
MCP Health Monitor - Monitor MCP server health and connectivity

This module provides:
- Health checks for MCP servers
- Connection validation
- Capability validation
- Health status reporting
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from mcplib.client.client import MCPClient, MCPClientConfig
from mcplib.transport import TransportType

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


@dataclass
class ServerHealth:
    """Health status for a single MCP server"""

    server_name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    connected: bool = False
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    error_message: Optional[str] = None
    tool_count: int = 0
    capabilities: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "server_name": self.server_name,
            "status": self.status.value,
            "connected": self.connected,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "error_message": self.error_message,
            "tool_count": self.tool_count,
            "capabilities": self.capabilities,
            "latency_ms": self.latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "metadata": self.metadata,
        }


class MCPHealthMonitor:
    """Monitor health of MCP servers"""

    def __init__(self):
        self._health_status: Dict[str, ServerHealth] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def health_status(self) -> Dict[str, ServerHealth]:
        """Get health status of all servers"""
        return self._health_status

    async def start(self, interval: int = 30) -> None:
        """Start health monitoring"""
        self._health_check_task = asyncio.create_task(self._health_check_loop(interval))
        logger.info("MCP health monitor started")

    async def stop(self) -> None:
        """Stop health monitoring"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("MCP health monitor stopped")

    async def check_server(
        self,
        server_name: str,
        url: str,
        transport_type: TransportType = TransportType.HTTP,
        timeout: int = 30,
    ) -> ServerHealth:
        """
        Check health of a single MCP server

        Args:
            server_name: Name of the server
            url: Server URL
            transport_type: Transport type
            timeout: Connection timeout

        Returns:
            ServerHealth instance
        """
        health = ServerHealth(server_name=server_name)
        health.last_check = datetime.utcnow()

        start_time = datetime.utcnow()

        try:
            # Create client config
            config = MCPClientConfig(
                server_name=server_name,
                server_url=url,
                transport_type=transport_type,
                timeout=timeout,
                auto_reconnect=False,
            )

            # Create and connect client
            client = MCPClient(config)

            try:
                connected = await asyncio.wait_for(client.connect(), timeout=timeout)

                if connected:
                    health.connected = True
                    health.status = HealthStatus.HEALTHY
                    health.last_success = datetime.utcnow()
                    health.tool_count = len(client.tools)
                    health.capabilities = list(client.tools.keys())
                    health.consecutive_failures = 0
                else:
                    health.connected = False
                    health.status = HealthStatus.UNHEALTHY
                    health.error_message = "Failed to connect"
                    health.consecutive_failures += 1

            finally:
                await client.disconnect()

        except asyncio.TimeoutError:
            health.connected = False
            health.status = HealthStatus.UNHEALTHY
            health.error_message = "Connection timeout"
            health.consecutive_failures += 1

        except Exception as e:
            health.connected = False
            health.status = HealthStatus.UNHEALTHY
            health.error_message = str(e)
            health.consecutive_failures += 1
            logger.warning(f"Health check failed for {server_name}: {e}")

        finally:
            # Calculate latency
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            health.latency_ms = latency

            # Update status based on consecutive failures
            if health.consecutive_failures >= 3:
                health.status = HealthStatus.UNHEALTHY
            elif health.consecutive_failures >= 1:
                health.status = HealthStatus.DEGRADED

        return health

    async def check_all_servers(
        self, server_configs: List[Dict[str, Any]]
    ) -> Dict[str, ServerHealth]:
        """
        Check health of all configured servers

        Args:
            server_configs: List of server configuration dictionaries

        Returns:
            Dictionary of server name to ServerHealth
        """
        results = {}

        # Check all servers in parallel
        tasks = []
        for config in server_configs:
            task = self.check_server(
                server_name=config.get("name", ""),
                url=config.get("url", ""),
                transport_type=TransportType(config.get("transport", "http")),
                timeout=config.get("timeout", 30),
            )
            tasks.append(task)

        # Wait for all checks to complete
        health_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(health_results):
            config = server_configs[i]
            server_name = config.get("name", "")

            if isinstance(result, Exception):
                # Handle exception
                health = ServerHealth(server_name=server_name)
                health.status = HealthStatus.UNHEALTHY
                health.error_message = str(result)
                health.last_check = datetime.utcnow()
            else:
                health = result

            results[server_name] = health

            # Update internal state
            async with self._lock:
                self._health_status[server_name] = health

        return results

    async def get_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        async with self._lock:
            total = len(self._health_status)
            healthy = sum(
                1 for h in self._health_status.values() if h.status == HealthStatus.HEALTHY
            )
            degraded = sum(
                1 for h in self._health_status.values() if h.status == HealthStatus.DEGRADED
            )
            unhealthy = sum(
                1 for h in self._health_status.values() if h.status == HealthStatus.UNHEALTHY
            )

            return {
                "total_servers": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "servers": {name: health.to_dict() for name, health in self._health_status.items()},
            }

    async def get_server_health(self, server_name: str) -> Optional[ServerHealth]:
        """Get health for a specific server"""
        async with self._lock:
            return self._health_status.get(server_name)

    async def _health_check_loop(self, interval: int) -> None:
        """Periodic health check loop"""
        while True:
            try:
                await asyncio.sleep(interval)
                logger.debug("Running periodic health check")

                # Note: This would be connected to the actual server configs
                # For now, just log that we're running

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")


# Global health monitor instance
_health_monitor: Optional[MCPHealthMonitor] = None


def get_health_monitor() -> MCPHealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = MCPHealthMonitor()
    return _health_monitor
