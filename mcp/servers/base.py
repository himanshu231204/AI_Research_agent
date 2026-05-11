"""
MCP Base Server - Base class for MCP servers
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from mcp.schemas.tool import Tool, ToolResult
from mcp.schemas.transport import TransportMessage, MessageType

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """MCP Server configuration"""

    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    capabilities: Dict[str, bool] = field(default_factory=dict)
    port: int = 8080
    host: str = "0.0.0.0"


class MCPServer(ABC):
    """Base class for MCP servers"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self._tools: Dict[str, Tool] = {}
        self._running = False
        self._message_handler: Optional[Callable] = None

    @property
    def tools(self) -> Dict[str, Tool]:
        """Get registered tools"""
        return self._tools

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._running

    async def start(self) -> bool:
        """Start the server"""
        if self._running:
            return True

        try:
            await self._setup()
            self._running = True
            logger.info(f"MCP server '{self.config.name}' started")
            return True
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False

    async def stop(self) -> None:
        """Stop the server"""
        if not self._running:
            return

        try:
            await self._teardown()
            self._running = False
            logger.info(f"MCP server '{self.config.name}' stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")

    async def handle_message(self, message: TransportMessage) -> TransportMessage:
        """Handle incoming MCP message"""
        try:
            if message.method == "initialize":
                return await self._handle_initialize(message)
            elif message.method == "tools/list":
                return await self._handle_list_tools(message)
            elif message.method == "tools/call":
                return await self._handle_call_tool(message)
            elif message.method == "resources/list":
                return await self._handle_list_resources(message)
            elif message.method == "prompts/list":
                return await self._handle_list_prompts(message)
            elif message.method == "ping":
                return await self._handle_ping(message)
            else:
                return self._create_error_response(
                    message.id, -32601, f"Method not found: {message.method}"
                )
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._create_error_response(message.id, -32603, str(e))

    async def _handle_initialize(self, message: TransportMessage) -> TransportMessage:
        """Handle initialize request"""
        return TransportMessage(
            id=message.id,
            message_type=MessageType.INITIALIZE_RESPONSE,
            result={
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.config.name,
                    "version": self.config.version,
                },
                "capabilities": self.config.capabilities,
            },
        )

    async def _handle_list_tools(self, message: TransportMessage) -> TransportMessage:
        """Handle tools/list request"""
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.param_type.value,
                        "description": param.description,
                        "required": param.required,
                    }
                    for param in tool.parameters
                ],
            }
            for tool in self._tools.values()
        ]

        return TransportMessage(
            id=message.id,
            message_type=MessageType.TOOLS_LIST_RESPONSE,
            result={"tools": tools},
        )

    async def _handle_call_tool(self, message: TransportMessage) -> TransportMessage:
        """Handle tools/call request"""
        params = message.params
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._create_error_response(message.id, -32602, "Tool name is required")

        tool = self._tools.get(tool_name)
        if not tool:
            return self._create_error_response(message.id, -32602, f"Tool not found: {tool_name}")

        try:
            result = await self._execute_tool(tool_name, arguments)

            return TransportMessage(
                id=message.id,
                message_type=MessageType.TOOLS_CALL_RESPONSE,
                result=result.to_dict(),
            )
        except Exception as e:
            return self._create_error_response(message.id, -32603, str(e))

    async def _handle_list_resources(self, message: TransportMessage) -> TransportMessage:
        """Handle resources/list request"""
        return TransportMessage(
            id=message.id,
            message_type=MessageType.RESOURCES_LIST_RESPONSE,
            result={"resources": []},
        )

    async def _handle_list_prompts(self, message: TransportMessage) -> TransportMessage:
        """Handle prompts/list request"""
        return TransportMessage(
            id=message.id,
            message_type=MessageType.PROMPTS_LIST_RESPONSE,
            result={"prompts": []},
        )

    async def _handle_ping(self, message: TransportMessage) -> TransportMessage:
        """Handle ping request"""
        return TransportMessage(
            id=message.id,
            message_type=MessageType.PONG,
            result={"status": "ok"},
        )

    def _create_error_response(self, message_id: str, code: int, message: str) -> TransportMessage:
        """Create error response"""
        return TransportMessage(
            id=message_id,
            message_type=MessageType.JSONRPC_ERROR,
            error={
                "code": code,
                "message": message,
            },
        )

    @abstractmethod
    async def _setup(self) -> None:
        """Server-specific setup"""
        pass

    @abstractmethod
    async def _teardown(self) -> None:
        """Server-specific teardown"""
        pass

    @abstractmethod
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool"""
        pass

    def register_tool(self, tool: Tool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
