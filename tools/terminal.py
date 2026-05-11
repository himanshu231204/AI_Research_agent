"""
Terminal Tool - Safe terminal command execution
"""

import asyncio
import logging
import os
import shlex
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


# Dangerous commands that should never be executed
BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=/dev/zero",
    ":(){:|:&};:",  # Fork bomb
    "chmod -R 777 /",
    "chown -R",
}


@dataclass
class TerminalConfig:
    """Terminal configuration"""

    allowed_commands: List[str] = field(default_factory=list)  # Empty = allow all
    blocked_commands: List[str] = field(default_factory=lambda: list(BLOCKED_COMMANDS))
    allowed_dirs: List[str] = field(default_factory=list)  # Empty = allow all
    env_whitelist: List[str] = field(default_factory=lambda: ["PATH", "HOME", "USER"])
    timeout: int = 30
    shell: str = "bash"


@dataclass
class TerminalResult:
    """Result of terminal operation"""

    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TerminalTool:
    """Safe terminal command execution tool"""

    def __init__(self, config: TerminalConfig = None):
        self.config = config or TerminalConfig()

    def _is_command_allowed(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if command is allowed"""
        # Check blocked commands
        for blocked in self.config.blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: {blocked}"

        # Check allowed commands list
        if self.config.allowed_commands:
            allowed = False
            for allowed_cmd in self.config.allowed_commands:
                if command.strip().startswith(allowed_cmd):
                    allowed = True
                    break
            if not allowed:
                return False, f"Command not in allowed list"

        return True, None

    def _is_directory_allowed(self, cwd: str) -> tuple[bool, Optional[str]]:
        """Check if directory is allowed"""
        if not self.config.allowed_dirs:
            return True, None

        cwd_path = os.path.abspath(cwd)

        for allowed_dir in self.config.allowed_dirs:
            allowed_path = os.path.abspath(allowed_dir)
            if cwd_path.startswith(allowed_path):
                return True, None

        return False, f"Directory not in allowed list: {cwd}"

    def _sanitize_env(self) -> Dict[str, str]:
        """Sanitize environment variables"""
        env = {}

        for key in self.config.env_whitelist:
            value = os.environ.get(key)
            if value:
                env[key] = value

        # Always add basic PATH
        if "PATH" not in env:
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin"

        return env

    async def execute(
        self, command: str, cwd: str = None, timeout: int = None, env: Dict[str, str] = None
    ) -> TerminalResult:
        """Execute terminal command"""
        start_time = datetime.utcnow()
        timeout = timeout or self.config.timeout
        cwd = cwd or os.getcwd()

        # Check command is allowed
        allowed, error = self._is_command_allowed(command)
        if not allowed:
            return TerminalResult(
                success=False,
                error=error,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
            )

        # Check directory is allowed
        allowed, error = self._is_directory_allowed(cwd)
        if not allowed:
            return TerminalResult(
                success=False,
                error=error,
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
            )

        # Prepare environment
        process_env = self._sanitize_env()
        if env:
            process_env.update(env)

        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=process_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )

                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")

                execution_time = (datetime.utcnow() - start_time).total_seconds()

                return TerminalResult(
                    success=process.returncode == 0,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=process.returncode,
                    execution_time=execution_time,
                    metadata={"command": command, "cwd": cwd},
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

                execution_time = (datetime.utcnow() - start_time).total_seconds()

                return TerminalResult(
                    success=False,
                    error=f"Command timed out after {timeout}s",
                    execution_time=execution_time,
                    metadata={"command": command, "cwd": cwd},
                )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            return TerminalResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
            )

    async def run_script(
        self, script: str, language: str = "bash", cwd: str = None, timeout: int = None
    ) -> TerminalResult:
        """Run a script"""
        if language == "python":
            command = f"python3 -c {shlex.quote(script)}"
        elif language == "bash":
            command = f"bash -c {shlex.quote(script)}"
        elif language == "sh":
            command = f"sh -c {shlex.quote(script)}"
        else:
            return TerminalResult(
                success=False,
                error=f"Unsupported language: {language}",
            )

        return await self.execute(command, cwd=cwd, timeout=timeout)
