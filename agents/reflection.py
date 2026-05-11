"""
Advanced Reflection/Critic Agent for Research OS.

Implements:
- Structured reflection outputs
- Hallucination detection
- Confidence scoring
- Missing topic identification
- Citation verification
- Task regeneration for research gaps
- Reflection loop intelligence
"""

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from agents.reflection_schema import (
    ReflectionResult,
    ReflectionResultDict,
    CitationIssue,
    MissingTopic,
    ResearchTask,
    ConfidenceLevel,
    HallucinationSeverity,
)
from graphs.state import ResearchState
from models.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# Reflection system prompts
REFLECTION_SYSTEM_PROMPT = """You are an expert research critic and quality assurance agent.
Your role is to evaluate research quality, detect issues, and guide improvements.

Evaluation Framework:
1. **Evidence Quality**: Assess the strength and breadth of evidence
2. **Citation Validity**: Verify sources are properly cited and credible
3. **Reasoning Soundness**: Evaluate logical consistency and coherence
4. **Completeness**: Identify gaps in coverage or missing perspectives
5. **Hallucination Detection**: Look for unsupported claims or fabricated facts

Be critical but constructive. Your goal is to improve research quality.

Output Format:
When evaluating, provide structured feedback with:
- confidence_score: 0.0-1.0
- hallucination_risk: 0.0-1.0
- reasoning_quality: 0.0-1.0
- missing_topics: list of topics needing more research
- citation_issues: list of citation problems
- recommended_actions: list of improvement actions
- requires_additional_research: boolean
"""

HALLUCINATION_CHECK_PROMPT = """Analyze the following content for potential hallucinations.

Check for:
1. **Unsourced claims**: Assertions without supporting citations
2. **Fabricated facts**: Numbers, dates, or details that seem invented
3. **Outdated information**: Claims that contradict current knowledge
4. **Contradictory statements**: Claims that contradict each other
5. **Overconfident language**: Absolute statements without qualification

Content to analyze:
{content}

Sources cited:
{sources}

Provide a hallucination risk assessment (0.0-1.0) and identify any problematic claims."""

CITATION_VERIFY_PROMPT = """Verify the following citations for a research report.

Original Query: {query}

Citations to verify:
{citations}

For each citation, check:
1. Is the source credible? (reputable domain, peer-reviewed, etc.)
2. Does it support the claims attributed to it?
3. Is the URL/reference valid format?
4. Are there broken or inaccessible links?
5. Are there hallucinated (fabricated) citations?

Report any issues found."""

CONFIDENCE_ASSESSMENT_PROMPT = """Assess the confidence level of this research.

Query: {query}

Findings:
{findings}

Sources: {sources}

Consider:
- Number and diversity of sources
- Source credibility and reputation
- Evidence consistency across findings
- Presence of expert consensus
- Quality of citations

Provide:
- confidence_score: 0.0-1.0
- confidence_level: high | medium | low | uncertain
- reasoning: brief explanation

Output format:
CONF_LEVEL: <high/medium/low/uncertain>
CONF_SCORE: <0.0-1.0>
REASONING: <brief explanation>"""

TASK_REGENERATION_PROMPT = """Based on the research gaps identified, generate new research tasks.

Original Query: {query}

Current Coverage:
- Total findings: {findings_count}
- Sources cited: {sources_count}
- Missing topics: {missing_topics}

Identified Gaps:
{gaps}

Generate {count} new research tasks to address these gaps.

For each task, provide:
- id: unique identifier
- description: what to research
- type: web_search | github_analysis | pdf_analysis | browser
- priority: 1-10
- target_topics: topics this addresses
- suggested_sources: where to look

Output as JSON array of task objects."""


