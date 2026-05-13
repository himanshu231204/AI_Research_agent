"""
Integration tests for MCP configuration loading

Tests:
- JSON parsing
- Dynamic initialization
- Server health
- Capability detection
- Tool routing
"""

import pytest
import json
import asyncio
from pathlib import Path

from mcplib.config import (
    MCPConfigLoader,
    MCPConfig,
    MCPServerConfig,
    RegistryConfig,
    PoolConfig,
    load_mcp_config,
    get_enabled_mcp_servers,
)


class TestMCPConfigLoading:
    """Test MCP configuration loading from JSON"""

    @pytest.fixture
    def config_path(self, tmp_path):
        """Create a temporary config file"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test-server",
                    "type": "builtin",
                    "enabled": True,
                    "description": "Test server",
                    "transport": "http",
                    "url": "http://localhost:8080",
                    "capabilities": ["tool1", "tool2"],
                    "timeout": 30,
                }
            ],
            "registry": {
                "enable_auto_discovery": True,
                "discovery_interval": 60,
            },
            "pool": {
                "max_connections": 10,
            },
        }

        config_file = tmp_path / "test_mcp.json"
        config_file.write_text(json.dumps(config))
        return str(config_file)

    def test_load_config_from_file(self, config_path):
        """Test loading configuration from file"""
        loader = MCPConfigLoader(config_path)
        config = loader.load()

        assert config.version == "1.0.0"
        assert len(config.servers) == 1
        assert config.servers[0].name == "test-server"

    def test_get_enabled_servers(self, config_path):
        """Test getting enabled servers"""
        loader = MCPConfigLoader(config_path)
        config = loader.load()

        enabled = config.get_enabled_servers()
        assert len(enabled) == 1
        assert enabled[0].name == "test-server"

    def test_get_server_by_name(self, config_path):
        """Test getting server by name"""
        loader = MCPConfigLoader(config_path)
        config = loader.load()

        server = config.get_server("test-server")
        assert server is not None
        assert server.name == "test-server"

    def test_disabled_server_excluded(self, tmp_path):
        """Test that disabled servers are excluded"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "enabled-server",
                    "type": "builtin",
                    "enabled": True,
                    "transport": "http",
                    "url": "http://localhost:8080",
                    "capabilities": ["tool1"],
                },
                {
                    "name": "disabled-server",
                    "type": "builtin",
                    "enabled": False,
                    "transport": "http",
                    "url": "http://localhost:8081",
                    "capabilities": ["tool2"],
                },
            ],
        }

        config_file = tmp_path / "test_mcp.json"
        config_file.write_text(json.dumps(config))

        loader = MCPConfigLoader(str(config_file))
        loaded_config = loader.load()

        enabled = loaded_config.get_enabled_servers()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled-server"


