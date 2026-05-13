"""
WebSocket endpoints for Research OS.

Provides real-time communication for research updates.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Set
from datetime import datetime, timedelta

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from api.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

settings = get_settings()


class WebSocketMessage(BaseModel):
    """WebSocket message model."""

    type: str
    payload: Dict[str, Any]


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket, token: str = None) -> bool:
        """
        Accept and track a new WebSocket connection.

        Returns True if authentication successful, False otherwise.
        """
        # Authenticate the connection
        if not await self._authenticate(websocket, token):
            await websocket.close(code=4001, reason="Authentication required")
            return False

        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        logger.info(
            f"WebSocket connected: session={session_id}, total={len(self.active_connections[session_id])}"
        )
        return True

    async def _authenticate(self, websocket: WebSocket, token: str = None) -> bool:
        """
        Authenticate WebSocket connection using JWT token.

        Args:
            websocket: The WebSocket connection
            token: Optional JWT token from query parameter

        Returns:
            True if authentication successful or disabled, False otherwise
        """
        # If authentication is disabled in settings, allow all connections
        if not getattr(settings, "websocket_auth_enabled", True):
            return True

        if not token:
            # Try to get token from query parameter
            return False

        try:
            # Verify JWT token
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

            # Check token expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                logger.warning("WebSocket token expired")
                return False

            # Store user info in connection state
            websocket.state.user_id = payload.get("sub")
            websocket.state.session_id = payload.get("session_id")

            return True

        except jwt.InvalidTokenError as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"WebSocket auth error: {e}")
            return False

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


def create_websocket_token(
    session_id: str, user_id: str = None, expires_delta: timedelta = timedelta(hours=24)
) -> str:
    """
    Create a JWT token for WebSocket authentication.

    Args:
        session_id: The session ID
        user_id: Optional user ID
        expires_delta: Token expiration time

    Returns:
        JWT token string
    """
    from datetime import datetime, timedelta

    payload = {
        "sub": user_id or "anonymous",
        "session_id": session_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + expires_delta,
        "type": "websocket",
    }

    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: str = None) -> None:
    """
    WebSocket endpoint for real-time research updates.

    Clients connect with a session_id to receive updates about their research tasks.
    Authentication via JWT token in query parameter 'token'.
    """
    # Authenticate and connect
    authenticated = await manager.connect(session_id, websocket, token)
    if not authenticated:
        logger.warning(f"WebSocket connection rejected: session={session_id}")
        return

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
    logger.info(f"WebSocket update for session {session_id}: {update.get('status', 'unknown')}")
    await manager.send_message(
        session_id,
        WebSocketMessage(type="research_update", payload=update),
    )


async def notify_agent_activity(session_id: str, agent: str, activity: str) -> None:
    """Send agent activity notification."""
    logger.info(f"Agent activity for session {session_id}: {agent} - {activity}")
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="agent_activity",
            payload={
                "agent": agent,
                "activity": activity,
                "timestamp": asyncio.get_running_loop().time(),
            },
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


# Model Selection WebSocket Events


async def notify_model_update(session_id: str, update: Dict[str, Any]) -> None:
    """
    Send model selection update to connected clients.

    This is called when:
    - User changes provider/model selection
    - Fallback occurs
    - Provider status changes
    """
    await manager.send_message(
        session_id,
        WebSocketMessage(type="model_update", payload=update),
    )


async def notify_fallback_event(
    session_id: str,
    from_provider: str,
    from_model: str,
    to_provider: str,
    to_model: str,
    reason: str,
) -> None:
    """
    Notify clients when a fallback occurs.

    This helps the frontend display:
    - That a fallback happened
    - What was the original model
    - What is the fallback model
    - Why the fallback occurred
    """
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="fallback_event",
            payload={
                "from_provider": from_provider,
                "from_model": from_model,
                "to_provider": to_provider,
                "to_model": to_model,
                "reason": reason,
                "timestamp": asyncio.get_running_loop().time(),
            },
        ),
    )


async def notify_provider_status_change(
    session_id: str,
    provider: str,
    status: str,
    available: bool,
) -> None:
    """
    Notify clients when provider status changes.

    This helps the frontend show:
    - Provider going offline/online
    - Health status changes
    - Model availability changes
    """
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="provider_status_change",
            payload={
                "provider": provider,
                "status": status,
                "available": available,
                "timestamp": asyncio.get_running_loop().time(),
            },
        ),
    )


async def notify_models_refreshed(session_id: str, models: Dict[str, Any]) -> None:
    """
    Notify clients when models are refreshed.

    This helps the frontend update the model list dynamically.
    """
    await manager.send_message(
        session_id,
        WebSocketMessage(
            type="models_refreshed",
            payload=models,
        ),
    )
