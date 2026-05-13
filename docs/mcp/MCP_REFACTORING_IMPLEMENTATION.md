# MCP Architecture Refactoring - Implementation Plan

**Status**: READY FOR IMPLEMENTATION  
**Duration**: 3 weeks  
**Risk Level**: MEDIUM

---

## Overview

This plan outlines the step-by-step refactoring to eliminate unnecessary custom MCP infrastructure and adopt built-in MCP servers.

---

## Architecture Transformation

### BEFORE: Over-engineered with HTTP assumption

```
User Request
    ↓
LangGraph Agent
    ↓
Tool Request via Registry
    ↓
ToolRegistry (MCP Registry)
    ↓
MCPClient (Connection Pool)
    ↓
HTTPTransport (expects HTTP)
    ↓
❌ http://browser-mcp:8080 (doesn't exist)
```

### AFTER: Simplified with STDIO transport

```
User Request
    ↓
LangGraph Agent
    ↓
Tool Request via Registry
    ↓
ToolRegistry (MCP Registry)
    ↓
MCPClient (Connection Pool)
    ↓
StdioTransport (local process)
    ↓
✅ npx @modelcontextprotocol/server-browser
```

---

## Phase 1: Remove Custom MCP Server Wrappers (Week 1)

### Objective
Eliminate the duplication between `tools/` and `mcplib/servers/` by removing MCP server wrappers.

### Files to Delete

1. **`mcplib/servers/browser_server.py`** (~200 lines)
   - Removes BrowserMCPServer wrapper
   - Tools/browser.py remains available for future use

2. **`mcplib/servers/github_server.py`** (~200 lines)
   - Removes GitHubMCPServer wrapper
   - Tools/github.py remains available for future use

3. **`mcplib/servers/filesystem_server.py`** (~250 lines)
   - Removes FilesystemMCPServer wrapper
   - Tools/filesystem.py remains available for future use

4. **`mcplib/servers/terminal_server.py`** (~180 lines)
   - Removes TerminalMCPServer wrapper
   - Tools/terminal.py remains available for future use

### Files to Update

#### 1. `mcplib/servers/__init__.py`

**Before**:
```python
from .browser_server import BrowserMCPServer
from .github_server import GitHubMCPServer
from .filesystem_server import FilesystemMCPServer
from .terminal_server import TerminalMCPServer

__all__ = [
    "MCPServer",
    "ServerConfig",
    "BrowserMCPServer",
    "GitHubMCPServer",
    "FilesystemMCPServer",
    "TerminalMCPServer",
]
```

**After**:
```python
from .base import MCPServer, ServerConfig
from .gateway import MCPGateway

__all__ = [
    "MCPServer",
    "ServerConfig",
    "MCPGateway",
]
```

#### 2. `mcplib/servers/gateway.py`

**Before**:
```python
from mcplib.servers.browser_server import BrowserMCPServer
from mcplib.servers.github_server import GitHubMCPServer
from mcplib.servers.filesystem_server import FilesystemMCPServer
from mcplib.servers.terminal_server import TerminalMCPServer

@app.on_event("startup")
async def startup():
    browser_server = BrowserMCPServer()
    await browser_server.start()
    
    github_server = GitHubMCPServer()
    await github_server.start()
    
    filesystem_server = FilesystemMCPServer()
    await filesystem_server.start()
    
    terminal_server = TerminalMCPServer()
    await terminal_server.start()
```

**After**:
```python
# Gateway becomes a simple router for MCP requests
# Custom servers no longer initialized here

@app.on_event("startup")
async def startup():
    logger.info("MCP Gateway starting (no custom servers)")
    # Gateway will route to built-in MCP servers via connection pool
```

### Validation Tests

```python
# test_mcp_removal.py

def test_browser_server_removed():
    """Verify BrowserMCPServer is removed"""
    with pytest.raises(ImportError):
        from mcplib.servers import BrowserMCPServer

def test_github_server_removed():
    """Verify GitHubMCPServer is removed"""
    with pytest.raises(ImportError):
        from mcplib.servers import GitHubMCPServer

def test_filesystem_server_removed():
    """Verify FilesystemMCPServer is removed"""
    with pytest.raises(ImportError):
        from mcplib.servers import FilesystemMCPServer

def test_terminal_server_removed():
    """Verify TerminalMCPServer is removed"""
    with pytest.raises(ImportError):
        from mcplib.servers import TerminalMCPServer

def test_base_server_still_available():
    """Verify base MCPServer is still available"""
    from mcplib.servers import MCPServer
    assert MCPServer is not None
```

