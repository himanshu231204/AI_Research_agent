"""
MCP Tool Discovery - Automatic tool discovery from various sources
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import importlib
import pkgutil

from mcplib.schemas.tool import Tool, ToolCategory, ToolParameter, ParameterType

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Discovery configuration"""

    discover_modules: List[str] = field(default_factory=list)
    discover_builtin: bool = True
    discover_custom: bool = True
    cache_discovery: bool = True


class ToolDiscovery:
    """Discover tools from various sources"""

    def __init__(self, config: DiscoveryConfig = None):
        self.config = config or DiscoveryConfig()
        self._discovered_tools: Dict[str, Tool] = {}
        self._discovery_sources: Dict[str, Any] = {}

    def register_source(self, name: str, source: Any) -> None:
        """Register a discovery source"""
        self._discovery_sources[name] = source
        logger.info(f"Registered discovery source: {name}")

    async def discover_all(self) -> Dict[str, Tool]:
        """Discover all available tools"""
        tools = {}

        # Discover from builtin sources
        if self.config.discover_builtin:
            builtin_tools = await self._discover_builtin()
            tools.update(builtin_tools)

        # Discover from custom modules
        if self.config.discover_custom:
            for module_name in self.config.discover_modules:
                module_tools = await self._discover_module(module_name)
                tools.update(module_tools)

        # Discover from registered sources
        for source_name, source in self._discovery_sources.items():
            try:
                if hasattr(source, "discover_tools"):
                    source_tools = await source.discover_tools()
                    tools.update(source_tools)
            except Exception as e:
                logger.error(f"Error discovering from {source_name}: {e}")

        self._discovered_tools = tools
        return tools

    async def _discover_builtin(self) -> Dict[str, Tool]:
        """Discover built-in tools"""
        tools = {}

        # Browser tools
        tools["browser_navigate"] = Tool(
            name="browser_navigate",
            description="Navigate to a URL in the browser",
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
                    description="Wait until DOM is in specific state",
                    required=False,
                    default="load",
                    enum=["load", "domcontentloaded", "networkidle", "commit"],
                ),
            ),
            server_name="browser",
            timeout=30,
        )

        tools["browser_screenshot"] = Tool(
            name="browser_screenshot",
            description="Take a screenshot of the current page",
            category=ToolCategory.BROWSER,
            parameters=(
                ToolParameter(
                    name="full_page",
                    param_type=ParameterType.BOOLEAN,
                    description="Capture full page or just viewport",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="format",
                    param_type=ParameterType.STRING,
                    description="Image format",
                    required=False,
                    default="png",
                    enum=["png", "jpeg", "webp"],
                ),
            ),
            server_name="browser",
            timeout=10,
        )

        tools["browser_click"] = Tool(
            name="browser_click",
            description="Click an element on the page",
            category=ToolCategory.BROWSER,
            parameters=(
                ToolParameter(
                    name="selector",
                    param_type=ParameterType.STRING,
                    description="CSS selector for the element",
                    required=True,
                ),
                ToolParameter(
                    name="button",
                    param_type=ParameterType.STRING,
                    description="Mouse button to use",
                    required=False,
                    default="left",
                    enum=["left", "right", "middle"],
                ),
            ),
            server_name="browser",
            timeout=10,
        )

        tools["browser_type"] = Tool(
            name="browser_type",
            description="Type text into an input field",
            category=ToolCategory.BROWSER,
            parameters=(
                ToolParameter(
                    name="selector",
                    param_type=ParameterType.STRING,
                    description="CSS selector for the input",
                    required=True,
                ),
                ToolParameter(
                    name="text",
                    param_type=ParameterType.STRING,
                    description="Text to type",
                    required=True,
                ),
                ToolParameter(
                    name="clear",
                    param_type=ParameterType.BOOLEAN,
                    description="Clear input before typing",
                    required=False,
                    default=True,
                ),
            ),
            server_name="browser",
            timeout=10,
        )

        tools["browser_evaluate"] = Tool(
            name="browser_evaluate",
            description="Execute JavaScript in the browser context",
            category=ToolCategory.BROWSER,
            parameters=(
                ToolParameter(
                    name="script",
                    param_type=ParameterType.STRING,
                    description="JavaScript code to execute",
                    required=True,
                ),
            ),
            server_name="browser",
            timeout=10,
        )

        # GitHub tools
        tools["github_search_repos"] = Tool(
            name="github_search_repos",
            description="Search GitHub repositories",
            category=ToolCategory.GITHUB,
            parameters=(
                ToolParameter(
                    name="query",
                    param_type=ParameterType.STRING,
                    description="Search query",
                    required=True,
                ),
                ToolParameter(
                    name="sort",
                    param_type=ParameterType.STRING,
                    description="Sort by",
                    required=False,
                    default="stars",
                    enum=["stars", "forks", "updated"],
                ),
                ToolParameter(
                    name="per_page",
                    param_type=ParameterType.INTEGER,
                    description="Results per page",
                    required=False,
                    default=10,
                ),
            ),
            server_name="github",
            timeout=15,
        )

        tools["github_get_file"] = Tool(
            name="github_get_file",
            description="Get file contents from a repository",
            category=ToolCategory.GITHUB,
            parameters=(
                ToolParameter(
                    name="owner",
                    param_type=ParameterType.STRING,
                    description="Repository owner",
                    required=True,
                ),
                ToolParameter(
                    name="repo",
                    param_type=ParameterType.STRING,
                    description="Repository name",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    param_type=ParameterType.STRING,
                    description="File path",
                    required=True,
                ),
                ToolParameter(
                    name="ref",
                    param_type=ParameterType.STRING,
                    description="Branch or commit",
                    required=False,
                    default="main",
                ),
            ),
            server_name="github",
            timeout=10,
        )

        tools["github_list_files"] = Tool(
            name="github_list_files",
            description="List files in a repository directory",
            category=ToolCategory.GITHUB,
            parameters=(
                ToolParameter(
                    name="owner",
                    param_type=ParameterType.STRING,
                    description="Repository owner",
                    required=True,
                ),
                ToolParameter(
                    name="repo",
                    param_type=ParameterType.STRING,
                    description="Repository name",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    param_type=ParameterType.STRING,
                    description="Directory path",
                    required=False,
                    default="",
                ),
                ToolParameter(
                    name="ref",
                    param_type=ParameterType.STRING,
                    description="Branch or commit",
                    required=False,
                    default="main",
                ),
            ),
            server_name="github",
            timeout=10,
        )

        # Filesystem tools
        tools["filesystem_read"] = Tool(
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
                ToolParameter(
                    name="encoding",
                    param_type=ParameterType.STRING,
                    description="File encoding",
                    required=False,
                    default="utf-8",
                ),
            ),
            server_name="filesystem",
            timeout=5,
        )

        tools["filesystem_write"] = Tool(
            name="filesystem_write",
            description="Write content to a file",
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
                ToolParameter(
                    name="encoding",
                    param_type=ParameterType.STRING,
                    description="File encoding",
                    required=False,
                    default="utf-8",
                ),
            ),
            server_name="filesystem",
            timeout=5,
        )

        tools["filesystem_list"] = Tool(
            name="filesystem_list",
            description="List files in a directory",
            category=ToolCategory.FILESYSTEM,
            parameters=(
                ToolParameter(
                    name="path",
                    param_type=ParameterType.STRING,
                    description="Directory path",
                    required=True,
                ),
                ToolParameter(
                    name="pattern",
                    param_type=ParameterType.STRING,
                    description="Glob pattern",
                    required=False,
                ),
            ),
            server_name="filesystem",
            timeout=5,
        )

        # Terminal tools
        tools["terminal_execute"] = Tool(
            name="terminal_execute",
            description="Execute a terminal command",
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
            server_name="terminal",
            timeout=60,
        )

        logger.info(f"Discovered {len(tools)} built-in tools")
        return tools

    async def _discover_module(self, module_name: str) -> Dict[str, Tool]:
        """Discover tools from a Python module"""
        tools = {}

        try:
            module = importlib.import_module(module_name)

            # Look for tool classes or functions
            for name, obj in vars(module).items():
                if isinstance(obj, type) and hasattr(obj, "to_tool"):
                    try:
                        tool = obj.to_tool()
                        tools[tool.name] = tool
                    except Exception as e:
                        logger.warning(f"Failed to convert {name} to tool: {e}")

        except ImportError as e:
            logger.warning(f"Failed to import module {module_name}: {e}")

        return tools

    def get_discovered_tools(self) -> Dict[str, Tool]:
        """Get cached discovered tools"""
        return self._discovered_tools
