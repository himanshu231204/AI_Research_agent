"""
Cost optimization and token management for Research OS.

This module provides:
- Token usage tracking
- Cost estimation
- Token budget enforcement
- Prompt compression
- Context trimming
- Cost telemetry
"""

import logging
import re
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from observability.token_tracking import (
    TokenTracker,
    DEFAULT_PRICING,
    ModelPricing,
    get_token_tracker,
)

logger = logging.getLogger(__name__)


@dataclass
class CostBudget:
    """Cost budget configuration."""

    max_cost_per_request: float = 1.0
    max_cost_per_session: float = 10.0
    max_tokens_per_request: int = 8192
    max_tokens_per_session: int = 100000
    warn_threshold: float = 0.8  # Warn at 80% of budget


@dataclass
class TokenBudget:
    """Token budget configuration."""

    max_prompt_tokens: int = 4096
    max_completion_tokens: int = 4096
    max_total_tokens: int = 8192
    compression_threshold: int = 2000
    trim_threshold: int = 6000


class CostOptimizer:
    """
    Cost optimization engine.

    Features:
    - Track token usage
    - Estimate costs
    - Enforce budgets
    - Optimize token usage
    """

    def __init__(
        self,
        session_id: str,
        cost_budget: Optional[CostBudget] = None,
        token_budget: Optional[TokenBudget] = None,
    ):
        """Initialize cost optimizer."""
        self.session_id = session_id
        self.cost_budget = cost_budget or CostBudget()
        self.token_budget = token_budget or TokenBudget()

        self._tracker = get_token_tracker(session_id)
        self._session_cost = 0.0
        self._session_tokens = 0

    def estimate_cost(
        self,
        model: str,
        provider: str = "ollama",
        prompt_tokens: int = 0,
        completion_tokens: int = 1000,
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            model: Model name
            provider: Provider name
            prompt_tokens: Estimated prompt tokens
            completion_tokens: Estimated completion tokens

        Returns:
            Estimated cost in USD
        """
        pricing = DEFAULT_PRICING.get(provider, {}).get(model)

        if pricing:
            prompt_cost = (prompt_tokens / 1_000_000) * pricing.prompt_cost_per_million
            completion_cost = (completion_tokens / 1_000_000) * pricing.completion_cost_per_million
            return prompt_cost + completion_cost

        return 0.0

    def can_afford_request(
        self,
        estimated_cost: float,
        estimated_tokens: int,
    ) -> tuple[bool, str]:
        """
        Check if request is within budget.

        Args:
            estimated_cost: Estimated cost
            estimated_tokens: Estimated tokens

        Returns:
            Tuple of (can_afford, reason)
        """
        # Check session cost
        if self._session_cost + estimated_cost > self.cost_budget.max_cost_per_session:
            return False, "Session cost budget exceeded"

        # Check session tokens
        if self._session_tokens + estimated_tokens > self.cost_budget.max_tokens_per_session:
            return False, "Session token budget exceeded"

        # Check per-request cost
        if estimated_cost > self.cost_budget.max_cost_per_request:
            return False, "Request cost exceeds limit"

        return True, "Within budget"

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        provider: str = "ollama",
        agent: str = "",
        operation: str = "",
    ) -> None:
        """
        Record token usage.

        Args:
            prompt_tokens: Prompt tokens used
            completion_tokens: Completion tokens used
            model: Model used
            provider: Provider used
            agent: Agent name
            operation: Operation type
        """
        self._tracker.record(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
            agent=agent,
            operation=operation,
            provider=provider,
        )

        # Update session totals
        total_tokens = prompt_tokens + completion_tokens
        self._session_tokens += total_tokens

        # Calculate and add to session cost
        cost = self.estimate_cost(model, provider, prompt_tokens, completion_tokens)
        self._session_cost += cost

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session cost summary."""
        tracker_summary = self._tracker.get_summary()

        return {
            "session_id": self.session_id,
            "total_cost_usd": self._session_cost,
            "total_tokens": self._session_tokens,
            "cost_budget": {
                "max_per_request": self.cost_budget.max_cost_per_request,
                "max_per_session": self.cost_budget.max_cost_per_session,
                "remaining": self.cost_budget.max_cost_per_session - self._session_cost,
            },
            "token_budget": {
                "max_per_request": self.token_budget.max_total_tokens,
                "max_per_session": self.cost_budget.max_tokens_per_session,
                "remaining": self.cost_budget.max_tokens_per_session - self._session_tokens,
            },
            "by_agent": tracker_summary.get("by_agent", {}),
            "by_model": tracker_summary.get("by_model", {}),
        }

    def should_warn(self) -> bool:
        """Check if budget warning should be issued."""
        cost_ratio = self._session_cost / self.cost_budget.max_cost_per_session
        token_ratio = self._session_tokens / self.cost_budget.max_tokens_per_session

        return (
            cost_ratio >= self.cost_budget.warn_threshold
            or token_ratio >= self.cost_budget.warn_threshold
        )


class TokenBudgetManager:
    """
    Token budget management.

    Features:
    - Max token enforcement
    - Prompt compression
    - Memory summarization
    - Context trimming
    """

    def __init__(self, budget: Optional[TokenBudget] = None):
        """Initialize token budget manager."""
        self.budget = budget or TokenBudget()

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses a simple approximation: ~4 characters per token.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return max(1, len(text) // 4)

    def truncate_prompt(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Truncate prompt to fit within token budget.

        Args:
            prompt: Prompt to truncate
            max_tokens: Max tokens (defaults to budget)

        Returns:
            Truncated prompt
        """
        max_tokens = max_tokens or self.budget.max_prompt_tokens
        max_chars = max_tokens * 4

        if len(prompt) <= max_chars:
            return prompt

        # Truncate and add indicator
        truncated = prompt[: max_chars - 50]
        return truncated + "\n\n[... truncated ...]"

    def compress_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Compress messages to fit within token budget.

        Args:
            messages: List of messages
            max_tokens: Max tokens (defaults to budget)

        Returns:
            Compressed messages
        """
        max_tokens = max_tokens or self.budget.max_prompt_tokens

        # Calculate current token count
        total_tokens = sum(self.estimate_tokens(m.get("content", "")) for m in messages)

        if total_tokens <= max_tokens:
            return messages

        # Keep system message if present
        system_msg = None
        other_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                other_messages.append(msg)

        # Keep recent messages, drop old ones
        compressed = []
        tokens_used = 0

        if system_msg:
            tokens_used += self.estimate_tokens(system_msg.get("content", ""))
            compressed.append(system_msg)

        # Add recent messages until budget exhausted
        for msg in reversed(other_messages):
            msg_tokens = self.estimate_tokens(msg.get("content", ""))
            if tokens_used + msg_tokens <= max_tokens:
                compressed.insert(1 if system_msg else 0, msg)
                tokens_used += msg_tokens
            else:
                break

        return compressed

    def trim_context(
        self,
        context: str,
        max_tokens: int,
    ) -> str:
        """
        Trim context to fit within token budget.

        Args:
            context: Context to trim
            max_tokens: Max tokens

        Returns:
            Trimmed context
        """
        current_tokens = self.estimate_tokens(context)

        if current_tokens <= max_tokens:
            return context

        # Calculate how much to keep
        keep_tokens = int(max_tokens * 0.8)  # Keep 80%
        keep_chars = keep_tokens * 4

        # Keep beginning and end
        if len(context) > keep_chars * 2:
            beginning = context[:keep_chars]
            end = context[-keep_chars:]
            return f"{beginning}\n\n[...] Context truncated [...]\n\n{end}"

        # Just truncate
        return self.truncate_prompt(context, max_tokens)

    def summarize_long_context(
        self,
        context: str,
        summary_prompt: Callable[[str], str],
    ) -> str:
        """
        Prepare context for summarization.

        Args:
            context: Context to summarize
            summary_prompt: Function to create summary prompt

        Returns:
            Prompt for summarization
        """
        tokens = self.estimate_tokens(context)

        if tokens < self.budget.compression_threshold:
            return context

        # Return prompt for summarization
        return summary_prompt(context)


class PromptOptimizer:
    """
    Prompt optimization utilities.

    Features:
    - Remove redundant whitespace
    - Compact format
    - Token-efficient formatting
    """

    @staticmethod
    def compact(prompt: str) -> str:
        """Compact prompt by removing redundant whitespace."""
        # Replace multiple newlines with double newline
        prompt = re.sub(r"\n{3,}", "\n\n", prompt)
        # Replace multiple spaces with single space
        prompt = re.sub(r" {2,}", " ", prompt)
        # Strip leading/trailing whitespace
        prompt = prompt.strip()
        return prompt

    @staticmethod
    def format_messages_compact(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Format messages compactly."""
        return [
            {
                "role": m.get("role", "user"),
                "content": PromptOptimizer.compact(m.get("content", "")),
            }
            for m in messages
        ]

    @staticmethod
    def extract_key_information(text: str, max_tokens: int = 500) -> str:
        """
        Extract key information from text.

        This is a simple extraction - in production, use a model.

        Args:
            text: Text to extract from
            max_tokens: Max tokens to extract

        Returns:
            Extracted key information
        """
        # Simple heuristic: take first N characters
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text

        # Try to end at a sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind(".")

        if last_period > max_chars * 0.7:  # If period is in last 30%
            return truncated[: last_period + 1]

        return truncated + "..."


# Global cost optimizer management
_cost_optimizers: Dict[str, CostOptimizer] = {}


def get_cost_optimizer(
    session_id: str,
    cost_budget: Optional[CostBudget] = None,
    token_budget: Optional[TokenBudget] = None,
) -> CostOptimizer:
    """Get or create cost optimizer for session."""
    if session_id not in _cost_optimizers:
        _cost_optimizers[session_id] = CostOptimizer(
            session_id,
            cost_budget,
            token_budget,
        )
    return _cost_optimizers[session_id]


def clear_cost_optimizer(session_id: str) -> None:
    """Clear cost optimizer for session."""
    if session_id in _cost_optimizers:
        del _cost_optimizers[session_id]


# Global token budget manager
_token_budget_manager: Optional[TokenBudgetManager] = None


def get_token_budget_manager() -> TokenBudgetManager:
    """Get global token budget manager."""
    global _token_budget_manager
    if _token_budget_manager is None:
        _token_budget_manager = TokenBudgetManager()
    return _token_budget_manager
