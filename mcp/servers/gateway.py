"""
MCP Gateway - Central hub for MCP server communication
"""

import asyncio
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mcp.servers.browser_server import BrowserMCPServer
from mcp.servers.github_server import GitHubMCPServer
from mcp.servers.filesystem_server import FilesystemMCPServer
from mcp.servers.terminal_server import TerminalMCPServer

logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Gateway")

# Server instances
_servers: Dict[str, Any] = {}


class MCPRequest(BaseModel):
    """MCP JSON-RPC request"""

    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any] = {}


class MCPResponse(BaseModel):
    """MCP JSON-RPC response"""

    jsonrpc: str = "2.0"
    id: str
    result: Any = None
    error: Dict[str, Any] = None


@app.on_event("startup")
async def startup():
    """Initialize MCP servers"""
    logger.info("Starting MCP Gateway")

    # Initialize servers
    browser_server = BrowserMCPServer()
    await browser_server.start()
    _servers["browser"] = browser_server

    github_server = GitHubMCPServer()
    await github_server.start()
    _servers["github"] = github_server

    filesystem_server = FilesystemMCPServer()
    await filesystem_server.start()
    _servers["filesystem"] = filesystem_server

    terminal_server = TerminalMCPServer()
    await terminal_server.start()
    _servers["terminal"] = terminal_server

    logger.info(f"MCP Gateway started with {len(_servers)} servers")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown MCP servers"""
    logger.info("Shutting down MCP Gateway")

    for server in _servers.values():
        await server.stop()

    _servers.clear()


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "servers": list(_servers.keys()),
    }


@app.get("/servers")
async def list_servers():
    """List available MCP servers"""
    return {
        servers: [
            {
                "name": name,
                "tools": list(server.tools.keys()),
                "running": server.is_running,
            }
            for name, server in _servers.items()
        ]
    }


@app.post("/mcp/{server_name}")
async def handle_mcp(server_name: str, request: MCPRequest):
    """Handle MCP request for specific server"""
    if server_name not in _servers:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_name}")

    server = _servers[server_name]

    # Create transport message
    from mcp.schemas.transport import TransportMessage, MessageType

    message = TransportMessage(
        id=request.id,
        message_type=MessageType.JSONRPC_REQUEST,
        method=request.method,
        params=request.params,
    )

    # Handle message
    response = await server.handle_message(message)

    return MCPResponse(
        id=response.id,
        result=response.result,
        error=response.error,
    )


@app.get("/tools")
async def list_all_tools():
    """List all available tools across servers"""
    tools = {}

    for server_name, server in _servers.items():
        for tool_name, tool in server.tools.items():
            tools[f"{server_name}:{tool_name}"] = {
                "name": tool_name,
                "description": tool.description,
                "category": tool.category.value,
                "server": server_name,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.param_type.value,
                        "required": p.required,
                    }
                    for p in tool.parameters
                ],
            }

    return {"tools": tools}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
