"""
MCP Configuration Loader - Load and manage MCP configuration from JSON

This module provides:
- JSON-based MCP server configuration
- Dynamic MCP server loading
- Configuration validation
- Environment variable substitution
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """MCP Server configuration from JSON"""

    name: str
    type: str
    enabled: bool = True
    description: str = ""
    transport: str = "http"
    url: str = ""
    capabilities: List[str] = field(default_factory=list)
    timeout: int = 30
    health_check_interval: int = 30
    config: Dict[str, Any] = field(default_factory=dict)
    # Stdio specific
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create config from dictionary"""
        return cls(
            name=data.get("name", ""),
            type=data.get("type", "builtin"),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            transport=data.get("transport", "http"),
            url=data.get("url", ""),
            capabilities=data.get("capabilities", []),
            timeout=data.get("timeout", 30),
            health_check_interval=data.get("health_check_interval", 30),
            config=data.get("config", {}),
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            cwd=data.get("cwd", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "description": self.description,
            "transport": self.transport,
            "url": self.url,
            "capabilities": self.capabilities,
            "timeout": self.timeout,
            "health_check_interval": self.health_check_interval,
            "config": self.config,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "cwd": self.cwd,
        }


@dataclass
class RegistryConfig:
    """Registry configuration from JSON"""

    enable_auto_discovery: bool = True
    discovery_interval: int = 60
    cache_ttl: int = 300
    max_tools: int = 1000

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegistryConfig":
        """Create config from dictionary"""
        return cls(
            enable_auto_discovery=data.get("enable_auto_discovery", True),
            discovery_interval=data.get("discovery_interval", 60),
            cache_ttl=data.get("cache_ttl", 300),
            max_tools=data.get("max_tools", 1000),
        )


@dataclass
class PoolConfig:
    """Connection pool configuration from JSON"""

    max_connections: int = 10
    max_per_server: int = 3
    connection_timeout: int = 30
    idle_timeout: int = 300
    max_retries: int = 3
    health_check_interval: int = 30

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoolConfig":
        """Create config from dictionary"""
        return cls(
            max_connections=data.get("max_connections", 10),
            max_per_server=data.get("max_per_server", 3),
            connection_timeout=data.get("connection_timeout", 30),
            idle_timeout=data.get("idle_timeout", 300),
            max_retries=data.get("max_retries", 3),
            health_check_interval=data.get("health_check_interval", 30),
        )


@dataclass
class MCPConfig:
    """Complete MCP configuration"""

    version: str = "1.0.0"
    servers: List[MCPServerConfig] = field(default_factory=list)
    registry: RegistryConfig = field(default_factory=RegistryConfig)
    pool: PoolConfig = field(default_factory=PoolConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """Create config from dictionary"""
        servers = [MCPServerConfig.from_dict(s) for s in data.get("servers", [])]
        registry = RegistryConfig.from_dict(data.get("registry", {}))
        pool = PoolConfig.from_dict(data.get("pool", {}))

        return cls(
            version=data.get("version", "1.0.0"),
            servers=servers,
            registry=registry,
            pool=pool,
        )

    def get_enabled_servers(self) -> List[MCPServerConfig]:
        """Get list of enabled servers"""
        return [s for s in self.servers if s.enabled]

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """Get server by name"""
        for server in self.servers:
            if server.name == name:
                return server
        return None


class MCPConfigLoader:
    """Load and manage MCP configuration from JSON"""

    def __init__(self, config_path: str = None):
        """
        Initialize config loader

        Args:
            config_path: Path to MCP configuration JSON file
        """
        if config_path is None:
            # Default to config/mcp_servers.json in project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "mcp_servers.json"

        self.config_path = Path(config_path)
        self._config: Optional[MCPConfig] = None

    def load(self, validate: bool = True) -> MCPConfig:
        """
        Load MCP configuration from JSON file

        Args:
            validate: Whether to validate the configuration

        Returns:
            MCPConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
            ValueError: If validation fails
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"MCP config file not found: {self.config_path}")

        logger.info(f"Loading MCP configuration from: {self.config_path}")

        with open(self.config_path, "r") as f:
            data = json.load(f)

        # Apply environment variable substitution
        data = self._substitute_env_vars(data)

        # Parse configuration
        self._config = MCPConfig.from_dict(data)

        # Validate if requested
        if validate:
            self._validate()

        logger.info(
            f"Loaded {len(self._config.servers)} MCP servers, "
            f"{len(self._config.get_enabled_servers())} enabled"
        )

        return self._config

    def _substitute_env_vars(self, data: Any) -> Any:
        """
        Recursively substitute environment variables in configuration

        Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax
        """
        if isinstance(data, dict):
            return {k: self._substitute_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_env_var_string(data)
        return data

    def _substitute_env_var_string(self, value: str) -> str:
        """Substitute environment variables in a string"""
        import re

        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r"\$\{([^}:]+)(?::(-[^}]*)?)?\}"

        def replacer(match):
            var_name = match.group(1)
            default = match.group(2)
            if default:
                default = default[1:]  # Remove leading '-'

            return os.environ.get(var_name, default if default else "")

        return re.sub(pattern, replacer, value)

    def _validate(self) -> None:
        """Validate configuration"""
        if not self._config:
            raise ValueError("Configuration not loaded")

        # Validate servers
        server_names = set()
        for server in self._config.servers:
            if not server.name:
                raise ValueError("Server name is required")

            if server.name in server_names:
                raise ValueError(f"Duplicate server name: {server.name}")

            server_names.add(server.name)

            # Validate transport
            if server.transport not in ["http", "stdio", "websocket"]:
                raise ValueError(f"Invalid transport type for {server.name}: {server.transport}")

            # Validate URL for HTTP transport
            if server.transport == "http" and not server.url:
                raise ValueError(f"URL is required for HTTP server: {server.name}")

            # Validate command for stdio transport
            if server.transport == "stdio" and not server.command:
                raise ValueError(f"Command is required for stdio server: {server.name}")

        logger.info("Configuration validation passed")

    def get_config(self) -> MCPConfig:
        """Get loaded configuration"""
        if self._config is None:
            self.load()
        return self._config

    def reload(self) -> MCPConfig:
        """Reload configuration from file"""
        return self.load()

    def get_server_configs(self) -> List[MCPServerConfig]:
        """Get list of server configurations"""
        return self.get_config().servers

    def get_enabled_server_configs(self) -> List[MCPServerConfig]:
        """Get list of enabled server configurations"""
        return self.get_config().get_enabled_servers()

    def get_capabilities_map(self) -> Dict[str, List[str]]:
        """Get mapping of server names to capabilities"""
        config = self.get_config()
        return {s.name: s.capabilities for s in config.servers if s.enabled}


# Global config loader instance
_config_loader: Optional[MCPConfigLoader] = None


def get_config_loader(config_path: str = None) -> MCPConfigLoader:
    """Get global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = MCPConfigLoader(config_path)
    return _config_loader


def load_mcp_config(config_path: str = None) -> MCPConfig:
    """Load MCP configuration from JSON file"""
    loader = get_config_loader(config_path)
    return loader.load()


def get_mcp_servers() -> List[MCPServerConfig]:
    """Get list of MCP server configurations"""
    return get_config_loader().get_server_configs()


def get_enabled_mcp_servers() -> List[MCPServerConfig]:
    """Get list of enabled MCP server configurations"""
    return get_config_loader().get_enabled_server_configs()
