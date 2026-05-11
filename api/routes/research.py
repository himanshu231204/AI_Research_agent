"""
Research API endpoints for Research OS.
"""

import asyncio
import logging
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from graphs.research_graph import ResearchGraph

logger = logging.getLogger(__name__)

router = APIRouter()


class ResearchRequest(BaseModel):
    """Request model for research tasks."""

    query: str = Field(..., min_length=1, max_length=5000)
    max_reflections: int = Field(default=3, ge=1, le=10)
    session_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What are the latest developments in quantum computing?",
                    "max_reflections": 3,
                }
            ]
        }
    }


class ResearchResponse(BaseModel):
    """Response model for research tasks."""

    session_id: str
    status: str
    message: str


class ResearchStatusResponse(BaseModel):
    """Response model for research status."""

    session_id: str
    status: str
    progress: float
    current_agent: Optional[str] = None
    completed_tasks: list[str] = []
    findings: list[dict] = []
    draft_report: Optional[str] = None
    final_report: Optional[str] = None
    error: Optional[str] = None


# In-memory storage for research sessions (use Redis in production)
_research_sessions: dict[str, ResearchGraph] = {}


@router.post("/research", response_model=ResearchResponse)
async def create_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
) -> ResearchResponse:
    """
    Create a new research task.

    Initiates an autonomous research workflow using LangGraph.
    """
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(f"Creating research task for session: {session_id}")
    logger.info(f"Query: {request.query[:100]}...")

    try:
        # Create research graph instance
        research_graph = ResearchGraph(
            session_id=session_id,
            query=request.query,
            max_reflections=request.max_reflections,
        )

        # Store in session
        _research_sessions[session_id] = research_graph

        # Start research in background
        background_tasks.add_task(research_graph.run)

        return ResearchResponse(
            session_id=session_id,
            status="initiated",
            message="Research task started. Use session_id to check status.",
        )

    except Exception as e:
        logger.error(f"Error creating research task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create research task: {str(e)}",
        )


@router.get("/research/{session_id}/status", response_model=ResearchStatusResponse)
async def get_research_status(session_id: str) -> ResearchStatusResponse:
    """
    Get the status of a research task.
    """
    if session_id not in _research_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    research_graph = _research_sessions[session_id]
    state = research_graph.get_state()

    return ResearchStatusResponse(
        session_id=session_id,
        status=state.get("status", "unknown"),
        progress=state.get("progress", 0.0),
        current_agent=state.get("current_agent"),
        completed_tasks=state.get("completed_tasks", []),
        findings=state.get("findings", []),
        draft_report=state.get("draft_report"),
        final_report=state.get("final_report"),
        error=state.get("error"),
    )


@router.get("/research/{session_id}/stream", response_model=None)
async def stream_research(session_id: str):
    """
    Stream research progress via Server-Sent Events.
    """
    if session_id not in _research_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    research_graph = _research_sessions[session_id]

    async for event in research_graph.stream_events():
        yield f"data: {event}\n\n"


@router.delete("/research/{session_id}")
async def cancel_research(session_id: str) -> dict:
    """
    Cancel a running research task.
    """
    if session_id not in _research_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    research_graph = _research_sessions[session_id]
    research_graph.cancel()

    del _research_sessions[session_id]

    return {"message": "Research task cancelled", "session_id": session_id}


@router.get("/research")
async def list_research_sessions(
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """
    List all research sessions.
    """
    sessions = list(_research_sessions.keys())[offset : offset + limit]

    return {
        "sessions": sessions,
        "total": len(_research_sessions),
        "limit": limit,
        "offset": offset,
    }
