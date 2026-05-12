"""
Terminal MCP Server - MCP server for terminal operations
"""

import logging
from typing import Dict, Any

from mcplib.servers.base import MCPServer, ServerConfig
from mcplib.schemas.tool import Tool, ToolResult, ToolCategory, ToolParameter, ParameterType
from tools.terminal import TerminalTool, TerminalConfig

logger = logging.getLogger(__name__)


class TerminalMCPServer(MCPServer):
    """MCP server for terminal operations"""

    def __init__(self, config: ServerConfig = None):
        config = config or ServerConfig(
            name="terminal",
            version="1.0.0",
            description="Terminal command execution",
            capabilities={"tools": True},
        )
        super().__init__(config)
        self._terminal: TerminalTool = None

    async def _setup(self) -> None:
        """Setup terminal"""
        terminal_config = TerminalConfig()
        self._terminal = TerminalTool(terminal_config)

        # Register tools
        self._register_tools()

        logger.info("Terminal MCP server setup complete")

    async def _teardown(self) -> None:
        """Teardown terminal"""
        logger.info("Terminal MCP server teardown complete")

    def _register_tools(self) -> None:
        """Register terminal tools"""
        # Execute
        self.register_tool(
            Tool(
                name="terminal_execute",
                description="Execute terminal command",
                category=ToolCategory.TERMINAL,
                parameters=(
                    ToolParameter(
                        name="command",
                        param_type=ParameterType.STRING,
                        description="Command to execute",
                        required=True,
                    ),
                    ToolParameter(
                        name="cwd",
                        param_type=ParameterType.STRING,
                        description="Working directory",
                        required=False,
                    ),
                    ToolParameter(
                        name="timeout",
                        param_type=ParameterType.INTEGER,
                        description="Timeout in seconds",
                        required=False,
                        default=30,
                    ),
                ),
                server_name=self.config.name,
            )
        )

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute terminal tool"""
        if tool_name == "terminal_execute":
            result = await self._terminal.execute(
                command=arguments.get("command", ""),
                cwd=arguments.get("cwd"),
                timeout=arguments.get("timeout", 30),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                },
                error=result.error,
                execution_time=result.execution_time,
            )

        return ToolResult(
            tool_id="",
            tool_name=tool_name,
            success=False,
            error=f"Unknown tool: {tool_name}",
        )
