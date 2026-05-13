"""
Research tasks for Celery workers.

Contains distributed tasks for:
- Web research
- PDF parsing
- GitHub analysis
"""

import logging
from typing import Any, Dict, Optional

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

    def __call__(self, *args, **kwargs):
        """Log task invocation with distributed metadata."""
        # Extract distributed metadata for logging
        correlation_id = kwargs.get("correlation_id", "unknown")
        workflow_id = kwargs.get("workflow_id", "unknown")
        trace_id = kwargs.get("trace_id", "unknown")

        logger.info(
            f"[correlation_id={correlation_id}] [workflow_id={workflow_id}] "
            f"[trace_id={trace_id}] Task {self.name} invoked"
        )

        return super().__call__(*args, **kwargs)


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.web_search",
    queue="research",
)
def web_search(
    self,
    query: str,
    session_id: str,
    # Distributed metadata - optional but supported
    correlation_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Perform web search for research.

    Args:
        query: Search query
        session_id: Session identifier
        correlation_id: Optional correlation ID for distributed tracing
        workflow_id: Optional workflow identifier
        trace_id: Optional LangSmith trace ID
        metadata: Optional additional metadata
        **kwargs: Additional keyword arguments for backward compatibility

    Returns:
        Search results
    """
    # Log with distributed metadata
    logger.info(
        f"[session_id={session_id}] [correlation_id={correlation_id}] "
        f"[workflow_id={workflow_id}] Web search: {query}"
    )

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
            # Include distributed metadata in result for tracing
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "metadata": metadata or {},
        }

        logger.info(
            f"[session_id={session_id}] [correlation_id={correlation_id}] Web search completed"
        )
        return result

    except Exception as e:
        logger.error(
            f"[session_id={session_id}] [correlation_id={correlation_id}] Web search failed: {e}"
        )
        raise


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.github_analysis",
    queue="research",
)
def github_analysis(
    self,
    repo_url: str,
    session_id: str,
    # Distributed metadata - optional but supported
    correlation_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Analyze GitHub repository.

    Args:
        repo_url: GitHub repository URL
        session_id: Session identifier
        correlation_id: Optional correlation ID for distributed tracing
        workflow_id: Optional workflow identifier
        trace_id: Optional LangSmith trace ID
        metadata: Optional additional metadata
        **kwargs: Additional keyword arguments for backward compatibility

    Returns:
        Analysis results
    """
    logger.info(
        f"[session_id={session_id}] [correlation_id={correlation_id}] "
        f"[workflow_id={workflow_id}] GitHub analysis: {repo_url}"
    )

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
            # Include distributed metadata in result for tracing
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "metadata": metadata or {},
        }

        logger.info(
            f"[session_id={session_id}] [correlation_id={correlation_id}] GitHub analysis completed"
        )
        return result

    except Exception as e:
        logger.error(
            f"[session_id={session_id}] [correlation_id={correlation_id}] "
            f"GitHub analysis failed: {e}"
        )
        raise


@celery_app.task(
    bind=True,
    base=ResearchTask,
    name="research.pdf_analysis",
    queue="research",
)
def pdf_analysis(
    self,
    file_path: str,
    session_id: str,
    # Distributed metadata - optional but supported
    correlation_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Analyze PDF document.

    Args:
        file_path: Path to PDF file
        session_id: Session identifier
        correlation_id: Optional correlation ID for distributed tracing
        workflow_id: Optional workflow identifier
        trace_id: Optional LangSmith trace ID
        metadata: Optional additional metadata
        **kwargs: Additional keyword arguments for backward compatibility

    Returns:
        Analysis results
    """
    logger.info(
        f"[session_id={session_id}] [correlation_id={correlation_id}] "
        f"[workflow_id={workflow_id}] PDF analysis: {file_path}"
    )

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
            # Include distributed metadata in result for tracing
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "metadata": metadata or {},
        }

        logger.info(
            f"[session_id={session_id}] [correlation_id={correlation_id}] PDF analysis completed"
        )
        return result

    except Exception as e:
        logger.error(
            f"[session_id={session_id}] [correlation_id={correlation_id}] PDF analysis failed: {e}"
        )
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
    # Distributed metadata - optional but supported
    correlation_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Aggregate findings from multiple research tasks.

    Args:
        session_id: Session identifier
        task_results: List of task results to aggregate
        correlation_id: Optional correlation ID for distributed tracing
        workflow_id: Optional workflow identifier
        trace_id: Optional LangSmith trace ID
        metadata: Optional additional metadata
        **kwargs: Additional keyword arguments for backward compatibility

    Returns:
        Aggregated findings
    """
    logger.info(
            f"[session_id={session_id}] [correlation_id={correlation_id}] "
            f"[workflow_id={workflow_id}] Aggregating {len(task_results)} findings"
        )

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

        logger.info(
            f"[session_id={session_id}] [correlation_id={correlation_id}] "
            f"Aggregation completed: {len(findings)} findings"
        )

        return {
            "session_id": session_id,
            "findings": findings,
            "sources": list(set(sources)),
            "total": len(findings),
            # Include distributed metadata in result for tracing
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "metadata": metadata or {},
        }

    except Exception as e:
        logger.error(
            f"[session_id={session_id}] [correlation_id={correlation_id}] "
            f"Aggregation failed: {e}"
        )
        raise