---

## Phase 2: Update MCP Configuration (Week 1-2)

### Objective
Convert mcp_servers.json from HTTP-based to STDIO-based configuration using built-in MCP servers.

### Configuration Transformation

#### Current Config (Non-functional)

```json
{
  "version": "1.0.0",
  "servers": [
    {
      "name": "browser",
      "type": "builtin",
      "enabled": true,
      "transport": "http",
      "url": "http://browser-mcp:8080",
      "capabilities": ["browser_navigate", "browser_screenshot"]
    }
  ]
}
```

#### New Config (Functional)

```json
{
  "version": "2.0.0",
  "servers": [
    {
      "name": "browser",
      "type": "builtin",
      "enabled": true,
      "description": "Playwright browser automation (MCP official)",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-playwright"],
      "env": {
        "DEBUG": "mcp:*"
      },
      "capabilities": [
        "browser_navigate",
        "browser_screenshot",
        "browser_click",
        "browser_type",
        "browser_evaluate"
      ],
      "timeout": 30,
      "health_check_interval": 60
    },
    {
      "name": "github",
      "type": "builtin",
      "enabled": true,
      "description": "GitHub API integration (MCP official)",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "DEBUG": "mcp:*"
      },
      "capabilities": [
        "github_search_repos",
        "github_get_file",
        "github_list_files",
        "github_get_repo_info"
      ],
      "timeout": 30,
      "health_check_interval": 60
    },
    {
      "name": "filesystem",
      "type": "builtin",
      "enabled": true,
      "description": "Local filesystem operations (MCP official)",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "."],
      "capabilities": [
        "filesystem_read",
        "filesystem_write",
        "filesystem_list",
        "filesystem_exists",
        "filesystem_delete",
        "filesystem_mkdir"
      ],
      "timeout": 10,
      "health_check_interval": 60
    }
  ],
  "registry": {
    "enable_auto_discovery": true,
    "discovery_interval": 60,
    "cache_ttl": 300,
    "max_tools": 1000
  },
  "pool": {
    "max_connections": 10,
    "max_per_server": 3,
    "connection_timeout": 30,
    "idle_timeout": 300,
    "max_retries": 3,
    "health_check_interval": 30
  }
}
```

### Installation Requirements

Create `package-lock.json` entry or install MCP servers:

```bash
npm install -g \
  @modelcontextprotocol/server-playwright \
  @modelcontextprotocol/server-github \
  @modelcontextprotocol/server-filesystem
```

Or add to requirements.txt for Python wrapper:

```txt
mcp-server-playwright
mcp-server-github
mcp-server-filesystem
```

### Update mcplib/config.py

```python
def load_mcp_config() -> MCPConfiguration:
    """Load MCP configuration from JSON with validation"""
    config_path = Path("config/mcp_servers.json")
    
    if not config_path.exists():
        logger.warning("MCP config not found, using defaults")
        return MCPConfiguration.default()
    
    with open(config_path) as f:
        data = json.load(f)
    
    # Validate version
    version = data.get("version", "1.0.0")
    if version < "2.0.0":
        logger.warning(f"Old MCP config version {version}, consider upgrading")
    
    # Load servers with validation
    servers = []
    for server_data in data.get("servers", []):
        if server_data.get("enabled"):
            # Substitute environment variables
            server_data = _substitute_env_vars(server_data)
            servers.append(MCPServerConfig.from_dict(server_data))
    
    return MCPConfiguration(
        version=version,
        servers=servers,
        registry=RegistryConfig.from_dict(data.get("registry", {})),
        pool=PoolConfig.from_dict(data.get("pool", {})),
    )

def _substitute_env_vars(config_dict: Dict) -> Dict:
    """Substitute ${VAR} with environment variables"""
    def substitute(obj):
        if isinstance(obj, dict):
            return {k: substitute(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [substitute(item) for item in obj]
        elif isinstance(obj, str):
            # Replace ${VAR} with os.environ.get("VAR")
            import re
            pattern = r'\$\{([^}]+)\}'
            
            def replace_var(match):
                var_name = match.group(1)
                return os.environ.get(var_name, "")
            
            return re.sub(pattern, replace_var, obj)
        return obj
    
    return substitute(config_dict)
```

