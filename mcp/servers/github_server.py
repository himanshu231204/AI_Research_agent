"""
GitHub MCP Server - MCP server for GitHub integration
"""

import os
import logging
from typing import Dict, Any

from mcp.servers.base import MCPServer, ServerConfig
from mcp.schemas.tool import Tool, ToolResult, ToolCategory, ToolParameter, ParameterType
from tools.github import GitHubTool, GitHubConfig

logger = logging.getLogger(__name__)


class GitHubMCPServer(MCPServer):
    """MCP server for GitHub integration"""

    def __init__(self, config: ServerConfig = None):
        config = config or ServerConfig(
            name="github",
            version="1.0.0",
            description="GitHub API integration",
            capabilities={"tools": True},
        )
        super().__init__(config)
        self._github: GitHubTool = None

    async def _setup(self) -> None:
        """Setup GitHub"""
        # Get token from environment
        token = os.environ.get("GITHUB_TOKEN", "")

        github_config = GitHubConfig(token=token)
        self._github = GitHubTool(github_config)

        # Register tools
        self._register_tools()

        logger.info("GitHub MCP server setup complete")

    async def _teardown(self) -> None:
        """Teardown GitHub"""
        if self._github:
            await self._github.close()
        logger.info("GitHub MCP server teardown complete")

    def _register_tools(self) -> None:
        """Register GitHub tools"""
        # Search repos
        self.register_tool(
            Tool(
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
                    ),
                ),
                server_name=self.config.name,
            )
        )

        # Get file
        self.register_tool(
            Tool(
                name="github_get_file",
                description="Get file from repository",
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
                ),
                server_name=self.config.name,
            )
        )

        # List files
        self.register_tool(
            Tool(
                name="github_list_files",
                description="List files in repository",
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
                ),
                server_name=self.config.name,
            )
        )

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute GitHub tool"""
        if tool_name == "github_search_repos":
            result = await self._github.search_repos(
                query=arguments.get("query", ""),
                sort=arguments.get("sort", "stars"),
            )
            return ToolResult(
                tool_id=self._tools[tool_name].id,
                tool_name=tool_name,
                success=result.success,
                result=result.data,
                error=result.error,
                execution_time=result.execution_time,
            )

        elif tool_name == "github_get_file":
            result = await self._github.get_file(
                owner=arguments.get("owner", ""),
                repo=arguments.get("repo", ""),
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

        elif tool_name == "github_list_files":
            result = await self._github.list_files(
                owner=arguments.get("owner", ""),
                repo=arguments.get("repo", ""),
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
