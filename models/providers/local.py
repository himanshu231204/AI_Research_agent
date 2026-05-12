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
import asyncio
import subprocess
import re
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

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


@dataclass
class GPUInfo:
    """Detailed GPU information from Ollama and system."""

    gpu_available: bool = False
    gpu_count: int = 0
    gpus: List[Dict[str, Any]] = field(default_factory=list)
    memory_total_mb: float = 0.0
    memory_used_mb: float = 0.0
    memory_free_mb: float = 0.0
    compute_utilization: float = 0.0
    temperature: Optional[float] = None
    driver_version: Optional[str] = None
    runtime_version: Optional[str] = None
    inference_mode: str = "unknown"  # "nvidia", "amd", "cpu"
    model_loaded: Optional[str] = None
    model_size_bytes: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def memory_percent(self) -> float:
        """Calculate memory usage percentage."""
        if self.memory_total_mb <= 0:
            return 0.0
        return (self.memory_used_mb / self.memory_total_mb) * 100

    @property
    def is_saturated(self) -> bool:
        """Check if GPU is saturated (>90% memory)."""
        return self.memory_percent > 90

    @property
    def is_busy(self) -> bool:
        """Check if GPU is busy (>70% memory)."""
        return self.memory_percent > 70

    @property
    def status(self) -> str:
        """Get human-readable status."""
        if not self.gpu_available:
            if self.inference_mode == "cpu":
                return "cpu_mode"
            return "unavailable"
        if self.is_saturated:
            return "saturated"
        if self.is_busy:
            return "busy"
        return "available"


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
        Get GPU information from Ollama and system.

        This method checks for GPU availability through multiple sources:
        1. Ollama's /api/ps endpoint (primary)
        2. Direct nvidia-smi command (verification)
        3. System GPU detection (fallback)

        Returns:
            Dict with gpu_available, inference_mode, and detailed GPU metrics
        """
        gpu_info = GPUInfo()

        # First, try Ollama's /api/ps endpoint
        try:
            client = await self._get_client()
            response = await client.get("/api/ps")
            response.raise_for_status()
            result = response.json()

            logger.debug(f"Ollama /api/ps response: {result}")

            # Parse Ollama's GPU information
            ollama_gpus = result.get("gpus", [])
            loaded_model = result.get("model", "")
            model_size = result.get("size", 0)
            duration = result.get("duration", 0)

            gpu_info.model_loaded = loaded_model
            gpu_info.model_size_bytes = model_size

            # Check if Ollama detected GPUs
            if ollama_gpus and len(ollama_gpus) > 0:
                gpu_info.gpu_available = True
                gpu_info.gpu_count = len(ollama_gpus)
                gpu_info.gpus = ollama_gpus

                # Parse each GPU's memory info
                total_memory = 0.0
                used_memory = 0.0

                for gpu in ollama_gpus:
                    # GPU memory in bytes, convert to MB
                    mem_used = gpu.get("memory_used", 0) / (1024 * 1024)
                    mem_total = gpu.get("memory_total", 0) / (1024 * 1024)
                    mem_free = gpu.get("memory_free", 0) / (1024 * 1024)

                    total_memory += mem_total
                    used_memory += mem_used

                    gpu_info.memory_used_mb = max(gpu_info.memory_used_mb, mem_used)
                    gpu_info.memory_free_mb = max(gpu_info.memory_free_mb, mem_free)

                    # Get utilization if available
                    utilization = gpu.get("utilization", 0)
                    gpu_info.compute_utilization = max(gpu_info.compute_utilization, utilization)

                gpu_info.memory_total_mb = total_memory
                gpu_info.memory_used_mb = used_memory

                # Determine inference mode from GPU vendor
                if ollama_gpus:
                    first_gpu = ollama_gpus[0]
                    vendor = first_gpu.get("vendor", "").lower()

                    if "nvidia" in vendor or "cuda" in str(first_gpu):
                        gpu_info.inference_mode = "nvidia"
                    elif "amd" in vendor or "rocm" in str(first_gpu):
                        gpu_info.inference_mode = "amd"
                    else:
                        gpu_info.inference_mode = "nvidia"  # Default assumption

                logger.info(
                    f"Ollama GPU detected: {gpu_info.gpu_count} GPU(s), "
                    f"mode={gpu_info.inference_mode}, "
                    f"memory={gpu_info.memory_used_mb:.0f}/{gpu_info.memory_total_mb:.0f}MB"
                )

            else:
                # No GPU detected by Ollama - check if it's CPU-only or GPU issue
                logger.debug("Ollama reports no GPUs (CPU mode or GPU not accessible)")

                # Try direct nvidia-smi as verification
                nvidia_result = await self._check_nvidia_smi()
                if nvidia_result["available"]:
                    # nvidia-smi works but Ollama doesn't see GPU
                    # This could mean GPU passthrough issue
                    logger.warning(
                        f"nvidia-smi available but Ollama doesn't detect GPU. "
                        f"Ollama may not be configured for GPU access."
                    )
                    gpu_info.inference_mode = "nvidia"
                    gpu_info.gpu_available = False  # Ollama can't use GPU
                    gpu_info.gpu_count = nvidia_result.get("gpu_count", 0)
                    gpu_info.driver_version = nvidia_result.get("driver_version")

                    # Populate GPU info from nvidia-smi
                    if nvidia_result.get("gpus"):
                        gpu_info.gpus = nvidia_result["gpus"]
                        gpu_info.memory_total_mb = nvidia_result.get("memory_total_mb", 0)
                        gpu_info.memory_used_mb = nvidia_result.get("memory_used_mb", 0)
                        gpu_info.memory_free_mb = nvidia_result.get("memory_free_mb", 0)
                else:
                    # No NVIDIA GPU - could be AMD or CPU-only
                    if nvidia_result.get("error") == "no_nvidia":
                        # Check for AMD GPU via rocm-smi if available
                        amd_result = await self._check_amd_gpu()
                        if amd_result["available"]:
                            gpu_info.inference_mode = "amd"
                            gpu_info.gpu_count = amd_result.get("gpu_count", 0)
                            gpu_info.gpus = amd_result.get("gpus", [])
                        else:
                            # Pure CPU mode
                            gpu_info.inference_mode = "cpu"
                            gpu_info.gpu_available = False
                            logger.info("Running in CPU-only mode (no GPU detected)")
                    else:
                        # Error checking GPU
                        gpu_info.inference_mode = "cpu"
                        gpu_info.gpu_available = False

        except httpx.TimeoutException:
            logger.warning("Timeout checking Ollama GPU status")
            gpu_info.inference_mode = "cpu"
            gpu_info.gpu_available = False

        except Exception as e:
            logger.error(f"Failed to get GPU info: {e}")
            gpu_info.inference_mode = "cpu"
            gpu_info.gpu_available = False

        # Update provider health with GPU info
        self._health.gpu_available = gpu_info.gpu_available
        self._health.gpu_memory_percent = gpu_info.memory_percent
        self._health.active_models = [gpu_info.model_loaded] if gpu_info.model_loaded else []

        # Convert to dictionary for API response
        return {
            "gpu_available": gpu_info.gpu_available,
            "inference_mode": gpu_info.inference_mode,
            "gpu_count": gpu_info.gpu_count,
            "gpus": gpu_info.gpus,
            "memory_total_mb": gpu_info.memory_total_mb,
            "memory_used_mb": gpu_info.memory_used_mb,
            "memory_free_mb": gpu_info.memory_free_mb,
            "memory_percent": gpu_info.memory_percent,
            "compute_utilization": gpu_info.compute_utilization,
            "temperature": gpu_info.temperature,
            "driver_version": gpu_info.driver_version,
            "runtime_version": gpu_info.runtime_version,
            "model_loaded": gpu_info.model_loaded,
            "model_size_bytes": gpu_info.model_size_bytes,
            "is_saturated": gpu_info.is_saturated,
            "is_busy": gpu_info.is_busy,
            "status": gpu_info.status,
            "last_updated": gpu_info.last_updated.isoformat(),
        }

    async def _check_nvidia_smi(self) -> Dict[str, Any]:
        """
        Check NVIDIA GPU status using nvidia-smi command.

        Returns:
            Dict with GPU info or error indication
        """
        result = {
            "available": False,
            "gpu_count": 0,
            "driver_version": None,
            "memory_total_mb": 0,
            "memory_used_mb": 0,
            "memory_free_mb": 0,
            "gpus": [],
            "error": None,
        }

        try:
            # Run nvidia-smi with JSON output for easier parsing
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,driver_version",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

            if proc.returncode == 0 and stdout:
                lines = stdout.decode("utf-8").strip().split("\n")
                for line in lines:
                    if line.strip():
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 7:
                            gpu_data = {
                                "index": int(parts[0]) if parts[0].isdigit() else 0,
                                "name": parts[1] if len(parts) > 1 else "Unknown",
                                "memory_total": int(parts[2]) if parts[2].isdigit() else 0,
                                "memory_used": int(parts[3]) if parts[3].isdigit() else 0,
                                "memory_free": int(parts[4]) if parts[4].isdigit() else 0,
                                "utilization": int(parts[5]) if parts[5].isdigit() else 0,
                                "temperature": int(parts[6])
                                if len(parts) > 6 and parts[6].isdigit()
                                else None,
                                "driver_version": parts[7] if len(parts) > 7 else None,
                            }
                            result["gpus"].append(gpu_data)
                            result["memory_total_mb"] += gpu_data["memory_total"]
                            result["memory_used_mb"] += gpu_data["memory_used"]
                            result["memory_free_mb"] += gpu_data["memory_free"]

                result["available"] = True
                result["gpu_count"] = len(result["gpus"])
                if result["gpus"]:
                    result["driver_version"] = result["gpus"][0].get("driver_version")

                logger.debug(
                    f"nvidia-smi: {result['gpu_count']} GPUs, "
                    f"memory={result['memory_used_mb']}/{result['memory_total_mb']}MB"
                )
            else:
                # nvidia-smi failed - likely no NVIDIA GPU
                error_msg = stderr.decode("utf-8") if stderr else "Unknown error"
                if "no nvidia" in error_msg.lower() or "not found" in error_msg.lower():
                    result["error"] = "no_nvidia"
                else:
                    result["error"] = error_msg
                logger.debug(f"nvidia-smi not available: {error_msg}")

        except asyncio.TimeoutError:
            result["error"] = "timeout"
            logger.warning("nvidia-smi command timed out")
        except FileNotFoundError:
            result["error"] = "no_nvidia"
            logger.debug("nvidia-smi command not found (no NVIDIA GPU)")
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"Error running nvidia-smi: {e}")

        return result

    async def _check_amd_gpu(self) -> Dict[str, Any]:
        """
        Check AMD GPU status using rocm-smi or sysfs.

        Returns:
            Dict with GPU info or error indication
        """
        result = {
            "available": False,
            "gpu_count": 0,
            "gpus": [],
            "error": None,
        }

        # Try rocm-smi first
        try:
            proc = await asyncio.create_subprocess_exec(
                "rocm-smi",
                "--showid",
                "--showmeminfo",
                "vram",
                "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)

            if proc.returncode == 0 and stdout:
                # Parse rocm-smi output
                result["available"] = True
                result["gpu_count"] = 1  # rocm-smi typically shows one at a time
                logger.debug("AMD GPU detected via rocm-smi")

        except (asyncio.TimeoutError, FileNotFoundError, Exception):
            # rocm-smi not available or failed
            result["error"] = "no_amd"

        # Fallback: check /sys/class/drm for AMD GPUs
        if not result["available"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ls",
                    "/sys/class/drm",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()

                if b"card" in stdout.lower():
                    # Potential GPU detected
                    result["available"] = True
                    result["gpu_count"] = stdout.decode().count("card")
                    logger.debug(f"Potential GPU detected in /sys/class/drm")

            except Exception:
                pass

        return result

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
