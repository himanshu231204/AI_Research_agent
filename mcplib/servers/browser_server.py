"""
Browser MCP Server - MCP server for browser automation
"""

import asyncio
import logging
from typing import Dict, Any

from mcplib.servers.base import MCPServer, ServerConfig
from mcplib.schemas.tool import Tool, ToolResult, ToolCategory, ToolParameter, ParameterType
from tools.browser import BrowserTool, BrowserConfig

logger = logging.getLogger(__name__)


class BrowserMCPServer(MCPServer):
    """MCP server for browser automation"""

    def __init__(self, config: ServerConfig = None):
        config = config or ServerConfig(
            name="browser",
            version="1.0.0",
            description="Browser automation via Playwright",
            capabilities={"tools": True},
        )
        super().__init__(config)
        self._browser: BrowserTool = None

    async def _setup(self) -> None:
        """Setup browser"""
        # Create browser tool
        browser_config = BrowserConfig(headless=True)
        self._browser = BrowserTool(browser_config)

        # Register tools
        self._register_tools()

        logger.info("Browser MCP server setup complete")

    async def _teardown(self) -> None:
        """Teardown browser"""
        if self._browser:
            await self._browser.stop()
        logger.info("Browser MCP server teardown complete")

    def _register_tools(self) -> None:
        """Register browser tools"""
        # Navigate
        self.register_tool(
            Tool(
                name="browser_navigate",
                description="Navigate to a URL",
                category=ToolCategory.BROWSER,
                parameters=(
                    ToolParameter(
                        name="url",
                        param_type=ParameterType.STRING,
                        description="URL to navigate to",
                        required=True,
                    ),
                    ToolParameter(
                        name="wait_until",
                        param_type=ParameterType.STRING,
                        description="Wait until DOM state",
                        required=False,
                        default="load",
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Screenshot
        self.register_tool(
            Tool(
                name="browser_screenshot",
                description="Take a screenshot",
                category=ToolCategory.BROWSER,
                parameters=(
                    ToolParameter(
                        name="full_page",
                        param_type=ParameterType.BOOLEAN,
                        description="Capture full page",
                        required=False,
                        default=False,
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Click
        self.register_tool(
            Tool(
                name="browser_click",
                description="Click an element",
                category=ToolCategory.BROWSER,
                parameters=(
                    ToolParameter(
                        name="selector",
                        param_type=ParameterType.STRING,
                        description="CSS selector",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Type
        self.register_tool(
            Tool(
                name="browser_type",
                description="Type text into element",
                category=ToolCategory.BROWSER,
                parameters=(
                    ToolParameter(
                        name="selector",
                        param_type=ParameterType.STRING,
                        description="CSS selector",
                        required=True,
                    ),
                    ToolParameter(
                        name="text",
                        param_type=ParameterType.STRING,
                        description="Text to type",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Evaluate
        self.register_tool(
            Tool(
                name="browser_evaluate",
                description="Execute JavaScript",
                category=ToolCategory.BROWSER,
                parameters=(
                    ToolParameter(
                        name="script",
                        param_type=ParameterType.STRING,
                        description="JavaScript code",
                        required=True,
                    ),
                ),
                server_name=self.config.name,
            )
        )

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute browser tool"""
        # Start browser if needed
        if not self._browser.is_running:
            await self._browser.start()

        if tool_name == "browser_navigate":
            result = await self._browser.navigate(
                arguments.get("url", ""),
                arguments.get("wait_until", "load"),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "browser_screenshot":
            result = await self._browser.screenshot(
                full_page=arguments.get("full_page", False),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
                artifacts=[result.screenshot] if result.screenshot else [],
            )

        elif tool_name == "browser_click":
            result = await self._browser.click(
                arguments.get("selector", ""),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "browser_type":
            result = await self._browser.type(
                arguments.get("selector", ""),
                arguments.get("text", ""),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "browser_evaluate":
            result = await self._browser.evaluate(
                arguments.get("script", ""),
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