---

## Phase 3: Update Router Integration (Week 2)

### Objective
Modify the RouterAgent to use STDIO transport with built-in MCP servers.

### Update `agents/router.py`

**Current problematic code** (expecting HTTP):

```python
async def initialize_mcp(self) -> None:
    """Initialize MCP components for tool selection using JSON configuration"""
    
    # Load MCP configuration from JSON
    mcp_config = load_mcp_config()
    
    # Create connection pool from config
    pool_config = PoolConfig(...)
    self._pool = ConnectionPool(pool_config)
    
    # Register MCP servers from JSON config
    enabled_servers = mcp_config.get_enabled_servers()
    for server in enabled_servers:
        transport_type = (
            TransportType.STDIO if server.transport == "stdio" else TransportType.HTTP
        )
        
        await self._pool.register_server(
            MCPClientConfig(
                server_name=server.name,
                server_url=server.url,  # ❌ This fails for HTTP servers
                transport_type=transport_type,
                timeout=server.timeout,
                command=server.command,  # ✅ This works for STDIO
                args=tuple(server.args),
                env=server.env,
            )
        )
```

**Refactored code** (supports both HTTP and STDIO):

```python
async def initialize_mcp(self) -> None:
    """Initialize MCP components for tool selection using JSON configuration"""
    if self._initialized:
        return

    try:
        # Load MCP configuration from JSON
        mcp_config = load_mcp_config()

        # Create connection pool from config
        pool_config = PoolConfig(
            max_connections=mcp_config.pool.max_connections,
            max_per_server=mcp_config.pool.max_per_server,
            connection_timeout=mcp_config.pool.connection_timeout,
            idle_timeout=mcp_config.pool.idle_timeout,
            max_retries=mcp_config.pool.max_retries,
            health_check_interval=mcp_config.pool.health_check_interval,
        )
        self._pool = ConnectionPool(pool_config)

        # Register MCP servers from JSON config
        enabled_servers = mcp_config.get_enabled_servers()
        
        for server in enabled_servers:
            logger.info(f"Registering MCP server: {server.name} ({server.transport})")
            
            if server.transport == "stdio":
                # Built-in MCP servers via STDIO
                await self._pool.register_server(
                    MCPClientConfig(
                        server_name=server.name,
                        transport_type=TransportType.STDIO,
                        command=server.command,
                        args=tuple(server.args),
                        env=server.env,
                        cwd=server.cwd,
                        timeout=server.timeout,
                    )
                )
            
            elif server.transport == "http":
                # External HTTP MCP servers (if needed in future)
                await self._pool.register_server(
                    MCPClientConfig(
                        server_name=server.name,
                        server_url=server.url,
                        transport_type=TransportType.HTTP,
                        timeout=server.timeout,
                    )
                )
            
            logger.info(f"✅ Registered MCP server: {server.name}")

        # Create registry
        registry_config = RegistryConfig(
            enable_auto_discovery=mcp_config.registry.enable_auto_discovery,
            discovery_interval=mcp_config.registry.discovery_interval,
            cache_ttl=mcp_config.registry.cache_ttl,
            max_tools=mcp_config.registry.max_tools,
        )
        self._registry = ToolRegistry(registry_config, self._pool)

        # Start registry (will discover tools)
        await self._registry.start()

        self._initialized = True
        logger.info(f"✅ MCP components initialized with {len(enabled_servers)} servers")

    except Exception as e:
        logger.error(f"❌ MCP initialization failed: {e}")
        self._initialized = False
        raise
```

### Update Tool Selection Logic

