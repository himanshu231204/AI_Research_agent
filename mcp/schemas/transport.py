"""
MCP Transport Schema - Message transport structures
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid
import json


class MessageType(str, Enum):
    """MCP message types"""

    # JSON-RPC
    JSONRPC_REQUEST = "jsonrpc_request"
    JSONRPC_RESPONSE = "jsonrpc_response"
    JSONRPC_ERROR = "jsonrpc_error"

    # MCP specific
    INITIALIZE = "initialize"
    INITIALIZE_RESPONSE = "initialize_response"
    TOOLS_LIST = "tools/list"
    TOOLS_LIST_RESPONSE = "tools/list_response"
    TOOLS_CALL = "tools/call"
    TOOLS_CALL_RESPONSE = "tools/call_response"
    RESOURCES_LIST = "resources/list"
    RESOURCES_LIST_RESPONSE = "resources/list_response"
    RESOURCES_READ = "resources/read"
    RESOURCES_READ_RESPONSE = "resources/read_response"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_LIST_RESPONSE = "prompts/list_response"
    PROMPTS_GET = "prompts/get"
    PROMPTS_GET_RESPONSE = "prompts/get_response"

    # Custom
    PING = "ping"
    PONG = "pong"
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"


@dataclass(frozen=True)
class TransportMessage:
    """MCP Transport message"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.JSONRPC_REQUEST
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_jsonrpc(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 format"""
        message = {
            "jsonrpc": "2.0",
            "id": self.id,
        }

        if self.message_type in (MessageType.JSONRPC_RESPONSE, MessageType.JSONRPC_ERROR):
            if self.error:
                message["error"] = self.error
            else:
                message["result"] = self.result
        else:
            message["method"] = self.method
            if self.params:
                message["params"] = self.params

        return message

    @classmethod
    def from_jsonrpc(cls, data: Dict[str, Any]) -> "TransportMessage":
        """Create from JSON-RPC 2.0 format"""
        msg_type = MessageType.JSONRPC_REQUEST

        if "result" in data:
            msg_type = MessageType.JSONRPC_RESPONSE
        elif "error" in data:
            msg_type = MessageType.JSONRPC_ERROR

        return TransportMessage(
            id=data.get("id", str(uuid.uuid4())),
            message_type=msg_type,
            method=data.get("method", ""),
            params=data.get("params", {}),
            result=data.get("result"),
            error=data.get("error"),
        )

    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_jsonrpc())

    @classmethod
    def from_json(cls, json_str: str) -> "TransportMessage":
        """Deserialize from JSON"""
        return cls.from_jsonrpc(json.loads(json_str))


@dataclass
class MessageQueue:
    """Queue for transport messages"""

    pending: List[TransportMessage] = field(default_factory=list)
    in_flight: Dict[str, TransportMessage] = field(default_factory=dict)
    completed: Dict[str, TransportMessage] = field(default_factory=dict)
    failed: Dict[str, TransportMessage] = field(default_factory=dict)

    def enqueue(self, message: TransportMessage) -> None:
        """Add message to pending queue"""
        self.pending.append(message)

    def mark_in_flight(self, message: TransportMessage) -> None:
        """Move message to in-flight"""
        if message in self.pending:
            self.pending.remove(message)
        self.in_flight[message.id] = message

    def mark_completed(self, message: TransportMessage) -> None:
        """Move message to completed"""
        self.in_flight.pop(message.id, None)
        self.completed[message.id] = message

    def mark_failed(self, message: TransportMessage) -> None:
        """Move message to failed"""
        self.in_flight.pop(message.id, None)
        self.failed[message.id] = message

    def retry(self, message_id: str) -> Optional[TransportMessage]:
        """Retry a failed message"""
        message = self.failed.pop(message_id, None)
        if message:
            self.pending.append(message)
        return message

    def get_pending_count(self) -> int:
        """Get count of pending messages"""
        return len(self.pending)

    def get_in_flight_count(self) -> int:
        """Get count of in-flight messages"""
        return len(self.in_flight)
