"""
LangGraph Research Orchestrator.

Builds and manages the state graph for autonomous research workflows.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graphs.state import ResearchState, create_initial_state
from agents.planner import PlannerAgent
from agents.router import RouterAgent
from agents.reflection import ReflectionAgent
from agents.writer import WriterAgent

logger = logging.getLogger(__name__)


class ResearchGraph:
    """
    LangGraph-based research orchestrator.

    Manages the complete research workflow including:
    - Planning
    - Task routing
    - Parallel execution
    - Reflection loops
    - Report generation
    """

    def __init__(
        self,
        session_id: str,
        query: str,
        max_reflections: int = 3,
    ):
        """
        Initialize the research graph.

        Args:
            session_id: Unique session identifier
            query: Research query
            max_reflections: Maximum reflection cycles
        """
        self.session_id = session_id
        self.query = query
        self.max_reflections = max_reflections

        # Initialize state
        self.initial_state = create_initial_state(
            session_id=session_id,
            query=query,
            max_reflections=max_reflections,
        )

        # Initialize agents
        self.planner = PlannerAgent()
        self.router = RouterAgent()
        self.reflection = ReflectionAgent()
        self.writer = WriterAgent()

        # Build the graph
        self.graph = self._build_graph()

        # Current state
        self._current_state: Optional[ResearchState] = None
        self._cancelled = False

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("router", self._router_node)
        workflow.add_node("aggregator", self._aggregator_node)
        workflow.add_node("reflection", self._reflection_node)
        workflow.add_node("writer", self._writer_node)

        # Set entry point
        workflow.set_entry_point("planner")

        # Add edges
        workflow.add_edge("planner", "router")

        # Conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._should_execute_tasks,
            {
                "execute": "aggregator",
                "writer": "writer",
            },
        )

        # After aggregator, go to reflection
        workflow.add_edge("aggregator", "reflection")

        # Conditional routing from reflection
        workflow.add_conditional_edges(
            "reflection",
            self._should_continue_reflection,
            {
                "writer": "writer",
                "research": "router",
            },
        )

        # Writer is terminal
        workflow.add_edge("writer", END)

        # Compile with checkpointing
        checkpointer = MemorySaver()
        compiled = workflow.compile(checkpointer=checkpointer)

        return compiled

    async def _planner_node(self, state: ResearchState) -> Dict[str, Any]:
        """Execute planner agent."""
        logger.info(f"[{self.session_id}] Running planner agent")

        state["current_agent"] = "planner"
        state["status"] = "planning"

        result = await self.planner.execute(state)

        return result

    async def _router_node(self, state: ResearchState) -> Dict[str, Any]:
        """Execute router agent."""
        logger.info(f"[{self.session_id}] Running router agent")

        state["current_agent"] = "router"
        state["status"] = "routing"

        result = await self.router.execute(state)

        return result

    async def _aggregator_node(self, state: ResearchState) -> Dict[str, Any]:
        """Aggregate results from parallel tasks."""
        logger.info(f"[{self.session_id}] Aggregating task results")

        state["current_agent"] = "aggregator"
        state["status"] = "aggregating"

        # In a full implementation, this would collect results from
        # Celery tasks and merge them into findings
        # For now, we'll simulate aggregation

        return {
            "progress": min(state["progress"] + 0.2, 1.0),
        }

    async def _reflection_node(self, state: ResearchState) -> Dict[str, Any]:
        """Execute reflection agent."""
        logger.info(f"[{self.session_id}] Running reflection agent")

        state["current_agent"] = "reflection"
        state["status"] = "reflecting"

        result = await self.reflection.execute(state)

        return result

    async def _writer_node(self, state: ResearchState) -> Dict[str, Any]:
        """Execute writer agent."""
        logger.info(f"[{self.session_id}] Running writer agent")

        state["current_agent"] = "writer"
        state["status"] = "writing"

        result = await self.writer.execute(state)

        return result

    def _should_execute_tasks(self, state: ResearchState) -> str:
        """
        Determine if we should execute tasks or go directly to writing.

        This is a conditional edge function.
        """
        if state.get("tasks"):
            return "execute"
        return "writer"

    def _should_continue_reflection(self, state: ResearchState) -> str:
        """
        Reflection guardrail - enforce max_reflections limit.

        This is the critical safety mechanism that prevents infinite loops.
        """
        reflection_count = state.get("reflection_count", 0)
        max_reflections = state.get("max_reflections", 3)

        logger.info(f"[{self.session_id}] Reflection check: {reflection_count}/{max_reflections}")

        if reflection_count >= max_reflections:
            logger.info(f"[{self.session_id}] Max reflections reached, proceeding to writer")
            return "writer"

        # Check if we have sufficient findings
        findings_count = len(state.get("findings", []))
        if findings_count >= 3:
            logger.info(f"[{self.session_id}] Sufficient findings, proceeding to writer")
            return "writer"

        return "research"

    async def run(self) -> ResearchState:
        """
        Execute the research graph.

        Returns:
            Final state after graph execution
        """
        logger.info(f"[{self.session_id}] Starting research graph execution")

        try:
            # Run the graph
            async for event in self.graph.astream(
                self.initial_state,
                config={"configurable": {"thread_id": self.session_id}},
            ):
                if self._cancelled:
                    break

                # Log events for debugging
                for node_name, node_output in event.items():
                    logger.debug(f"[{self.session_id}] Node: {node_name}")

                # Update current state
                self._current_state = event

            logger.info(f"[{self.session_id}] Research graph completed")

            return self.get_state()

        except Exception as e:
            logger.error(f"[{self.session_id}] Error in research graph: {e}")
            if self._current_state:
                self._current_state["error_state"] = {
                    "error": str(e),
                    "stage": self._current_state.get("current_agent", "unknown"),
                }
            raise

    async def stream_events(self) -> AsyncGenerator[str, None]:
        """Stream graph events for real-time updates."""
        try:
            async for event in self.graph.astream(
                self.initial_state,
                config={"configurable": {"thread_id": self.session_id}},
            ):
                if self._cancelled:
                    break

                yield str(event)

        except Exception as e:
            logger.error(f"[{self.session_id}] Error streaming events: {e}")
            yield f'{{"error": "{str(e)}"}}'

    def get_state(self) -> ResearchState:
        """Get current graph state."""
        if self._current_state:
            # Get the last node's output
            return list(self._current_state.values())[-1]
        return self.initial_state

    def cancel(self) -> None:
        """Cancel the running research task."""
        logger.info(f"[{self.session_id}] Cancelling research task")
        self._cancelled = True
