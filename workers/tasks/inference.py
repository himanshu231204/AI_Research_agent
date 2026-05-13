"""
Distributed inference workers for Research OS.

This module provides:
- Local inference worker
- Cloud inference worker
- Embeddings worker
- Reflection models worker

All workers support:
- Retries
- Provider failover
- Health metrics
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from celery import Task
from celery.result import AsyncResult

from workers.celery_app import celery_app
from workers.routing import TaskRouter, TaskType
from models.routing.router import (
    ModelRouter,
    get_model_router,
    TaskType as RoutingTaskType,
)
from models.routing.cost_optimizer import get_cost_optimizer, CostBudget
from models.routing.telemetry import record_inference_telemetry

logger = logging.getLogger(__name__)


@dataclass
class InferenceRequest:
    """Inference request payload."""

    session_id: str
    task_type: str  # planning, coding, reflection, etc.
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    system: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    prefer_local: bool = True


@dataclass
class InferenceResult:
    """Inference result payload."""

    content: str
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    success: bool
    error: Optional[str] = None
    fallback_used: bool = False
    fallback_chain: List[str] = None


class LocalInferenceWorker:
    """
    Worker for local model inference.

    Queue: local_inference
    """

    def __init__(self):
        """Initialize local inference worker."""
        self._router: Optional[ModelRouter] = None

    def _get_router(self) -> ModelRouter:
        """Get or create model router."""
        if self._router is None:
            self._router = get_model_router()
        return self._router

    async def process(
        self,
        request: InferenceRequest,
    ) -> InferenceResult:
        """
        Process inference request.

        Args:
            request: Inference request

        Returns:
            Inference result
        """
        router = self._get_router()

        # Convert task type
        task_type = RoutingTaskType(request.task_type)

        try:
            if request.messages:
                response, decision = await router.chat(
                    task_type=task_type,
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
            else:
                response, decision = await router.route(
                    task_type=task_type,
                    prompt=request.prompt or "",
                    system=request.system,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )

            # Record telemetry
            record_inference_telemetry(
                provider=decision.provider,
                model=decision.model,
                task_type=task_type,
                latency_ms=response.latency_ms,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                success=True,
                fallback_used=decision.fallback_attempted,
                fallback_chain=decision.fallback_chain,
            )

            return InferenceResult(
                content=response.content,
                provider=decision.provider,
                model=decision.model,
                latency_ms=response.latency_ms,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                cost_usd=0.0,  # Local models are free
                success=True,
                fallback_used=decision.fallback_attempted,
                fallback_chain=decision.fallback_chain,
            )

        except Exception as e:
            logger.error(f"Local inference failed: {e}")

            # Record failure telemetry
            record_inference_telemetry(
                provider="ollama",
                model="unknown",
                task_type=task_type,
                latency_ms=0,
                success=False,
                error=str(e),
            )

            return InferenceResult(
                content="",
                provider="ollama",
                model="unknown",
                latency_ms=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )

    async def stream(
        self,
        request: InferenceRequest,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream inference results."""
        router = self._get_router()
        task_type = RoutingTaskType(request.task_type)

        try:
            async for chunk, decision in router.stream(
                task_type=task_type,
                messages=request.messages or [],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield {
                    "content": chunk.content,
                    "delta": chunk.delta,
                    "model": chunk.model,
                    "provider": chunk.provider,
                    "index": chunk.index,
                    "finish_reason": chunk.finish_reason,
                }

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield {"error": str(e)}


class CloudInferenceWorker:
    """
    Worker for cloud model inference.

    Queue: cloud_inference
    """

    def __init__(self):
        """Initialize cloud inference worker."""
        self._router: Optional[ModelRouter] = None

    def _get_router(self) -> ModelRouter:
        """Get or create model router."""
        if self._router is None:
            self._router = get_model_router()
        return self._router

    async def process(
        self,
        request: InferenceRequest,
    ) -> InferenceResult:
        """
        Process cloud inference request.

        Args:
            request: Inference request

        Returns:
            Inference result
        """
        router = self._get_router()
        task_type = RoutingTaskType(request.task_type)

        # Force cloud provider
        policy = router.get_policy(task_type)

        try:
            if request.messages:
                response, decision = await router.chat(
                    task_type=task_type,
                    messages=request.messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
            else:
                response, decision = await router.route(
                    task_type=task_type,
                    prompt=request.prompt or "",
                    system=request.system,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )

            # Calculate cost
            cost_optimizer = get_cost_optimizer(request.session_id)
            cost = cost_optimizer.estimate_cost(
                decision.model,
                decision.provider,
                response.prompt_tokens,
                response.completion_tokens,
            )

            # Record telemetry
            record_inference_telemetry(
                provider=decision.provider,
                model=decision.model,
                task_type=task_type,
                latency_ms=response.latency_ms,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cost_usd=cost,
                success=True,
                fallback_used=decision.fallback_attempted,
            )

            return InferenceResult(
                content=response.content,
                provider=decision.provider,
                model=decision.model,
                latency_ms=response.latency_ms,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                cost_usd=cost,
                success=True,
                fallback_used=decision.fallback_attempted,
                fallback_chain=decision.fallback_chain,
            )

        except Exception as e:
            logger.error(f"Cloud inference failed: {e}")

            record_inference_telemetry(
                provider="cloud",
                model="unknown",
                task_type=task_type,
                latency_ms=0,
                success=False,
                error=str(e),
            )

            return InferenceResult(
                content="",
                provider="cloud",
                model="unknown",
                latency_ms=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_usd=0.0,
                success=False,
                error=str(e),
            )


class EmbeddingsWorker:
    """
    Worker for embedding generation.

    Queue: embeddings
    """

    def __init__(self):
        """Initialize embeddings worker."""
        pass

    async def generate_embeddings(
        self,
        texts: List[str],
        model: str = "nomic-embed-text",
        provider: str = "ollama",
    ) -> List[List[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: Texts to embed
            model: Embedding model
            provider: Provider

        Returns:
            List of embeddings
        """
        from models.providers.local import get_ollama_provider

        ollama = get_ollama_provider()

        try:
            embeddings = await ollama.embeddings(texts, model)
            return embeddings

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return [[] for _ in texts]


# Celery task wrappers


def _run_async(coro):
    """
    Safely run async function in event loop with proper error handling.

    Args:
        coro: Coroutine to run

    Returns:
        Result from coroutine

    Raises:
        Exception: Re-raises any exception from the coroutine
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except RuntimeError:
        # Event loop already exists in this thread
        loop = asyncio.get_event_loop()

    try:
        return loop.run_until_complete(coro)
    except RuntimeError as e:
        # Handle event loop in worker context
        logger.error(f"Event loop error: {e}")
        raise
    finally:
        # Only close if we created the loop
        try:
            loop.close()
        except RuntimeError:
            pass  # Loop was already running


@celery_app.task(
    bind=True,
    name="inference.local",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(asyncio.TimeoutError, ConnectionError),
    retry_backoff=True,
)
def local_inference_task(
    self,
    session_id: str,
    task_type: str,
    prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Celery task for local inference.

    Args:
        session_id: Session ID
        task_type: Task type
        prompt: Prompt text
        messages: Chat messages
        system: System prompt
        temperature: Temperature
        max_tokens: Max tokens

    Returns:
        Result dictionary
    """
    request = InferenceRequest(
        session_id=session_id,
        task_type=task_type,
        prompt=prompt,
        messages=messages,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        prefer_local=True,
    )

    worker = LocalInferenceWorker()

    try:
        result = _run_async(worker.process(request))
        return {
            "content": result.content,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "success": result.success,
            "error": result.error,
            "fallback_used": result.fallback_used,
        }
    except Exception as e:
        logger.error(f"Local inference task failed: {e}")
        # Retry will be handled by Celery's autoretry
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    name="inference.cloud",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(asyncio.TimeoutError, ConnectionError),
    retry_backoff=True,
)
def cloud_inference_task(
    self,
    session_id: str,
    task_type: str,
    prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Celery task for cloud inference.

    Args:
        session_id: Session ID
        task_type: Task type
        prompt: Prompt text
        messages: Chat messages
        system: System prompt
        temperature: Temperature
        max_tokens: Max tokens

    Returns:
        Result dictionary
    """
    request = InferenceRequest(
        session_id=session_id,
        task_type=task_type,
        prompt=prompt,
        messages=messages,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        prefer_local=False,
    )

    worker = CloudInferenceWorker()

    try:
        result = _run_async(worker.process(request))
        return {
            "content": result.content,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
            "cost_usd": result.cost_usd,
            "success": result.success,
            "error": result.error,
            "fallback_used": result.fallback_used,
        }
    except Exception as e:
        logger.error(f"Cloud inference task failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    name="inference.embeddings",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(asyncio.TimeoutError, ConnectionError),
    retry_backoff=True,
)
def embeddings_task(
    self,
    texts: List[str],
    model: str = "nomic-embed-text",
    provider: str = "ollama",
) -> Dict[str, Any]:
    """
    Celery task for embeddings.

    Args:
        texts: Texts to embed
        model: Embedding model
        provider: Provider

    Returns:
        Result dictionary
    """
    worker = EmbeddingsWorker()

    try:
        embeddings = _run_async(worker.generate_embeddings(texts, model, provider))
        return {
            "embeddings": embeddings,
            "count": len(embeddings),
            "success": True,
        }
    except Exception as e:
        logger.error(f"Embeddings task failed: {e}")
        return {
            "embeddings": [],
            "count": 0,
            "success": False,
            "error": str(e),
        }


# Worker dispatch functions


def dispatch_local_inference(
    session_id: str,
    task_type: str,
    **kwargs,
) -> AsyncResult:
    """Dispatch local inference task."""
    return local_inference_task.delay(session_id, task_type, **kwargs)


def dispatch_cloud_inference(
    session_id: str,
    task_type: str,
    **kwargs,
) -> AsyncResult:
    """Dispatch cloud inference task."""
    return cloud_inference_task.delay(session_id, task_type, **kwargs)


def dispatch_embeddings(
    texts: List[str],
    model: str = "nomic-embed-text",
) -> AsyncResult:
    """Dispatch embeddings task."""
    return embeddings_task.delay(texts, model)
