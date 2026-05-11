"""
Writer Agent for Research OS.

Responsible for:
- Aggregating findings
- Writing reports
- Improving readability
"""

import logging
from typing import Any, Dict

from datetime import datetime

from agents.base import BaseAgent
from graphs.state import ResearchState
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """
    Writer agent for generating final research reports.

    Aggregates all findings and produces a polished report.
    """

    def __init__(self):
        super().__init__(agent_name="writer")
        self.ollama = OllamaClient()

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the writer agent.

        Generates the final research report.

        Args:
            state: Current research state with all findings

        Returns:
            Updated state with final report
        """
        session_id = state["session_id"]

        logger.info(f"[{session_id}] Generating final report")

        try:
            # Generate draft report
            draft = await self._generate_draft(state)

            # Refine into final report
            final = await self._refine_report(draft, state)

            logger.info(f"[{session_id}] Report generated successfully")

            return {
                "draft_report": draft,
                "final_report": final,
                "status": "completed",
                "progress": 1.0,
                "metadata": {
                    "completed_at": datetime.utcnow().isoformat(),
                    "total_reflections": state.get("reflection_count", 0),
                },
            }

        except Exception as e:
            logger.error(f"[{session_id}] Report generation failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "writing",
                },
                "status": "failed",
            }

    async def _generate_draft(self, state: ResearchState) -> str:
        """
        Generate a draft report from findings.

        Args:
            state: Current research state

        Returns:
            Draft report string
        """
        query = state["query"]
        findings = state.get("findings", [])
        sources = state.get("sources", [])
        reflections = state.get("reflections", [])

        # Build findings context
        findings_text = ""
        for i, finding in enumerate(findings, 1):
            summary = finding.get("summary", "No summary")
            source = finding.get("source", "Unknown")
            findings_text += f"\n{i}. {summary} (Source: {source})"

        if not findings_text:
            findings_text = "No specific findings recorded."

        # Build sources context
        sources_text = "\n".join([f"- {s}" for s in sources]) or "No sources cited."

        # Build reflections context
        reflections_text = ""
        for i, reflection in enumerate(reflections, 1):
            reflections_text += f"\n### Reflection {i}\n{reflection}\n"

        if not reflections_text:
            reflections_text = "No reflections recorded."

        prompt = f"""You are a research writer. Create a comprehensive research report.

# Research Query
{query}

# Findings
{findings_text}

# Sources
{sources_text}

# Reflections
{reflections_text}

Write a well-structured research report that:
1. Starts with an executive summary
2. Presents findings in a logical order
3. Includes proper citations
4. Provides analysis and insights
5. Concludes with key takeaways

Make it professional, clear, and informative."""

        draft = await self.ollama.generate(prompt)
        return draft

    async def _refine_report(self, draft: str, state: ResearchState) -> str:
        """
        Refine the draft into a polished final report.

        Args:
            draft: Draft report
            state: Current research state

        Returns:
            Final refined report
        """
        query = state["query"]

        prompt = f"""Refine the following research report for better readability and quality.

Original Query: {query}

Draft Report:
{draft}

Improve the report by:
1. Fixing any awkward phrasing
2. Improving structure and flow
3. Enhancing clarity
4. Ensuring consistent formatting
5. Adding appropriate transitions

Return the refined report only, without explanations."""

        final = await self.ollama.generate(prompt)
        return final
