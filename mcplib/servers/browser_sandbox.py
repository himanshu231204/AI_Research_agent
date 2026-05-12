"""
Browser Sandbox - Isolated Docker container for browser execution
"""

import asyncio
import logging
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Sandbox configuration"""

    image: str = "browser-sandbox:latest"
    container_name: str = "research-agent-browser"
    network: str = "bridge"
    memory_limit: str = "2g"
    cpu_limit: float = 1.0
    # Security
    read_only: bool = True
    cap_drop: List[str] = field(default_factory=lambda: ["ALL"])
    # Volumes
    artifacts_dir: str = "/artifacts"
    # Health check
    health_check_interval: int = 30
    health_check_timeout: int = 10


class BrowserSandbox:
    """Isolated Docker container for browser execution"""

    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self._container_id: Optional[str] = None
        self._docker_available: bool = False

    async def initialize(self) -> bool:
        """Initialize the sandbox"""
        try:
            # Check if Docker is available
            process = await asyncio.create_subprocess_exec(
                "docker",
                "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await process.communicate()

            if process.returncode == 0:
                self._docker_available = True
                logger.info("Docker available for browser sandbox")
                return True
            else:
                logger.warning("Docker not available, using fallback mode")
                return False

        except FileNotFoundError:
            logger.warning("Docker not installed, using fallback mode")
            return False
        except Exception as e:
            logger.warning(f"Docker check failed: {e}")
            return False

    async def start(self) -> bool:
        """Start the sandbox container"""
        if not self._docker_available:
            logger.info("Starting browser in fallback mode (no sandbox)")
            return True

        try:
            # Pull image if needed
            await self._pull_image()

            # Create and start container
            container_id = await self._create_container()

            if container_id:
                self._container_id = container_id
                await self._start_container()
                logger.info(f"Browser sandbox started: {container_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to start sandbox: {e}")
            return False

    async def stop(self) -> None:
        """Stop the sandbox container"""
        if not self._container_id:
            return

        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "stop",
                self._container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            # Remove container
            process = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                self._container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            logger.info("Browser sandbox stopped")

        except Exception as e:
            logger.error(f"Error stopping sandbox: {e}")

        self._container_id = None

    async def execute(self, command: str) -> Dict[str, Any]:
        """Execute command in sandbox"""
        if not self._docker_available or not self._container_id:
            return {"success": False, "error": "Sandbox not available"}

        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                self._container_id,
                "sh",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "exit_code": process.returncode,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def health_check(self) -> bool:
        """Check sandbox health"""
        if not self._docker_available or not self._container_id:
            return True  # Fallback mode is always "healthy"

        try:
            result = await self.execute("echo 'ok'")
            return result.get("success", False)
        except Exception:
            return False

    async def _pull_image(self) -> None:
        """Pull Docker image"""
        process = await asyncio.create_subprocess_exec(
            "docker",
            "pull",
            self.config.image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

    async def _create_container(self) -> Optional[str]:
        """Create Docker container"""
        cmd = [
            "docker",
            "create",
            "--name",
            self.config.container_name,
            "--memory",
            self.config.memory_limit,
            "--cpus",
            str(self.config.cpu_limit),
            "--read-only" if self.config.read_only else "",
            "--cap-drop",
            *self.config.cap_drop,
            "--network",
            self.config.network,
            "-v",
            f"{self.config.artifacts_dir}:/artifacts",
            self.config.image,
            "sleep",
            "infinity",
        ]

        # Filter empty strings
        cmd = [c for c in cmd if c]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout.decode().strip()

        logger.error(f"Failed to create container: {stderr.decode()}")
        return None

    async def _start_container(self) -> bool:
        """Start Docker container"""
        process = await asyncio.create_subprocess_exec(
            "docker",
            "start",
            self._container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        await process.communicate()
        return process.returncode == 0

    @property
    def container_id(self) -> Optional[str]:
        """Get container ID"""
        return self._container_id

    @property
    def is_running(self) -> bool:
        """Check if sandbox is running"""
        return self._container_id is not None

    @property
    def is_sandboxed(self) -> bool:
        """Check if running in sandbox mode"""
        return self._docker_available and self._container_id is not None
