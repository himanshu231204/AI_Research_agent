"""
Reflection Agent for Research OS.

Responsible for:
- Detecting hallucinations
- Validating outputs
- Improving reports
- Triggering additional research
"""

import logging
from typing import Any, Dict, List

from agents.base import BaseAgent
from graphs.state import ResearchState
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ReflectionAgent(BaseAgent):
    """
    Reflection/critic agent for validating and improving research outputs.

    Performs self-critique to ensure quality and completeness.
    """

    def __init__(self):
        super().__init__(agent_name="reflection")
        self.ollama = OllamaClient()

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the reflection agent.

        Analyzes current findings and determines if more research is needed.

        Args:
            state: Current research state

        Returns:
            Updated state with reflection results
        """
        session_id = state["session_id"]
        reflection_count = state.get("reflection_count", 0)
        max_reflections = state.get("max_reflections", 3)

        logger.info(
            f"[{session_id}] Running reflection (cycle {reflection_count + 1}/{max_reflections})"
        )

        try:
            # Analyze current state
            analysis = await self._analyze_findings(state)

            # Generate reflection
            reflection = await self._generate_reflection(state, analysis)

            # Update state
            new_reflection_count = reflection_count + 1

            logger.info(f"[{session_id}] Reflection complete: {reflection[:100]}...")

            return {
                "reflections": state.get("reflections", []) + [reflection],
                "reflection_count": new_reflection_count,
                "status": "reflected",
                "progress": min(0.5 + (new_reflection_count * 0.1), 0.9),
                "metadata": {
                    "last_reflection": reflection,
                    "analysis": analysis,
                },
            }

        except Exception as e:
            logger.error(f"[{session_id}] Reflection failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "reflection",
                },
                "status": "failed",
            }

    async def _analyze_findings(self, state: ResearchState) -> Dict[str, Any]:
        """
        Analyze current findings for quality and completeness.

        Args:
            state: Current research state

        Returns:
            Analysis results
        """
        findings = state.get("findings", [])
        tasks = state.get("tasks", [])
        completed_tasks = state.get("completed_tasks", [])

        analysis = {
            "total_findings": len(findings),
            "total_tasks": len(tasks),
            "completed_tasks": len(completed_tasks),
            "pending_tasks": len(tasks) - len(completed_tasks),
            "has_sufficient_data": len(findings) >= 3,
            "has_sources": len(state.get("sources", [])) > 0,
        }

        return analysis

    async def _generate_reflection(self, state: ResearchState, analysis: Dict[str, Any]) -> str:
        """
        Generate a reflection on the current research state.

        Args:
            state: Current research state
            analysis: Analysis results

        Returns:
            Reflection string
        """
        query = state["query"]
        findings = state.get("findings", [])
        sources = state.get("sources", [])

        # Build context for reflection
        findings_summary = (
            "\n".join([f"- {f.get('summary', 'No summary')}" for f in findings[:5]])
            or "No findings yet"
        )

        sources_list = "\n".join([f"- {s}" for s in sources[:5]]) or "No sources"

        prompt = f"""You are a research critic. Evaluate the current state of research 
and provide a critical reflection.

Original Query: {query}

Current Findings:
{findings_summary}

Sources:
{sources_list}

Analysis:
- Total findings: {analysis["total_findings"]}
- Tasks completed: {analysis["completed_tasks"]}/{analysis["total_tasks"]}
- Has sufficient data: {analysis["has_sufficient_data"]}

Provide a critical reflection that:
1. Evaluates the quality of current findings
2. Identifies gaps or missing information
3. Suggests areas for additional research
4. Assesses whether the research is complete

Be honest and critical. If more research is needed, say so."""

        reflection = await self.ollama.generate(prompt)
        return reflection
