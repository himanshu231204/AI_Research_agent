# MCP Architecture Audit Report

**Date**: May 14, 2026  
**Status**: ✅ AUDIT COMPLETE  
**Severity**: MEDIUM - Unnecessary complexity, not breaking

---

## Executive Summary

The AI Research Agent platform implements a **custom MCP server infrastructure** that wraps custom tool implementations. While the JSON-based configuration system is well-designed, the actual MCP servers are **over-engineered** and should be replaced with built-in MCP servers to reduce complexity and maintenance burden.

### Key Findings

| Finding | Status | Action |
|---------|--------|--------|
| Custom MCP servers exist | ✅ Confirmed | Remove & replace |
| JSON config exists | ✅ Present | Update endpoints |
| HTTP transport assumption | ⚠️ Issue | Convert to STDIO |
| Duplication in tools/ & mcplib/servers/ | ⚠️ Issue | Remove duplication |
| Router integration works | ✅ Confirmed | Update for built-in servers |
| Frontend MCP display | ⚠️ Partial | Needs enhancement |

---

## 1. Current Architecture Analysis

### 1.1 Custom MCP Servers

The platform implements **4 custom MCP servers**:

```
mcplib/servers/
├── browser_server.py       (BrowserMCPServer)
├── github_server.py        (GitHubMCPServer)
├── filesystem_server.py    (FilesystemMCPServer)
├── terminal_server.py      (TerminalMCPServer)
└── gateway.py              (MCP Gateway - initializes all servers)
```

### 1.2 Duplication Pattern

```
LAYER 1: Custom Tools              LAYER 2: MCP Wrappers          LAYER 3: Configuration
┌────────────────────────┐         ┌──────────────────────┐        ┌─────────────────────┐
│ tools/browser.py       │────────→│ BrowserMCPServer     │───────→│ mcp_servers.json    │
│ tools/github.py        │────────→│ GitHubMCPServer      │        │ (HTTP transport)    │
│ tools/filesystem.py    │────────→│ FilesystemMCPServer  │        │                     │
│ tools/terminal.py      │────────→│ TerminalMCPServer    │        │ Expected endpoints: │
│                        │         │                      │        │ - browser-mcp:8080  │
│ Result Objects         │         │ MCP Protocol Layer   │        │ - github-mcp:8080   │
│ + error handling       │         │ + tool registration  │        │ - filesystem-mcp:80 │
│ + execution tracking   │         │ + JSON-RPC marshaling│        │ - terminal-mcp:8080 │
└────────────────────────┘         └──────────────────────┘        └─────────────────────┘
       ↑                                    ↑                              ↑
       │                                    │                              │
   CUSTOM CODE                        CUSTOM CODE                    CONFIGURATION
   (unnecessary)                      (over-engineered)              (mismatches reality)
```

### 1.3 Configuration vs. Reality

**mcp_servers.json expects:**
```json
{
  "servers": [
    {
      "name": "browser",
      "transport": "http",
      "url": "http://browser-mcp:8080"  // ❌ These services don't exist
    }
  ]
}
```

**Actual state:**
- ❌ No HTTP MCP services running on those ports
- ❌ No Docker containers for MCP servers
- ✅ Custom MCP server classes exist but aren't instantiated as HTTP services
- ✅ Gateway.py initializes servers locally but doesn't expose them

### 1.4 Integration Points

```
agents/router.py
    ↓
1. Loads config from mcp_servers.json
2. Creates ConnectionPool (expects HTTP connections)
3. Registers MCP servers (tries to connect to HTTP URLs)
4. Creates ToolRegistry
5. Loads tools from config
    ↓
agents/planner.py, agents/reflection.py, etc.
    ↓
Attempt to use tools via registry
    ↓
FAILS because HTTP services don't exist
```

---

## 2. Detected Custom MCP Servers

### 2.1 BrowserMCPServer

**File**: [mcplib/servers/browser_server.py](../../mcplib/servers/browser_server.py)

