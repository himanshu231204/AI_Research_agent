"""
MCP HTTP Transport - HTTP-based transport implementation
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import aiohttp
import uuid

from .base import BaseTransport, TransportConfig, TransportResult, TransportState

logger = logging.getLogger(__name__)


class HTTPTransport(BaseTransport):
    """HTTP transport for MCP servers"""

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}

    async def connect(self) -> bool:
        """Establish HTTP connection"""
        if self.state == TransportState.CONNECTED:
            return True

        try:
            self.state = TransportState.CONNECTING

            # Create connection pool
            self._connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                keepalive_timeout=self.config.timeout,
            )

            # Create session with timeout
            timeout = aiohttp.ClientTimeout(
                total=self.config.timeout,
                connect=self.config.timeout,
                sock_read=self.config.timeout,
            )

            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers=self.config.headers,
            )

            self._connection_time = datetime.utcnow()
            self.state = TransportState.CONNECTED
            logger.info(f"HTTP transport connected to {self.config.url}")
            return True

        except Exception as e:
            self.state = TransportState.ERROR
            self._last_error = str(e)
            logger.error(f"Failed to connect HTTP transport: {e}")
            return False

    async def disconnect(self) -> None:
        """Close HTTP connection"""
        try:
            self.state = TransportState.DISCONNECTING

            # Cancel pending requests
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()

            # Close session
            if self._session:
                await self._session.close()
                self._session = None

            if self._connector:
                await self._connector.close()
                self._connector = None

            self.state = TransportState.DISCONNECTED
            logger.info("HTTP transport disconnected")

        except Exception as e:
            logger.error(f"Error disconnecting HTTP transport: {e}")
            self.state = TransportState.ERROR

    async def send(self, message: Dict[str, Any]) -> TransportResult:
        """Send JSON-RPC message and wait for response"""
        start_time = datetime.utcnow()

        if not self.is_connected():
            await self.connect()

        try:
            # Add JSON-RPC fields
            jsonrpc_message = {
                "jsonrpc": "2.0",
                "id": message.get("id", str(uuid.uuid4())),
                "method": message.get("method", ""),
                "params": message.get("params", {}),
            }

            async with self._session.post(
                self.config.url,
                json=jsonrpc_message,
            ) as response:
                latency = (datetime.utcnow() - start_time).total_seconds()

                if response.status == 200:
                    result_data = await response.json()
                    self._update_stats(True)

                    return TransportResult(
                        success=True,
                        data=result_data.get("result"),
                        status_code=response.status,
                        latency=latency,
                        metadata={"response_id": result_data.get("id")},
                    )
                else:
                    error_text = await response.text()
                    self._update_stats(False)

                    return TransportResult(
                        success=False,
                        error=f"HTTP {response.status}: {error_text}",
                        status_code=response.status,
                        latency=latency,
                    )

        except asyncio.TimeoutError:
            self._update_stats(False)
            latency = (datetime.utcnow() - start_time).total_seconds()
            return TransportResult(
                success=False,
                error="Request timeout",
                latency=latency,
            )

        except aiohttp.ClientError as e:
            self._update_stats(False)
            latency = (datetime.utcnow() - start_time).total_seconds()
            self._last_error = str(e)
            return TransportResult(
                success=False,
                error=str(e),
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

        # Fire and forget
        asyncio.create_task(self._session.post(self.config.url, json=jsonrpc_message))

        return message_id

    async def receive(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Receive message (not applicable for HTTP)"""
        logger.warning("HTTP transport does not support receive()")
        return None

    async def _receive_loop(self) -> None:
        """Background task to receive responses"""
        while self.state == TransportState.CONNECTED:
            try:
                async with self._session.get(self.config.url) as response:
                    if response.status == 200:
                        data = await response.json()
                        message_id = data.get("id")

                        if message_id in self._pending_requests:
                            future = self._pending_requests.pop(message_id)
                            if not future.done():
                                future.set_result(data)
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(1)
