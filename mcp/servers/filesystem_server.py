"""
Filesystem MCP Server - MCP server for filesystem operations
"""

import logging
from typing import Dict, Any

from mcp.servers.base import MCPServer, ServerConfig
from mcp.schemas.tool import Tool, ToolResult, ToolCategory, ToolParameter, ParameterType
from tools.filesystem import FilesystemTool, FilesystemConfig

logger = logging.getLogger(__name__)


class FilesystemMCPServer(MCPServer):
    """MCP server for filesystem operations"""

    def __init__(self, config: ServerConfig = None, base_path: str = "."):
        config = config or ServerConfig(
            name="filesystem",
            version="1.0.0",
            description="Local filesystem operations",
            capabilities={"tools": True},
        )
        super().__init__(config)
        self._base_path = base_path
        self._filesystem: FilesystemTool = None

    async def _setup(self) -> None:
        """Setup filesystem"""
        fs_config = FilesystemConfig(base_path=self._base_path)
        self._filesystem = FilesystemTool(fs_config)

        # Register tools
        self._register_tools()

        logger.info("Filesystem MCP server setup complete")

    async def _teardown(self) -> None:
        """Teardown filesystem"""
        logger.info("Filesystem MCP server teardown complete")

    def _register_tools(self) -> None:
        """Register filesystem tools"""
        # Read
        self.register_tool(
            Tool(
                name="filesystem_read",
                description="Read file contents",
                category=ToolCategory.FILESYSTEM,
                parameters=(
                    ToolParameter(
                        name="path",
                        param_type=ParameterType.STRING,
                        description="File path",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Write
        self.register_tool(
            Tool(
                name="filesystem_write",
                description="Write file contents",
                category=ToolCategory.FILESYSTEM,
                parameters=(
                    ToolParameter(
                        name="path",
                        param_type=ParameterType.STRING,
                        description="File path",
                        required=True,
                    ),
                    ToolParameter(
                        name="content",
                        param_type=ParameterType.STRING,
                        description="Content to write",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # List
        self.register_tool(
            Tool(
                name="filesystem_list",
                description="List directory contents",
                category=ToolCategory.FILESYSTEM,
                parameters=(
                    ToolParameter(
                        name="path",
                        param_type=ParameterType.STRING,
                        description="Directory path",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute filesystem tool"""
        if tool_name == "filesystem_read":
            result = await self._filesystem.read(
                path=arguments.get("path", ""),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "filesystem_write":
            result = await self._filesystem.write(
                path=arguments.get("path", ""),
                content=arguments.get("content", ""),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "filesystem_list":
            result = await self._filesystem.list(
                path=arguments.get("path", ""),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        return ToolResult(
            tool_id="",
            tool_name=tool_name,
            success=False,
            error=f"Unknown tool: {tool_name}",
        )
