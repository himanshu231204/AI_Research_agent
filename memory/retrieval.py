"""
Memory Retrieval System for Research OS.

Provides semantic retrieval of:
- Past sessions
- Prior findings
- Reusable research
- Contextual knowledge

Supports:
- Similarity search
- Metadata filtering
- Hybrid retrieval
- Reranking
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory.base import MemoryEntry, MemoryType
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.compression import CompressedMemory
from memory.embeddings import get_embedding_model

logger = logging.getLogger(__name__)


@dataclass
class RetrievalQuery:
    """Query specification for memory retrieval."""

    text: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    memory_types: Optional[List[MemoryType]] = None
    tags: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 10
    threshold: float = 0.0  # Relevance threshold


@dataclass
class RetrievalResult:
    """Result from memory retrieval."""

    entries: List[MemoryEntry]
    total_found: int
    retrieval_time_ms: float
    scores: List[float]
    cache_hit: bool = False


class MemoryRetriever:
    """
    Semantic retrieval engine for memory system.

    Provides unified access to episodic, semantic, and compressed memory.
    """

    def __init__(
        self,
        episodic_memory: Optional[EpisodicMemory] = None,
        semantic_memory: Optional[SemanticMemory] = None,
        compressed_memory: Optional[CompressedMemory] = None,
    ):
        """
        Initialize memory retriever.

        Args:
            episodic_memory: Episodic memory instance
            semantic_memory: Semantic memory instance
            compressed_memory: Compressed memory instance
        """
        from memory.base import MemoryConfig

        self.config = MemoryConfig()
        self.episodic = episodic_memory or EpisodicMemory(self.config)
        self.semantic = semantic_memory or SemanticMemory(self.config)
        self.compressed = compressed_memory or CompressedMemory(self.config)

        self._embedding_model = None
        self._cache: Dict[str, List[MemoryEntry]] = {}

    async def _get_embedding_model(self):
        """Get embedding model lazily."""
        if self._embedding_model is None:
            self._embedding_model = get_embedding_model()
        return self._embedding_model

    async def retrieve(
        self,
        query: RetrievalQuery,
    ) -> RetrievalResult:
        """
        Retrieve memory entries matching query.

        Args:
            query: Retrieval query specification

        Returns:
            RetrievalResult with matching entries
        """
        import time

        start_time = time.time()

        # Check cache
        cache_key = self._make_cache_key(query)
        if cache_key in self._cache:
            cached_entries = self._cache[cache_key]
            return RetrievalResult(
                entries=cached_entries[: query.limit],
                total_found=len(cached_entries),
                retrieval_time_ms=(time.time() - start_time) * 1000,
                scores=[1.0] * len(cached_entries[: query.limit]),
                cache_hit=True,
            )

        # Determine which memory types to search
        memory_types = query.memory_types or [
            MemoryType.EPISODIC,
            MemoryType.SEMANTIC,
            MemoryType.COMPRESSED,
        ]

        all_entries = []

        # Search each memory type
        if MemoryType.EPISODIC in memory_types:
            entries = await self._search_episodic(query)
            all_entries.extend(entries)

        if MemoryType.SEMANTIC in memory_types:
            entries = await self._search_semantic(query)
            all_entries.extend(entries)

        if MemoryType.COMPRESSED in memory_types:
            entries = await self._search_compressed(query)
            all_entries.extend(entries)

        # Score and rank results
        scored_entries = await self._score_and_rank(all_entries, query)

        # Apply threshold
        filtered_entries = [
            (entry, score) for entry, score in scored_entries if score >= query.threshold
        ][: query.limit]

        entries = [e for e, _ in filtered_entries]
        scores = [s for _, s in filtered_entries]

        # Cache results
        self._cache[cache_key] = entries

        return RetrievalResult(
            entries=entries,
            total_found=len(all_entries),
            retrieval_time_ms=(time.time() - start_time) * 1000,
            scores=scores,
            cache_hit=False,
        )

    async def _search_episodic(
        self,
        query: RetrievalQuery,
    ) -> List[MemoryEntry]:
        """Search episodic memory."""
        try:
            # For episodic, filter by session_id
            entries = await self.episodic.retrieve(
                session_id=query.session_id,
                limit=query.limit,
            )

            # Filter by user if specified
            if query.user_id:
                entries = [e for e in entries if e.user_id == query.user_id]

            # Filter by date range
            if query.date_from or query.date_to:
                entries = self._filter_by_date(
                    entries,
                    query.date_from,
                    query.date_to,
                )

            return entries

        except Exception as e:
            logger.error(f"Episodic search failed: {e}")
            return []

    async def _search_semantic(
        self,
        query: RetrievalQuery,
    ) -> List[MemoryEntry]:
        """Search semantic memory."""
        try:
            # Semantic search uses text query
            entries = await self.semantic.retrieve(
                query=query.text,
                session_id=query.session_id,
                limit=query.limit,
            )

            # Filter by tags if specified
            if query.tags:
                entries = [e for e in entries if any(tag in e.tags for tag in query.tags)]

            return entries

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def _search_compressed(
        self,
        query: RetrievalQuery,
    ) -> List[MemoryEntry]:
        """Search compressed memory."""
        try:
            entries = await self.compressed.retrieve(
                session_id=query.session_id,
                limit=query.limit,
            )

            return entries

        except Exception as e:
            logger.error(f"Compressed search failed: {e}")
            return []

    async def _score_and_rank(
        self,
        entries: List[MemoryEntry],
        query: RetrievalQuery,
    ) -> List[tuple[MemoryEntry, float]]:
        """
        Score and rank entries by relevance.

        Args:
            entries: Entries to score
            query: Query for scoring

        Returns:
            List of (entry, score) tuples sorted by score
        """
        if not entries:
            return []

        # Get query embedding
        model = await self._get_embedding_model()
        query_embedding = await model.embed(query.text)

        scored = []

        for entry in entries:
            # Base score from importance
            score = entry.importance_score * 0.3

            # Boost for session match
            if entry.session_id == query.session_id:
                score += 0.2

            # Boost for user match
            if entry.user_id == query.user_id:
                score += 0.1

            # Boost for tag match
            if query.tags:
                tag_matches = sum(1 for tag in query.tags if tag in entry.tags)
                score += min(0.2, tag_matches * 0.05)

            # Boost for recency
            days_old = (datetime.utcnow() - entry.updated_at).days
            if days_old < 7:
                score += 0.1
            elif days_old < 30:
                score += 0.05

            # Boost for access count
            if entry.access_count > 0:
                score += min(0.1, entry.access_count * 0.01)

            # Calculate semantic similarity if embedding available
            if entry.embedding:
                try:
                    similarity = await self._calculate_similarity(
                        query_embedding,
                        entry.embedding,
                    )
                    score += similarity * 0.3
                except Exception:
                    pass

            score = min(1.0, max(0.0, score))
            scored.append((entry, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored

    async def _calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """Calculate cosine similarity between embeddings."""
        import numpy as np

        v1 = np.array(embedding1)
        v2 = np.array(embedding2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def _filter_by_date(
        self,
        entries: List[MemoryEntry],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
    ) -> List[MemoryEntry]:
        """Filter entries by date range."""
        filtered = []

        for entry in entries:
            if date_from and entry.created_at < date_from:
                continue
            if date_to and entry.created_at > date_to:
                continue
            filtered.append(entry)

        return filtered

    def _make_cache_key(self, query: RetrievalQuery) -> str:
        """Create cache key from query."""
        import hashlib

        key_parts = [
            query.text,
            query.session_id or "",
            query.user_id or "",
            str(query.limit),
        ]

        key = "|".join(key_parts)
        return hashlib.md5(key.encode()).hexdigest()

    async def clear_cache(self) -> None:
        """Clear retrieval cache."""
        self._cache.clear()


class KnowledgeReuseEngine:
    """
    Reuse prior research findings to accelerate workflows.

    The engine:
    - Finds relevant prior research
    - Checks for duplicate work
    - Accelerates repeated workflows
    """

    def __init__(self, retriever: Optional[MemoryRetriever] = None):
        """Initialize knowledge reuse engine."""
        self.retriever = retriever or MemoryRetriever()

    async def find_relevant_prior_research(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find prior research relevant to current query.

        Args:
            query: Current research query
            session_id: Current session to exclude
            limit: Maximum results

        Returns:
            List of relevant prior research
        """
        retrieval_query = RetrievalQuery(
            text=query,
            session_id=session_id,
            memory_types=[MemoryType.SEMANTIC, MemoryType.COMPRESSED],
            limit=limit,
            threshold=0.3,
        )

        result = await self.retriever.retrieve(retrieval_query)

        prior_research = []
        for entry in result.entries:
            prior_research.append(
                {
                    "id": entry.id,
                    "content": entry.content,
                    "session_id": entry.session_id,
                    "relevance": result.scores[result.entries.index(entry)],
                    "metadata": entry.metadata,
                }
            )

        return prior_research

    async def check_duplicate_work(
        self,
        query: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if similar research has been done.

        Args:
            query: Research query to check

        Returns:
            Prior research if found, None otherwise
        """
        retrieval_query = RetrievalQuery(
            text=query,
            memory_types=[MemoryType.SEMANTIC],
            limit=1,
            threshold=0.8,  # High threshold for duplicates
        )

        result = await self.retriever.retrieve(retrieval_query)

        if result.entries:
            entry = result.entries[0]
            return {
                "is_duplicate": True,
                "prior_session_id": entry.session_id,
                "content": entry.content,
                "relevance": result.scores[0],
            }

        return None

    async def build_reuse_context(
        self,
        query: str,
        session_id: Optional[str] = None,
        max_context: int = 2000,
    ) -> str:
        """
        Build context from prior research for reuse.

        Args:
            query: Current query
            session_id: Current session
            max_context: Maximum context length

        Returns:
            Context string from prior research
        """
        prior_research = await self.find_relevant_prior_research(
            query=query,
            session_id=session_id,
        )

        if not prior_research:
            return ""

        context_parts = []
        total_length = 0

        for research in prior_research:
            content = research["content"]
            if total_length + len(content) > max_context:
                break

            context_parts.append(content)
            total_length += len(content)

        return "\n\n---\n\n".join(context_parts)


# Convenience function
async def retrieve_memory(
    query: str,
    session_id: Optional[str] = None,
    limit: int = 10,
) -> RetrievalResult:
    """
    Quick memory retrieval.

    Args:
        query: Search query
        session_id: Optional session filter
        limit: Maximum results

    Returns:
        RetrievalResult
    """
    retriever = MemoryRetriever()
    retrieval_query = RetrievalQuery(
        text=query,
        session_id=session_id,
        limit=limit,
    )
    return await retriever.retrieve(retrieval_query)