class ReflectionAgent(BaseAgent):
    """
    Advanced Reflection/Critic agent for validating and improving research.

    Performs comprehensive quality assessment including:
    - Hallucination detection with risk scoring
    - Citation verification and validation
    - Confidence scoring based on evidence quality
    - Missing topic identification
    - Task regeneration for research gaps
    - Reflection loop intelligence with termination safety

    The agent produces structured outputs for programmatic decision-making.
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the reflection agent.

        Args:
            model: Optional Ollama model override
        """
        super().__init__(agent_name="reflection")
        self.ollama = OllamaClient(model=model or "mistral")
        self._reflection_cache: Dict[str, ReflectionResult] = {}

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the reflection agent.

        Evaluates current research state and produces structured feedback.

        Args:
            state: Current research state

        Returns:
            Updated state with reflection results
        """
        session_id = state["session_id"]
        reflection_count = state.get("reflection_count", 0)
        max_reflections = state.get("max_reflections", 3)

        logger.info(
            f"[{session_id}] Running advanced reflection (cycle {reflection_count + 1}/{max_reflections})"
        )

        try:
            # Run comprehensive reflection
            result = await self._run_reflection(state)

            # Convert to state updates
            state_updates = self._build_state_updates(result)

            # Add tracking metadata
            state_updates["metadata"] = {
                "last_reflection": result.to_dict(),
                "reflection_count": reflection_count + 1,
                "reflection_enforced": True,
                "requires_more_research": result.requires_additional_research,
            }

            logger.info(
                f"[{session_id}] Reflection complete: "
                f"confidence={result.confidence_score:.2f}, "
                f"hallucination_risk={result.hallucination_risk:.2f}, "
                f"gaps={len(result.missing_topics)}"
            )

            return state_updates

        except Exception as e:
            logger.error(f"[{session_id}] Reflection failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "reflection",
                },
                "status": "failed",
            }

    async def _run_reflection(self, state: ResearchState) -> ReflectionResult:
        """
        Run comprehensive reflection analysis.

        Args:
            state: Current research state

        Returns:
            Structured reflection result
        """
        findings = state.get("findings", [])
        sources = state.get("sources", [])
        query = state["query"]

        # Run analysis tasks in parallel
        hallucination_task = self._detect_hallucinations(state)
        citation_task = self._verify_citations(state)
        confidence_task = self._assess_confidence(state)

        # Execute in parallel
        hallucination_result, citation_result, confidence_result = await asyncio.gather(
            hallucination_task,
            citation_task,
            confidence_task,
            return_exceptions=True,
        )

        # Build result from individual analyses
        result = ReflectionResult()
        result.source_findings_count = len(findings)
        result.source_citations_count = len(sources)

        # Process hallucination check
        if isinstance(hallucination_result, ReflectionResult):
            result.hallucination_risk = hallucination_result.hallucination_risk
            result.hallucination_severity = hallucination_result.hallucination_severity
            result.quality_flags.extend(hallucination_result.quality_flags)

        # Process citation check
        if isinstance(citation_result, ReflectionResult):
            result.citation_issues = citation_result.citation_issues

        # Process confidence assessment
        if isinstance(confidence_result, ReflectionResult):
            result.confidence_score = confidence_result.confidence_score
            result.confidence_level = confidence_result.confidence_level
            result.reasoning_assessment = confidence_result.reasoning_assessment

        # Identify missing topics
        missing = await self._identify_missing_topics(state)
        result.missing_topics = missing

        # Assess reasoning quality
        result.reasoning_quality = self._assess_reasoning_quality(findings, sources)

        # Determine if more research needed
        result.requires_additional_research = self._should_research_more(result)

        # Generate recommended actions
        result.recommended_actions = self._generate_actions(result)

        # Generate new tasks if needed
        if result.requires_additional_research:
            result.new_tasks = await self._generate_tasks(result, state)

        return result

    async def _detect_hallucinations(self, state: ResearchState) -> ReflectionResult:
        """
        Detect potential hallucinations in findings.

        Args:
            state: Current research state

        Returns:
            ReflectionResult with hallucination analysis
        """
        result = ReflectionResult()

        findings = state.get("findings", [])
        sources = state.get("sources", [])
        query = state["query"]

        # Build content for analysis
        findings_text = "\n\n".join([f.get("summary", "") for f in findings[:10]])
        sources_text = "\n\n".join([f"- {s}" for s in sources[:10]])

        prompt = HALLUCINATION_CHECK_PROMPT.format(
            content=findings_text,
            sources=sources_text,
        )

        try:
            response = await self.ollama.generate(prompt)
            result.hallucination_risk = self._parse_risk_score(response, "hallucination")
            result.hallucination_severity = self._severity_from_risk(result.hallucination_risk)

            # Extract quality flags
            result.quality_flags.append(response[:500])

        except Exception as e:
            logger.error(f"Hallucination detection failed: {e}")
            result.hallucination_risk = 0.3  # Default to moderate risk on error
            result.quality_flags.append("Hallucination check failed, assuming moderate risk")

        return result

    async def _verify_citations(self, state: ResearchState) -> ReflectionResult:
        """
        Verify citations for validity and credibility.

        Args:
            state: Current research state

        Returns:
            ReflectionResult with citation analysis
        """
        result = ReflectionResult()

        sources = state.get("sources", [])
        query = state["query"]

        if not sources:
            result.citation_issues.append("No citations provided")
            return result

        sources_text = "\n\n".join([f"- {s}" for s in sources[:20]])

        prompt = CITATION_VERIFY_PROMPT.format(
            query=query,
            citations=sources_text,
        )

        try:
            response = await self.ollama.generate(prompt)

            # Check for common issues
            response_lower = response.lower()

            if "broken" in response_lower or "invalid" in response_lower:
                result.citation_issues.append("Some citations may be broken or invalid")

            if "fabricated" in response_lower or "hallucinated" in response_lower:
                result.citation_issues.append("Some citations appear to be fabricated")

            if "credible" in response_lower and "not" in response_lower:
                result.citation_issues.append("Some sources lack credibility")

            if not result.citation_issues:
                result.citation_issues.append("No major citation issues detected")

        except Exception as e:
            logger.error(f"Citation verification failed: {e}")
            result.citation_issues.append("Citation verification failed")

        return result

    async def _assess_confidence(self, state: ResearchState) -> ReflectionResult:
        """
        Assess overall confidence in research quality.

        Args:
            state: Current research state

        Returns:
            ReflectionResult with confidence analysis
        """
        result = ReflectionResult()

        findings = state.get("findings", [])
        sources = state.get("sources", [])
        query = state["query"]

        findings_text = "\n\n".join([f.get("summary", "") for f in findings[:10]])
        sources_text = "\n\n".join([f"- {s}" for s in sources[:10]])

        prompt = CONFIDENCE_ASSESSMENT_PROMPT.format(
            query=query,
            findings=findings_text,
            sources=sources_text,
        )

        try:
            response = await self.ollama.generate(prompt)

            # Parse response
            for line in response.split("\n"):
                line = line.strip().upper()
                if line.startswith("CONF_SCORE:"):
                    try:
                        score = float(line.split(":")[1].strip())
                        result.confidence_score = min(1.0, max(0.0, score))
                    except ValueError:
                        pass
                elif line.startswith("CONF_LEVEL:"):
                    level = line.split(":")[1].strip().lower()
                    result.confidence_level = level

            result.reasoning_assessment = response[:200]

        except Exception as e:
            logger.error(f"Confidence assessment failed: {e}")
            # Base confidence on findings count
            result.confidence_score = min(1.0, len(findings) / 5)
            result.confidence_level = "medium"

        return result

    async def _identify_missing_topics(self, state: ResearchState) -> List[str]:
        """
        Identify topics that need more research coverage.

        Args:
            state: Current research state

        Returns:
            List of missing topic names
        """
        findings = state.get("findings", [])
        query = state["query"]

        # Extract topics from query
        query_topics = [w for w in query.split() if len(w) > 4][:10]

        # Extract topics from findings
        findings_topics = set()
        for finding in findings:
            summary = finding.get("summary", "")
            findings_topics.update([w for w in summary.split() if len(w) > 4][:20])

        # Find topics in query not well-covered in findings
        missing = []
        for topic in query_topics:
            if topic.lower() not in [t.lower() for t in findings_topics]:
                missing.append(topic)

        return missing[:5]  # Limit to top 5

    async def _generate_tasks(
        self,
        result: ReflectionResult,
        state: ResearchState,
    ) -> List[Dict[str, Any]]:
        """
        Generate new research tasks to address gaps.

        Args:
            result: Reflection analysis result
            state: Current research state

        Returns:
            List of new task dicts
        """
        if not result.requires_additional_research:
            return []

        query = state["query"]
        findings_count = len(state.get("findings", []))
        sources_count = len(state.get("sources", []))

        gaps = "\n".join([f"- {t}" for t in result.missing_topics])

        prompt = TASK_REGENERATION_PROMPT.format(
            query=query,
            findings_count=findings_count,
            sources_count=sources_count,
            missing_topics=result.missing_topics,
            gaps=gaps,
            count=3,
        )

        try:
            response = await self.ollama.generate(prompt)
            tasks = self._parse_tasks_from_response(response)
            return tasks

        except Exception as e:
            logger.error(f"Task generation failed: {e}")
            # Return fallback tasks based on missing topics
            return self._generate_fallback_tasks(result.missing_topics)

    def _assess_reasoning_quality(
        self,
        findings: List[Dict[str, Any]],
        sources: List[str],
    ) -> float:
        """
        Assess the quality of reasoning in findings.

        Args:
            findings: Research findings
            sources: Source citations

        Returns:
            Quality score 0.0-1.0
        """
        score = 0.5  # Base score

        # More findings = better coverage
        if len(findings) >= 5:
            score += 0.1
        if len(findings) >= 10:
            score += 0.1

        # Source diversity
        unique_domains = set()
        for source in sources:
            if "github.com" in source:
                unique_domains.add("github")
            elif "arxiv.org" in source:
                unique_domains.add("arxiv")
            elif "wikipedia.org" in source:
                unique_domains.add("wikipedia")

        score += min(0.2, len(unique_domains) * 0.05)

        # Source count
        if len(sources) >= 5:
            score += 0.1

        return min(1.0, score)

    def _should_research_more(self, result: ReflectionResult) -> bool:
        """
        Determine if additional research is needed.

        Args:
            result: Reflection analysis

        Returns:
            True if more research recommended
        """
        # Need more research if confidence is low
        if result.confidence_score < 0.5:
            return True

        # Need more research if hallucination risk is high
        if result.hallucination_risk > 0.4:
            return True

        # Need more research if many topics are missing
        if len(result.missing_topics) >= 3:
            return True

        # Need more research if citation issues exist
        if len(result.citation_issues) >= 2:
            return True

        return False

    def _generate_actions(self, result: ReflectionResult) -> List[str]:
        """
        Generate recommended actions based on analysis.

        Args:
            result: Reflection analysis

        Returns:
            List of action recommendations
        """
        actions = []

        if result.hallucination_risk > 0.3:
            actions.append("Review claims for unsupported assertions")
            actions.append("Strengthen citations with additional sources")

        if result.confidence_score < 0.6:
            actions.append("Expand research with more diverse sources")
            actions.append("Seek expert consensus on key claims")

        if result.missing_topics:
            actions.append(f"Research additional topics: {', '.join(result.missing_topics[:3])}")

        if len(result.citation_issues) > 2:
            actions.append("Verify and fix citation issues")

        if result.reasoning_quality < 0.6:
            actions.append("Strengthen logical structure of arguments")

        if not actions:
            actions.append("Research quality meets acceptable standards")

        return actions

    def _parse_risk_score(self, text: str, risk_type: str) -> float:
        """Parse risk score from text response."""
        text_lower = text.lower()

        # Look for explicit scores
        keywords = ["high", "medium", "low", "risk", "score"]
        if any(kw in text_lower for kw in keywords):
            if "high" in text_lower and "risk" in text_lower:
                return 0.7
            elif "low" in text_lower and "risk" in text_lower:
                return 0.2

        # Count negative indicators
        negative_count = sum(
            1
            for kw in ["unsupported", "fabricated", "contradict", "invented", "missing source"]
            if kw in text_lower
        )

        return min(1.0, 0.2 + (negative_count * 0.15))

    def _severity_from_risk(self, risk: float) -> str:
        """Convert risk score to severity string."""
        if risk < 0.2:
            return "none"
        elif risk < 0.4:
            return "low"
        elif risk < 0.6:
            return "medium"
        elif risk < 0.8:
            return "high"
        else:
            return "critical"

    def _parse_tasks_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse generated tasks from LLM response."""
        tasks = []

        # Simple JSON-like parsing
        lines = response.split("\n")
        current_task = None

        for line in lines:
            line = line.strip()
            if line.startswith("{"):
                current_task = {}
            elif line.startswith("}") and current_task:
                tasks.append(current_task)
                current_task = None
            elif current_task and ":" in line:
                key, value = line.split(":", 1)
                current_task[key.strip().strip('"')] = value.strip().strip(",}").strip('"')

        return tasks

    def _generate_fallback_tasks(self, missing_topics: List[str]) -> List[Dict[str, Any]]:
        """Generate fallback tasks when LLM parsing fails."""
        tasks = []

        for i, topic in enumerate(missing_topics[:3]):
            tasks.append(
                {
                    "id": f"regenerated_{i}_{uuid.uuid4().hex[:8]}",
                    "description": f"Research additional information about: {topic}",
                    "type": "web_search",
                    "priority": 7 - i,
                    "target_topics": [topic],
                    "suggested_sources": [],
                    "estimated_time_minutes": 5,
                }
            )

        return tasks

    def _build_state_updates(self, result: ReflectionResult) -> Dict[str, Any]:
        """
        Build state updates from reflection result.

        Args:
            result: Structured reflection result

        Returns:
            State dict updates
        """
        return {
            "reflections": [str(result)],
            "reflection_count": 1,  # Will be incremented by graph
            "status": "reflected",
            "progress": min(0.5 + (result.confidence_score * 0.3), 0.9),
            "metadata": {
                "reflection_result": result.to_dict(),
                "hallucination_risk": result.hallucination_risk,
                "confidence_score": result.confidence_score,
                "missing_topics": result.missing_topics,
                "citation_issues": result.citation_issues,
                "requires_research": result.requires_additional_research,
                "recommended_actions": result.recommended_actions,
            },
        }

    async def quick_reflect(
        self,
        query: str,
        findings: List[Dict[str, Any]],
        sources: List[str],
    ) -> ReflectionResult:
        """
        Quick reflection for lightweight validation.

        Args:
            query: Research query
            findings: Research findings
            sources: Source citations

        Returns:
            Simplified reflection result
        """
        state: ResearchState = {
            "session_id": f"quick_{uuid.uuid4().hex[:8]}",
            "query": query,
            "findings": findings,
            "sources": sources,
            "reflection_count": 0,
            "max_reflections": 1,
            # Required fields
            "tasks": [],
            "active_tasks": [],
            "completed_tasks": [],
            "failed_tasks": [],
            "memory_context": {},
            "reflections": [],
            "draft_report": "",
            "final_report": "",
            "current_agent": "",
            "next_action": "",
            "status": "reflecting",
            "progress": 0.0,
            "error_state": None,
            "requires_human_input": False,
            "token_usage": {},
            "metadata": {},
        }

        return await self._run_reflection(state)


# Convenience function
async def reflect_research(
    query: str,
    findings: List[Dict[str, Any]],
    sources: List[str],
) -> ReflectionResult:
    """
    Quick reflection without agent initialization.

    Args:
        query: Research query
        findings: Research findings
        sources: Source citations

    Returns:
        ReflectionResult
    """
    agent = ReflectionAgent()
    return await agent.quick_reflect(query, findings, sources)
