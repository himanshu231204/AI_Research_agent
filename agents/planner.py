"""
Planner Agent for Research OS.

Responsible for:
- Query decomposition
- Planning
- Prioritization
- Strategy generation
"""

import logging
from typing import Any, Dict, List

from agents.base import BaseAgent
from graphs.state import ResearchState
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class PlannerAgent(BaseAgent):
    """
    Planner agent for decomposing research queries into actionable tasks.

    Uses Ollama to generate a structured plan for research execution.
    """

    def __init__(self):
        super().__init__(agent_name="planner")
        self.ollama = OllamaClient()

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the planner agent.

        Decomposes the user's query into a structured plan of tasks.

        Args:
            state: Current research state containing the query

        Returns:
            Updated state with tasks and strategy
        """
        query = state["query"]
        session_id = state["session_id"]

        logger.info(f"[{session_id}] Planning research for: {query[:100]}...")

        try:
            # Generate plan using Ollama
            plan = await self._generate_plan(query)

            # Parse plan into tasks
            tasks = self._parse_tasks(plan)

            logger.info(f"[{session_id}] Generated {len(tasks)} tasks")

            return {
                "tasks": tasks,
                "next_action": "router",
                "status": "planned",
                "progress": 0.1,
                "metadata": {
                    "planning_model": self.ollama.model_name,
                },
            }

        except Exception as e:
            logger.error(f"[{session_id}] Planning failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "planning",
                },
                "status": "failed",
            }

    async def _generate_plan(self, query: str) -> str:
        """
        Generate a research plan using Ollama.

        Args:
            query: User's research query

        Returns:
            Structured plan as string
        """
        prompt = f"""You are a research planner. Given the following query, 
create a detailed plan for conducting research.

Query: {query}

Create a plan with:
1. Key research areas to explore
2. Information sources to check
3. Analysis approach
4. Expected deliverables

Be specific and actionable. Format your response as a clear plan."""

        response = await self.ollama.generate(prompt)
        return response

    def _parse_tasks(self, plan: str) -> List[Dict[str, Any]]:
        """
        Parse the plan into structured tasks.

        Args:
            plan: The generated plan string

        Returns:
            List of task dictionaries
        """
        # Simple task parsing - in production, use more sophisticated parsing
        tasks = []

        # Split by lines and look for task-like content
        lines = [l.strip() for l in plan.split("\n") if l.strip()]

        task_id = 1
        for line in lines:
            # Look for numbered items or bullet points
            if line[0].isdigit() or line.startswith("-") or line.startswith("*"):
                # Extract task description
                task_text = line.lstrip("0123456789.-* ").strip()

                if task_text and len(task_text) > 10:
                    tasks.append(
                        {
                            "id": f"task_{task_id}",
                            "description": task_text,
                            "status": "pending",
                            "priority": task_id,
                            "type": self._infer_task_type(task_text),
                        }
                    )
                    task_id += 1

        # Ensure we have at least one task
        if not tasks:
            tasks.append(
                {
                    "id": "task_1",
                    "description": "Conduct comprehensive research on the query",
                    "status": "pending",
                    "priority": 1,
                    "type": "general",
                }
            )

        return tasks

    def _infer_task_type(self, description: str) -> str:
        """Infer the type of task from its description."""
        desc_lower = description.lower()

        if any(kw in desc_lower for kw in ["search", "web", "internet", "google"]):
            return "web_search"
        elif any(kw in desc_lower for kw in ["github", "repo", "code", "repository"]):
            return "github_analysis"
        elif any(kw in desc_lower for kw in ["pdf", "document", "paper", "read"]):
            return "pdf_analysis"
        elif any(kw in desc_lower for kw in ["browse", "visit", "website", "scrape"]):
            return "browser"
        else:
            return "general"
