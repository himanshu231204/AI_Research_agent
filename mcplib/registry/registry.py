"""
MCP Tool Registry - Dynamic tool registration and discovery
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import uuid

from mcplib.schemas.tool import Tool, ToolCategory, ToolResult
from mcplib.client.pool import ConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Registry configuration"""

    enable_auto_discovery: bool = True
    discovery_interval: int = 60
    cache_ttl: int = 300
    max_tools: int = 1000


class ToolRegistry:
    """Registry for managing tools across MCP servers"""

    def __init__(self, config: RegistryConfig = None, pool: ConnectionPool = None):
        self.config = config or RegistryConfig()
        self._pool = pool
        self._tools: Dict[str, Tool] = {}
        self._tool_metadata: Dict[str, Dict[str, Any]] = {}
        self._categories: Dict[ToolCategory, List[str]] = {cat: [] for cat in ToolCategory}
        self._tags: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()
        self._discovery_task: Optional[asyncio.Task] = None
        self._listeners: List[Callable] = []

    @property
    def tools(self) -> Dict[str, Tool]:
        """Get all registered tools"""
        return self._tools

    async def start(self) -> None:
        """Start the registry"""
        if self.config.enable_auto_discovery and self._pool:
            self._discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info("Tool registry started")

    async def stop(self) -> None:
        """Stop the registry"""
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        logger.info("Tool registry stopped")

    async def register_tool(self, tool: Tool, metadata: Dict[str, Any] = None) -> None:
        """Register a tool"""
        async with self._lock:
            self._tools[tool.name] = tool
            self._tool_metadata[tool.name] = {
                "registered_at": datetime.utcnow(),
                "last_used": None,
                "use_count": 0,
                "metadata": metadata or {},
            }

            # Update categories
            if tool.category not in self._categories:
                self._categories[tool.category] = []
            if tool.name not in self._categories[tool.category]:
                self._categories[tool.category].append(tool.name)

            # Update tags
            for tag in metadata.get("tags", []):
                if tag not in self._tags:
                    self._tags[tag] = []
                if tool.name not in self._tags[tag]:
                    self._tags[tag].append(tool.name)

            # Notify listeners
            await self._notify_listeners("register", tool)

            logger.info(f"Registered tool: {tool.name}")

    async def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool"""
        async with self._lock:
            tool = self._tools.pop(tool_name, None)
            if not tool:
                return False

            # Remove from categories
            if tool.category in self._categories:
                self._categories[tool.category] = [
                    t for t in self._categories[tool.category] if t != tool_name
                ]

            # Remove from tags
            for tag_list in self._tags.values():
                if tool_name in tag_list:
                    tag_list.remove(tool_name)

            self._tool_metadata.pop(tool_name, None)

            await self._notify_listeners("unregister", tool)
            logger.info(f"Unregistered tool: {tool_name}")
            return True

    async def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a tool by name"""
        async with self._lock:
            tool = self._tools.get(tool_name)
            if tool:
                # Update usage stats
                if tool_name in self._tool_metadata:
                    self._tool_metadata[tool_name]["last_used"] = datetime.utcnow()
                    self._tool_metadata[tool_name]["use_count"] += 1
            return tool

    async def get_tools_by_category(self, category: ToolCategory) -> List[Tool]:
        """Get tools by category"""
        async with self._lock:
            tool_names = self._categories.get(category, [])
            return [self._tools[name] for name in tool_names if name in self._tools]

    async def get_tools_by_tag(self, tag: str) -> List[Tool]:
        """Get tools by tag"""
        async with self._lock:
            tool_names = self._tags.get(tag, [])
            return [self._tools[name] for name in tool_names if name in self._tools]

    async def search_tools(self, query: str) -> List[Tool]:
        """Search tools by name or description"""
        async with self._lock:
            query_lower = query.lower()
            results = []

            for tool in self._tools.values():
                if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                    results.append(tool)

            return results

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], server_name: str = None
    ) -> ToolResult:
        """Execute a tool"""
        tool = await self.get_tool(tool_name)

        if not tool:
            return ToolResult(
                tool_id="",
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found",
            )

        # Determine server
        if not server_name:
            server_name = tool.server_name

        if not server_name:
            return ToolResult(
                tool_id=tool.id,
                tool_name=tool_name,
                success=False,
                error="No server specified for tool execution",
            )

        # Execute via pool
        if self._pool:
            return await self._pool.call_tool(server_name, tool_name, parameters)

        return ToolResult(
            tool_id=tool.id,
            tool_name=tool_name,
            success=False,
            error="No connection pool available",
        )

    async def get_tool_stats(self) -> Dict[str, Any]:
        """Get tool statistics"""
        async with self._lock:
            return {
                "total_tools": len(self._tools),
                "by_category": {
                    category.value: len(tools) for category, tools in self._categories.items()
                },
                "total_tags": len(self._tags),
                "most_used": sorted(
                    [(name, meta["use_count"]) for name, meta in self._tool_metadata.items()],
                    key=lambda x: x[1],
                    reverse=True,
                )[:10],
            }

    def add_listener(self, listener: Callable) -> None:
        """Add a listener for tool events"""
        self._listeners.append(listener)

    async def _notify_listeners(self, event: str, tool: Tool) -> None:
        """Notify listeners of tool events"""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, tool)
                else:
                    listener(event, tool)
            except Exception as e:
                logger.error(f"Error in listener: {e}")

    async def _discovery_loop(self) -> None:
        """Periodic tool discovery"""
        while True:
            try:
                await asyncio.sleep(self.config.discovery_interval)

                if self._pool:
                    # Refresh tools from all connected servers
                    all_tools = await self._pool.get_all_tools()

                    async with self._lock:
                        # Add new tools
                        for tool_name, tool in all_tools.items():
                            if tool_name not in self._tools:
                                await self.register_tool(tool)

                    logger.debug(f"Discovered {len(all_tools)} tools")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in discovery: {e}")
