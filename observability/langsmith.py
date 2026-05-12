"""
LangSmith tracing helpers.

This module keeps LangSmith integration optional at import time while still
allowing the application to enable tracing through environment variables.
"""

from __future__ import annotations

import os
from typing import Any, Callable, TypeVar

try:
    from langsmith import traceable as _traceable
except Exception:  # pragma: no cover - optional runtime dependency
    _traceable = None

F = TypeVar("F", bound=Callable[..., Any])


def configure_langsmith(settings: Any) -> None:
    """Map app settings to the LangSmith/LangChain tracing environment."""
    if not getattr(settings, "langsmith_tracing", False):
        return

    api_key = getattr(settings, "langsmith_api_key", None)
    project = getattr(settings, "langsmith_project", "research-agent")

    if api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", api_key)
        os.environ.setdefault("LANGCHAIN_API_KEY", api_key)

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    os.environ.setdefault("LANGCHAIN_PROJECT", project)


def traceable(*trace_args: Any, **trace_kwargs: Any):
    """Return LangSmith's traceable decorator when available, otherwise a no-op."""
    if _traceable is None:

        def decorator(func: F) -> F:
            return func

        return decorator

    return _traceable(*trace_args, **trace_kwargs)
