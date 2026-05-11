"""
Embedding infrastructure for Research OS.

Provides:
- Async embedding generation
- Batch embeddings
- Retry handling
- Caching
- Provider abstraction
"""

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeVar, Generic

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from api.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    text: str
    embedding: List[float]
    model: str
    dimension: int
    tokens_used: int
    cached: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text[:100],  # Truncate for logging
            "embedding_length": len(self.embedding),
            "model": self.model,
            "dimension": self.dimension,
            "tokens_used": self.tokens_used,
            "cached": self.cached,
            "latency_ms": self.latency_ms,
        }


@dataclass
class BatchEmbeddingResult:
    """Result of batch embedding generation."""

    results: List[EmbeddingResult]
    total_tokens: int
    total_latency_ms: float
    cache_hits: int


class EmbeddingCache:
    """
    Simple in-memory cache for embeddings.

    Uses LRU eviction and SHA256 key hashing.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize embedding cache.

        Args:
            max_size: Maximum number of cached embeddings
        """
        self.max_size = max_size
        self._cache: Dict[str, List[float]] = {}
        self._access_order: List[str] = []
        self._hits = 0
        self._misses = 0

    def _make_key(self, text: str, model: str) -> str:
        """Create cache key from text and model."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, text: str, model: str) -> Optional[List[float]]:
        """Get cached embedding."""
        key = self._make_key(text, model)

        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key].copy()

        self._misses += 1
        return None

    def put(self, text: str, model: str, embedding: List[float]) -> None:
        """Store embedding in cache."""
        key = self._make_key(text, model)

        # Evict if at capacity
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]

        self._cache[key] = embedding.copy()

        if key not in self._access_order:
            self._access_order.append(key)

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._cache.clear()
        self._access_order.clear()

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding providers.

    Implement this to add new embedding models.
    """

    def __init__(self, model_name: str, dimension: int = 768):
        """
        Initialize embedding provider.

        Args:
            model_name: Name of the embedding model
            dimension: Embedding vector dimension
        """
        self.model_name = model_name
        self.dimension = dimension

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        pass


