"""
ResearchState schema for LangGraph.

This TypedDict defines the complete state structure used throughout
the research orchestration graph.
"""

from typing import Any, Dict, List, Optional, TypedDict


class ResearchState(TypedDict):
    """
    State schema for the research orchestration graph.

    This is the single source of truth for all agent communication
    and state management in the system.
    """

    # Session identification
    session_id: str

    # User query
    query: str

    # Task management
    tasks: List[Dict[str, Any]]
    active_tasks: List[str]
    completed_tasks: List[str]
    failed_tasks: List[Dict[str, Any]]

    # Research findings
    findings: List[Dict[str, Any]]
    sources: List[str]

    # Memory context
    memory_context: Dict[str, Any]

    # Reflection tracking
    reflections: List[str]
    reflection_count: int
    max_reflections: int

    # Report generation
    draft_report: str
    final_report: str

    # Execution state
    current_agent: str
    next_action: str
    status: str
    progress: float

    # Error handling
    error_state: Optional[Dict[str, Any]]

    # Human-in-the-loop
    requires_human_input: bool

    # Token usage tracking
    token_usage: Dict[str, int]

    # Metadata
    metadata: Dict[str, Any]

    # Model Selection State (User-controlled model selection)
    # These fields persist across workflow execution, websocket updates, and retries
    selected_provider: str  # "auto", "ollama", "openai", "anthropic", "google", "groq"
    selected_model: str  # Model name (e.g., "qwen3", "gpt-4o")
    routing_mode: str  # "auto", "local_only", "cloud_only", "hybrid"

    # Active model info (resolved at runtime)
    active_provider: str  # Actual provider being used
    active_model: str  # Actual model being used

    # Fallback tracking
    fallback_occurred: bool  # Whether a fallback happened
    fallback_reason: Optional[str]  # Reason for fallback
    fallback_from: Optional[str]  # Original provider:model
    fallback_to: Optional[str]  # Fallback provider:model


def create_initial_state(
    session_id: str,
    query: str,
    max_reflections: int = 3,
    selected_provider: str = "auto",
    selected_model: str = "",
    routing_mode: str = "auto",
) -> ResearchState:
    """
    Create initial state for a new research session.

    Args:
        session_id: Unique identifier for the session
        query: User's research query
        max_reflections: Maximum number of reflection cycles
        selected_provider: User-selected provider (default: "auto")
        selected_model: User-selected model (default: "")
        routing_mode: User-selected routing mode (default: "auto")

    Returns:
        Initial ResearchState with default values
    """
    return {
        "session_id": session_id,
        "query": query,
        "tasks": [],
        "active_tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "findings": [],
        "sources": [],
        "memory_context": {},
        "reflections": [],
        "reflection_count": 0,
        "max_reflections": max_reflections,
        "draft_report": "",
        "final_report": "",
        "current_agent": "",
        "next_action": "planner",
        "status": "initiated",
        "progress": 0.0,
        "error_state": None,
        "requires_human_input": False,
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "metadata": {
            "started_at": None,
            "completed_at": None,
            "model_used": None,
        },
        # Model Selection State
        "selected_provider": selected_provider,
        "selected_model": selected_model,
        "routing_mode": routing_mode,
        "active_provider": "",
        "active_model": "",
        "fallback_occurred": False,
        "fallback_reason": None,
        "fallback_from": None,
        "fallback_to": None,
    }