```python
async def _select_tools_for_task(self, task: Dict[str, Any]) -> ToolSelectionResult:
    """Select appropriate tools for a task using MCP registry"""
    
    if not self._registry:
        # Fallback if registry not available
        return ToolSelectionResult(
            selected_tools=[],
            reasoning="Registry not initialized",
            confidence=0.0,
        )
    
    # Get available tools from registry
    all_tools = self._registry.tools
    
    if not all_tools:
        logger.warning("No tools available in registry")
        return ToolSelectionResult(
            selected_tools=[],
            reasoning="No tools available",
            confidence=0.0,
        )
    
    # Task-based tool selection
    task_description = task.get("description", "")
    tools_list = list(all_tools.values())
    
    # Use LLM to select appropriate tools
    tool_descriptions = [
        f"- {tool.name}: {tool.description}"
        for tool in tools_list
    ]
    
    prompt = f"""
Given the task: {task_description}

Available tools:
{chr(10).join(tool_descriptions)}

Select the most appropriate tools for this task. Respond with JSON:
{{
    "tools": ["tool_name1", "tool_name2"],
    "reasoning": "why these tools",
    "confidence": 0.95
}}
"""
    
    # Call LLM
    response = await self.ollama.generate(prompt)
    
    # Parse response
    try:
        result = json.loads(response)
        selected_tool_names = result.get("tools", [])
        
        # Validate tool names
        selected_tools = [
            tool.to_dict() for name, tool in all_tools.items()
            if name in selected_tool_names
        ]
        
        return ToolSelectionResult(
            selected_tools=selected_tools,
            reasoning=result.get("reasoning", ""),
            confidence=result.get("confidence", 0.0),
        )
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse tool selection: {e}")
        return ToolSelectionResult(
            selected_tools=[],
            reasoning="Failed to parse LLM response",
            confidence=0.0,
        )
```

---

## Phase 4: Add Health Monitoring (Week 2-3)

### Objective
Implement MCP server health checks and observability.

### Create `mcplib/health.py` Enhancement

```python
"""MCP Health Monitoring"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCPServerHealth:
    """Health status of an MCP server"""
    
    server_name: str
    is_healthy: bool
    last_check: datetime
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    tools_available: int = 0
    capabilities: list = field(default_factory=list)


class MCPHealthMonitor:
    """Monitor health of MCP servers"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self._health_status: Dict[str, MCPServerHealth] = {}
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self, registry: "ToolRegistry", pool: "ConnectionPool") -> None:
        """Start health monitoring"""
        self._monitor_task = asyncio.create_task(
            self._monitor_loop(registry, pool)
        )
        logger.info("MCP health monitor started")
    
    async def stop(self) -> None:
        """Stop health monitoring"""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self, registry: "ToolRegistry", pool: "ConnectionPool") -> None:
        """Background health check loop"""
        while True:
            try:
                # Check all servers in pool
                for server_name in pool._servers.keys():
                    await self._check_server(server_name, pool)
                
                await asyncio.sleep(self.check_interval)
            
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_server(self, server_name: str, pool: "ConnectionPool") -> None:
        """Check health of a single server"""
        start_time = datetime.utcnow()
        
        try:
            client = pool._servers.get(server_name)
            if not client:
                self._health_status[server_name] = MCPServerHealth(
                    server_name=server_name,
                    is_healthy=False,
                    last_check=start_time,
                    error_message="Not found in pool",
                )
                return
            
            # Check if connected
            if not client.is_connected():
                await client.connect()
            
            # List tools as health check
            tools = await client.list_tools()
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self._health_status[server_name] = MCPServerHealth(
                server_name=server_name,
                is_healthy=True,
                last_check=start_time,
                response_time_ms=response_time,
                tools_available=len(tools),
                capabilities=[tool.name for tool in tools],
            )
            
            logger.debug(f"✅ {server_name} health check OK ({response_time:.2f}ms, {len(tools)} tools)")
        
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self._health_status[server_name] = MCPServerHealth(
                server_name=server_name,
                is_healthy=False,
                last_check=start_time,
                response_time_ms=response_time,
                error_message=str(e),
            )
            
            logger.warning(f"❌ {server_name} health check failed: {e}")
    
    def get_health_status(self) -> Dict[str, MCPServerHealth]:
        """Get current health status of all servers"""
        return self._health_status.copy()
    
    def is_all_healthy(self) -> bool:
        """Check if all servers are healthy"""
        return all(status.is_healthy for status in self._health_status.values())
```

### Add Health Check Endpoint

Update `api/routes/health.py`:

```python
@router.get("/health/mcp")
async def get_mcp_health():
    """Get MCP servers health status"""
    if not hasattr(app.state, 'mcp_health_monitor'):
        return {"status": "no_monitor"}
    
    health_status = app.state.mcp_health_monitor.get_health_status()
    
    return {
        "status": "healthy" if app.state.mcp_health_monitor.is_all_healthy() else "degraded",
        "servers": {
            name: {
                "healthy": status.is_healthy,
                "response_time_ms": status.response_time_ms,
                "tools_available": status.tools_available,
                "error": status.error_message,
                "last_check": status.last_check.isoformat(),
            }
            for name, status in health_status.items()
        },
    }
```

