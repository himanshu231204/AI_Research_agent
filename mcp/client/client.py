"""
MCP Client - Main client for MCP server communication
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import uuid

from mcp.schemas.tool import Tool, ToolResult, ToolCategory
from mcp.schemas.session import MCPSession, SessionStatus
from mcp.transport import (
    BaseTransport,
    TransportConfig,
    TransportType,
    HTTPTransport,
    StdioTransport,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    """MCP Client configuration"""

    server_name: str = ""
    server_url: str = ""
    transport_type: TransportType = TransportType.HTTP
    timeout: int = 30
    max_retries: int = 3
    auto_reconnect: bool = True
    reconnect_delay: float = 5.0
    max_reconnect_attempts: int = 3
    # Stdio specific
    command: str = ""
    args: tuple = field(default_factory=tuple)
    env: Dict[str, str] = field(default_factory=dict)


class MCPClient:
    """Async MCP Client for server communication"""

    def __init__(self, config: MCPClientConfig):
        self.config = config
        self._transport: Optional[BaseTransport] = None
        self._session: Optional[MCPSession] = None
        self._tools: Dict[str, Tool] = {}
        self._reconnect_attempts: int = 0
        self._health_check_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {
            "connect": [],
            "disconnect": [],
            "error": [],
            "tool_registered": [],
        }

    @property
    def session(self) -> Optional[MCPSession]:
        """Get current session"""
        return self._session

    @property
    def tools(self) -> Dict[str, Tool]:
        """Get registered tools"""
        return self._tools

    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._session is not None and self._session.is_active()

    async def connect(self) -> bool:
        """Connect to MCP server"""
        try:
            # Create transport config
            transport_config = TransportConfig(
                transport_type=self.config.transport_type,
                url=self.config.server_url,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
            )

            # Create transport
            if self.config.transport_type == TransportType.HTTP:
                self._transport = HTTPTransport(transport_config)
            elif self.config.transport_type == TransportType.STDIO:
                self._transport = StdioTransport(transport_config)
            else:
                raise ValueError(f"Unsupported transport type: {self.config.transport_type}")

            # Connect
            if not await self._transport.connect():
                return False

            # Initialize session
            await self._initialize_session()

            # Start health check
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            # Notify callbacks
            await self._notify_callbacks("connect", self._session)

            logger.info(f"MCP client connected to {self.config.server_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect MCP client: {e}")
            await self._notify_callbacks("error", str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from MCP server"""
        try:
            # Stop health check
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # Disconnect transport
            if self._transport:
                await self._transport.disconnect()

            # Update session
            if self._session:
                self._session = self._session.with_status(SessionStatus.DISCONNECTED)

            # Notify callbacks
            await self._notify_callbacks("disconnect", self._session)

            logger.info(f"MCP client disconnected from {self.config.server_name}")

        except Exception as e:
            logger.error(f"Error disconnecting MCP client: {e}")

    async def reconnect(self) -> bool:
        """Reconnect to MCP server"""
        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False

        self._reconnect_attempts += 1
        logger.info(
            f"Reconnecting to {self.config.server_name} (attempt {self._reconnect_attempts})"
        )

        await self.disconnect()
        await asyncio.sleep(self.config.reconnect_delay)

        return await self.connect()

    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Call a tool on the MCP server"""
        start_time = datetime.utcnow()

        if not self.is_connected:
            return ToolResult(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error="Client not connected",
            )

        # Get tool
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        # Validate parameters
        valid, errors = tool.validate_parameters(parameters)
        if not valid:
            return ToolResult(
                tool_id=tool.id,
                tool_name=tool_name,
                success=False,
                error=f"Parameter validation failed: {', '.join(errors)}",
            )

        try:
            # Send tool call request
            result = await self._transport.send(
                {
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": parameters,
                    },
                }
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            if result.success:
                return ToolResult(
                    tool_id=tool.id,
                    tool_name=tool_name,
                    success=True,
                    result=result.data,
                    execution_time=execution_time,
                )
            else:
                return ToolResult(
                    tool_id=tool.id,
                    tool_name=tool_name,
                    success=False,
                    error=result.error,
                    execution_time=execution_time,
                )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Error calling tool {tool_name}: {e}")
            return ToolResult(
                tool_id=tool.id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def list_tools(self) -> List[Tool]:
        """List available tools from server"""
        if not self.is_connected:
            return []

        try:
            result = await self._transport.send(
                {
                    "method": "tools/list",
                    "params": {},
                }
            )

            if result.success and result.data:
                tools_data = result.data.get("tools", [])
                return [self._parse_tool(tool_data) for tool_data in tools_data]

            return []

        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register event callback"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    async def _initialize_session(self) -> None:
        """Initialize MCP session"""
        try:
            # Send initialize request
            result = await self._transport.send(
                {
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "research-agent",
                            "version": "1.0.0",
                        },
                    },
                }
            )

            if result.success and result.data:
                # Create session
                self._session = MCPSession(
                    server_name=self.config.server_name,
                    server_url=self.config.server_url,
                    status=SessionStatus.CONNECTED,
                    capabilities=tuple(result.data.get("capabilities", {}).keys()),
                    connected_at=datetime.utcnow(),
                    last_activity=datetime.utcnow(),
                )

                # Load tools
                await self._load_tools()

            else:
                raise Exception("Failed to initialize session")

        except Exception as e:
            logger.error(f"Failed to initialize session: {e}")
            raise

    async def _load_tools(self) -> None:
        """Load tools from server"""
        tools = await self.list_tools()
        for tool in tools:
            self._tools[tool.name] = tool
            await self._notify_callbacks("tool_registered", tool)

    def _parse_tool(self, tool_data: Dict[str, Any]) -> Tool:
        """Parse tool data from server response"""
        from mcp.schemas.tool import ToolParameter, ParameterType

        params = []
        for param_data in tool_data.get("parameters", []):
            param = ToolParameter(
                name=param_data.get("name", ""),
                param_type=ParameterType(param_data.get("type", "string")),
                description=param_data.get("description", ""),
                required=param_data.get("required", False),
            )
            params.append(param)

        return Tool(
            id=tool_data.get("id", str(uuid.uuid4())),
            name=tool_data.get("name", ""),
            description=tool_data.get("description", ""),
            category=ToolCategory.CUSTOM,
            parameters=tuple(params),
            server_name=self.config.server_name,
        )

    async def _health_check_loop(self) -> None:
        """Periodic health check"""
        while True:
            try:
                await asyncio.sleep(30)

                if self._transport and not await self._transport.health_check():
                    logger.warning(f"Health check failed for {self.config.server_name}")

                    if self.config.auto_reconnect:
                        await self.reconnect()
                    else:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")

    async def _notify_callbacks(self, event: str, data: Any) -> None:
        """Notify registered callbacks"""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback {event}: {e}")
