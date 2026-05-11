"""
WebSocket endpoints for Research OS.

Provides real-time communication for research updates.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: str
    payload: Dict[str, Any]


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept and track a new WebSocket connection."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        logger.info(
            f"WebSocket connected: session={session_id}, total={len(self.active_connections[session_id])}"
        )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        logger.info(f"WebSocket disconnected: session={session_id}")

    async def send_message(self, session_id: str, message: WebSocketMessage) -> None:
        """Send a message to all connections for a session."""
        if session_id not in self.active_connections:
            return

        message_json = message.model_dump_json()

        # Send to all connections for this session
        disconnected = set()
        for websocket in self.active_connections[session_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.add(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(session_id, ws)

    async def broadcast(self, message: WebSocketMessage) -> None:
        """Broadcast a message to all connected clients."""
        message_json = message.model_dump_json()

        for session_id, connections in self.active_connections.items():
            disconnected = set()
            for websocket in connections:
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    logger.error(f"Error broadcasting: {e}")
                    disconnected.add(websocket)

            for ws in disconnected:
                self.disconnect(session_id, ws)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for real-time research updates.

    Clients connect with a session_id to receive updates about their research tasks.
    """
    await manager.connect(session_id, websocket)

    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_client_message(session_id, message)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from client: {data}")
            except Exception as e:
                logger.error(f"Error handling client message: {e}")

    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        logger.info(f"Client disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(session_id, websocket)


async def handle_client_message(session_id: str, message: dict) -> None:
    """Handle incoming WebSocket messages from clients."""
    message_type = message.get("type")

    if message_type == "ping":
        await manager.send_message(
            session_id,
            WebSocketMessage(type="pong", payload={"session_id": session_id}),
        )
    elif message_type == "subscribe":
        # Client wants to subscribe to specific updates
        logger.info(f"Client subscribed: session={session_id}")
    elif message_type == "unsubscribe":
        logger.info(f"Client unsubscribed: session={session_id}")
    else:
        logger.warning(f"Unknown message type: {message_type}")


async def notify_research_update(session_id: str, update: Dict[str, Any]) -> None:
    """
    Send research update to connected clients.

    This function is called by the research graph to notify clients of progress.
    """
    await manager.send_message(
        session_id,
        WebSocketMessage(type="research_update", payload=update),
    )


async def notify_agent_activity(session_id: str, agent: str, activity: str) -> None:
    """Send agent activity notification."""
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="agent_activity",
            payload={"agent": agent, "activity": activity},
        ),
    )


async def notify_research_complete(session_id: str, report: str) -> None:
    """Send research completion notification."""
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="research_complete",
            payload={"report": report},
        ),
    )
