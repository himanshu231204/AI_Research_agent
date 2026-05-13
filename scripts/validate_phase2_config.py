#!/usr/bin/env python
"""Phase 2 Configuration Validation Script"""

import json
import os
import sys
from pathlib import Path

def validate_config():
    """Validate MCP configuration"""
    
    print("=" * 70)
    print("Phase 2: MCP Configuration Validation")
    print("=" * 70)
    print()
    
    # Load config
    config_path = Path("config/mcp_servers.json")
    if not config_path.exists():
        print(f"✗ Configuration file not found: {config_path}")
        return False
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Check version
    version = config.get("version")
    if version != "2.0.0":
        print(f"✗ Expected version 2.0.0, got {version}")
        return False
    print(f"✓ Configuration version: {version}")
    
    # Check servers
    servers = config.get("servers", [])
    print(f"✓ Servers configured: {len(servers)}")
    print()
    
    # Validate each server
    all_valid = True
    for server in servers:
        name = server.get("name", "unknown")
        transport = server.get("transport", "")
        command = server.get("command", "")
        args = server.get("args", [])
        
        if transport == "stdio" and command and args:
            args_str = " ".join(args)
            print(f"  ✓ {name:12s} | {command} {args_str}")
        else:
            print(f"  ✗ {name:12s} | Invalid configuration")
            all_valid = False
    
    print()
    if all_valid:
        print("✓ All servers configured correctly for STDIO transport")
    else:
        print("✗ Some servers have invalid configuration")
        return False
    
    # Test environment variable substitution
    print()
    print("Testing environment variable substitution...")
    
    # Set test environment variables
    os.environ["GITHUB_TOKEN"] = "ghp_test_token_12345"
    os.environ["DEBUG"] = "true"
    
    try:
        from mcplib.config import MCPConfigLoader
        
        loader = MCPConfigLoader("config/mcp_servers.json")
        loaded_config = loader.load()
        
        print(f"✓ Configuration loaded: {len(loaded_config.servers)} servers")
        
        # Check GitHub server env var substitution
        github_server = loaded_config.get_server("github")
        if github_server:
            github_token = github_server.env.get("GITHUB_TOKEN", "")
            if github_token == "ghp_test_token_12345":
                print(f"✓ Environment variable substitution: GITHUB_TOKEN")
            else:
                print(f"✗ GITHUB_TOKEN not substituted correctly")
                print(f"  Expected: ghp_test_token_12345")
                print(f"  Got: {github_token}")
                return False
        
        # Check DEBUG with default value
        browser_server = loaded_config.get_server("browser")
        if browser_server:
            debug = browser_server.env.get("DEBUG", "")
            if debug == "true":
                print(f"✓ Environment variable substitution: DEBUG")
            else:
                print(f"✗ DEBUG not substituted correctly: {debug}")
        
    except Exception as e:
        print(f"✗ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    print("=" * 70)
    print("✓ Phase 2 Validation Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Install MCP server packages: python scripts/phase2_setup.ps1")
    print("  2. Configure GITHUB_TOKEN in .env")
    print("  3. Proceed to Phase 3: Router Integration")
    print()
    
    return True

if __name__ == "__main__":
    success = validate_config()
    sys.exit(0 if success else 1)