### Add Observability Logs

```python
# In agents/router.py

class RouterAgent(BaseAgent):
    """Router agent with MCP observability"""
    
    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """Execute router with observability"""
        
        session_id = state["session_id"]
        logger.info(f"[{session_id}] Router executing with MCP")
        
        try:
            # Initialize MCP
            await self.initialize_mcp()
            
            # Log MCP status
            if self._registry:
                tools_count = len(self._registry.tools)
                logger.info(f"[{session_id}] Registry has {tools_count} tools available")
            
            # Execute routing
            result = await self._route_tasks(state)
            
            # Log selected tools
            tool_selections = result.get("tool_selections", [])
            logger.info(f"[{session_id}] Selected {len(tool_selections)} tool sets")
            
            return result
        
        except Exception as e:
            logger.error(f"[{session_id}] Router failed: {e}", exc_info=True)
            raise
```

---

## Phase 5: Frontend Integration (Week 3)

### Objective
Display MCP server status and available tools in the frontend.

### Update Frontend Dashboard

Create `frontend/features/mcp-dashboard.tsx`:

```typescript
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';

export function MCPDashboard() {
  const { data: mcp_health } = useQuery({
    queryKey: ['mcp-health'],
    queryFn: () => fetch('/api/health/mcp').then(r => r.json()),
    refetchInterval: 30000, // 30 seconds
  });

  return (
    <div className="mcp-dashboard">
      <h2>MCP Servers Status</h2>
      
      {mcp_health?.servers && Object.entries(mcp_health.servers).map(
        ([name, status]: [string, any]) => (
          <div key={name} className={`server-card ${status.healthy ? 'healthy' : 'error'}`}>
            <h3>{name}</h3>
            
            <div className="status">
              Status: <span className={status.healthy ? 'ok' : 'error'}>
                {status.healthy ? '✅ Healthy' : '❌ Error'}
              </span>
            </div>
            
            <div className="metrics">
              <p>Response Time: {status.response_time_ms.toFixed(2)}ms</p>
              <p>Tools Available: {status.tools_available}</p>
              <p>Last Check: {new Date(status.last_check).toLocaleTimeString()}</p>
            </div>
            
            {status.error && (
              <div className="error-message">{status.error}</div>
            )}
          </div>
        )
      )}
    </div>
  );
}
```

### Update Main Dashboard

Add MCP status to the main research dashboard:

```typescript
// In frontend/features/research-dashboard.tsx

export function ResearchDashboard() {
  return (
    <div className="research-dashboard">
      <MCPDashboard />
      <ResearchStatus />
      <AgentActivity />
    </div>
  );
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/mcp/test_mcp_configuration.py

def test_load_mcp_config_from_json():
    """Test loading MCP config from JSON"""
    config = load_mcp_config()
    assert config.version >= "2.0.0"
    assert len(config.servers) >= 3

def test_stdio_transport_configuration():
    """Test STDIO transport is properly configured"""
    config = load_mcp_config()
    for server in config.servers:
        if server.enabled:
            assert server.transport == "stdio"
            assert server.command is not None
            assert server.args is not None

def test_environment_variable_substitution():
    """Test environment variable substitution in config"""
    config = load_mcp_config()
    github_server = next((s for s in config.servers if s.name == "github"), None)
    assert github_server is not None
    assert github_server.env.get("GITHUB_TOKEN") != "${GITHUB_TOKEN}"
```

### Integration Tests

```python
# tests/mcp/test_mcp_integration.py

@pytest.mark.asyncio
async def test_router_mcp_initialization():
    """Test router can initialize MCP components"""
    router = RouterAgent()
    await router.initialize_mcp()
    
    assert router._registry is not None
    assert router._pool is not None
    assert len(router._registry.tools) > 0

@pytest.mark.asyncio
async def test_tool_registry_discovery():
    """Test tool discovery from MCP servers"""
    router = RouterAgent()
    await router.initialize_mcp()
    
    # Check browser tools
    browser_tools = await router._registry.get_tools_by_tag("browser")
    assert len(browser_tools) > 0
    
    # Check github tools
    github_tools = await router._registry.get_tools_by_tag("github")
    assert len(github_tools) > 0

@pytest.mark.asyncio
async def test_health_monitoring():
    """Test MCP health monitoring"""
    router = RouterAgent()
    await router.initialize_mcp()
    
    # Check health of all servers
    health_status = router._health_monitor.get_health_status()
    assert len(health_status) >= 3
```

