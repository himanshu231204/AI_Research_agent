"""
Ollama client wrapper for Research OS.

Provides:
- Model routing
- Timeout handling
- Fallback-ready architecture (for future cloud fallback)
"""

import logging
from typing import Optional, Dict, Any, List

import httpx

from api.config import get_settings
from observability.langsmith import traceable

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Ollama client for local LLM inference.

    Provides a unified interface for LLM calls with:
    - Configurable model
    - Timeout handling
    - Error handling
    - Fallback architecture (prepares for cloud fallback)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize the Ollama client.

        Args:
            model: Model name (defaults to config)
            base_url: Ollama base URL (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
        """
        settings = get_settings()

        self.model_name = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout or settings.ollama_timeout

        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"OllamaClient initialized with model: {self.model_name}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    @traceable(name="ollama.generate", run_type="llm")
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text using Ollama.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        client = await self._get_client()

        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if system:
            payload["system"] = system

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except httpx.TimeoutException:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            raise OllamaTimeoutError(f"Request timed out after {self.timeout}s")

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            raise OllamaError(f"HTTP error: {e.response.status_code}")

        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            raise OllamaError(f"Request failed: {str(e)}")

    @traceable(name="ollama.chat", run_type="llm")
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate chat completion using Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Assistant's response
        """
        client = await self._get_client()

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()

            result = response.json()
            return result.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"Ollama chat failed: {e}")
            raise OllamaError(f"Chat failed: {str(e)}")

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models.

        Returns:
            List of model information
        """
        client = await self._get_client()

        try:
            response = await client.get("/api/tags")
            response.raise_for_status()

            result = response.json()
            return result.get("models", [])

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    async def health_check(self) -> bool:
        """
        Check if Ollama is available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class OllamaError(Exception):
    """Base exception for Ollama errors."""

    pass


class OllamaTimeoutError(OllamaError):
    """Exception for Ollama timeout errors."""

    pass


class OllamaFallbackError(OllamaError):
    """Exception for when fallback is needed (for future cloud fallback)."""

    pass
