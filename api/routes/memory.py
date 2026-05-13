"""
Memory and RAG API endpoints for Research OS.
"""

import asyncio
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.reflection import reflect_research, ReflectionAgent
from memory.rag_pipeline import (
    RAGPipeline,
    DocumentMetadata,
    ChunkingStrategy,
    RetrievalContext,
)
from memory.retrieval import MemoryRetriever, RetrievalQuery, RetrievalResult
from memory.vector_store import get_vector_store, VectorStoreProvider

logger = logging.getLogger(__name__)

# Memory endpoints are prefixed with /api/v1 by main.py
# Additional prefix /memory is applied here for proper route organization
router = APIRouter(prefix="/memory", tags=["Memory"])


# Request/Response Models
class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""

    file_name: str
    file_type: str
    title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    chunk_size: int = Field(default=1000, ge=100, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)


class MemorySearchRequest(BaseModel):
    """Request model for memory search."""

    query: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[str] = None
    limit: int = Field(default=10, ge=1, le=100)
    memory_types: Optional[List[str]] = None


class ReflectRequest(BaseModel):
    """Request model for reflection."""

    query: str
    findings: List[dict]
    sources: List[str]


# Document Upload
@router.post("/documents/upload")
async def upload_document(
    request: DocumentUploadRequest,
    content: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Upload and index a document.

    Returns task ID for tracking progress.
    """
    document_id = str(uuid.uuid4())

    # Queue for background processing
    from workers.tasks.memory_tasks import store_document

    task = store_document.delay(
        document_id=document_id,
        content=content,
        metadata={
            "file_name": request.file_name,
            "file_type": request.file_type,
            "title": request.title,
            "tags": request.tags,
        },
        session_id=request.session_id or document_id,
    )

    return {
        "document_id": document_id,
        "task_id": str(task.id),
        "status": "queued",
        "message": "Document queued for indexing",
    }


@router.get("/documents/{document_id}")
async def get_document(document_id: str) -> dict:
    """
    Get document information.
    """
    try:
        pipeline = RAGPipeline()
        info = await pipeline.get_document_info(document_id)

        if not info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        return info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> dict:
    """
    Delete a document and its embeddings.
    """
    try:
        pipeline = RAGPipeline()
        success = await pipeline.delete_document(document_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document",
            )

        return {"status": "deleted", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Memory Search
@router.post("/search")
async def search_memory(
    request: MemorySearchRequest,
) -> dict:
    """
    Search memory system.
    """
    try:
        retriever = MemoryRetriever()

        from memory.base import MemoryType

        types = None
        if request.memory_types:
            types = [MemoryType(t) for t in request.memory_types]

        query = RetrievalQuery(
            text=request.query,
            session_id=request.session_id,
            memory_types=types,
            limit=request.limit,
        )

        result = await retriever.retrieve(query)

        return {
            "query": request.query,
            "entries": [e.to_dict() for e in result.entries],
            "total_found": result.total_found,
            "retrieval_time_ms": result.retrieval_time_ms,
            "cache_hit": result.cache_hit,
        }

    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/session/{session_id}")
async def get_session_memory(session_id: str) -> dict:
    """
    Get all memory entries for a session.
    """
    try:
        retriever = MemoryRetriever()

        query = RetrievalQuery(
            text="",
            session_id=session_id,
            limit=100,
        )

        result = await retriever.retrieve(query)

        return {
            "session_id": session_id,
            "entries": [e.to_dict() for e in result.entries],
            "total_entries": len(result.entries),
        }

    except Exception as e:
        logger.error(f"Session memory retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/stats")
async def get_memory_stats() -> dict:
    """
    Get memory system statistics.
    """
    try:
        from memory.base import MemoryConfig
        from memory.episodic import EpisodicMemory
        from memory.semantic import SemanticMemory

        config = MemoryConfig()

        # Get counts from each memory type
        episodic = EpisodicMemory(config)
        semantic = SemanticMemory(config)

        async def _count():
            e = await episodic.count()
            s = await semantic.count()
            return e, s

        episodic_count, semantic_count = await _count()

        return {
            "episodic_entries": episodic_count,
            "semantic_entries": semantic_count,
            "total_entries": episodic_count + semantic_count,
        }

    except Exception as e:
        logger.error(f"Memory stats failed: {e}")
        return {
            "error": str(e),
            "episodic_entries": 0,
            "semantic_entries": 0,
        }


# RAG Retrieval
@router.post("/retrieve")
async def retrieve_context(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Retrieve context from RAG pipeline.
    """
    try:
        pipeline = RAGPipeline()
        context = await pipeline.retrieve(query=query, top_k=top_k)

        return {
            "query": query,
            "results": [r.to_dict() for r in context.results],
            "context": context.combined_context[:2000],
            "sources": context.sources,
            "scores": context.relevance_scores,
        }

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/retrieve/stream")
async def stream_retrieve_context(
    query: str,
    top_k: int = 5,
):
    """
    Stream RAG retrieval results.
    """
    try:
        pipeline = RAGPipeline()

        async def generate():
            async for chunk in pipeline.stream_retrieve(query=query, top_k=top_k):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/plain",
        )

    except Exception as e:
        logger.error(f"RAG streaming failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Reflection Endpoints
@router.post("/reflect")
async def run_reflection(request: ReflectRequest) -> dict:
    """
    Run reflection analysis on research.
    """
    try:
        result = await reflect_research(
            query=request.query,
            findings=request.findings,
            sources=request.sources,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Reflection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/compress")
async def compress_memory(
    session_id: str,
    entries: List[dict],
    target_tokens: int = 2000,
) -> dict:
    """
    Compress memory entries.
    """
    try:
        from workers.tasks.memory_tasks import compress_memory

        task = compress_memory.delay(
            session_id=session_id,
            entries=entries,
            target_tokens=target_tokens,
        )

        return {
            "task_id": str(task.id),
            "status": "queued",
            "message": "Memory compression queued",
        }

    except Exception as e:
        logger.error(f"Memory compression failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Vector Store Management
@router.get("/vector-store/health")
async def vector_store_health() -> dict:
    """
    Check vector store health.
    """
    try:
        vector_store = get_vector_store()
        is_healthy = await vector_store.health_check()

        return {
            "healthy": is_healthy,
            "provider": vector_store.config.provider,
        }

    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
        }


@router.get("/vector-store/collections")
async def list_collections() -> dict:
    """
    List vector store collections.
    """
    try:
        vector_store = get_vector_store()
        await vector_store.initialize()

        collections = ["research_findings", "knowledge_base", "reports"]
        collection_info = []

        for name in collections:
            try:
                info = await vector_store.get_collection_info(name)
                collection_info.append(info)
            except Exception:
                pass

        return {
            "collections": collection_info,
        }

    except Exception as e:
        logger.error(f"Collection listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# Memory Worker Status
@router.get("/worker/status")
async def memory_worker_status() -> dict:
    """
    Get memory worker status.
    """
    try:
        from workers.tasks.memory_tasks import memory_health_check

        task = memory_health_check.delay()
        result = task.get(timeout=10)

        return result

    except Exception as e:
        logger.error(f"Worker status check failed: {e}")
        return {
            "overall": "error",
            "error": str(e),
        }


# Research Retry
@router.post("/research/retry")
async def retry_research(
    session_id: str,
    query: str,
    missing_topics: List[str],
) -> dict:
    """
    Retry research for missing topics.
    """
    try:
        # Create new tasks for missing topics
        tasks = []

        for i, topic in enumerate(missing_topics):
            tasks.append(
                {
                    "id": f"retry_{i}_{uuid.uuid4().hex[:8]}",
                    "description": f"Research: {topic}",
                    "type": "web_search",
                    "priority": 8 - i,
                    "target_topics": [topic],
                }
            )

        return {
            "session_id": session_id,
            "query": query,
            "new_tasks": tasks,
            "status": "generated",
        }

    except Exception as e:
        logger.error(f"Research retry failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
