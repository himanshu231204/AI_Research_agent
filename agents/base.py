"""
Base agent interface for Research OS.

All agents must inherit from BaseAgent and implement the execute method.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from graphs.state import ResearchState


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Provides a common interface for:
    - Execution
    - State management
    - Logging
    """

    def __init__(self, agent_name: str = "base"):
        """
        Initialize the agent.

        Args:
            agent_name: Name of the agent for logging
        """
        self.agent_name = agent_name

    @abstractmethod
    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the agent's logic.

        Args:
            state: Current research state

        Returns:
            Updated state dict with agent's output
        """
        pass

    def log(self, message: str, level: str = "info") -> None:
        """Log a message with the agent's name."""
        import logging

        logger = logging.getLogger(f"agents.{self.agent_name}")
        getattr(logger, level)(message)
