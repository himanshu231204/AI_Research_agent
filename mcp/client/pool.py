"""
MCP Connection Pool - Manage multiple MCP client connections
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from datetime import datetime

from mcp.client.client import MCPClient, MCPClientConfig
from mcp.schemas.tool import Tool, ToolResult
from mcp.schemas.session import MCPSession, SessionStatus

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Connection pool configuration"""

    max_connections: int = 10
    max_per_server: int = 3
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_retries: int = 3
    health_check_interval: int = 30


class ConnectionPool:
    """Pool for managing multiple MCP client connections"""

    def __init__(self, config: PoolConfig = None):
        self.config = config or PoolConfig()
        self._clients: Dict[str, MCPClient] = {}
        self._server_configs: Dict[str, MCPClientConfig] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def clients(self) -> Dict[str, MCPClient]:
        """Get all clients"""
        return self._clients

    async def start(self) -> None:
        """Start the connection pool"""
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Connection pool started")

    async def stop(self) -> None:
        """Stop the connection pool"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Disconnect all clients
        async with self._lock:
            for client in self._clients.values():
                await client.disconnect()

        self._clients.clear()
        logger.info("Connection pool stopped")

    async def register_server(self, config: MCPClientConfig) -> None:
        """Register an MCP server configuration"""
        async with self._lock:
            self._server_configs[config.server_name] = config
            logger.info(f"Registered server: {config.server_name}")

    async def connect_server(self, server_name: str) -> bool:
        """Connect to a registered server"""
        config = self._server_configs.get(server_name)
        if not config:
            logger.error(f"Server {server_name} not registered")
            return False

        async with self._lock:
            # Check if already connected
            if server_name in self._clients:
                client = self._clients[server_name]
                if client.is_connected:
                    return True

            # Create new client
            client = MCPClient(config)

            # Connect
            if await client.connect():
                self._clients[server_name] = client
                return True

            return False

    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect from a server"""
        async with self._lock:
            client = self._clients.pop(server_name, None)
            if client:
                await client.disconnect()

    async def get_client(self, server_name: str) -> Optional[MCPClient]:
        """Get client for a server"""
        client = self._clients.get(server_name)

        if client and not client.is_connected:
            # Try to reconnect
            if await client.reconnect():
                return client
            return None

        return client

    async def call_tool(
        self, server_name: str, tool_name: str, parameters: Dict[str, Any]
    ) -> ToolResult:
        """Call a tool on a specific server"""
        client = await self.get_client(server_name)

        if not client:
            return ToolResult(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error=f"Server {server_name} not connected",
            )

        return await client.call_tool(tool_name, parameters)

    async def get_all_tools(self) -> Dict[str, Tool]:
        """Get all tools from all connected servers"""
        all_tools = {}

        async with self._lock:
            for server_name, client in self._clients.items():
                if client.is_connected:
                    for tool_name, tool in client.tools.items():
                        # Prefix tool name with server
                        full_name = f"{server_name}:{tool_name}"
                        all_tools[full_name] = tool

        return all_tools

    async def get_server_status(self) -> Dict[str, Any]:
        """Get status of all servers"""
        status = {}

        async with self._lock:
            for server_name, config in self._server_configs.items():
                client = self._clients.get(server_name)

                if client and client.is_connected:
                    status[server_name] = {
                        "connected": True,
                        "tools": len(client.tools),
                        "session": client.session.to_dict() if client.session else None,
                    }
                else:
                    status[server_name] = {
                        "connected": False,
                        "tools": 0,
                        "session": None,
                    }

        return status

    async def _health_check_loop(self) -> None:
        """Periodic health check for all connections"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                async with self._lock:
                    for server_name, client in list(self._clients.items()):
                        if not client.is_connected:
                            logger.warning(
                                f"Server {server_name} disconnected, attempting reconnect"
                            )
                            try:
                                await client.reconnect()
                            except Exception as e:
                                logger.error(f"Failed to reconnect {server_name}: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
