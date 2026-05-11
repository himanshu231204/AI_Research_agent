"""
Reflection tasks for Celery workers.

Contains distributed tasks for:
- Reflection/critic analysis
- Quality validation
- Hallucination detection
- Research gap analysis
"""

import logging
from typing import Any, Dict, List, Optional

from celery import Task

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class ReflectionTask(Task):
    """Base class for reflection tasks with retry logic."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 300  # 5 minutes
    retry_jitter = True
    max_retries = 2


@celery_app.task(
    bind=True,
    base=ReflectionTask,
    name="reflection.analyze_findings",
    queue="reflection",
    max_retries=2,
)
def analyze_findings(
    self,
    findings: List[Dict[str, Any]],
    query: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Analyze research findings for quality and completeness.

    Args:
        findings: List of research findings
        query: Original research query
        session_id: Session identifier

    Returns:
        Analysis results
    """
    logger.info(f"[{session_id}] Analyzing {len(findings)} findings")

    try:
        # In production, this would use LLM for analysis

        analysis = {
            "quality_score": min(1.0, len(findings) / 5),
            "completeness_score": 0.8,
            "total_findings": len(findings),
            "findings_by_type": _categorize_findings(findings),
            "gaps_identified": _identify_gaps(findings, query),
            "suggestions": _generate_suggestions(findings),
        }

        result = {
            "session_id": session_id,
            "status": "completed",
            "analysis": analysis,
            "quality_flags": _detect_quality_issues(findings),
        }

        logger.info(
            f"[{session_id}] Analysis complete with quality score {analysis['quality_score']}"
        )
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Finding analysis failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=ReflectionTask,
    name="reflection.detect_hallucinations",
    queue="reflection",
    max_retries=2,
)
def detect_hallucinations(
    self,
    content: str,
    sources: List[str],
    session_id: str,
) -> Dict[str, Any]:
    """
    Detect potential hallucinations in content.

    Args:
        content: Content to validate
        sources: List of sources for verification
        session_id: Session identifier

    Returns:
        Hallucination detection results
    """
    logger.info(f"[{session_id}] Detecting hallucinations in content")

    try:
        # In production, this would use fact-checking LLM

        # Mock detection - check for common patterns
        hallucinations = []
        confidence = 0.95

        # Simple pattern checks
        if len(content) > 100:
            # Look for unsourced claims
            sentences = content.split(".")
            unsourced = sum(
                1 for s in sentences if s.strip() and not any(src in s for src in sources)
            )
            if unsourced > len(sentences) * 0.3:
                hallucinations.append(
                    {
                        "type": "unsourced_claim",
                        "severity": "medium",
                        "affected_sentences": unsourced,
                    }
                )

        result = {
            "session_id": session_id,
            "status": "completed",
            "hallucinations_detected": len(hallucinations),
            "hallucinations": hallucinations,
            "confidence": confidence,
            "content_length": len(content),
        }

        logger.info(f"[{session_id}] Hallucination check complete: {len(hallucinations)} found")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Hallucination detection failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=ReflectionTask,
    name="reflection.identify_gaps",
    queue="reflection",
    max_retries=2,
)
def identify_gaps(
    self,
    findings: List[Dict[str, Any]],
    query: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Identify gaps in research coverage.

    Args:
        findings: Current research findings
        query: Original research query
        session_id: Session identifier

    Returns:
        Gap analysis results
    """
    logger.info(f"[{session_id}] Identifying research gaps")

    try:
        # Analyze findings to identify gaps
        covered_topics = set()
        for finding in findings:
            if "summary" in finding:
                # Extract key topics (simplified)
                words = finding["summary"].lower().split()[:10]
                covered_topics.update(words)

        # Identify common research gaps
        gaps = []

        if len(findings) < 5:
            gaps.append(
                {
                    "type": "insufficient_findings",
                    "severity": "high",
                    "description": "Need more comprehensive research coverage",
                }
            )

        if not any(f.get("type") == "github" for f in findings):
            gaps.append(
                {
                    "type": "missing_code_analysis",
                    "severity": "medium",
                    "description": "Consider adding GitHub repository analysis",
                }
            )

        if not any(f.get("type") == "web" for f in findings):
            gaps.append(
                {
                    "type": "missing_web_search",
                    "severity": "medium",
                    "description": "Need additional web search results",
                }
            )

        result = {
            "session_id": session_id,
            "status": "completed",
            "gaps": gaps,
            "gap_count": len(gaps),
            "recommendations": [g["description"] for g in gaps],
        }

        logger.info(f"[{session_id}] Identified {len(gaps)} research gaps")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Gap identification failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=ReflectionTask,
    name="reflection.validate_sources",
    queue="reflection",
    max_retries=2,
)
def validate_sources(
    self,
    sources: List[str],
    session_id: str,
) -> Dict[str, Any]:
    """
    Validate the credibility and relevance of sources.

    Args:
        sources: List of source URLs
        session_id: Session identifier

    Returns:
        Validation results
    """
    logger.info(f"[{session_id}] Validating {len(sources)} sources")

    try:
        validated = []
        issues = []

        for source in sources:
            # Check URL format
            if not source.startswith(("http://", "https://")):
                issues.append(
                    {
                        "source": source,
                        "issue": "invalid_url",
                        "severity": "high",
                    }
                )
                continue

            # Check for common reputable domains
            reputable_domains = ["github.com", "arxiv.org", "wikipedia.org", "stackoverflow.com"]
            is_reputable = any(domain in source for domain in reputable_domains)

            # Check for government/edu domains
            academic_domains = [".edu", ".gov", ".ac.uk"]
            is_academic = any(domain in source for domain in academic_domains)

            validated.append(
                {
                    "source": source,
                    "is_valid": True,
                    "reputable": is_reputable,
                    "academic": is_academic,
                    "trust_score": 0.9 if (is_reputable or is_academic) else 0.6,
                }
            )

        result = {
            "session_id": session_id,
            "status": "completed",
            "validated_sources": len(validated),
            "issues": issues,
            "sources": validated,
            "average_trust_score": sum(s["trust_score"] for s in validated)
            / max(len(validated), 1),
        }

        logger.info(f"[{session_id}] Source validation complete: {len(validated)} valid")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Source validation failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=ReflectionTask,
    name="reflection.critique_report",
    queue="reflection",
    max_retries=2,
)
def critique_report(
    self,
    report: str,
    query: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Provide critical feedback on research report.

    Args:
        report: Research report content
        query: Original research query
        session_id: Session identifier

    Returns:
        Critique results
    """
    logger.info(f"[{session_id}] Critiquing research report")

    try:
        # In production, this would use a critic LLM

        critique_points = []

        # Check report structure
        if len(report) < 500:
            critique_points.append(
                {
                    "aspect": "length",
                    "issue": "report_too_short",
                    "severity": "high",
                    "suggestion": "Expand the report with more detailed analysis",
                }
            )

        # Check for citations
        if "[source]" not in report.lower() and "citation" not in report.lower():
            critique_points.append(
                {
                    "aspect": "citations",
                    "issue": "missing_citations",
                    "severity": "medium",
                    "suggestion": "Add proper source citations",
                }
            )

        # Check for executive summary
        if "executive summary" not in report.lower():
            critique_points.append(
                {
                    "aspect": "structure",
                    "issue": "missing_executive_summary",
                    "severity": "low",
                    "suggestion": "Add an executive summary section",
                }
            )

        # Overall quality assessment
        quality_score = 0.7
        if len(report) > 1000:
            quality_score += 0.1
        if len(critique_points) < 3:
            quality_score += 0.1

        result = {
            "session_id": session_id,
            "status": "completed",
            "quality_score": min(1.0, quality_score),
            "critique_points": critique_points,
            "overall_assessment": "The report provides a good foundation but could be improved with more depth and citations."
            if quality_score > 0.7
            else "The report needs significant improvements to meet quality standards.",
        }

        logger.info(f"[{session_id}] Report critique complete: score {quality_score}")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Report critique failed: {e}")
        raise self.retry(exc=e)


# Helper functions for analysis


def _categorize_findings(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Categorize findings by type."""
    categories = {}
    for finding in findings:
        f_type = finding.get("type", "unknown")
        categories[f_type] = categories.get(f_type, 0) + 1
    return categories


def _identify_gaps(findings: List[Dict[str, Any]], query: str) -> List[str]:
    """Identify gaps in research coverage."""
    gaps = []

    if len(findings) < 3:
        gaps.append("Insufficient number of sources")

    sources = [f.get("source", "") for f in findings]
    if not any("github.com" in s for s in sources):
        gaps.append("Missing code repository analysis")

    return gaps


def _generate_suggestions(findings: List[Dict[str, Any]]) -> List[str]:
    """Generate suggestions for improving research."""
    suggestions = []

    if len(findings) < 5:
        suggestions.append("Expand research with more diverse sources")

    if not any(f.get("type") == "analysis" for f in findings):
        suggestions.append("Add deeper analysis of key topics")

    return suggestions


def _detect_quality_issues(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect potential quality issues in findings."""
    issues = []

    for i, finding in enumerate(findings):
        if not finding.get("summary"):
            issues.append(
                {
                    "finding_index": i,
                    "issue": "missing_summary",
                    "severity": "high",
                }
            )

        if not finding.get("source"):
            issues.append(
                {
                    "finding_index": i,
                    "issue": "missing_source",
                    "severity": "medium",
                }
            )

    return issues
