"""
Cloud model providers for Research OS.

Implements LLMProvider interface for:
- OpenAI (GPT-4, GPT-5)
- Anthropic (Claude)
- Google (Gemini)

All providers support:
- Async clients
- Retries
- Timeout handling
- Rate limiting
- Usage tracking
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
    LLMResponse,
    StreamingChunk,
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
)
from api.config import get_settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider for cloud LLM inference.

    Supports GPT-4, GPT-4o, GPT-5 models.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        """Initialize OpenAI provider."""
        settings = get_settings()

        if config is None:
            config = ProviderConfig(
                provider_type=ProviderType.OPENAI,
                name="openai",
                base_url="https://api.openai.com/v1",
                api_key=settings.openai_api_key if hasattr(settings, "openai_api_key") else None,
                timeout=120,
                default_model="gpt-4o",
                supported_models=["gpt-4o", "gpt-4o-mini", "gpt-5"],
                max_retries=3,
                prompt_cost=5.0,
                completion_cost=15.0,
            )

        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
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
        """Generate text using OpenAI."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages, temperature, max_tokens, stop)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate chat completion using OpenAI."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if stop:
                payload["stop"] = stop

            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")

                usage = result.get("usage", {})

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                return LLMResponse(
                    content=content,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=self.config.default_model,
                    provider="openai",
                    finish_reason=choice.get("finish_reason", ""),
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError(f"OpenAI request timed out")

            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)

                if e.response.status_code == 429:
                    raise ProviderRateLimitError("OpenAI rate limit exceeded")
                elif e.response.status_code == 401:
                    raise ProviderAuthenticationError("OpenAI authentication failed")

                raise ProviderError(f"OpenAI HTTP error: {e.response.status_code}")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                raise ProviderError(f"OpenAI request failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream chat completion from OpenAI."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            try:
                async with client.stream("POST", "/chat/completions", json=payload) as response:
                    response.raise_for_status()

                    index = 0
                    accumulated_content = ""

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        if not line.startswith("data: "):
                            continue

                        data = line[6:]  # Remove "data: " prefix

                        if data == "[DONE]":
                            latency_ms = (time.perf_counter() - start_time) * 1000
                            self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                            yield StreamingChunk(
                                content=accumulated_content,
                                delta="",
                                model=self.config.default_model,
                                provider="openai",
                                index=index,
                                finish_reason="stop",
                            )
                            break

                        try:
                            chunk_data = eval(data)
                        except Exception:
                            continue

                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            accumulated_content += content
                            yield StreamingChunk(
                                content=accumulated_content,
                                delta=content,
                                model=self.config.default_model,
                                provider="openai",
                                index=index,
                            )
                            index += 1

            except Exception as e:
                self.update_health(ProviderStatus.UNHEALTHY, 0, False)
                raise ProviderError(f"OpenAI stream failed: {str(e)}")

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI."""
        client = await self._get_client()

        embedding_model = model or "text-embedding-3-small"
        embeddings = []

        # OpenAI supports batch embeddings
        try:
            response = await client.post(
                "/embeddings",
                json={
                    "input": texts,
                    "model": embedding_model,
                },
            )
            response.raise_for_status()

            result = response.json()
            for item in result.get("data", []):
                embeddings.append(item.get("embedding", []))

        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            embeddings = [[] for _ in texts]

        return embeddings

    async def health_check(self) -> bool:
        """Check if OpenAI is available."""
        try:
            client = await self._get_client()
            start_time = time.perf_counter()

            # Use models endpoint for health check
            response = await client.get("/models")
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)
                return True

            self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
            return False

        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            self.update_health(ProviderStatus.UNHEALTHY, 0, False)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class AnthropicProvider(LLMProvider):
    """
    Anthropic provider for cloud LLM inference.

    Supports Claude models.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        """Initialize Anthropic provider."""
        settings = get_settings()

        if config is None:
            config = ProviderConfig(
                provider_type=ProviderType.ANTHROPIC,
                name="anthropic",
                base_url="https://api.anthropic.com/v1",
                api_key=settings.anthropic_api_key
                if hasattr(settings, "anthropic_api_key")
                else None,
                timeout=120,
                default_model="claude-sonnet-4-20250514",
                supported_models=[
                    "claude-opus-4-20250514",
                    "claude-sonnet-4-20250514",
                    "claude-3-5-sonnet-20240620",
                ],
                max_retries=3,
                prompt_cost=3.0,
                completion_cost=15.0,
            )

        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
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
        """Generate text using Anthropic."""
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages, temperature, max_tokens, stop)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate chat completion using Anthropic."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            # Convert messages to Anthropic format
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                if role == "assistant":
                    role = "assistant"
                elif role == "system":
                    continue  # Anthropic uses system separately
                anthropic_messages.append(
                    {
                        "role": role,
                        "content": msg.get("content", ""),
                    }
                )

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
            }

            if stop:
                payload["stop_sequences"] = stop

            try:
                response = await client.post("/messages", json=payload)
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                content = result.get("content", [{}])[0].get("text", "")

                usage = result.get("usage", {})

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                return LLMResponse(
                    content=content,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    model=self.config.default_model,
                    provider="anthropic",
                    finish_reason=result.get("stop_reason", ""),
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError("Anthropic request timed out")

            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)

                if e.response.status_code == 429:
                    raise ProviderRateLimitError("Anthropic rate limit exceeded")
                elif e.response.status_code == 401:
                    raise ProviderAuthenticationError("Anthropic authentication failed")

                raise ProviderError(f"Anthropic HTTP error: {e.response.status_code}")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                raise ProviderError(f"Anthropic request failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream chat completion from Anthropic."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            anthropic_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                if role == "system":
                    continue
                anthropic_messages.append(
                    {
                        "role": role,
                        "content": msg.get("content", ""),
                    }
                )

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens or 4096,
                "temperature": temperature,
                "stream": True,
            }

            try:
                async with client.stream("POST", "/messages", json=payload) as response:
                    response.raise_for_status()

                    index = 0
                    accumulated_content = ""

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        if line.startswith("data: "):
                            data = line[6:]

                            try:
                                chunk_data = eval(data)
                            except Exception:
                                continue

                            if chunk_data.get("type") == "content_block_delta":
                                delta = chunk_data.get("delta", {})
                                content = delta.get("text", "")

                                if content:
                                    accumulated_content += content
                                    yield StreamingChunk(
                                        content=accumulated_content,
                                        delta=content,
                                        model=self.config.default_model,
                                        provider="anthropic",
                                        index=index,
                                    )
                                    index += 1

                            elif chunk_data.get("type") == "message_delta":
                                finish_reason = chunk_data.get("delta", {}).get(
                                    "stop_reason", "stop"
                                )
                                latency_ms = (time.perf_counter() - start_time) * 1000
                                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                                yield StreamingChunk(
                                    content=accumulated_content,
                                    delta="",
                                    model=self.config.default_model,
                                    provider="anthropic",
                                    index=index,
                                    finish_reason=finish_reason,
                                )

            except Exception as e:
                self.update_health(ProviderStatus.UNHEALTHY, 0, False)
                raise ProviderError(f"Anthropic stream failed: {str(e)}")

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """Anthropic doesn't provide embeddings, return empty."""
        return [[] for _ in texts]

    async def health_check(self) -> bool:
        """Check if Anthropic is available."""
        try:
            client = await self._get_client()
            start_time = time.perf_counter()

            # Use a simple request to check availability
            response = await client.post(
                "/messages",
                json={
                    "model": self.config.default_model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code in (200, 201):
                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)
                return True

            self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
            return False

        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            self.update_health(ProviderStatus.UNHEALTHY, 0, False)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class GoogleProvider(LLMProvider):
    """
    Google provider for cloud LLM inference.

    Supports Gemini models.
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        """Initialize Google provider."""
        settings = get_settings()

        if config is None:
            config = ProviderConfig(
                provider_type=ProviderType.GOOGLE,
                name="google",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                api_key=settings.google_api_key if hasattr(settings, "google_api_key") else None,
                timeout=120,
                default_model="gemini-2.0-flash",
                supported_models=["gemini-2.0-flash", "gemini-2.5-pro"],
                max_retries=3,
                prompt_cost=0.10,
                completion_cost=0.40,
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

    def _get_model_path(self) -> str:
        """Get model path for API calls."""
        return f"models/{self.config.default_model}"

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate text using Google Gemini."""
        messages = [{"role": "user", "parts": [{"text": prompt}]}]
        if system:
            messages.insert(0, {"role": "system", "parts": [{"text": system}]})

        return await self.chat(messages, temperature, max_tokens, stop)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate chat completion using Google Gemini."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                role = msg.get("role", "user")
                if role == "system":
                    continue
                # Map roles
                if role == "assistant":
                    role = "model"
                contents.append(
                    {
                        "role": role,
                        "parts": [{"text": msg.get("content", "")}],
                    }
                )

            payload: Dict[str, Any] = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                },
            }

            if max_tokens:
                payload["generationConfig"]["maxOutputTokens"] = max_tokens

            if stop:
                payload["generationConfig"]["stopSequences"] = stop

            model_path = self._get_model_path()
            url = f"{self.config.base_url}/{model_path}:generateContent"

            try:
                response = await client.post(
                    url,
                    json=payload,
                    params={"key": self.config.api_key},
                )
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                candidates = result.get("candidates", [{}])
                content = candidates[0].get("content", {})
                parts = content.get("parts", [{}])
                text = parts[0].get("text", "")

                # Estimate tokens
                prompt_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
                completion_tokens = len(text) // 4

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                return LLMResponse(
                    content=text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    model=self.config.default_model,
                    provider="google",
                    finish_reason=candidates[0].get("finishReason", ""),
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError("Google request timed out")

            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)

                if e.response.status_code == 429:
                    raise ProviderRateLimitError("Google rate limit exceeded")

                raise ProviderError(f"Google HTTP error: {e.response.status_code}")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                raise ProviderError(f"Google request failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream chat completion from Google Gemini."""
        # Gemini streaming is complex, fall back to non-streaming
        response = await self.chat(messages, temperature, max_tokens)
        yield StreamingChunk(
            content=response.content,
            delta=response.content,
            model=self.config.default_model,
            provider="google",
            index=0,
            finish_reason="stop",
        )

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """Generate embeddings using Google."""
        client = await self._get_client()
        embeddings = []

        embedding_model = model or "embedding-001"

        for text in texts:
            try:
                response = await client.post(
                    f"models/{embedding_model}:predict",
                    json={"content": text},
                    params={"key": self.config.api_key},
                )
                response.raise_for_status()

                result = response.json()
                embedding = result.get("embedding", {}).get("values", [])
                embeddings.append(embedding)

            except Exception as e:
                logger.error(f"Google embedding failed: {e}")
                embeddings.append([])

        return embeddings

    async def health_check(self) -> bool:
        """Check if Google is available."""
        try:
            client = await self._get_client()
            start_time = time.perf_counter()

            # Use models list for health check
            response = await client.get(
                f"{self.config.base_url}/models",
                params={"key": self.config.api_key},
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)
                return True

            self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
            return False

        except Exception as e:
            logger.warning(f"Google health check failed: {e}")
            self.update_health(ProviderStatus.UNHEALTHY, 0, False)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class GroqProvider(LLMProvider):
    """
    Groq provider for cloud LLM inference.

    Supports Groq's fast inference models including:
    - LLaMA models
    - Mixtral models
    - Gemma models
    """

    def __init__(self, config: Optional[ProviderConfig] = None):
        """Initialize Groq provider."""
        settings = get_settings()

        if config is None:
            config = ProviderConfig(
                provider_type=ProviderType.OPENROUTER,  # Groq uses OpenAI-compatible API
                name="groq",
                base_url="https://api.groq.com/openai/v1",
                api_key=settings.groq_api_key if hasattr(settings, "groq_api_key") else None,
                timeout=120,
                default_model="llama-3.3-70b-versatile",
                supported_models=[
                    "llama-3.3-70b-versatile",
                    "llama-3.1-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                ],
                max_retries=3,
                prompt_cost=0.0,  # Groq pricing varies, check current rates
                completion_cost=0.0,
            )

        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
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
        """Generate text using Groq."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(messages, temperature, max_tokens, stop)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate chat completion using Groq."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            if stop:
                payload["stop"] = stop

            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()

                result = response.json()
                latency_ms = (time.perf_counter() - start_time) * 1000

                choice = result.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")

                usage = result.get("usage", {})

                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                return LLMResponse(
                    content=content,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    model=self.config.default_model,
                    provider="groq",
                    finish_reason=choice.get("finish_reason", ""),
                    latency_ms=latency_ms,
                    raw_response=result,
                )

            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.DEGRADED, latency_ms, False)
                raise ProviderTimeoutError(f"Groq request timed out")

            except httpx.HTTPStatusError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)

                if e.response.status_code == 429:
                    raise ProviderRateLimitError("Groq rate limit exceeded")
                elif e.response.status_code == 401:
                    raise ProviderAuthenticationError("Groq authentication failed")

                raise ProviderError(f"Groq HTTP error: {e.response.status_code}")

            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
                raise ProviderError(f"Groq request failed: {str(e)}")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[StreamingChunk, None]:
        """Stream chat completion from Groq."""
        start_time = time.perf_counter()

        async with self._semaphore:
            client = await self._get_client()

            payload: Dict[str, Any] = {
                "model": self.config.default_model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                payload["max_tokens"] = max_tokens

            try:
                async with client.stream("POST", "/chat/completions", json=payload) as response:
                    response.raise_for_status()

                    index = 0
                    accumulated_content = ""

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        if not line.startswith("data: "):
                            continue

                        data = line[6:]

                        if data == "[DONE]":
                            latency_ms = (time.perf_counter() - start_time) * 1000
                            self.update_health(ProviderStatus.HEALTHY, latency_ms, True)

                            yield StreamingChunk(
                                content=accumulated_content,
                                delta="",
                                model=self.config.default_model,
                                provider="groq",
                                index=index,
                                finish_reason="stop",
                            )
                            break

                        try:
                            chunk_data = eval(data)
                        except Exception:
                            continue

                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            accumulated_content += content
                            yield StreamingChunk(
                                content=accumulated_content,
                                delta=content,
                                model=self.config.default_model,
                                provider="groq",
                                index=index,
                            )
                            index += 1

            except Exception as e:
                self.update_health(ProviderStatus.UNHEALTHY, 0, False)
                raise ProviderError(f"Groq stream failed: {str(e)}")

    async def embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        """Groq doesn't provide embeddings, return empty."""
        return [[] for _ in texts]

    async def health_check(self) -> bool:
        """Check if Groq is available."""
        try:
            client = await self._get_client()
            start_time = time.perf_counter()

            # Use models endpoint for health check
            response = await client.get("/models")
            latency_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                self.update_health(ProviderStatus.HEALTHY, latency_ms, True)
                return True

            self.update_health(ProviderStatus.UNHEALTHY, latency_ms, False)
            return False

        except Exception as e:
            logger.warning(f"Groq health check failed: {e}")
            self.update_health(ProviderStatus.UNHEALTHY, 0, False)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Provider factory functions


def create_openai_provider(config: Optional[ProviderConfig] = None) -> OpenAIProvider:
    """Create OpenAI provider."""
    return OpenAIProvider(config)


def create_anthropic_provider(config: Optional[ProviderConfig] = None) -> AnthropicProvider:
    """Create Anthropic provider."""
    return AnthropicProvider(config)


def create_google_provider(config: Optional[ProviderConfig] = None) -> GoogleProvider:
    """Create Google provider."""
    return GoogleProvider(config)


def create_groq_provider(config: Optional[ProviderConfig] = None) -> GroqProvider:
    """Create Groq provider."""
    return GroqProvider(config)
