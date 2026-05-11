"""
Router Agent for Research OS.

Responsible for:
- Determining required tools
- Routing tasks to specialized agents
- Managing task execution flow
"""

import logging
from typing import Any, Dict, List

from agents.base import BaseAgent
from graphs.state import ResearchState
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class RouterAgent(BaseAgent):
    """
    Router agent for directing tasks to appropriate execution paths.

    Analyzes tasks and determines the best way to execute them.
    """

    def __init__(self):
        super().__init__(agent_name="router")
        self.ollama = OllamaClient()

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the router agent.

        Analyzes tasks and prepares them for execution.

        Args:
            state: Current research state with tasks

        Returns:
            Updated state with active tasks
        """
        tasks = state.get("tasks", [])
        session_id = state["session_id"]

        logger.info(f"[{session_id}] Routing {len(tasks)} tasks")

        if not tasks:
            logger.warning(f"[{session_id}] No tasks to route")
            return {
                "next_action": "writer",
                "status": "routed",
            }

        try:
            # Analyze and categorize tasks
            categorized_tasks = await self._categorize_tasks(tasks)

            # Mark tasks as active
            active_task_ids = [t["id"] for t in categorized_tasks]

            logger.info(f"[{session_id}] Activated {len(active_task_ids)} tasks")

            return {
                "tasks": categorized_tasks,
                "active_tasks": active_task_ids,
                "next_action": "aggregator",
                "status": "routed",
                "progress": 0.2,
            }

        except Exception as e:
            logger.error(f"[{session_id}] Routing failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "routing",
                },
                "status": "failed",
            }

    async def _categorize_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Categorize tasks and add execution metadata.

        Args:
            tasks: List of task dictionaries

        Returns:
            Categorized tasks with execution metadata
        """
        categorized = []

        for task in tasks:
            task_type = task.get("type", "general")

            # Add execution metadata based on task type
            execution_info = self._get_execution_info(task_type)

            categorized_task = {
                **task,
                "execution": execution_info,
                "status": "ready",
            }

            categorized.append(categorized_task)

        return categorized

    def _get_execution_info(self, task_type: str) -> Dict[str, Any]:
        """
        Get execution metadata for a task type.

        Args:
            task_type: Type of task

        Returns:
            Execution metadata dictionary
        """
        execution_map = {
            "web_search": {
                "method": "celery",
                "queue": "research",
                "agent": "web_research",
                "timeout": 60,
            },
            "github_analysis": {
                "method": "celery",
                "queue": "research",
                "agent": "github",
                "timeout": 120,
            },
            "pdf_analysis": {
                "method": "celery",
                "queue": "research",
                "agent": "pdf_rag",
                "timeout": 180,
            },
            "browser": {
                "method": "celery",
                "queue": "browser",
                "agent": "browser_automation",
                "timeout": 300,
            },
            "general": {
                "method": "async",
                "queue": None,
                "agent": "general",
                "timeout": 60,
            },
        }

        return execution_map.get(task_type, execution_map["general"])
