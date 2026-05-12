"""
Token usage tracking for Research OS distributed execution.

This module provides:
- Per-agent token accounting
- Per-workflow token tracking
- Model usage statistics
- Estimated cost calculation
- Cross-worker aggregation
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from observability.distributed_logging import get_logger, set_session_context

logger = get_logger(__name__)


@dataclass
class TokenUsage:
    """
    Token usage record for a single operation.

    Tracks prompt, completion, and total tokens
    for a specific model and operation.
    """

    # Timestamps
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Token counts
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Model info
    model: str = ""
    provider: str = "ollama"  # ollama, openai, anthropic, etc.

    # Context
    session_id: str = ""
    workflow_id: str = ""
    agent: str = ""

    # Operation info
    operation: str = ""  # planning, routing, reflection, writing, etc.

    # Cost estimation (USD)
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0

    def __post_init__(self):
        """Calculate total tokens if not set."""
        if self.total_tokens == 0:
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class ModelPricing:
    """
    Pricing information for different models.

    Based on approximate token costs.
    """

    # Provider name
    provider: str

    # Model name
    model: str

    # Cost per 1M tokens (USD)
    prompt_cost_per_million: float = 0.0
    completion_cost_per_million: float = 0.0

    def calculate_cost(
        self, prompt_tokens: int, completion_tokens: int
    ) -> tuple[float, float, float]:
        """
        Calculate cost for given token counts.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Tuple of (prompt_cost, completion_cost, total_cost)
        """
        prompt_cost = (prompt_tokens / 1_000_000) * self.prompt_cost_per_million
        completion_cost = (completion_tokens / 1_000_000) * self.completion_cost_per_million
        total_cost = prompt_cost + completion_cost

        return prompt_cost, completion_cost, total_cost


# Default model pricing (approximate)
DEFAULT_PRICING: Dict[str, Dict[str, ModelPricing]] = {
    "ollama": {
        "qwen3": ModelPricing("ollama", "qwen3", 0.0, 0.0),  # Free for local
        "llama3": ModelPricing("ollama", "llama3", 0.0, 0.0),
        "mistral": ModelPricing("ollama", "mistral", 0.0, 0.0),
        "deepseek-coder": ModelPricing("ollama", "deepseek-coder", 0.0, 0.0),
        "nomic-embed-text": ModelPricing("ollama", "nomic-embed-text", 0.0, 0.0),
    },
    "openai": {
        "gpt-4o": ModelPricing("openai", "gpt-4o", 5.0, 15.0),
        "gpt-4o-mini": ModelPricing("openai", "gpt-4o-mini", 0.15, 0.60),
        "gpt-5": ModelPricing("openai", "gpt-5", 15.0, 75.0),  # Estimated
    },
    "anthropic": {
        "claude-sonnet-4": ModelPricing("anthropic", "claude-sonnet-4", 3.0, 15.0),
        "claude-opus-4": ModelPricing("anthropic", "claude-opus-4", 15.0, 75.0),
        "claude-3-5-sonnet": ModelPricing("anthropic", "claude-3-5-sonnet", 3.0, 15.0),
    },
    "google": {
        "gemini-2.0-flash": ModelPricing("google", "gemini-2.0-flash", 0.10, 0.40),
        "gemini-2.5-pro": ModelPricing("google", "gemini-2.5-pro", 1.25, 5.00),
    },
}


class TokenTracker:
    """
    Central token usage tracking system.

    Features:
    - Track tokens per agent
    - Track tokens per workflow
    - Aggregate across distributed workers
    - Calculate estimated costs
    - Store in state for persistence
    """

    def __init__(self, session_id: str, workflow_id: Optional[str] = None):
        """
        Initialize token tracker.

        Args:
            session_id: Session identifier
            workflow_id: Optional workflow identifier
        """
        self.session_id = session_id
        self.workflow_id = workflow_id or f"wf_{session_id[:8]}"

        # Usage records
        self._usages: List[TokenUsage] = []

        # Aggregate by agent
        self._by_agent: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "count": 0}
        )

        # Aggregate by model
        self._by_model: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "count": 0}
        )

        # Aggregate by operation
        self._by_operation: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "count": 0}
        )

        # Total cost
        self._total_cost: float = 0.0

        # Start time
        self._start_time = datetime.utcnow()

    def record(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        agent: str,
        operation: str,
        provider: str = "ollama",
    ) -> TokenUsage:
        """
        Record token usage for an operation.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: Model name
            agent: Agent name
            operation: Operation type
            provider: Model provider

        Returns:
            TokenUsage record
        """
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            provider=provider,
            session_id=self.session_id,
            workflow_id=self.workflow_id,
            agent=agent,
            operation=operation,
        )

        # Calculate cost
        cost = self._calculate_cost(
            prompt_tokens,
            completion_tokens,
            model,
            provider,
        )
        usage.prompt_cost = cost[0]
        usage.completion_cost = cost[1]
        usage.total_cost = cost[2]

        # Store usage
        self._usages.append(usage)

        # Update aggregates
        self._by_agent[agent]["prompt_tokens"] += prompt_tokens
        self._by_agent[agent]["completion_tokens"] += completion_tokens
        self._by_agent[agent]["total_tokens"] += prompt_tokens + completion_tokens
        self._by_agent[agent]["count"] += 1

        self._by_model[model]["prompt_tokens"] += prompt_tokens
        self._by_model[model]["completion_tokens"] += completion_tokens
        self._by_model[model]["total_tokens"] += prompt_tokens + completion_tokens
        self._by_model[model]["count"] += 1

        self._by_operation[operation]["prompt_tokens"] += prompt_tokens
        self._by_operation[operation]["completion_tokens"] += completion_tokens
        self._by_operation[operation]["total_tokens"] += prompt_tokens + completion_tokens
        self._by_operation[operation]["count"] += 1

        self._total_cost += usage.total_cost

        logger.debug(
            "token_usage_recorded",
            agent=agent,
            operation=operation,
            model=model,
            total_tokens=usage.total_tokens,
            cost=usage.total_cost,
        )

        return usage

    def _calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str,
    ) -> tuple[float, float, float]:
        """
        Calculate cost for token usage.

        Args:
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            model: Model name
            provider: Provider name

        Returns:
            Tuple of (prompt_cost, completion_cost, total_cost)
        """
        # Look up pricing
        provider_pricing = DEFAULT_PRICING.get(provider, {})
        model_pricing = provider_pricing.get(model)

        if model_pricing:
            return model_pricing.calculate_cost(prompt_tokens, completion_tokens)

        # Default pricing for unknown models
        # Assume free for local models
        return 0.0, 0.0, 0.0

    def get_summary(self) -> Dict[str, Any]:
        """
        Get token usage summary.

        Returns:
            Summary dictionary
        """
        duration = (datetime.utcnow() - self._start_time).total_seconds()

        return {
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "total_usages": len(self._usages),
            "duration_seconds": duration,
            "total_cost_usd": self._total_cost,
            "by_agent": dict(self._by_agent),
            "by_model": dict(self._by_model),
            "by_operation": dict(self._by_operation),
            "total_prompt_tokens": sum(u.prompt_tokens for u in self._usages),
            "total_completion_tokens": sum(u.completion_tokens for u in self._usages),
            "total_tokens": sum(u.total_tokens for u in self._usages),
        }

    def get_state_token_usage(self) -> Dict[str, int]:
        """
        Get token usage formatted for ResearchState.

        Returns:
            Token usage dictionary for state
        """
        return {
            "prompt_tokens": sum(u.prompt_tokens for u in self._usages),
            "completion_tokens": sum(u.completion_tokens for u in self._usages),
            "total_tokens": sum(u.total_tokens for u in self._usages),
        }

    def get_detailed_usage(self) -> List[Dict[str, Any]]:
        """
        Get detailed usage records.

        Returns:
            List of usage dictionaries
        """
        return [asdict(u) for u in self._usages]

    def merge_from_remote(self, remote_summary: Dict[str, Any]) -> None:
        """
        Merge token usage from a remote worker.

        This allows aggregating token counts across
        distributed Celery workers.

        Args:
            remote_summary: Token usage summary from remote
        """
        # Merge by agent
        remote_by_agent = remote_summary.get("by_agent", {})
        for agent, stats in remote_by_agent.items():
            self._by_agent[agent]["prompt_tokens"] += stats.get("prompt_tokens", 0)
            self._by_agent[agent]["completion_tokens"] += stats.get("completion_tokens", 0)
            self._by_agent[agent]["total_tokens"] += stats.get("total_tokens", 0)
            self._by_agent[agent]["count"] += stats.get("count", 0)

        # Merge by model
        remote_by_model = remote_summary.get("by_model", {})
        for model, stats in remote_by_model.items():
            self._by_model[model]["prompt_tokens"] += stats.get("prompt_tokens", 0)
            self._by_model[model]["completion_tokens"] += stats.get("completion_tokens", 0)
            self._by_model[model]["total_tokens"] += stats.get("total_tokens", 0)
            self._by_model[agent]["count"] += stats.get("count", 0)

        # Update total cost
        self._total_cost += remote_summary.get("total_cost_usd", 0.0)

    def estimate_cost(
        self,
        model: str,
        provider: str = "ollama",
        token_count: int = 1000,
        is_completion: bool = False,
    ) -> float:
        """
        Estimate cost for a given token count.

        Args:
            model: Model name
            provider: Provider name
            token_count: Number of tokens
            is_completion: Whether this is completion (vs prompt)

        Returns:
            Estimated cost in USD
        """
        provider_pricing = DEFAULT_PRICING.get(provider, {})
        model_pricing = provider_pricing.get(model)

        if model_pricing:
            cost = (token_count / 1_000_000) * (
                model_pricing.completion_cost_per_million
                if is_completion
                else model_pricing.prompt_cost_per_million
            )
            return cost

        return 0.0


class TokenUsageMiddleware:
    """
    Middleware for tracking LLM token usage.

    Can wrap LLM calls to automatically track token usage.
    """

    def __init__(self, tracker: TokenTracker):
        """
        Initialize middleware.

        Args:
            tracker: TokenTracker instance
        """
        self.tracker = tracker

    async def wrap_llm_call(
        self,
        call_func: callable,
        agent: str,
        operation: str,
        model: str,
        provider: str = "ollama",
    ):
        """
        Wrap an LLM call to track token usage.

        Args:
            agent: Agent name
            operation: Operation type
            model: Model name
            provider: Provider name
            call_func: Async function to call

        Returns:
            LLM response
        """
        import time

        start = time.perf_counter()

        try:
            response = await call_func()

            # Extract token usage from response if available
            # Different providers have different response formats
            prompt_tokens = getattr(response, "prompt_tokens", 0) or 0
            completion_tokens = getattr(response, "completion_tokens", 0) or 0

            # Record usage
            self.tracker.record(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=model,
                agent=agent,
                operation=operation,
                provider=provider,
            )

            return response

        finally:
            duration = time.perf_counter() - start
            logger.debug(
                "llm_call_completed",
                agent=agent,
                operation=operation,
                model=model,
                duration_ms=duration * 1000,
            )


# Global token tracker per session
_session_trackers: Dict[str, TokenTracker] = {}


def get_token_tracker(session_id: str, workflow_id: Optional[str] = None) -> TokenTracker:
    """
    Get or create token tracker for a session.

    Args:
        session_id: Session identifier
        workflow_id: Optional workflow identifier

    Returns:
        TokenTracker instance
    """
    if session_id not in _session_trackers:
        _session_trackers[session_id] = TokenTracker(session_id, workflow_id)

    return _session_trackers[session_id]


def clear_token_tracker(session_id: str) -> None:
    """Clear token tracker for a session."""
    if session_id in _session_trackers:
        del _session_trackers[session_id]


def record_token_usage(
    session_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    agent: str,
    operation: str,
    provider: str = "ollama",
) -> None:
    """
    Record token usage for a session.

    Convenience function for recording usage.

    Args:
        session_id: Session identifier
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model: Model name
        agent: Agent name
        operation: Operation type
        provider: Model provider
    """
    tracker = get_token_tracker(session_id)
    tracker.record(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
        agent=agent,
        operation=operation,
        provider=provider,
    )


# Utility to convert state token usage to structured format
def format_state_token_usage(state: Dict[str, Any]) -> Dict[str, int]:
    """
    Format token usage from ResearchState.

    Args:
        state: ResearchState dictionary

    Returns:
        Formatted token usage
    """
    token_usage = state.get("token_usage", {})

    return {
        "prompt_tokens": token_usage.get("prompt_tokens", 0),
        "completion_tokens": token_usage.get("completion_tokens", 0),
        "total_tokens": token_usage.get("total_tokens", 0),
    }


def update_state_token_usage(state: Dict[str, Any], tracker: TokenTracker) -> Dict[str, Any]:
    """
    Update state with token usage from tracker.

    Args:
        state: ResearchState dictionary
        tracker: TokenTracker instance

    Returns:
        Updated state
    """
    state["token_usage"] = tracker.get_state_token_usage()
    return state


# Cost estimation helpers


def estimate_workflow_cost(
    agents: List[str],
    operations: List[str],
    estimated_tokens_per_operation: int = 1000,
) -> Dict[str, float]:
    """
    Estimate total cost for a workflow.

    Args:
        agents: List of agent names
        operations: List of operation types
        estimated_tokens_per_operation: Estimated tokens per operation

    Returns:
        Cost breakdown by provider
    """
    costs = defaultdict(float)

    for agent in agents:
        # Assume qwen3 for planning, llama3 for others
        model = "qwen3" if agent == "planner" else "llama3"
        provider = "ollama"

        # Local models are free
        cost = 0.0

        costs[provider] += cost * len(operations)

    return dict(costs)


def get_model_pricing(model: str, provider: str = "ollama") -> Optional[ModelPricing]:
    """
    Get pricing for a model.

    Args:
        model: Model name
        provider: Provider name

    Returns:
        ModelPricing or None
    """
    return DEFAULT_PRICING.get(provider, {}).get(model)
