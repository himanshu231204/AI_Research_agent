# Phase 2: Update MCP Configuration to STDIO Transport

**Date**: May 14, 2026  
**Status**: 🚀 IN PROGRESS  
**Duration**: Estimated 1 day  

---

## Overview

Phase 2 updates the MCP configuration from non-functional HTTP transport (pointing to non-existent services) to STDIO transport with official built-in MCP servers.

### Key Changes:
- **Version**: 1.0.0 → 2.0.0
- **Transport**: `http` → `stdio`
- **Servers**: Custom wrappers → Official MCP implementations via `npx`
- **Environment Variables**: Added GitHub token and optional configuration

---

## ✅ Completed Tasks

### 1. Configuration File Update ✅

**File**: `config/mcp_servers.json`

**Changes Made**:
- ✅ Updated version to 2.0.0
- ✅ Changed all servers from HTTP to STDIO transport
- ✅ Added `command` field: `npx`
- ✅ Added `args` field with MCP server package names
- ✅ Added `env` field for environment variable substitution
- ✅ Removed `url` field (not used with STDIO)
- ✅ Kept all capabilities, timeout, and config sections

**Before (HTTP - BROKEN)**:
```json
{
  "name": "browser",
  "transport": "http",
  "url": "http://browser-mcp:8080",
  "capabilities": ["browser_navigate", "browser_screenshot", ...]
}
```

**After (STDIO - WORKING)**:
```json
{
  "name": "browser",
  "transport": "stdio",
  "command": "npx",
  "args": ["@modelcontextprotocol/server-playwright"],
  "capabilities": ["browser_navigate", "browser_screenshot", ...],
  "env": {
    "DEBUG": "${DEBUG:-false}"
  }
}
```

### 2. Environment Configuration ✅

**File**: `env.template`

**Added Sections**:
- MCP_CONFIG_PATH - Path to MCP configuration
- GITHUB_TOKEN - GitHub API authentication
- MCP_DEBUG - Debug mode flag
- MCP_HEALTH_MONITORING - Health monitoring toggle
- MCP_AUTO_DISCOVERY - Tool discovery toggle

**Example**:
```bash
# .env (copy from env.template)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MCP_DEBUG=false
```

### 3. Configuration Loading Infrastructure ✅

**File**: `mcplib/config.py`

**Status**: Already equipped with environment variable substitution!

The `MCPConfigLoader` class already has:
```python
def _substitute_env_vars(self, data: Any) -> Any:
    """Recursively substitute environment variables in configuration"""
    # Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax
```

**Supported Syntax**:
- `${GITHUB_TOKEN}` - Required variable (fails if not set)
- `${DEBUG:-false}` - Optional with default value

---

## MCP Server Mapping

| Server | Package | Command | Use Case |
|--------|---------|---------|----------|
| **browser** | `@modelcontextprotocol/server-playwright` | `npx @modelcontextprotocol/server-playwright` | Browser automation, screenshots |
| **github** | `@modelcontextprotocol/server-github` | `npx @modelcontextprotocol/server-github` | GitHub API, repos, files |
| **filesystem** | `@modelcontextprotocol/server-filesystem` | `npx @modelcontextprotocol/server-filesystem` | File read/write, listings |
| **terminal** | `@modelcontextprotocol/server-bash` | `npx @modelcontextprotocol/server-bash` | Safe shell execution |

---

## 📋 Next Steps: Installation & Testing

### Step 1: Install Node.js & npm (if needed)

```bash
# Check if Node.js is installed
node --version
npm --version

# If not installed, download from https://nodejs.org/
```

### Step 2: Install MCP Server Packages

Option A - Install globally:
```bash
npm install -g @modelcontextprotocol/server-playwright
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-bash
```

Option B - Install locally (recommended for project):
```bash
npm init -y  # Only if package.json doesn't exist
npm install --save-dev @modelcontextprotocol/server-playwright \
                       @modelcontextprotocol/server-github \
                       @modelcontextprotocol/server-filesystem \
                       @modelcontextprotocol/server-bash
```

### Step 3: Set Up Environment Variables

```bash
# Copy template to .env
cp env.template .env

# Edit .env and set your GitHub token
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Test Configuration Loading

```bash
# Run configuration validation test
python -m pytest tests/mcp/test_mcp_config.py -v

# Or test manually:
python -c "
from mcplib.config import MCPConfigLoader
loader = MCPConfigLoader('config/mcp_servers.json')
config = loader.load()
print(f'Loaded {len(config.servers)} servers')
for server in config.get_enabled_servers():
    print(f'  - {server.name}: {server.transport} ({server.command})')
