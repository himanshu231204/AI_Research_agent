"""
Summarization Pipeline for Research OS.

Provides:
- Async summarization
- Batch processing
- Context-aware summaries
- Key point extraction
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """Result of summarization."""

    summary: str
    key_points: List[str]
    entities: List[str]
    tokens_used: int
    generated_at: datetime
    quality_score: float


class Summarizer:
    """
    Summarization service for memory compression.

    Generates concise summaries while preserving key information.
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize summarizer.

        Args:
            model: Optional model override
        """
        self.ollama = OllamaClient(model=model or "llama3")

    async def summarize(
        self,
        content: str,
        style: str = "concise",
        max_length: int = 500,
    ) -> str:
        """
        Generate a summary of content.

        Args:
            content: Content to summarize
            style: Summarization style (concise | detailed | bullet_points)
            max_length: Maximum summary length

        Returns:
            Summary string
        """
        style_prompts = {
            "concise": "Provide a concise summary",
            "detailed": "Provide a detailed summary",
            "bullet_points": "Provide key points as bullet points",
        }

        prompt = f"""{style_prompts.get(style, "Provide a summary")}.

Content:
{content}

Summary ({max_length} words max):"""

        try:
            summary = await self.ollama.generate(prompt)
            return summary

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return content[:max_length]

    async def summarize_findings(
        self,
        findings: List[Dict[str, Any]],
        query: str,
    ) -> SummaryResult:
        """
        Summarize research findings.

        Args:
            findings: List of research findings
            query: Original research query

        Returns:
            SummaryResult with summary, key points, entities
        """
        # Build findings context
        findings_text = "\n\n".join([f"- {f.get('summary', '')}" for f in findings[:10]])

        prompt = f"""Analyze the following research findings for the query: {query}

Findings:
{findings_text}

Provide a structured analysis with:
1. A concise summary (2-3 sentences)
2. Key points (bullet list)
3. Important entities, dates, or statistics mentioned

Format your response as:
SUMMARY: <summary>
KEY_POINTS: <bullet points>
ENTITIES: <important entities mentioned>"""

        try:
            response = await self.ollama.generate(prompt)
            return self._parse_findings_summary(response)

        except Exception as e:
            logger.error(f"Findings summarization failed: {e}")
            return SummaryResult(
                summary="Summary generation failed",
                key_points=[],
                entities=[],
                tokens_used=0,
                generated_at=datetime.utcnow(),
                quality_score=0.0,
            )

    def _parse_findings_summary(self, response: str) -> SummaryResult:
        """Parse structured response into SummaryResult."""
        summary = ""
        key_points = []
        entities = []

        current_section = None
        for line in response.split("\n"):
            line = line.strip()

            if line.startswith("SUMMARY:"):
                current_section = "summary"
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("KEY_POINTS:"):
                current_section = "key_points"
            elif line.startswith("ENTITIES:"):
                current_section = "entities"
            elif line.startswith("-") and current_section == "key_points":
                key_points.append(line[1:].strip())
            elif line and current_section == "key_points":
                key_points.append(line)
            elif line and current_section == "entities":
                entities.append(line)

        return SummaryResult(
            summary=summary or response[:200],
            key_points=key_points,
            entities=entities,
            tokens_used=len(response.split()),
            generated_at=datetime.utcnow(),
            quality_score=0.8,
        )

    async def extract_key_points(
        self,
        content: str,
        max_points: int = 5,
    ) -> List[str]:
        """
        Extract key points from content.

        Args:
            content: Content to analyze
            max_points: Maximum points to extract

        Returns:
            List of key points
        """
        prompt = f"""Extract the {max_points} most important key points from this content.

Content:
{content}

List each key point as a bullet point starting with "-":"""

        try:
            response = await self.ollama.generate(prompt)
            points = []

            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    points.append(line[1:].strip())
                elif points and len(points) < max_points:
                    points.append(line)

            return points[:max_points]

        except Exception as e:
            logger.error(f"Key point extraction failed: {e}")
            return []

    async def compare_summaries(
        self,
        summary1: str,
        summary2: str,
    ) -> Dict[str, Any]:
        """
        Compare two summaries for overlap and differences.

        Args:
            summary1: First summary
            summary2: Second summary

        Returns:
            Comparison result dict
        """
        prompt = f"""Compare these two summaries and identify:
1. Common information they share
2. Unique information in each
3. Any contradictions

Summary 1:
{summary1}

Summary 2:
{summary2}

Provide comparison in structured format:"""

        try:
            response = await self.ollama.generate(prompt)
            return {"comparison": response, "summary1": summary1, "summary2": summary2}

        except Exception as e:
            logger.error(f"Summary comparison failed: {e}")
            return {"comparison": "Comparison failed", "summary1": summary1, "summary2": summary2}

    async def batch_summarize(
        self,
        contents: List[str],
        style: str = "concise",
    ) -> List[str]:
        """
        Summarize multiple contents in batch.

        Args:
            contents: List of contents to summarize
            style: Summarization style

        Returns:
            List of summaries
        """
        # Process in parallel
        tasks = [self.summarize(c, style) for c in contents]
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        return [s if isinstance(s, str) else f"Summary failed: {str(s)}" for s in summaries]

    async def contextual_summary(
        self,
        history: List[str],
        current_query: str,
    ) -> str:
        """
        Generate a summary that provides context for current query.

        Args:
            history: Previous conversation/research
            current_query: Current research query

        Returns:
            Contextual summary
        """
        history_text = "\n\n".join(history[-5:])  # Last 5 items

        prompt = f"""Given the previous context and current query, provide relevant background.

Previous Context:
{history_text}

Current Query: {current_query}

Provide a brief contextual summary that connects the previous work to the current query:"""

        try:
            return await self.ollama.generate(prompt)

        except Exception as e:
            logger.error(f"Contextual summary failed: {e}")
            return ""