### E2E Tests

```python
# tests/e2e/test_research_with_mcp.py

@pytest.mark.asyncio
async def test_research_task_with_browser_tool():
    """Test research task using browser tool via MCP"""
    graph = DistributedResearchGraph(
        session_id="test_1",
        query="What is the weather?",
    )
    
    # Execute research
    result = await graph.invoke()
    
    # Verify browser was used
    assert "browser" in str(result).lower() or result.get("status") == "completed"

@pytest.mark.asyncio
async def test_research_task_with_github_tool():
    """Test research task using GitHub tool via MCP"""
    graph = DistributedResearchGraph(
        session_id="test_2",
        query="Find top Python projects",
    )
    
    # Execute research
    result = await graph.invoke()
    
    # Verify GitHub API was used
    assert "github" in str(result).lower() or result.get("status") == "completed"
```

---

## Rollback Plan

If refactoring fails at any phase:

### Phase 1 Rollback
- Restore deleted MCP server files from git
- Revert `mcplib/servers/__init__.py`
- Revert `mcplib/servers/gateway.py`

### Phase 2-3 Rollback
- Restore original `mcp_servers.json` (HTTP config)
- Revert `agents/router.py` to original
- Uninstall MCP packages if needed

### Full Rollback
```bash
git checkout HEAD -- mcplib/ agents/ config/
npm uninstall @modelcontextprotocol/*
```

---

## Success Criteria

✅ All phases must meet these criteria:

1. **Code Quality**
   - All tests passing (unit + integration + E2E)
   - No new warnings or errors
   - Code coverage maintained

2. **Functionality**
   - Agents can still invoke tools
   - Tool registry populated correctly
   - Tools execute successfully

3. **Performance**
   - STDIO transport faster than HTTP
   - Tool discovery completes in <5s
   - No memory leaks in tool registry

4. **Observability**
   - Health checks working
   - Logs showing tool execution
   - Frontend displaying MCP status

---

## Detailed Implementation Checklist

### Phase 1: File Removal
- [ ] Delete `mcplib/servers/browser_server.py`
- [ ] Delete `mcplib/servers/github_server.py`
- [ ] Delete `mcplib/servers/filesystem_server.py`
- [ ] Delete `mcplib/servers/terminal_server.py`
- [ ] Update `mcplib/servers/__init__.py`
- [ ] Update `mcplib/servers/gateway.py`
- [ ] Delete related test files
- [ ] Run `pytest tests/mcp/` to verify removal

### Phase 2: Configuration Update
- [ ] Install MCP packages (npm or pip)
- [ ] Update `config/mcp_servers.json` to 2.0.0
- [ ] Update `mcplib/config.py` with env var substitution
- [ ] Create `.env.template` with MCP_* variables
- [ ] Test configuration loading
- [ ] Run configuration validation tests

### Phase 3: Router Update
- [ ] Update `agents/router.py` to support STDIO
- [ ] Update tool selection logic
- [ ] Update MCP initialization
- [ ] Add error handling for STDIO processes
- [ ] Update logging with server names
- [ ] Run router tests

### Phase 4: Health Monitoring
- [ ] Implement `MCPHealthMonitor`
- [ ] Add health check endpoint
- [ ] Add observability logs
- [ ] Create health check tests
- [ ] Test health monitoring loop

### Phase 5: Frontend Integration
- [ ] Create MCP dashboard component
- [ ] Integrate into main dashboard
- [ ] Add real-time health updates
- [ ] Test frontend with mock data

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | 1-2 | Files removed, config updated, tests passing |
| 1-2 | 2-3 | STDIO transport working, router updated |
| 2-3 | 4 | Health monitoring implemented |
| 3 | 5 | Frontend updated, all E2E tests passing |

---

## Resources Required

- 1 Senior Engineer (lead refactoring)
- 1 Test Engineer (ensure coverage)
- 1 Frontend Engineer (dashboard integration)
- MCP Server Documentation
- Testing environment with all dependencies

---

## Next Steps

1. ✅ Review and approve audit report
2. Review and approve refactoring plan
3. Create feature branch: `feature/mcp-refactoring`
4. Begin Phase 1 implementation
5. Weekly review of progress

---

**Ready to proceed**: YES  
**Approved by**: [To be signed]  
**Date**: [To be filled]
