"""
Semantic Memory System for Research OS.

Stores:
- Embeddings
- Extracted knowledge
- Reusable insights

Uses vector store for semantic search.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory.base import (
    MemoryBase,
    MemoryConfig,
    MemoryEntry,
    MemoryType,
)
from memory.vector_store import (
    VectorStoreProvider,
    VectorDocument,
    SearchResult,
    get_vector_store,
)
from memory.embeddings import get_embedding_model, generate_embeddings

logger = logging.getLogger(__name__)


class SemanticMemory(MemoryBase[MemoryEntry]):
    """
    Semantic memory for storing embeddings and knowledge.

    Uses vector store for semantic search and retrieval.
    """

    def __init__(self, config: MemoryConfig):
        """
        Initialize semantic memory.

        Args:
            config: Memory configuration
        """
        super().__init__(config)
        self._vector_store: Optional[VectorStoreProvider] = None
        self._initialized = False

    async def _get_vector_store(self) -> VectorStoreProvider:
        """Get vector store lazily."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
            await self._vector_store.initialize()
        return self._vector_store

    async def initialize(self) -> None:
        """Initialize semantic memory collections."""
        if self._initialized:
            return

        try:
            vector_store = await self._get_vector_store()

            # Create collections for different memory types
            collections = [
                ("research_findings", "Research findings and insights"),
                ("knowledge_base", "Extracted knowledge and facts"),
                ("reports", "Research reports and summaries"),
            ]

            for collection_name, description in collections:
                await vector_store.create_collection(
                    name=collection_name,
                    metadata={"description": description},
                )

            self._initialized = True
            logger.info("Semantic memory initialized")

        except Exception as e:
            logger.error(f"Failed to initialize semantic memory: {e}")
            raise

    async def store(self, entry: MemoryEntry) -> bool:
        """
        Store a semantic memory entry with embedding.

        Args:
            entry: Memory entry to store

        Returns:
            True if stored successfully
        """
        if entry.type != MemoryType.SEMANTIC:
            entry.type = MemoryType.SEMANTIC

        try:
            vector_store = await self._get_vector_store()
            embedding_model = get_embedding_model()

            # Generate embedding
            embedding = await embedding_model.embed(entry.content)

            # Determine collection based on metadata
            collection_name = entry.metadata.get(
                "collection",
                "research_findings",
            )

            # Create document
            document = VectorDocument(
                id=entry.id,
                content=entry.content,
                embedding=embedding,
                metadata={
                    "session_id": entry.session_id,
                    "user_id": entry.user_id,
                    "tags": entry.tags,
                    "importance": entry.importance_score,
                    "metadata": entry.metadata,
                },
            )

            # Store in vector store
            await vector_store.add_documents([document], collection_name)

            logger.debug(f"Stored semantic memory: {entry.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store semantic memory: {e}")
            return False

    async def retrieve(
        self,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """
        Retrieve semantic memory via similarity search.

        Args:
            query: Text query for semantic search
            session_id: Filter by session
            limit: Maximum entries
            memory_type: Filter by type

        Returns:
            List of relevant memory entries
        """
        if not query:
            return []

        try:
            vector_store = await self._get_vector_store()
            embedding_model = get_embedding_model()

            # Generate query embedding
            query_embedding = await embedding_model.embed(query)

            # Search in relevant collections
            all_results: List[MemoryEntry] = []

            collections = ["research_findings", "knowledge_base", "reports"]
            filter_metadata = {"session_id": session_id} if session_id else None

            for collection in collections:
                results = await vector_store.similarity_search(
                    query_embedding,
                    collection_name=collection,
                    top_k=limit,
                    filter_metadata=filter_metadata,
                )

                for result in results:
                    entry = MemoryEntry(
                        id=result.id,
                        type=MemoryType.SEMANTIC,
                        content=result.content,
                        metadata=result.metadata,
                        embedding=[],  # Don't store embeddings in results
                        session_id=result.metadata.get("session_id"),
                        importance_score=result.metadata.get("importance", 1.0),
                    )
                    all_results.append(entry)

            # Sort by relevance score
            all_results.sort(
                key=lambda x: x.importance_score,
                reverse=True,
            )

            return all_results[:limit]

        except Exception as e:
            logger.error(f"Failed to retrieve semantic memory: {e}")
            return []

    async def update(self, entry: MemoryEntry) -> bool:
        """
        Update semantic memory (delete and re-add).

        Args:
            entry: Updated entry

        Returns:
            True if updated successfully
        """
        await self.delete(entry.id)
        return await self.store(entry)

    async def delete(self, entry_id: str) -> bool:
        """
        Delete semantic memory entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted successfully
        """
        try:
            vector_store = await self._get_vector_store()

            # Try all collections
            collections = ["research_findings", "knowledge_base", "reports"]
            for collection in collections:
                await vector_store.delete([entry_id], collection)

            logger.debug(f"Deleted semantic memory: {entry_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete semantic memory: {e}")
            return False

    async def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count semantic memory entries."""
        try:
            vector_store = await self._get_vector_store()
            total = 0

            collections = ["research_findings", "knowledge_base", "reports"]
            for collection in collections:
                info = await vector_store.get_collection_info(collection)
                total += info.get("count", 0)

            return total

        except Exception as e:
            logger.error(f"Failed to count semantic memory: {e}")
            return 0

    async def clear(self, session_id: Optional[str] = None) -> int:
        """
        Clear semantic memory.

        Args:
            session_id: Clear entries for specific session

        Returns:
            Number of entries cleared
        """
        if session_id is None:
            # Clear all - recreate collections
            try:
                vector_store = await self._get_vector_store()
                collections = ["research_findings", "knowledge_base", "reports"]

                for collection in collections:
                    await vector_store.delete_collection(collection)
                    await vector_store.create_collection(collection)

                self._initialized = False
                return 1

            except Exception as e:
                logger.error(f"Failed to clear semantic memory: {e}")
                return 0

        # For specific session, would need to track and delete
        return 0

    async def health_check(self) -> bool:
        """Check vector store health."""
        try:
            vector_store = await self._get_vector_store()
            return await vector_store.health_check()

        except Exception as e:
            logger.error(f"Semantic memory health check failed: {e}")
            return False

    # Additional semantic-specific methods

    async def store_findings(
        self,
        findings: List[Dict[str, Any]],
        session_id: str,
    ) -> int:
        """
        Store multiple research findings.

        Args:
            findings: List of finding dicts
            session_id: Associated session

        Returns:
            Number of findings stored
        """
        entries = []
        embedding_model = get_embedding_model()

        for i, finding in enumerate(findings):
            entry = MemoryEntry(
                id=f"{session_id}:finding:{i}",
                type=MemoryType.SEMANTIC,
                content=finding.get("summary", ""),
                metadata={
                    "collection": "research_findings",
                    "finding_type": finding.get("type", "unknown"),
                    "source": finding.get("source", ""),
                    "session_id": session_id,
                },
                session_id=session_id,
                importance_score=finding.get("importance", 1.0),
            )
            entries.append(entry)

        # Store all in parallel
        results = await asyncio.gather(*[self.store(e) for e in entries])
        return sum(1 for r in results if r)

    async def store_report(
        self,
        report: str,
        session_id: str,
        query: str,
    ) -> bool:
        """
        Store a research report.

        Args:
            report: Report content
            session_id: Session ID
            query: Original query

        Returns:
            True if stored
        """
        entry = MemoryEntry(
            id=f"{session_id}:report",
            type=MemoryType.SEMANTIC,
            content=report,
            metadata={
                "collection": "reports",
                "query": query,
                "session_id": session_id,
                "report_type": "research",
            },
            session_id=session_id,
            importance_score=0.9,
        )

        return await self.store(entry)

    async def find_similar_topics(
        self,
        topic: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find similar topics from memory.

        Args:
            topic: Topic to search
            limit: Maximum results

        Returns:
            List of similar topic entries
        """
        results = await self.retrieve(
            query=topic,
            limit=limit,
        )

        return [
            {
                "id": r.id,
                "content": r.content,
                "session_id": r.session_id,
                "relevance": r.importance_score,
            }
            for r in results
        ]

    async def get_knowledge_context(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """
        Get contextual knowledge for a query.

        Args:
            query: Query to get context for
            session_id: Optional session filter
            limit: Maximum context entries

        Returns:
            Combined context string
        """
        entries = await self.retrieve(
            query=query,
            session_id=session_id,
            limit=limit,
        )

        if not entries:
            return ""

        context_parts = []
        for entry in entries:
            if entry.content:
                context_parts.append(entry.content)

        return "\n\n---\n\n".join(context_parts)