**Wraps**: [tools/browser.py](../../tools/browser.py) → BrowserTool using Playwright

**Tools Implemented**:
- `browser_navigate` - Navigate to URL
- `browser_screenshot` - Take screenshot
- `browser_click` - Click element
- `browser_type` - Type text
- `browser_evaluate` - Execute JavaScript

**Config from JSON**:
```json
{
  "name": "browser",
  "type": "builtin",
  "transport": "http",
  "url": "http://browser-mcp:8080",
  "capabilities": ["browser_navigate", "browser_screenshot", "browser_click", "browser_type", "browser_evaluate"]
}
```

**Status**: ❌ OVER-ENGINEERED
- Native Playwright MCP server available
- Custom wrapper adds unnecessary complexity
- No performance benefit

**Action**: REMOVE and use built-in Playwright MCP server

---

### 2.2 GitHubMCPServer

**File**: [mcplib/servers/github_server.py](../../mcplib/servers/github_server.py)

**Wraps**: [tools/github.py](../../tools/github.py) → GitHubTool using GitHub API

**Tools Implemented**:
- `github_search_repos` - Search repositories
- `github_get_file` - Get file from repo
- `github_list_files` - List files in repo
- `github_get_repo_info` - Get repository info

**Config from JSON**:
```json
{
  "name": "github",
  "type": "builtin",
  "transport": "http",
  "url": "http://github-mcp:8080",
  "capabilities": ["github_search_repos", "github_get_file", "github_list_files", "github_get_repo_info"]
}
```

**Status**: ❌ OVER-ENGINEERED
- Official GitHub MCP server available
- Custom implementation duplicates functionality
- No special authentication handling

**Action**: REMOVE and use official GitHub MCP server

---

### 2.3 FilesystemMCPServer

**File**: [mcplib/servers/filesystem_server.py](../../mcplib/servers/filesystem_server.py)

**Wraps**: [tools/filesystem.py](../../tools/filesystem.py) → FilesystemTool for local file operations

**Tools Implemented**:
- `filesystem_read` - Read file
- `filesystem_write` - Write file
- `filesystem_list` - List directory
- `filesystem_exists` - Check existence
- `filesystem_delete` - Delete file
- `filesystem_mkdir` - Create directory

**Config from JSON**:
```json
{
  "name": "filesystem",
  "type": "builtin",
  "transport": "http",
  "url": "http://filesystem-mcp:8080",
  "capabilities": ["filesystem_read", "filesystem_write", "filesystem_list", "filesystem_exists", "filesystem_delete", "filesystem_mkdir"]
}
```

**Status**: ❌ OVER-ENGINEERED
- Official filesystem MCP server available
- Custom implementation has redundant path validation
- No special security features beyond base implementation

**Action**: REMOVE and use official filesystem MCP server

---

### 2.4 TerminalMCPServer

**File**: [mcplib/servers/terminal_server.py](../../mcplib/servers/terminal_server.py)

**Wraps**: [tools/terminal.py](../../tools/terminal.py) → TerminalTool for safe command execution

**Tools Implemented**:
- `terminal_execute` - Execute shell command
- `terminal_run_script` - Run shell script

**Config from JSON**:
```json
{
  "name": "terminal",
  "type": "builtin",
  "transport": "http",
  "url": "http://terminal-mcp:8080",
  "capabilities": ["terminal_execute", "terminal_run_script"]
}
```

**Status**: ❌ OVER-ENGINEERED
- Has command blocking/whitelisting (useful)
- Official terminal MCP server available but needs security config
- Custom implementation provides value-add security

**Action**: EVALUATE - Keep if official MCP doesn't have security controls, otherwise remove

---

## 3. Duplication Analysis

### 3.1 Code Duplication