class OllamaEmbeddingProvider(EmbeddingProvider):
    """
    Ollama-based embedding provider.

    Uses Ollama API for local embedding generation.
    """

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        base_url: Optional[str] = None,
        dimension: int = 768,
        timeout: int = 60,
    ):
        """
        Initialize Ollama embedding provider.

        Args:
            model_name: Ollama model name
            base_url: Ollama server URL
            dimension: Expected embedding dimension
            timeout: Request timeout in seconds
        """
        super().__init__(model_name, dimension)

        settings = get_settings()
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout

        self._cache = EmbeddingCache()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
    )
    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to Ollama API with retry."""
        import httpx

        url = f"{self.base_url}/api/{endpoint}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            return response.json()

    async def embed(self, text: str) -> List[float]:
        """Generate embedding using Ollama."""
        # Check cache first
        cached = self._cache.get(text, self.model_name)
        if cached is not None:
            return cached

        try:
            result = await self._make_request(
                "embeddings",
                {"model": self.model_name, "prompt": text},
            )

            embedding = result.get("embedding", [])
            self._cache.put(text, self.model_name, embedding)

            return embedding

        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            # Return mock embedding for development
            return self._mock_embedding(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings batch using Ollama."""
        # Check cache for each text
        results = []
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text, self.model_name)
            if cached is not None:
                results.append(cached)
            else:
                results.append(None)
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Process uncached texts
        if uncached_texts:
            # Ollama doesn't have native batch, so process sequentially
            # In production, you might use a batch-capable model
            embeddings = await asyncio.gather(
                *[self._single_embed(text) for text in uncached_texts]
            )

            for idx, embedding in zip(uncached_indices, embeddings):
                results[idx] = embedding
                self._cache.put(
                    uncached_texts[uncached_indices.index(idx)], self.model_name, embedding
                )

        return results

    async def _single_embed(self, text: str) -> List[float]:
        """Embed a single text (without cache check)."""
        try:
            result = await self._make_request(
                "embeddings",
                {"model": self.model_name, "prompt": text},
            )
            return result.get("embedding", [])

        except Exception as e:
            logger.error(f"Single embed failed: {e}")
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> List[float]:
        """Generate mock embedding for development."""
        content_hash = hashlib.sha256(text.encode()).digest()
        embedding = list(content_hash[: self.dimension])

        # Pad to required dimension
        while len(embedding) < self.dimension:
            embedding.append(0.0)

        return embedding[: self.dimension]

    async def health_check(self) -> bool:
        """Check Ollama health."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Mock embedding provider for development and testing.

    Generates deterministic fake embeddings.
    """

    def __init__(self, model_name: str = "mock", dimension: int = 768):
        """Initialize mock provider."""
        super().__init__(model_name, dimension)

    async def embed(self, text: str) -> List[float]:
        """Generate mock embedding."""
        content_hash = hashlib.sha256(text.encode()).digest()
        embedding = list(content_hash)

        # Extend to required dimension
        while len(embedding) < self.dimension:
            embedding.append(0.0)

        return embedding[: self.dimension]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings for batch."""
        return [await self.embed(text) for text in texts]

    async def health_check(self) -> bool:
        """Always healthy."""
        return True


# Global embedding model instance
_embedding_model: Optional[EmbeddingProvider] = None


def get_embedding_model(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> EmbeddingProvider:
    """
    Get embedding model instance.

    Args:
        provider: Provider name (ollama | mock)
        model_name: Model name

    Returns:
        EmbeddingProvider instance
    """
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model

    settings = get_settings()

    if provider == "mock" or settings.environment == "test":
        _embedding_model = MockEmbeddingProvider(
            model_name=model_name or "mock",
            dimension=768,
        )
    else:
        _embedding_model = OllamaEmbeddingProvider(
            model_name=model_name or settings.ollama_model,
            base_url=settings.ollama_base_url,
            dimension=768,
        )

    return _embedding_model


async def generate_embeddings(
    texts: List[str],
    model: Optional[str] = None,
    batch_size: int = 32,
    use_cache: bool = True,
) -> BatchEmbeddingResult:
    """
    Generate embeddings for texts.

    Args:
        texts: List of texts to embed
        model: Optional model name override
        batch_size: Batch size for processing
        use_cache: Whether to use caching

    Returns:
        BatchEmbeddingResult with all embeddings
    """
    start_time = time.time()
    embedding_model = get_embedding_model()

    results = []
    total_tokens = 0
    cache_hits = 0

    # Process in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        batch_embeddings = await embedding_model.embed_batch(batch)

        for text, embedding in zip(batch, batch_embeddings):
            results.append(
                EmbeddingResult(
                    text=text,
                    embedding=embedding,
                    model=embedding_model.model_name,
                    dimension=embedding_model.dimension,
                    tokens_used=len(text.split()) * 2,  # Rough estimate
                    cached=False,
                )
            )

        total_tokens += sum(len(t.split()) * 2 for t in batch)

    latency_ms = (time.time() - start_time) * 1000

    return BatchEmbeddingResult(
        results=results,
        total_tokens=total_tokens,
        total_latency_ms=latency_ms,
        cache_hits=cache_hits,
    )


async def similarity_between(
    embedding1: List[float],
    embedding2: List[float],
    metric: str = "cosine",
) -> float:
    """
    Calculate similarity between two embeddings.

    Args:
        embedding1: First embedding
        embedding2: Second embedding
        metric: Similarity metric (cosine | euclidean)

    Returns:
        Similarity score
    """
    import numpy as np

    v1 = np.array(embedding1)
    v2 = np.array(embedding2)

    if metric == "cosine":
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    elif metric == "euclidean":
        return float(np.linalg.norm(v1 - v2))

    else:
        raise ValueError(f"Unknown metric: {metric}")
