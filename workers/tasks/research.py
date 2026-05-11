"""
Research tasks for Celery workers.

Contains distributed tasks for:
- Web research
- PDF parsing
- GitHub analysis
"""

import logging
from typing import Any, Dict

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class ResearchTask(Task):
    """Base class for research tasks with retry logic."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes
    retry_jitter = True
    max_retries = 3


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.web_search",
    queue="research",
)
def web_search(self, query: str, session_id: str) -> Dict[str, Any]:
    """
    Perform web search for research.

    Args:
        query: Search query
        session_id: Session identifier

    Returns:
        Search results
    """
    logger.info(f"[{session_id}] Web search: {query}")

    try:
        # In a full implementation, this would use Tavily or Brave Search
        # For now, return a placeholder result

        result = {
            "query": query,
            "session_id": session_id,
            "status": "completed",
            "results": [
                {
                    "title": "Sample Result",
                    "url": "https://example.com",
                    "snippet": "This is a sample search result for demonstration.",
                }
            ],
        }

        logger.info(f"[{session_id}] Web search completed")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] Web search failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.github_analysis",
    queue="research",
)
def github_analysis(self, repo_url: str, session_id: str) -> Dict[str, Any]:
    """
    Analyze GitHub repository.

    Args:
        repo_url: GitHub repository URL
        session_id: Session identifier

    Returns:
        Analysis results
    """
    logger.info(f"[{session_id}] GitHub analysis: {repo_url}")

    try:
        # In a full implementation, this would use GitHub MCP
        # For now, return a placeholder result

        result = {
            "repo_url": repo_url,
            "session_id": session_id,
            "status": "completed",
            "analysis": {
                "readme_summary": "Repository analysis placeholder",
                "language": "Unknown",
                "stars": 0,
            },
        }

        logger.info(f"[{session_id}] GitHub analysis completed")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] GitHub analysis failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.pdf_analysis",
    queue="research",
)
def pdf_analysis(self, file_path: str, session_id: str) -> Dict[str, Any]:
    """
    Analyze PDF document.

    Args:
        file_path: Path to PDF file
        session_id: Session identifier

    Returns:
        Analysis results
    """
    logger.info(f"[{session_id}] PDF analysis: {file_path}")

    try:
        # In a full implementation, this would use RAG pipeline
        # For now, return a placeholder result

        result = {
            "file_path": file_path,
            "session_id": session_id,
            "status": "completed",
            "analysis": {
                "summary": "PDF analysis placeholder",
                "pages": 0,
                "key_findings": [],
            },
        }

        logger.info(f"[{session_id}] PDF analysis completed")
        return result

    except Exception as e:
        logger.error(f"[{session_id}] PDF analysis failed: {e}")
        raise


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.aggregate_findings",
    queue="research",
)
def aggregate_findings(
    self,
    session_id: str,
    task_results: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Aggregate findings from multiple research tasks.

    Args:
        session_id: Session identifier
        task_results: List of task results to aggregate

    Returns:
        Aggregated findings
    """
    logger.info(f"[{session_id}] Aggregating {len(task_results)} findings")

    try:
        findings = []
        sources = []

        for result in task_results:
            if "results" in result:
                for r in result["results"]:
                    findings.append(
                        {
                            "summary": r.get("snippet", ""),
                            "source": r.get("url", ""),
                            "type": "web",
                        }
                    )
                    sources.append(r.get("url", ""))

            if "analysis" in result:
                findings.append(
                    {
                        "summary": result["analysis"].get("summary", ""),
                        "source": result.get("repo_url", result.get("file_path", "")),
                        "type": "analysis",
                    }
                )

        logger.info(f"[{session_id}] Aggregation completed: {len(findings)} findings")

        return {
            "session_id": session_id,
            "findings": findings,
            "sources": list(set(sources)),
            "total": len(findings),
        }

    except Exception as e:
        logger.error(f"[{session_id}] Aggregation failed: {e}")
        raise