| Component | Lines | Status | Note |
|-----------|-------|--------|------|
| tools/browser.py | ~500 | Redundant | Playwright async wrapper |
| mcplib/servers/browser_server.py | ~200 | Redundant | Wraps browser.py |
| tools/github.py | ~300 | Redundant | GitHub API wrapper |
| mcplib/servers/github_server.py | ~200 | Redundant | Wraps github.py |
| tools/filesystem.py | ~350 | Redundant | File system wrapper |
| mcplib/servers/filesystem_server.py | ~250 | Redundant | Wraps filesystem.py |
| tools/terminal.py | ~200 | Useful | Has security controls |
| mcplib/servers/terminal_server.py | ~180 | Redundant | Wraps terminal.py |
| **TOTAL** | **~2,180 lines** | | |

**Can be reduced to: ~300 lines** (terminal tool security controls only)

### 3.2 Functional Duplication

```
BrowserTool                    BrowserMCPServer
├── __init__                  ├── __init__
├── async start()             ├── async _setup()      ← calls start()
├── async stop()              ├── async _teardown()   ← calls stop()
├── async navigate()          └── _register_tools()   ← wraps navigate()
├── async screenshot()            as MCP tool
├── async click()
├── async type()
└── async evaluate()
        ↓
        All the same logic!
```

---

## 4. Root Cause Analysis

### Why This Architecture Exists

1. **Initial Design**: Started with custom tools
2. **Standards Push**: Added MCP layer for tool standardization
3. **Incomplete Implementation**: Created custom MCP servers but never deployed as HTTP services
4. **Configuration Ready**: JSON config prepared but pointing to non-existent services
5. **Router Updated**: Router code updated to use JSON config but fails to connect

### What Went Wrong

| Decision | Rationale | Problem |
|----------|-----------|---------|
| Custom tool implementations | Flexibility | Duplication |
| Wrap in MCP servers | Standardization | Over-engineering |
| HTTP transport config | Microservices pattern | Services don't exist |
| Keep both layers | Gradual migration | Technical debt |

---

## 5. Architecture Issues

### 5.1 Structural Issues

```
Issue 1: Unnecessary Abstraction Layers
┌─────────────────────────────────────────────────────┐
│ Agent needs to use browser automation                │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼ (calls)
    ┌─────────────────────────────────────┐
    │ ToolRegistry (MCP Registry)         │
    └────────────┬────────────────────────┘
                 │
                 ▼ (looks up)
    ┌─────────────────────────────────────┐
    │ MCPClient (connection pool)          │
    └────────────┬────────────────────────┘
                 │
                 ▼ (sends to)
    ┌─────────────────────────────────────┐
    │ HTTPTransport (expects HTTP service)│
    └────────────┬────────────────────────┘
                 │
                 ▼ (connects to)
    ┌─────────────────────────────────────┐
    │ http://browser-mcp:8080 ❌ MISSING  │
    └─────────────────────────────────────┘

Better approach:
┌─────────────────────────────────────────────────────┐
│ Agent needs to use browser automation                │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼ (calls)
    ┌─────────────────────────────────────┐
    │ Built-in Playwright MCP Server      │
    │ (via StdioTransport)                │
    └─────────────────────────────────────┘
```

### 5.2 Configuration Issues

```
mcp_servers.json specifies:           Reality:
- "transport": "http"                 - No HTTP services
- "url": "http://browser-mcp:8080"    - Custom servers exist locally
                                      - But not exposed as HTTP
```

---

## 6. Impact Assessment

### 6.1 What Works Today

✅ **Configuration System**
- JSON schema is well-designed
- Registry/discovery works
- Dynamic loading implemented

✅ **Router Agent**
- MCP initialization code exists
- Tool selection logic implemented
- Capability-based routing ready

❌ **What's Broken**
- HTTP services don't exist
- Router tries to connect → fails silently
- Tool registry loads empty
- Agents can't use registered tools

### 6.2 Which Agents Are Affected

```
Planner Agent          ✅ Works (doesn't use MCP tools)
Router Agent           ⚠️ Partial (MCP init fails)
Web Research Agent     ✅ Works (uses Tavily/Brave directly)
GitHub Research Agent  ❌ BROKEN (expects GitHub MCP server)
PDF/RAG Agent          ✅ Works (uses ChromaDB directly)
Browser Automation     ❌ BROKEN (expects Browser MCP server)
Memory Agent           ✅ Works (uses Redis/Postgres directly)
Reflection Agent       ✅ Works (doesn't use MCP tools)
Writer Agent           ✅ Works (doesn't use MCP tools)
Citation Agent         ✅ Works (doesn't use MCP tools)
```

