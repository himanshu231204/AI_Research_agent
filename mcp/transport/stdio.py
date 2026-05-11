"""
MCP Stdio Transport - Standard I/O transport for local MCP servers
"""

import asyncio
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import os

from .base import BaseTransport, TransportConfig, TransportResult, TransportState

logger = logging.getLogger(__name__)


class StdioTransport(BaseTransport):
    """Stdio transport for local MCP server processes"""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._response_buffer: str = ""

    async def connect(self) -> bool:
        """Start MCP server process"""
        if self.state == TransportState.CONNECTED:
            return True

        try:
            self.state = TransportState.CONNECTING

            # Prepare environment
            env = os.environ.copy()
            env.update(self.config.env)

            # Start process
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.config.cwd or None,
            )

            # Start reader task
            self._reader_task = asyncio.create_task(self._read_output())

            self._connection_time = datetime.utcnow()
            self.state = TransportState.CONNECTED
            logger.info(f"Stdio transport started process: {self.config.command}")
            return True

        except Exception as e:
            self.state = TransportState.ERROR
            self._last_error = str(e)
            logger.error(f"Failed to start stdio transport: {e}")
            return False

    async def disconnect(self) -> None:
        """Stop MCP server process"""
        try:
            self.state = TransportState.DISCONNECTING

            # Cancel reader task
            if self._reader_task:
                self._reader_task.cancel()
                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

            # Terminate process
            if self._process:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()

            # Clear pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()

            self._process = None
            self.state = TransportState.DISCONNECTED
            logger.info("Stdio transport stopped")

        except Exception as e:
            logger.error(f"Error disconnecting stdio transport: {e}")
            self.state = TransportState.ERROR

    async def send(self, message: Dict[str, Any]) -> TransportResult:
        """Send JSON-RPC message and wait for response"""
        start_time = datetime.utcnow()

        if not self.is_connected():
            await self.connect()

        try:
            message_id = message.get("id", str(uuid.uuid4()))

            # Create JSON-RPC message
            jsonrpc_message = {
                "jsonrpc": "2.0",
                "id": message_id,
                "method": message.get("method", ""),
                "params": message.get("params", {}),
            }

            # Create future for response
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending_requests[message_id] = future

            # Send message
            message_bytes = (json.dumps(jsonrpc_message) + "\n").encode()
            self._process.stdin.write(message_bytes)
            await self._process.stdin.drain()

            # Wait for response
            try:
                response = await asyncio.wait_for(future, timeout=self.config.timeout)
                latency = (datetime.utcnow() - start_time).total_seconds()
                self._update_stats(True)

                if "error" in response:
                    return TransportResult(
                        success=False,
                        error=response["error"].get("message", "Unknown error"),
                        latency=latency,
                    )

                return TransportResult(
                    success=True,
                    data=response.get("result"),
                    latency=latency,
                )

            except asyncio.TimeoutError:
                self._pending_requests.pop(message_id, None)
                self._update_stats(False)
                latency = (datetime.utcnow() - start_time).total_seconds()
                return TransportResult(
                    success=False,
                    error="Request timeout",
                    latency=latency,
                )

        except Exception as e:
            self._update_stats(False)
            latency = (datetime.utcnow() - start_time).total_seconds()
            self._last_error = str(e)
            return TransportResult(
                success=False,
                error=str(e),
                latency=latency,
            )

    async def send_async(self, message: Dict[str, Any]) -> str:
        """Send message without waiting for response"""
        message_id = str(uuid.uuid4())

        if not self.is_connected():
            await self.connect()

        jsonrpc_message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": message.get("method", ""),
            "params": message.get("params", {}),
        }

        message_bytes = (json.dumps(jsonrpc_message) + "\n").encode()
        self._process.stdin.write(message_bytes)
        await self._process.stdin.drain()

        return message_id

    async def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message from stdout"""
        try:
            if timeout:
                return await asyncio.wait_for(self._read_line(), timeout=timeout)
            return await self._read_line()
        except asyncio.TimeoutError:
            return None

    async def _read_output(self) -> None:
        """Background task to read stdout"""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break

                await self._handle_output(line.decode().strip())

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error reading output: {e}")

    async def _read_line(self) -> Optional[Dict[str, Any]]:
        """Read a single line from stdout"""
        if self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            if line:
                return json.loads(line.decode().strip())
        return None

    async def _handle_output(self, line: str) -> None:
        """Handle received JSON-RPC response"""
        try:
            data = json.loads(line)
            message_id = data.get("id")

            if message_id and message_id in self._pending_requests:
                future = self._pending_requests.pop(message_id)
                if not future.done():
                    future.set_result(data)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {line}")
        except Exception as e:
            logger.error(f"Error handling output: {e}")