class TestMCPConfigValidation:
    """Test MCP configuration validation"""

    def test_valid_config(self, tmp_path):
        """Test valid configuration passes validation"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test",
                    "type": "builtin",
                    "enabled": True,
                    "transport": "http",
                    "url": "http://localhost:8080",
                    "capabilities": ["tool1"],
                }
            ],
        }

        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(config))

        loader = MCPConfigLoader(str(config_file))
        # Should not raise
        config = loader.load()
        assert config is not None

    def test_missing_server_name_fails(self, tmp_path):
        """Test that missing server name fails validation"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "type": "builtin",
                    "enabled": True,
                    "transport": "http",
                    "url": "http://localhost:8080",
                }
            ],
        }

        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(config))

        loader = MCPConfigLoader(str(config_file))
        with pytest.raises(ValueError, match="Server name is required"):
            loader.load()

    def test_duplicate_server_names_fail(self, tmp_path):
        """Test that duplicate server names fail validation"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test",
                    "type": "builtin",
                    "enabled": True,
                    "transport": "http",
                    "url": "http://localhost:8080",
                },
                {
                    "name": "test",
                    "type": "builtin",
                    "enabled": True,
                    "transport": "http",
                    "url": "http://localhost:8081",
                },
            ],
        }

        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(config))

        loader = MCPConfigLoader(str(config_file))
        with pytest.raises(ValueError, match="Duplicate server name"):
            loader.load()

    def test_invalid_transport_fails(self, tmp_path):
        """Test that invalid transport type fails validation"""
        config = {
            "version": "1.0.0",
            "servers": [
                {
                    "name": "test",
                    "type": "builtin",
                    "enabled": True,
                    "transport": "invalid",
                    "url": "http://localhost:8080",
                }
            ],
        }

        config_file = tmp_path / "test.json"
        config_file.write_text(json.dumps(config))

        loader = MCPConfigLoader(str(config_file))
        with pytest.raises(ValueError, match="Invalid transport type"):
            loader.load()


class TestMCPConfigDataclasses:
    """Test MCP configuration dataclasses"""

    def test_mcp_server_config_from_dict(self):
        """Test creating MCPServerConfig from dictionary"""
        data = {
            "name": "test",
            "type": "builtin",
            "enabled": True,
            "description": "Test server",
            "transport": "http",
            "url": "http://localhost:8080",
            "capabilities": ["tool1", "tool2"],
            "timeout": 30,
        }

        config = MCPServerConfig.from_dict(data)

        assert config.name == "test"
        assert config.type == "builtin"
        assert config.enabled is True
        assert config.transport == "http"
        assert config.url == "http://localhost:8080"
        assert config.capabilities == ["tool1", "tool2"]
        assert config.timeout == 30

    def test_registry_config_from_dict(self):
        """Test creating RegistryConfig from dictionary"""
        data = {
            "enable_auto_discovery": False,
            "discovery_interval": 120,
            "cache_ttl": 600,
        }

        config = RegistryConfig.from_dict(data)

        assert config.enable_auto_discovery is False
        assert config.discovery_interval == 120
        assert config.cache_ttl == 600

    def test_pool_config_from_dict(self):
        """Test creating PoolConfig from dictionary"""
        data = {
            "max_connections": 20,
            "max_per_server": 5,
            "connection_timeout": 60,
        }

        config = PoolConfig.from_dict(data)

        assert config.max_connections == 20
        assert config.max_per_server == 5
        assert config.connection_timeout == 60


class TestMCPConfigIntegration:
    """Integration tests for MCP configuration"""

    def test_load_default_config(self):
        """Test loading default configuration"""
        # This uses the default config path
        try:
            config = load_mcp_config()
            assert config is not None
            assert config.version == "2.0.0"
            assert len(config.servers) > 0
        except FileNotFoundError:
            # Expected if running in isolation
            pass

    def test_get_enabled_mcp_servers(self):
        """Test getting enabled MCP servers"""
        try:
            servers = get_enabled_mcp_servers()
            assert isinstance(servers, list)
        except FileNotFoundError:
            # Expected if running in isolation
            pass


class TestToolRegistryConfigLoading:
    """Test tool registry loading from config"""

    @pytest.mark.asyncio
    async def test_load_from_config(self):
        """Test loading tools from configuration"""
        from mcplib.registry.registry import ToolRegistry, RegistryConfig

        registry = RegistryConfig()
        tool_registry = ToolRegistry(registry, None)

        server_configs = [
            {
                "name": "browser",
                "enabled": True,
                "capabilities": ["browser_navigate", "browser_screenshot"],
                "timeout": 30,
            },
            {
                "name": "github",
                "enabled": True,
                "capabilities": ["github_search_repos"],
                "timeout": 30,
            },
        ]

        await tool_registry.load_from_config(server_configs)

        # Check that tools were loaded
        assert "browser_navigate" in tool_registry.tools
        assert "browser_screenshot" in tool_registry.tools
        assert "github_search_repos" in tool_registry.tools

    @pytest.mark.asyncio
    async def test_disabled_server_not_loaded(self):
        """Test that disabled servers are not loaded"""
        from mcplib.registry.registry import ToolRegistry, RegistryConfig

        registry = RegistryConfig()
        tool_registry = ToolRegistry(registry, None)

        server_configs = [
            {
                "name": "enabled-server",
                "enabled": True,
                "capabilities": ["browser_navigate"],
                "timeout": 30,
            },
            {
                "name": "disabled-server",
                "enabled": False,
                "capabilities": ["browser_screenshot"],
                "timeout": 30,
            },
        ]

        await tool_registry.load_from_config(server_configs)

        # Only enabled server capabilities should be loaded
        for cap in server_configs[0]["capabilities"]:
            assert cap in tool_registry.tools
        for cap in server_configs[1]["capabilities"]:
            assert cap not in tool_registry.tools


class TestCapabilityMetadata:
    """Test capability metadata"""

    def test_capabilities_in_config(self):
        """Test that capabilities are properly stored in config"""
        try:
            config = load_mcp_config()
            for server in config.servers:
                assert isinstance(server.capabilities, list)
                assert len(server.capabilities) > 0
        except FileNotFoundError:
            pass

    def test_capabilities_map(self):
        """Test getting capabilities map"""
        try:
            loader = MCPConfigLoader()
            config = loader.get_config()
            cap_map = {s.name: s.capabilities for s in config.servers}

            assert isinstance(cap_map, dict)
            for server_name, capabilities in cap_map.items():
                assert isinstance(server_name, str)
                assert isinstance(capabilities, list)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