---

## 7. Recommended Refactoring Strategy

### Phase 1: Simplify Tool Implementations (Week 1)

**Objective**: Remove duplication between `tools/` and `mcplib/servers/`

**Actions**:
1. Remove `mcplib/servers/browser_server.py`
2. Remove `mcplib/servers/github_server.py`
3. Remove `mcplib/servers/filesystem_server.py`
4. Remove `mcplib/servers/terminal_server.py`
5. Keep `tools/` for potential future use or local execution

**Outcome**:
- 4 files removed (~600 lines)
- Custom tool implementations still available
- No functional change to agents

---

### Phase 2: Adopt Built-In MCP Servers (Week 1-2)

**Objective**: Replace custom servers with official MCP implementations

**Configuration**:
```json
{
  "version": "2.0.0",
  "servers": [
    {
      "name": "browser",
      "type": "builtin",
      "enabled": true,
      "description": "Playwright browser automation",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-playwright"],
      "capabilities": ["browser_navigate", "browser_screenshot", "browser_click"],
      "timeout": 30
    },
    {
      "name": "github",
      "type": "builtin",
      "enabled": true,
      "description": "GitHub API integration",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github", "--token", "${GITHUB_TOKEN}"],
      "capabilities": ["github_search_repos", "github_get_file"],
      "timeout": 30,
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    {
      "name": "filesystem",
      "type": "builtin",
      "enabled": true,
      "description": "Local filesystem operations",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "."],
      "capabilities": ["filesystem_read", "filesystem_write", "filesystem_list"],
      "timeout": 10
    }
  ],
  "registry": {
    "enable_auto_discovery": true,
    "discovery_interval": 60,
    "cache_ttl": 300,
    "max_tools": 1000
  }
}
```

**Actions**:
1. Install MCP servers via npm
2. Update mcp_servers.json configuration
3. Change transport from HTTP to STDIO
4. Update router to use STDIO transport

---

### Phase 3: Update Router Integration (Week 2)

**Objective**: Make router work with built-in MCP servers

**Updates needed** in [agents/router.py](../../agents/router.py):
```python
# Before: Expects HTTP services
await self._pool.register_server(
    MCPClientConfig(
        server_name="browser",
        server_url="http://browser-mcp:8080",  # ❌ HTTP
        transport_type=TransportType.HTTP,
    )
)

# After: Uses STDIO local processes
await self._pool.register_server(
    MCPClientConfig(
        server_name="browser",
        transport_type=TransportType.STDIO,
        command="npx",
        args=("@modelcontextprotocol/server-playwright",),
    )
)
```

---

### Phase 4: Health Monitoring & Observability (Week 2-3)

**Objective**: Add health checks for MCP servers

**Implementation**:
1. Add health check endpoint to `mcplib/health.py`
2. Implement MCP server capability detection
3. Add observability logs for tool execution
4. Frontend dashboard integration

**Metrics to track**:
- Server availability
- Tool execution latency
- Tool error rates
- Capability discovery results

---

### Phase 5: Frontend Integration (Week 3)

**Objective**: Update frontend to display MCP state

**Display**:
- Active MCP servers
- Available tools
- Server health status
- Tool execution activity

---

## 8. Validation Checklist

### Pre-Refactoring

- [ ] All tests passing
- [ ] All agents functional
- [ ] Current architecture documented
- [ ] Backup created

### Phase 1: Simplification

- [ ] Custom MCP servers removed
- [ ] Router still loads config
- [ ] No compilation errors
- [ ] Unit tests for removed code deleted

### Phase 2: Built-In Adoption

- [ ] MCP servers installed
- [ ] mcp_servers.json updated
- [ ] STDIO transport working
- [ ] Tool discovery working

