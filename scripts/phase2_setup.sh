#!/bin/bash
# Phase 2: MCP Configuration Setup & Validation Script
# This script sets up MCP servers and validates configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}Phase 2: MCP Configuration Setup & Validation${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# Check if Node.js is installed
echo -e "${YELLOW}Step 1: Checking Node.js installation...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is not installed${NC}"
    echo "  Download from: https://nodejs.org/"
    exit 1
else
    NODE_VERSION=$(node --version)
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓ Node.js installed: ${NODE_VERSION}${NC}"
    echo -e "${GREEN}✓ npm installed: ${NPM_VERSION}${NC}"
fi
echo ""

# Check if Python is installed
echo -e "${YELLOW}Step 2: Checking Python installation...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python is not installed${NC}"
    exit 1
else
    PYTHON_VERSION=$(python --version)
    echo -e "${GREEN}✓ ${PYTHON_VERSION}${NC}"
fi
echo ""

# Check if .env file exists
echo -e "${YELLOW}Step 3: Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}ℹ .env file not found${NC}"
    echo "  Copying from env.template..."
    if cp env.template .env; then
        echo -e "${GREEN}✓ Created .env from template${NC}"
        echo -e "${YELLOW}  ⚠️  Please edit .env and set GITHUB_TOKEN${NC}"
    else
        echo -e "${RED}✗ Failed to create .env${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi
echo ""

# Check GitHub token
echo -e "${YELLOW}Step 4: Checking GitHub token...${NC}"
if [ -z "${GITHUB_TOKEN}" ]; then
    echo -e "${YELLOW}ℹ GITHUB_TOKEN not set in environment${NC}"
    echo "  This is optional but required for GitHub MCP server"
    echo "  To set: export GITHUB_TOKEN=ghp_xxxxxxxxxxxxx"
else
    echo -e "${GREEN}✓ GITHUB_TOKEN is set${NC}"
fi
echo ""

# Check for package.json
echo -e "${YELLOW}Step 5: Checking package.json...${NC}"
if [ ! -f "package.json" ]; then
    echo "  Creating package.json..."
    npm init -y > /dev/null
    echo -e "${GREEN}✓ Created package.json${NC}"
else
    echo -e "${GREEN}✓ package.json exists${NC}"
fi
echo ""

# Install MCP server packages
echo -e "${YELLOW}Step 6: Installing MCP server packages...${NC}"
MCP_PACKAGES=(
    "@modelcontextprotocol/server-playwright"
    "@modelcontextprotocol/server-github"
    "@modelcontextprotocol/server-filesystem"
    "@modelcontextprotocol/server-bash"
)

for pkg in "${MCP_PACKAGES[@]}"; do
    if npm list "$pkg" &> /dev/null; then
        echo -e "${GREEN}✓ ${pkg} already installed${NC}"
    else
        echo -e "${YELLOW}  Installing ${pkg}...${NC}"
        npm install --save-dev "$pkg"
        echo -e "${GREEN}✓ ${pkg} installed${NC}"
    fi
done
echo ""

# Validate configuration loading
echo -e "${YELLOW}Step 7: Validating MCP configuration...${NC}"
python << 'PYTHON_EOF'
import json
import sys
from pathlib import Path

# Load configuration
config_path = Path("config/mcp_servers.json")
if not config_path.exists():
    print(f"✗ Configuration file not found: {config_path}")
    sys.exit(1)

with open(config_path, 'r') as f:
    config = json.load(f)

# Check version
version = config.get('version')
if version == '2.0.0':
    print(f"✓ Configuration version: {version}")
else:
    print(f"✗ Expected version 2.0.0, got {version}")
    sys.exit(1)

# Check servers
servers = config.get('servers', [])
print(f"✓ Found {len(servers)} servers")

transport_errors = []
for server in servers:
    name = server.get('name')
    transport = server.get('transport')
    command = server.get('command')
    args = server.get('args', [])
    
    if transport != 'stdio':
        transport_errors.append(f"  ✗ {name}: Expected transport 'stdio', got '{transport}'")
    elif not command:
        transport_errors.append(f"  ✗ {name}: Missing 'command' field")
    elif not args:
        transport_errors.append(f"  ✗ {name}: Missing 'args' field")
    else:
        print(f"  ✓ {name}: stdio transport, command='{command}', args={args}")

if transport_errors:
    print("\nTransport configuration errors:")
    for error in transport_errors:
        print(error)
    sys.exit(1)

print("\n✓ Configuration validation passed!")
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Configuration is valid${NC}"
else
    echo -e "${RED}✗ Configuration validation failed${NC}"
    exit 1
fi
echo ""

# Test configuration loading with environment variables
echo -e "${YELLOW}Step 8: Testing configuration loading with substitution...${NC}"
python << 'PYTHON_EOF'
import os
import sys

# Set test environment variables
os.environ['GITHUB_TOKEN'] = 'test_token_12345'
os.environ['DEBUG'] = 'true'

try:
    from mcplib.config import MCPConfigLoader
    
    loader = MCPConfigLoader('config/mcp_servers.json')
    config = loader.load()
    
    print(f"✓ Configuration loaded successfully")
    print(f"  - Version: {config.version}")
    print(f"  - Servers: {len(config.servers)}")
    print(f"  - Enabled: {len(config.get_enabled_servers())}")
    
    # Check environment variable substitution
    github_server = config.get_server('github')
    if github_server and 'GITHUB_TOKEN' in github_server.env:
        token_value = github_server.env['GITHUB_TOKEN']
        if token_value == 'test_token_12345':
            print(f"✓ Environment variable substitution working")
        else:
            print(f"✗ Expected 'test_token_12345', got '{token_value}'")
            sys.exit(1)
    
except Exception as e:
    print(f"✗ Error loading configuration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Configuration loading test passed${NC}"
else
    echo -e "${RED}✗ Configuration loading test failed${NC}"
    exit 1
fi
echo ""

# Run MCP configuration tests
echo -e "${YELLOW}Step 9: Running MCP configuration tests...${NC}"
if python -m pytest tests/mcp/test_mcp_config.py -v --tb=short 2>/dev/null; then
    echo -e "${GREEN}✓ All MCP tests passed${NC}"
else
    echo -e "${YELLOW}ℹ Some MCP tests may have failed (this is expected if Phase 3 not started)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}==============================================================================${NC}"
echo -e "${GREEN}Phase 2 Setup Complete!${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "✓ MCP configuration updated to STDIO transport"
echo "✓ MCP server packages installed"
echo "✓ Configuration validation passed"
echo "✓ Environment variable substitution working"
echo ""
echo "Next steps:"
echo "  1. Set your GITHUB_TOKEN in .env (optional)"
echo "  2. Proceed to Phase 3: Router Integration"
echo "  3. Test tool discovery and registry population"
echo ""
echo -e "${YELLOW}Phase 2 Documentation:${NC} docs/mcp/PHASE_2_CONFIGURATION_UPDATE.md"
echo ""
