"""
MCP Gateway - Central hub for MCP server communication

NOTE: Custom MCP servers removed in Phase 1 refactoring.
Gateway now routes to built-in MCP servers via connection pool.
"""

import asyncio
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
    """Initialize MCP Gateway"""
    logger.info("Starting MCP Gateway")
    logger.info("✅ Custom MCP servers removed (Phase 1 refactoring)")
    logger.info("📦 Using built-in MCP servers via connection pool (see config/mcp_servers.json)")


@app.on_event("shutdown")
async def shutdown():
    """Shutdown MCP Gateway"""
    logger.info("Shutting down MCP Gateway")
    # Custom servers removed in Phase 1


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
    from mcplib.schemas.transport import TransportMessage, MessageType

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
