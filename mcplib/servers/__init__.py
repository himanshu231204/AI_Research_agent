"""
MCP Servers - Server implementations for MCP protocol

NOTE: Custom MCP servers removed in Phase 1 refactoring.
Using built-in MCP servers via config/mcp_servers.json
"""

from .base import MCPServer, ServerConfig

__all__ = [
    "MCPServer",
    "ServerConfig",
]