### Phase 3: Router Update

- [ ] Router loads built-in servers
- [ ] Tools registered in registry
- [ ] Tool selection working
- [ ] Router tests updated

### Phase 4: Health Monitoring

- [ ] Health checks implemented
- [ ] Observability logs in place
- [ ] Dashboard updated
- [ ] E2E tests passing

### Phase 5: Validation

- [ ] All agents working
- [ ] All tools accessible
- [ ] Distributed execution OK
- [ ] Frontend displays MCP state correctly

---

## 9. Benefits of Refactoring

| Benefit | Impact | Effort |
|---------|--------|--------|
| **Reduced Code** | ~1,900 lines removed | Low |
| **Simpler Architecture** | 2-3 layers → 1 layer | Medium |
| **Better Performance** | HTTP → STDIO (local) | Low |
| **Official Support** | Maintained by Anthropic | N/A |
| **Easier Debugging** | Built-in MCP is well-documented | Low |
| **Future Extensibility** | New MCP servers easier to add | Low |
| **Test Coverage** | Use official MCP tests | Low |

---

## 10. Migration Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| Tool API changes | Medium | Update agents incrementally, test thoroughly |
| Temporary breakage | Medium | Phase migration, maintain fallbacks |
| Performance regression | Low | Profile before/after STDIO vs HTTP |
| Capability gaps | Low | Keep custom tools as fallback |
| Configuration errors | Medium | Extensive testing, validation schema |

---

## 11. Timeline & Deliverables

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | 1-2 | Remove custom servers, Update config, Tests updated |
| 1-2 | 2-3 | Router updated, STDIO transport working |
| 2-3 | 4-5 | Health monitoring, Frontend integration |
| 3 | 5 | Complete validation, All tests passing |

---

## 12. Conclusion

The current MCP architecture is **well-intentioned but over-engineered**. The system wraps custom tools in custom MCP servers that aren't exposed as services, creating unnecessary complexity and duplication.

By adopting **built-in MCP servers** and using **STDIO transport**, we can:
- ✅ Remove 1,900 lines of code
- ✅ Simplify the tool layer
- ✅ Use officially maintained MCP servers
- ✅ Maintain all existing functionality
- ✅ Improve long-term maintainability

**Recommendation**: Proceed with Phase 1-5 refactoring as outlined.

---

## Appendix A: File Structure Changes

### Files to Remove

```
mcplib/servers/
├── browser_server.py          ← DELETE
├── github_server.py           ← DELETE
├── filesystem_server.py       ← DELETE
├── terminal_server.py         ← DELETE
└── (keep: base.py, gateway.py, browser_sandbox.py)
```

### Files to Update

```
config/
├── mcp_servers.json           ← UPDATE (use STDIO, not HTTP)

agents/
├── router.py                  ← UPDATE (STDIO transport)

mcplib/servers/
├── __init__.py                ← UPDATE (remove imports)

tests/
├── mcp/                       ← UPDATE (remove deleted server tests)
```

### Files to Create

```
docs/
├── mcp/MCP_REFACTORING_GUIDE.md        ← NEW

mcplib/
├── health.py (enhance)                  ← UPDATE (add MCP health)

observability/
├── mcp_observability.py                 ← NEW (MCP metrics)
```

---

## Appendix B: Configuration Examples

### Current (Broken) Config

```json
{
  "servers": [
    {
      "name": "browser",
      "type": "builtin",
      "transport": "http",
      "url": "http://browser-mcp:8080"  // ❌ Doesn't exist
    }
  ]
}
```

### New (Working) Config

```json
{
  "servers": [
    {
      "name": "browser",
      "type": "builtin",
      "transport": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-playwright"],
      "capabilities": ["browser_navigate", "browser_screenshot", "browser_click"],
      "timeout": 30
    }
  ]
}
```

---

**Report Generated**: 2026-05-14  
**Audit Status**: ✅ COMPLETE  
**Next Step**: Review findings and approve refactoring plan
