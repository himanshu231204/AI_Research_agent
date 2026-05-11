"""
MCP Tool Schema - Tool definitions and parameters
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from enum import Enum
from datetime import datetime
import uuid


class ParameterType(str, Enum):
    """Types of tool parameters"""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolCategory(str, Enum):
    """Categories of tools"""

    BROWSER = "browser"
    GITHUB = "github"
    FILESYSTEM = "filesystem"
    TERMINAL = "terminal"
    SEARCH = "search"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ToolParameter:
    """Tool parameter definition"""

    name: str
    param_type: ParameterType
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[str]] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


@dataclass(frozen=True)
class Tool:
    """MCP Tool definition"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.CUSTOM
    parameters: tuple = field(default_factory=tuple)
    handler: Optional[Any] = field(default=None, repr=False)
    server_name: str = ""
    enabled: bool = True
    timeout: int = 30
    retry_count: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Tool name is required")

    def get_parameter(self, name: str) -> Optional[ToolParameter]:
        """Get parameter by name"""
        for param in self.parameters:
            if param.name == name:
                return param
        return None

    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate parameters against tool definition"""
        errors = []

        for param in self.parameters:
            if param.required and param.name not in params:
                errors.append(f"Required parameter '{param.name}' is missing")
                continue

            if param.name in params:
                value = params[param.name]

                # Type validation
                if param.param_type == ParameterType.STRING and not isinstance(value, str):
                    errors.append(f"Parameter '{param.name}' must be a string")
                elif param.param_type == ParameterType.NUMBER and not isinstance(
                    value, (int, float)
                ):
                    errors.append(f"Parameter '{param.name}' must be a number")
                elif param.param_type == ParameterType.INTEGER and not isinstance(value, int):
                    errors.append(f"Parameter '{param.name}' must be an integer")
                elif param.param_type == ParameterType.BOOLEAN and not isinstance(value, bool):
                    errors.append(f"Parameter '{param.name}' must be a boolean")
                elif param.param_type == ParameterType.ARRAY and not isinstance(value, list):
                    errors.append(f"Parameter '{param.name}' must be an array")
                elif param.param_type == ParameterType.OBJECT and not isinstance(value, dict):
                    errors.append(f"Parameter '{param.name}' must be an object")

                # String validations
                if param.param_type == ParameterType.STRING:
                    if param.min_length and len(value) < param.min_length:
                        errors.append(
                            f"Parameter '{param.name}' must be at least {param.min_length} characters"
                        )
                    if param.max_length and len(value) > param.max_length:
                        errors.append(
                            f"Parameter '{param.name}' must be at most {param.max_length} characters"
                        )
                    if param.pattern and not __import__("re").match(param.pattern, value):
                        errors.append(f"Parameter '{param.name}' does not match required pattern")

                # Enum validation
                if param.enum and value not in param.enum:
                    errors.append(
                        f"Parameter '{param.name}' must be one of: {', '.join(param.enum)}"
                    )

        return len(errors) == 0, errors


@dataclass
class ToolResult:
    """Result of tool execution"""

    tool_id: str
    tool_name: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    artifacts: tuple = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "artifacts": list(self.artifacts),
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