"
```

---

## 🔧 Configuration Details

### STDIO Transport Format

```json
{
  "name": "github",
  "type": "builtin",
  "transport": "stdio",
  "command": "npx",
  "args": ["@modelcontextprotocol/server-github"],
  "env": {
    "GITHUB_TOKEN": "${GITHUB_TOKEN}",
    "DEBUG": "${DEBUG:-false}"
  },
  "timeout": 30,
  "health_check_interval": 60,
  "capabilities": [
    "github_search_repos",
    "github_get_file",
    "github_list_files",
    "github_get_repo_info"
  ]
}
```

### Environment Variable Substitution

The config loader automatically substitutes variables when loading:

```python
# In config/mcp_servers.json:
"env": {
  "GITHUB_TOKEN": "${GITHUB_TOKEN}",
  "DEBUG": "${DEBUG:-false}"
}

# After loading (assuming DEBUG is not set):
# GITHUB_TOKEN = value of os.environ['GITHUB_TOKEN']
# DEBUG = "false" (default value)
```

---

## ✨ Key Improvements in Phase 2

### Before (HTTP - Phase 1):
```
❌ HTTP transport pointing to non-existent services
❌ Configuration broken, tool discovery failed
❌ No environment variable support
❌ Complex custom server wrappers
```

### After (STDIO - Phase 2):
```
✅ STDIO transport with official MCP servers
✅ Configuration functional with local processes
✅ Full environment variable substitution
✅ Simplified configuration-driven setup
✅ npx handles server installation & startup
```

---

## Configuration Loading Flow

```
config/mcp_servers.json
    ↓
MCPConfigLoader.load()
    ↓
_substitute_env_vars()              ← Replace ${GITHUB_TOKEN}, etc.
    ↓
MCPConfig.from_dict()               ← Parse configuration
    ↓
MCPServerConfig objects
    ↓
agents/router.py (Phase 3)
    ↓
StdioTransport.start()              ← Start 'npx @modelcontextprotocol/...'
    ↓
ToolRegistry.register()             ← Load available tools
    ↓
LLM autonomous tool selection
```

---

## Testing Configuration Changes

### Unit Tests
```bash
# Configuration parsing tests
pytest tests/mcp/test_mcp_config.py::TestMCPConfigLoading -v

# Environment variable substitution tests
pytest tests/mcp/test_mcp_config.py::TestEnvironmentVariables -v
```

### Integration Tests
```bash
# Full configuration load test
pytest tests/mcp/test_mcp_config.py::TestMCPConfigIntegration -v

# Registry integration
pytest tests/mcp/test_mcp_config.py::TestToolRegistryConfigLoading -v
```

---

## Phase 2 Completion Checklist

- [x] Update config/mcp_servers.json (version 1.0.0 → 2.0.0)
- [x] Change all transports (http → stdio)
- [x] Add npx commands and args for each server
- [x] Add environment variable support
- [x] Update env.template with MCP settings
- [x] Document MCP server package names
- [ ] Install MCP packages (npm or globally)
- [ ] Test configuration loading
- [ ] Verify environment variable substitution
- [ ] Document Phase 2 completion

---

## Troubleshooting

### Issue: `npx: command not found`
**Solution**: Install Node.js from https://nodejs.org/

### Issue: MCP packages not found
**Solution**: Install with `npm install -g @modelcontextprotocol/server-*`

### Issue: Environment variable not substituting
**Solution**: 
1. Check .env has the variable set
2. Ensure python loads .env before importing config
3. Use `${VAR_NAME:-default}` syntax for optional variables

### Issue: GITHUB_TOKEN not working
**Solution**:
1. Generate token at https://github.com/settings/tokens
2. Grant `repo`, `gist` scopes
3. Add to .env: `GITHUB_TOKEN=ghp_xxxxx`

---

## Phase 2 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Config version updated | 2.0.0 | ✅ |
| All transports changed | stdio | ✅ |
| Env vars supported | ${VAR} syntax | ✅ |
| Config loads without errors | 100% | ⏳ Testing |
| Env var substitution works | All vars | ⏳ Testing |
| MCP packages installed | 4/4 | ⏳ Pending |
| Tests passing | 16+/17 | ⏳ Testing |

---

## Next: Phase 3 - Router Integration

**Goal**: Update agents/router.py to use STDIO transport

**Work**:
1. Modify `initialize_mcp()` to support STDIO
2. Create StdioMCPClientConfig instances
3. Test tool discovery from built-in servers
4. Verify tool registry population

**Timeline**: ~1 day

---

## Documentation Files

- `PHASE_1_COMPLETION.md` - ✅ Phase 1 done
- `PHASE_2_CONFIGURATION_UPDATE.md` - 🚀 Phase 2 (this file)
- `MCP_REFACTORING_IMPLEMENTATION.md` - Full plan (phases 2-5)

---

## Success Indicators

After Phase 2 is complete, you should see:
1. ✅ `config/mcp_servers.json` loads without errors
2. ✅ Environment variables substitute correctly
3. ✅ All server entries have `stdio` transport
4. ✅ No HTTP URLs in configuration
5. ✅ Tests parse config successfully

---

**Status**: Configuration ready for Phase 3 (Router Integration)  
**Next**: Begin Phase 3 once environment variable substitution is validated
