"""
LangGraph Research Orchestrator with distributed execution.

This module implements the complete research workflow with:
- Parallel task dispatch via Celery
- Async task execution
- Distributed result aggregation
- Reflection safety enforcement
- Token usage tracking
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, AsyncGenerator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graphs.state import ResearchState, create_initial_state
from agents.planner import PlannerAgent
from agents.router import RouterAgent
from agents.reflection import ReflectionAgent
from agents.writer import WriterAgent
from observability.langsmith import traceable

from workers.routing import TaskRouter, TaskType, get_router
from workers.tasks.research import web_search, github_analysis, pdf_analysis
from workers.tasks.browser import browser_navigate
from workers.tasks.rag import semantic_retrieval
from workers.tasks.reflection import analyze_findings

logger = logging.getLogger(__name__)


class DistributedResearchGraph:
    """
    LangGraph-based distributed research orchestrator.

    Manages the complete research workflow including:
    - Planning
    - Task routing
    - Parallel Celery task dispatch
    - Result aggregation
    - Reflection loops
    - Report generation

    Key features:
    - Distributed task execution via Celery
    - Async result collection
    - Partial failure tolerance
    - Reflection safety enforcement
    """

    def __init__(
        self,
        session_id: str,
        query: str,
        max_reflections: int = 3,
    ):
        """
        Initialize the distributed research graph.

        Args:
            session_id: Unique session identifier
            query: Research query
            max_reflections: Maximum reflection cycles
        """
        self.session_id = session_id
        self.query = query
        self.max_reflections = max_reflections

        # Generate workflow ID for distributed tracing
        self.workflow_id = f"wf_{session_id[:8]}"

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

        # Initialize task router for distributed execution
        self.task_router = get_router()

        # Build the graph
        self.graph = self._build_graph()

        # Current state
        self._current_state: Optional[ResearchState] = None
        self._cancelled = False

        # Pending Celery tasks for tracking
        self._pending_tasks: Dict[str, Any] = {}

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine with distributed execution."""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("router", self._router_node)
        workflow.add_node("dispatcher", self._dispatcher_node)
        workflow.add_node("aggregator", self._aggregator_node)
        workflow.add_node("reflection", self._reflection_node)
        workflow.add_node("writer", self._writer_node)

        # Set entry point
        workflow.set_entry_point("planner")

        # Edge: planner -> router
        workflow.add_edge("planner", "router")

        # Conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._should_execute_tasks,
            {
                "dispatch": "dispatcher",
                "writer": "writer",
            },
        )

        # Edge: dispatcher -> aggregator (after parallel tasks complete)
        workflow.add_edge("dispatcher", "aggregator")

        # Edge: aggregator -> reflection
        workflow.add_edge("aggregator", "reflection")

        # Conditional routing from reflection (ENFORCEMENT POINT)
        workflow.add_conditional_edges(
            "reflection",
            self._should_continue_reflection,
            {
                "writer": "writer",
                "router": "router",  # Continue research loop
            },
        )

        # Writer is terminal
        workflow.add_edge("writer", END)

        # Compile with checkpointing
        checkpointer = MemorySaver()
        compiled = workflow.compile(checkpointer=checkpointer)

        return compiled

    async def _planner_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute planner agent to decompose the query into tasks.

        Args:
            state: Current research state

        Returns:
            Updated state with tasks
        """
        logger.info(f"[{self.session_id}] Running planner agent")

        state["current_agent"] = "planner"
        state["status"] = "planning"

        try:
            result = await self.planner.execute(state)

            # Add workflow tracking
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["workflow_id"] = self.workflow_id
            result["metadata"]["planner_completed"] = True

            logger.info(
                f"[{self.session_id}] Planner generated {len(result.get('tasks', []))} tasks"
            )
            return result

        except Exception as e:
            logger.error(f"[{self.session_id}] Planner failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "planner",
                    "workflow_id": self.workflow_id,
                },
                "status": "failed",
            }

    async def _router_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute router agent to categorize and prepare tasks.

        Args:
            state: Current research state

        Returns:
            Updated state with categorized tasks
        """
        logger.info(f"[{self.session_id}] Running router agent")

        state["current_agent"] = "router"
        state["status"] = "routing"

        try:
            result = await self.router.execute(state)

            # Track routing completion
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["router_completed"] = True

            # Extract active task IDs
            active_tasks = result.get("active_tasks", [])
            logger.info(f"[{self.session_id}] Router activated {len(active_tasks)} tasks")

            return result

        except Exception as e:
            logger.error(f"[{self.session_id}] Router failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "router",
                    "workflow_id": self.workflow_id,
                },
                "status": "failed",
            }

    async def _dispatcher_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Dispatch tasks to Celery workers for parallel execution.

        This is the key distributed execution node that:
        1. Dispatches tasks to appropriate queues
        2. Tracks pending tasks
        3. Handles task correlation

        Args:
            state: Current research state

        Returns:
            Updated state with pending tasks
        """
        logger.info(f"[{self.session_id}] Dispatching tasks to Celery")

        state["current_agent"] = "dispatcher"
        state["status"] = "dispatching"

        tasks = state.get("tasks", [])
        pending_task_ids = []
        dispatch_results = []

        for task in tasks:
            task_id = task.get("id", str(uuid.uuid4())[:8])
            task_type = task.get("type", "general")
            description = task.get("description", "")

            # Create correlation ID for tracking
            correlation_id = f"{self.session_id}_{task_id}"

            try:
                # Dispatch based on task type
                celery_result = self._dispatch_task(
                    task_type=task_type,
                    task_id=task_id,
                    description=description,
                    correlation_id=correlation_id,
                )

                # Track pending task
                self._pending_tasks[correlation_id] = {
                    "celery_id": celery_result.id,
                    "task_type": task_type,
                    "task_id": task_id,
                    "dispatched_at": None,
                }

                pending_task_ids.append(correlation_id)
                dispatch_results.append(
                    {
                        "correlation_id": correlation_id,
                        "celery_id": celery_result.id,
                        "status": "dispatched",
                    }
                )

                logger.debug(f"[{self.session_id}] Dispatched {task_type} task {task_id}")

            except Exception as e:
                logger.error(f"[{self.session_id}] Failed to dispatch {task_type} task: {e}")
                dispatch_results.append(
                    {
                        "task_id": task_id,
                        "task_type": task_type,
                        "status": "failed",
                        "error": str(e),
                    }
                )

        logger.info(f"[{self.session_id}] Dispatched {len(pending_task_ids)} tasks to workers")

        return {
            "active_tasks": pending_task_ids,
            "dispatch_results": dispatch_results,
            "status": "dispatched",
            "metadata": {
                "dispatcher_completed": True,
                "total_dispatched": len(pending_task_ids),
                "workflow_id": self.workflow_id,
            },
        }

    def _dispatch_task(
        self,
        task_type: str,
        task_id: str,
        description: str,
        correlation_id: str,
    ):
        """
        Dispatch a single task to the appropriate Celery queue.

        Args:
            task_type: Type of task (web_search, github, etc.)
            task_id: Task identifier
            description: Task description
            correlation_id: Correlation ID for tracking

        Returns:
            Celery AsyncResult
        """
        # Map task types to Celery tasks
        task_mapping = {
            "web_search": web_search,
            "github_analysis": github_analysis,
            "pdf_analysis": pdf_analysis,
            "browser": browser_navigate,
            "rag": semantic_retrieval,
        }

        celery_task = task_mapping.get(task_type, web_search)

        # Extract parameters based on task type
        if task_type == "web_search":
            params = {
                "query": description,
                "session_id": self.session_id,
            }
        elif task_type == "github_analysis":
            params = {
                "repo_url": description,
                "session_id": self.session_id,
            }
        elif task_type == "pdf_analysis":
            params = {
                "file_path": description,
                "session_id": self.session_id,
            }
        elif task_type == "browser":
            params = {
                "url": description,
                "session_id": self.session_id,
            }
        else:
            params = {
                "query": description,
                "session_id": self.session_id,
            }

        # Add correlation ID
        params["correlation_id"] = correlation_id

        # Dispatch to Celery
        result = celery_task.delay(**params)

        return result

    async def _aggregator_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Aggregate results from distributed Celery tasks.

        This is the production-grade Aggregator Node that:
        1. Waits for task completion
        2. Merges findings from all workers
        3. Deduplicates sources
        4. Tracks failed tasks
        5. Collects metadata
        6. Tolerates partial failures

        Args:
            state: Current research state with pending tasks

        Returns:
            Updated state with aggregated findings
        """
        logger.info(f"[{self.session_id}] Aggregating results from workers")

        state["current_agent"] = "aggregator"
        state["status"] = "aggregating"

        pending_tasks = state.get("active_tasks", [])
        completed_findings = []
        completed_sources = []
        failed_tasks = []

        # Wait for all tasks with timeout
        timeout = 120  # seconds
        start_time = asyncio.get_event_loop().time()

        for correlation_id in pending_tasks:
            if self._cancelled:
                break

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"[{self.session_id}] Aggregation timeout reached")
                break

            # Get task info from router
            task_info = self._pending_tasks.get(correlation_id, {})
            celery_id = task_info.get("celery_id")

            if celery_id:
                try:
                    # Wait for task completion with polling
                    result = await self._wait_for_task(celery_id, timeout - elapsed)

                    if result.ready():
                        if result.successful():
                            task_result = result.result
                            completed_findings.extend(
                                self._extract_findings(task_result, task_info.get("task_type"))
                            )
                            completed_sources.extend(self._extract_sources(task_result))
                            logger.debug(f"[{self.session_id}] Task {correlation_id} completed")
                        else:
                            # Task failed
                            failed_tasks.append(
                                {
                                    "correlation_id": correlation_id,
                                    "celery_id": celery_id,
                                    "error": str(result.result),
                                    "task_type": task_info.get("task_type"),
                                }
                            )
                            logger.warning(
                                f"[{self.session_id}] Task {correlation_id} failed: {result.result}"
                            )
                    else:
                        # Task still running - add to failed (timeout)
                        failed_tasks.append(
                            {
                                "correlation_id": correlation_id,
                                "celery_id": celery_id,
                                "error": "timeout",
                                "task_type": task_info.get("task_type"),
                            }
                        )

                except Exception as e:
                    logger.error(f"[{self.session_id}] Error collecting task {correlation_id}: {e}")
                    failed_tasks.append(
                        {
                            "correlation_id": correlation_id,
                            "error": str(e),
                            "task_type": task_info.get("task_type"),
                        }
                    )

        # Deduplicate findings and sources
        unique_findings = self._deduplicate_findings(completed_findings)
        unique_sources = list(set(completed_sources))

        # Aggregate token usage from results
        total_tokens = self._sum_token_usage(completed_findings)

        logger.info(
            f"[{self.session_id}] Aggregation complete: "
            f"{len(unique_findings)} findings, "
            f"{len(unique_sources)} sources, "
            f"{len(failed_tasks)} failed"
        )

        return {
            "findings": unique_findings,
            "sources": unique_sources,
            "failed_tasks": failed_tasks,
            "completed_tasks": [
                t["correlation_id"]
                for t in pending_tasks
                if t not in [f["correlation_id"] for f in failed_tasks]
            ],
            "active_tasks": [],  # Clear active tasks after aggregation
            "status": "aggregated",
            "progress": 0.6,
            "metadata": {
                "aggregator_completed": True,
                "total_findings": len(unique_findings),
                "total_sources": len(unique_sources),
                "failed_count": len(failed_tasks),
                "workflow_id": self.workflow_id,
            },
            "token_usage": {
                "total": total_tokens,
                "breakdown": {
                    "research": total_tokens,
                },
            },
        }

    async def _wait_for_task(self, celery_id: str, timeout: float) -> Any:
        """
        Wait for a Celery task to complete.

        Args:
            celery_id: Celery task ID
            timeout: Maximum wait time in seconds

        Returns:
            AsyncResult
        """
        # Use asyncio to wait without blocking
        for _ in range(int(timeout * 10)):  # Poll every 100ms
            if self._cancelled:
                break

            from workers.celery_app import celery_app
            from celery.result import AsyncResult

            result = AsyncResult(celery_id, app=celery_app)

            if result.ready():
                return result

            await asyncio.sleep(0.1)

        # Return a result indicating timeout
        from celery.result import AsyncResult

        return AsyncResult(celery_id, app=celery_app)

    def _extract_findings(self, result: Any, task_type: str) -> List[Dict[str, Any]]:
        """Extract findings from task result."""
        findings = []

        if isinstance(result, dict):
            if "results" in result:
                for r in result["results"]:
                    findings.append(
                        {
                            "summary": r.get("snippet", str(r)),
                            "source": r.get("url", ""),
                            "type": task_type,
                            "collected_at": None,
                        }
                    )

            if "analysis" in result:
                findings.append(
                    {
                        "summary": result["analysis"].get("summary", ""),
                        "source": result.get("repo_url", result.get("file_path", "")),
                        "type": "analysis",
                        "collected_at": None,
                    }
                )

        return findings

    def _extract_sources(self, result: Any) -> List[str]:
        """Extract sources from task result."""
        sources = []

        if isinstance(result, dict):
            if "results" in result:
                for r in result["results"]:
                    if "url" in r:
                        sources.append(r["url"])

            if "sources" in result:
                sources.extend(result["sources"])

        return sources

    def _deduplicate_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate findings by content."""
        seen = set()
        unique = []

        for finding in findings:
            content = finding.get("summary", "")
            source = finding.get("source", "")

            key = (content, source)
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique

    def _sum_token_usage(self, findings: List[Dict[str, Any]]) -> int:
        """Sum token usage from findings."""
        # In production, extract actual token counts
        return len(findings) * 100  # Mock token count

    async def _reflection_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute reflection agent with safety enforcement.

        This is the reflection agent execution node that:
        1. Analyzes current findings
        2. Triggers additional research if needed
        3. Enforces max_reflections limit

        Args:
            state: Current research state

        Returns:
            Updated state with reflection results
        """
        logger.info(f"[{self.session_id}] Running reflection agent")

        state["current_agent"] = "reflection"

        # CRITICAL: Check reflection count BEFORE execution
        reflection_count = state.get("reflection_count", 0)
        max_reflections = state.get("max_reflections", 3)

        if reflection_count >= max_reflections:
            logger.info(
                f"[{self.session_id}] REFLECTION SAFETY: Max reflections ({max_reflections}) reached"
            )
            return {
                "next_action": "writer",
                "status": "reflection_complete",
                "metadata": {
                    "reflection_stopped": True,
                    "reason": "max_reflections_reached",
                    "reflection_count": reflection_count,
                    "max_reflections": max_reflections,
                },
            }

        state["status"] = "reflecting"

        try:
            result = await self.reflection.execute(state)

            # Add reflection tracking
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["reflection_count"] = result.get("reflection_count", 0)
            result["metadata"]["reflection_enforced"] = True

            logger.info(
                f"[{self.session_id}] Reflection cycle {result.get('reflection_count', 0)} complete"
            )
            return result

        except Exception as e:
            logger.error(f"[{self.session_id}] Reflection failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "reflection",
                    "workflow_id": self.workflow_id,
                },
                "status": "failed",
            }

    async def _writer_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute writer agent to generate final report.

        Args:
            state: Current research state with all findings

        Returns:
            Updated state with final report
        """
        logger.info(f"[{self.session_id}] Running writer agent")

        state["current_agent"] = "writer"
        state["status"] = "writing"

        try:
            result = await self.writer.execute(state)

            # Add completion metadata
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["writer_completed"] = True
            result["metadata"]["workflow_id"] = self.workflow_id
            result["metadata"]["completed_at"] = None

            logger.info(f"[{self.session_id}] Final report generated")
            return result

        except Exception as e:
            logger.error(f"[{self.session_id}] Writer failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "writer",
                    "workflow_id": self.workflow_id,
                },
                "status": "failed",
            }

    def _should_execute_tasks(self, state: ResearchState) -> str:
        """
        Determine if we should execute tasks or go directly to writing.

        This is a conditional edge function.

        Args:
            state: Current research state

        Returns:
            Routing decision
        """
        tasks = state.get("tasks", [])

        if tasks and len(tasks) > 0:
            return "dispatch"
        return "writer"

    def _should_continue_reflection(self, state: ResearchState) -> str:
        """
        REFLECTION SAFETY GUARDRAIL - Enforce max_reflections limit.

        This is the CRITICAL safety mechanism that prevents infinite loops.
        It is called at the end of every reflection cycle.

        Args:
            state: Current research state

        Returns:
            Routing decision: "writer" to stop, "router" to continue
        """
        reflection_count = state.get("reflection_count", 0)
        max_reflections = state.get("max_reflections", 3)
        findings = state.get("findings", [])

        # Log the reflection check
        logger.info(
            f"[{self.session_id}] REFLECTION CHECK: "
            f"{reflection_count}/{max_reflections} cycles, "
            f"{len(findings)} findings"
        )

        # CRITICAL: Hard stop on max reflections
        if reflection_count >= max_reflections:
            logger.info(
                f"[{self.session_id}] REFLECTION STOPPED: "
                f"Max reflections ({max_reflections}) reached"
            )
            return "writer"

        # Check for sufficient findings
        if len(findings) >= 5:
            logger.info(
                f"[{self.session_id}] REFLECTION STOPPED: Sufficient findings ({len(findings)})"
            )
            return "writer"

        # Check for failed state
        if state.get("error_state"):
            logger.warning(f"[{self.session_id}] REFLECTION STOPPED: Error state present")
            return "writer"

        # Continue research loop
        logger.info(f"[{self.session_id}] REFLECTION CONTINUE: Need more research")
        return "router"

    @traceable(name="research.run", run_type="chain")
    async def run(self) -> ResearchState:
        """
        Execute the distributed research graph.

        Returns:
            Final state after graph execution
        """
        logger.info(f"[{self.session_id}] Starting distributed research execution")
        logger.info(f"[{self.session_id}] Workflow ID: {self.workflow_id}")

        try:
            # Run the graph
            async for event in self.graph.astream(
                self.initial_state,
                config={"configurable": {"thread_id": self.session_id}},
            ):
                if self._cancelled:
                    logger.info(f"[{self.session_id}] Execution cancelled")
                    break

                # Log events for debugging
                for node_name, node_output in event.items():
                    logger.debug(f"[{self.session_id}] Node {node_name} executed")

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
                    "workflow_id": self.workflow_id,
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


# Backwards compatibility alias
ResearchGraph = DistributedResearchGraph
