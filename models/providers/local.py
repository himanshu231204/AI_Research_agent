"""
Local model provider (Ollama) for Research OS.

Implements the LLMProvider interface for Ollama local inference.
Supports model health checks, GPU monitoring, streaming, and
concurrent request handling.

Supported models:
- qwen3
- llama3
- mistral
- deepseek-coder
"""

import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass

import httpx

from models.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderStatus,
    ProviderHealth,
    LLMResponse,
    StreamingChunk,
    ProviderError,
    ProviderTimeoutError,
    ProviderModelUnavailableError,
)
from api.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class OllamaModel:
    """Ollama model information."""

    name: str
    size: int
    modified_at: str
    digest: str


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.

    Features:
    - Model health checks
    - GPU monitoring
    - Streaming support
    - Concurrent request handling
    - Automatic model availability checks
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        """Initialize Ollama provider."""
        settings = get_settings()

        if config is None:
            config = ProviderConfig(
                provider_type=ProviderType.LOCAL,
                name="ollama",
                base_url=settings.ollama_base_url,
                timeout=settings.ollama_timeout,
                default_model=settings.ollama_model,
                supported_models=["qwen3", "llama3", "mistral", "deepseek-coder"],
                gpu_enabled=True,
                gpu_memory_threshold=0.9,
            )

        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate text using Ollama.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
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

            if stop:
                payload["options"]["stop"] = stop

            try:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                return LLMResponse(
                    content=result.get("response", ""),
                    model=self.config.default_model,
                    provider="ollama",
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError(f"Request timed out after {self.config.timeout}s")

            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)

                if e.response.status_code == 404:
                    raise ProviderModelUnavailableError(
                        f"Model {self.config.default_model} not found"
                    )
                raise ProviderError(f"HTTP error: {e.response.status_code}")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                logger.error(f"Ollama request failed: {e}")
                raise ProviderError(f"Request failed: {str(e)}")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate chat completion using Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content
        """
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            if stop:
                payload["options"]["stop"] = stop

            try:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                message = result.get("message", {})
                content = message.get("content", "")

                # Estimate tokens (Ollama doesn't return exact counts)
                prompt_tokens = self._estimate_tokens(messages)
                completion_tokens = self._estimate_tokens([content])

                return LLMResponse(
                    content=content,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    model=self.config.default_model,
                    provider="ollama",
                    finish_reason=result.get("done_reason", ""),
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError(f"Chat timed out after {self.config.timeout}s")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                logger.error(f"Ollama chat failed: {e}")
                raise ProviderError(f"Chat failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Stream chat completion from Ollama.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            StreamingChunk for each token
        """
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                },
            }

            if max_tokens:
                payload["options"]["num_predict"] = max_tokens

            try:
                async with client.stream("POST", "/api/chat", json=payload) as response:
                    response.raise_for_status()

                    index = 0
                    accumulated_content = ""

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            chunk_data = eval(line)
                        except Exception:
                            continue

                        if chunk_data.get("done"):
                            finish_reason = chunk_data.get("done_reason", "stop")
                            latency_ms = (time.perf_counter() - start_time) * 1000
                            self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                            yield StreamingChunk(
                                content=accumulated_content,
                                delta="",
                                model=self.config.default_model,
                                provider="ollama",
                                index=index,
                                finish_reason=finish_reason,
                            )
                            break

                        message = chunk_data.get("message", {})
                        content = message.get("content", "")
                        delta = content

                        if content:
                            accumulated_content += content
                            yield StreamingChunk(
                                content=accumulated_content,
                                delta=delta,
                                model=self.config.default_model,
                                provider="ollama",
                                index=index,
                            )
                            index += 1

            except httpx.TimeoutException:
                self.update_health(ProviderStatus.DEGRADED, self.config.timeout * 1000, False)
                raise ProviderTimeoutError(f"Stream timed out after {self.config.timeout}s")

            except Exception as e:
                self.update_health(ProviderStatus.UNHEALTHY, 0, False)
                logger.error(f"Ollama stream failed: {e}")
                raise ProviderError(f"Stream failed: {str(e)}")

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """
        Generate embeddings using Ollama.

        Args:
            texts: List of texts to embed
            model: Optional embedding model override

        Returns:
            List of embedding vectors
        """
        client = await self._get_client()

        embedding_model = model or "nomic-embed-text"
        embeddings = []

        for text in texts:
            try:
                response = await client.post(
                    "/api/embeddings",
                    json={"model": embedding_model, "prompt": text},
                )
                response.raise_for_status()

                result = response.json()
                embedding = result.get("embedding", [])
                embeddings.append(embedding)

            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                embeddings.append([])  # Return empty on failure

        return embeddings

    async def health_check(self) -> bool:
        """
        Check if Ollama is available and healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            client = await self._get_client()
            start_time = time.perf_counter()

            response = await client.get("/api/tags")
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)
                return True

            self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
            return False

        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            self.update_health(ProviderStatus.UNHEALTHY, 0, False)
            return False

    async def get_available_models(self) -> List[str]:
        """
        Get list of available Ollama models.

        Returns:
            List of model names
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            result = response.json()
            models = result.get("models", [])

            return [m.get("name", "") for m in models if m.get("name")]

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return self.config.supported_models

    async def get_gpu_info(self) -> Dict[str, Any]:
        """
        Get GPU information from Ollama.

        Returns:
            GPU info dictionary
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/ps")
            response.raise_for_status()

            result = response.json()

            return {
                "gpu_available": True,
                "gpus": result.get("gpus", []),
                "model": result.get("model", ""),
                "size": result.get("size", 0),
                "duration": result.get("duration", 0),
            }

        except Exception as e:
            logger.warning(f"Failed to get GPU info: {e}")
            return {"gpu_available": False}

    async def get_model_info(self, model: str) -> Optional[OllamaModel]:
        """
        Get information about a specific model.

        Args:
            model: Model name

        Returns:
            OllamaModel or None
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()

            result = response.json()
            models = result.get("models", [])

            for m in models:
                if m.get("name", "").startswith(model):
                    return OllamaModel(
                        name=m.get("name", ""),
                        size=m.get("size", 0),
                        modified_at=m.get("modified_at", ""),
                        digest=m.get("digest", ""),
                    )

            return None

        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return None

    def _estimate_tokens(self, texts: List[str]) -> int:
        """
        Estimate token count for texts.

        This is a rough approximation since Ollama doesn't
        return exact token counts.

        Args:
            texts: List of text strings

        Returns:
            Estimated token count
        """
        total_chars = sum(len(t) for t in texts)
        # Rough estimate: ~4 characters per token
        return max(1, total_chars // 4)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global provider instance
_ollama_provider: Optional[OllamaProvider] = None


def get_ollama_provider(config: Optional[ProviderConfig] = None) -> OllamaProvider:
    """
    Get or create global Ollama provider instance.

    Args:
        config: Optional configuration override

    Returns:
        OllamaProvider instance
    """
    global _ollama_provider

    if _ollama_provider is None:
        _ollama_provider = OllamaProvider(config)

    return _ollama_provider


async def create_ollama_provider(config: Optional[ProviderConfig] = None) -> OllamaProvider:
    """
    Create a new Ollama provider instance.

    Args:
        config: Optional configuration

    Returns:
        New OllamaProvider instance
    """
    return OllamaProvider(config)
