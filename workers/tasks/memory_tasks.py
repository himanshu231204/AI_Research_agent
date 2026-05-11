"""
Memory and RAG worker tasks for Celery.

Contains distributed tasks for:
- Memory compression
- Embedding generation
- Document indexing
- Memory retrieval
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class MemoryWorkerTask(Task):
    """Base class for memory worker tasks."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 3


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.compress",
    queue="rag",
    max_retries=3,
)
def compress_memory(
    self,
    session_id: str,
    entries: List[Dict[str, Any]],
    target_tokens: int = 2000,
) -> Dict[str, Any]:
    """
    Compress memory entries using summarization.

    Args:
        session_id: Session identifier
        entries: Memory entries to compress
        target_tokens: Target token budget

    Returns:
        Compression result
    """
    logger.info(f"[{session_id}] Compressing {len(entries)} memory entries")

    try:
        from memory.base import MemoryEntry, MemoryType
        from memory.compression import CompressedMemory, CompressionResult
        from memory.base import MemoryConfig

        config = MemoryConfig()
        compressor = CompressedMemory(config)

        # Convert dicts to MemoryEntry objects
        memory_entries = []
        for entry_dict in entries:
            entry = MemoryEntry.from_dict(entry_dict)
            memory_entries.append(entry)

        # Compress
        async def _compress():
            return await compressor.compress_entries(memory_entries, target_tokens)

        result = asyncio.run(_compress())

        return {
            "session_id": session_id,
            "status": "completed",
            "original_entries": result.original_entries,
            "compressed_entries": result.compressed_entries,
            "compression_ratio": result.compression_ratio,
            "summary": result.summary[:500],
            "compressed_at": result.compressed_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"[{session_id}] Memory compression failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.embed_batch",
    queue="rag",
    max_retries=3,
)
def embed_batch(
    self,
    texts: List[str],
    session_id: str,
    model: str = "nomic-embed-text",
) -> Dict[str, Any]:
    """
    Generate embeddings for text batch.

    Args:
        texts: Texts to embed
        session_id: Session identifier
        model: Embedding model

    Returns:
        Embedding results
    """
    logger.info(f"[{session_id}] Embedding batch of {len(texts)} texts")

    try:
        from memory.embeddings import generate_embeddings

        async def _embed():
            return await generate_embeddings(texts, model=model, batch_size=32)

        result = asyncio.run(_embed())

        return {
            "session_id": session_id,
            "status": "completed",
            "embeddings_count": len(result.results),
            "total_tokens": result.total_tokens,
            "total_latency_ms": result.total_latency_ms,
            "cache_hits": result.cache_hits,
        }

    except Exception as e:
        logger.error(f"[{session_id}] Batch embedding failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.store_document",
    queue="rag",
    max_retries=3,
)
def store_document(
    self,
    document_id: str,
    content: str,
    metadata: Dict[str, Any],
    session_id: str,
) -> Dict[str, Any]:
    """
    Store a document in RAG pipeline.

    Args:
        document_id: Document identifier
        content: Document content
        metadata: Document metadata
        session_id: Session identifier

    Returns:
        Storage result
    """
    logger.info(f"[{session_id}] Storing document: {document_id}")

    try:
        from datetime import datetime
        from memory.rag_pipeline import (
            DocumentMetadata,
            RAGPipeline,
            ChunkingStrategy,
        )

        doc_metadata = DocumentMetadata(
            document_id=document_id,
            file_name=metadata.get("file_name", "unknown"),
            file_type=metadata.get("file_type", "txt"),
            file_size=len(content),
            chunk_count=0,
            uploaded_at=datetime.utcnow(),
            source_url=metadata.get("source_url"),
            title=metadata.get("title"),
            tags=metadata.get("tags", []),
            session_id=session_id,
        )

        async def _store():
            pipeline = RAGPipeline()
            return await pipeline.ingest_document(
                content=content,
                metadata=doc_metadata,
                chunk_size=1000,
                chunk_overlap=200,
                strategy=ChunkingStrategy.RECURSIVE,
            )

        result = asyncio.run(_store())

        return {
            "document_id": document_id,
            "session_id": session_id,
            "status": result.get("status", "completed"),
            "chunk_count": result.get("chunk_count", 0),
        }

    except Exception as e:
        logger.error(f"[{session_id}] Document storage failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.retrieve",
    queue="rag",
    max_retries=2,
)
def retrieve_memory(
    self,
    query: str,
    session_id: str,
    limit: int = 5,
    memory_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Retrieve from memory system.

    Args:
        query: Search query
        session_id: Session identifier
        limit: Maximum results
        memory_types: Types of memory to search

    Returns:
        Retrieval results
    """
    logger.info(f"[{session_id}] Retrieving memory for query: {query[:50]}...")

    try:
        from memory.retrieval import (
            MemoryRetriever,
            RetrievalQuery,
            MemoryType,
        )

        types = None
        if memory_types:
            types = [MemoryType(t) for t in memory_types]

        async def _retrieve():
            retriever = MemoryRetriever()
            return await retriever.retrieve(
                RetrievalQuery(
                    text=query,
                    session_id=session_id,
                    memory_types=types,
                    limit=limit,
                )
            )

        result = asyncio.run(_retrieve())

        return {
            "session_id": session_id,
            "query": query,
            "status": "completed",
            "entries_count": len(result.entries),
            "total_found": result.total_found,
            "retrieval_time_ms": result.retrieval_time_ms,
            "cache_hit": result.cache_hit,
            "entries": [e.to_dict() for e in result.entries],
        }

    except Exception as e:
        logger.error(f"[{session_id}] Memory retrieval failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.summarize",
    queue="rag",
    max_retries=3,
)
def summarize_content(
    self,
    content: str,
    session_id: str,
    style: str = "concise",
) -> Dict[str, Any]:
    """
    Summarize content.

    Args:
        content: Content to summarize
        session_id: Session identifier
        style: Summarization style

    Returns:
        Summary result
    """
    logger.info(f"[{session_id}] Summarizing content")

    try:
        from memory.summarization import Summarizer

        async def _summarize():
            summarizer = Summarizer()
            return await summarizer.summarize(content, style=style)

        summary = asyncio.run(_summarize())

        return {
            "session_id": session_id,
            "status": "completed",
            "summary": summary,
            "style": style,
            "original_length": len(content),
            "summary_length": len(summary),
        }

    except Exception as e:
        logger.error(f"[{session_id}] Summarization failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.reflection.analyze",
    queue="reflection",
    max_retries=2,
)
def run_reflection_analysis(
    self,
    findings: List[Dict[str, Any]],
    sources: List[str],
    query: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Run reflection analysis on findings.

    Args:
        findings: Research findings
        sources: Source citations
        query: Original research query
        session_id: Session identifier

    Returns:
        Reflection analysis result
    """
    logger.info(f"[{session_id}] Running reflection analysis")

    try:
        from agents.reflection import reflect_research

        async def _reflect():
            return await reflect_research(query, findings, sources)

        result = asyncio.run(_reflect())

        return {
            "session_id": session_id,
            "status": "completed",
            "reflection": result.to_dict(),
            "requires_additional_research": result.requires_additional_research,
            "confidence_score": result.confidence_score,
            "hallucination_risk": result.hallucination_risk,
            "missing_topics": result.missing_topics,
            "new_tasks": result.new_tasks,
        }

    except Exception as e:
        logger.error(f"[{session_id}] Reflection analysis failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.rolling_compress",
    queue="rag",
    max_retries=2,
)
def rolling_memory_compress(
    self,
    entries: List[Dict[str, Any]],
    session_id: str,
    window_size: int = 10,
    overlap: int = 2,
) -> Dict[str, Any]:
    """
    Apply rolling window compression to memory.

    Args:
        entries: Memory entries to compress
        session_id: Session identifier
        window_size: Size of each window
        overlap: Overlap between windows

    Returns:
        Compression results
    """
    logger.info(f"[{session_id}] Rolling compression with window={window_size}")

    try:
        from memory.base import MemoryEntry, MemoryType, MemoryConfig
        from memory.compression import CompressedMemory

        config = MemoryConfig()
        compressor = CompressedMemory(config)

        memory_entries = [MemoryEntry.from_dict(e) for e in entries]

        async def _compress():
            return await compressor.rolling_window_compress(
                memory_entries,
                window_size=window_size,
                overlap=overlap,
            )

        compressed = asyncio.run(_compress())

        return {
            "session_id": session_id,
            "status": "completed",
            "original_count": len(entries),
            "compressed_count": len(compressed),
            "entries": [e.to_dict() for e in compressed],
        }

    except Exception as e:
        logger.error(f"[{session_id}] Rolling compression failed: {e}")
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    base=MemoryWorkerTask,
    name="memory.health_check",
    queue="rag",
    max_retries=1,
)
def memory_health_check() -> Dict[str, Any]:
    """
    Check health of memory system components.

    Returns:
        Health status for each component
    """
    logger.info("Running memory health check")

    status = {
        "overall": "healthy",
        "components": {},
    }

    # Check episodic memory
    try:
        from memory.base import MemoryConfig
        from memory.episodic import EpisodicMemory

        config = MemoryConfig()
        episodic = EpisodicMemory(config)

        async def _check():
            return await episodic.health_check()

        is_healthy = asyncio.run(_check())
        status["components"]["episodic"] = "healthy" if is_healthy else "unhealthy"

    except Exception as e:
        status["components"]["episodic"] = f"error: {str(e)}"
        status["overall"] = "degraded"

    # Check semantic memory
    try:
        from memory.base import MemoryConfig
        from memory.semantic import SemanticMemory

        config = MemoryConfig()
        semantic = SemanticMemory(config)

        async def _check():
            return await semantic.health_check()

        is_healthy = asyncio.run(_check())
        status["components"]["semantic"] = "healthy" if is_healthy else "unhealthy"

    except Exception as e:
        status["components"]["semantic"] = f"error: {str(e)}"
        status["overall"] = "degraded"

    # Check vector store
    try:
        from memory.vector_store import get_vector_store

        vector_store = get_vector_store()

        async def _check():
            return await vector_store.health_check()

        is_healthy = asyncio.run(_check())
        status["components"]["vector_store"] = "healthy" if is_healthy else "unhealthy"

    except Exception as e:
        status["components"]["vector_store"] = f"error: {str(e)}"
        status["overall"] = "degraded"

    return status
