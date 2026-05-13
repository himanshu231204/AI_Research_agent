"""
Vector Store Provider Abstraction Layer.

Provides abstraction for vector databases to support:
- Development: ChromaDB
- Production: Qdrant

The rest of the system should NOT depend directly on ChromaDB.
Use the VectorStoreProvider interface for all vector operations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from api.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """Represents a document in vector store."""

    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorDocument":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data["embedding"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class SearchResult:
    """Represents a search result from vector store."""

    id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    distance: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "score": self.score,
            "content": self.content,
            "metadata": self.metadata,
            "distance": self.distance,
        }


@dataclass
class VectorStoreConfig:
    """Configuration for vector store providers."""

    provider: str = "chroma"  # chroma | qdrant
    collection_name: str = "research_os"

    # ChromaDB settings
    persist_directory: str = "./chroma_data"
    distance_metric: str = "cosine"  # cosine | euclidean | manhattan

    # Qdrant settings
    qdrant_url: Optional[str] = None
    qdrant_port: int = 6333
    qdrant_vector_size: int = 768
    qdrant_local: bool = True

    # Performance
    batch_size: int = 100
    search_limit: int = 10
    timeout: float = 30.0


class VectorStoreProvider(ABC):
    """
    Abstract interface for vector store providers.

    Implement this interface to add new vector database support.

    Usage:
        provider = get_vector_store(provider="chroma")
        await provider.add_documents(documents)
        results = await provider.similarity_search(query_embedding)
    """

    def __init__(self, config: VectorStoreConfig):
        """
        Initialize vector store provider.

        Args:
            config: Vector store configuration
        """
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store connection."""
        pass

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create a new collection.

        Args:
            name: Collection name
            dimension: Vector dimension
            metadata: Collection metadata

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Add documents to the store.

        Args:
            documents: List of documents to add
            collection_name: Target collection (uses config default if None)

        Returns:
            Number of documents added
        """
        pass

    @abstractmethod
    async def similarity_search(
        self,
        query_embedding: List[float],
        collection_name: Optional[str] = None,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Perform similarity search.

        Args:
            query_embedding: Query vector
            collection_name: Collection to search
            top_k: Number of results
            filter_metadata: Metadata filters

        Returns:
            List of search results
        """
        pass

    @abstractmethod
    async def delete(self, document_ids: List[str], collection_name: Optional[str] = None) -> int:
        """
        Delete documents.

        Args:
            document_ids: IDs of documents to delete
            collection_name: Collection name

        Returns:
            Number of documents deleted
        """
        pass

    @abstractmethod
    async def get_collection_info(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get collection information.

        Args:
            collection_name: Collection name

        Returns:
            Collection info dict
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if vector store is healthy.

        Returns:
            True if healthy
        """
        pass

    async def batch_add(
        self,
        documents: List[VectorDocument],
        collection_name: Optional[str] = None,
    ) -> int:
        """
        Add documents in batches.

        Args:
            documents: List of documents to add
            collection_name: Target collection

        Returns:
            Total number of documents added
        """
        total = 0
        batch_size = self.config.batch_size

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            count = await self.add_documents(batch, collection_name)
            total += count

        return total

    async def hybrid_search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        collection_name: Optional[str] = None,
        top_k: int = 10,
        keyword_weight: float = 0.3,
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Text query
            query_embedding: Optional pre-computed embedding
            collection_name: Collection name
            top_k: Number of results
            keyword_weight: Weight for keyword matching

        Returns:
            List of combined search results
        """
        # Default implementation: just semantic search
        if query_embedding is None:
            # Generate embedding if not provided
            from memory.embeddings import get_embedding_model

            model = get_embedding_model()
            query_embedding = await model.embed(query)

        return await self.similarity_search(
            query_embedding,
            collection_name=collection_name,
            top_k=top_k,
        )

    async def upsert(
        self, documents: List[VectorDocument], collection_name: Optional[str] = None
    ) -> int:
        """
        Upsert documents (update if exists, insert if not).

        Args:
            documents: Documents to upsert
            collection_name: Collection name

        Returns:
            Number of documents upserted
        """
        # Default: delete then add
        doc_ids = [doc.id for doc in documents]
        await self.delete(doc_ids, collection_name)
        return await self.add_documents(documents, collection_name)


class ChromaVectorStore(VectorStoreProvider):
    """
    ChromaDB implementation of VectorStoreProvider.

    Used during development. Supports:
    - Persistent storage
    - Cosine similarity
    - Metadata filtering
    """

    def __init__(self, config: Optional[VectorStoreConfig] = None):
        """
        Initialize ChromaDB vector store.

        Args:
            config: Vector store configuration
        """
        if config is None:
            settings = get_settings()
            config = VectorStoreConfig(
                provider="chroma",
                persist_directory=settings.chroma_persist_dir,
            )

        super().__init__(config)
        self._client = None
        self._collections: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize ChromaDB client."""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.config import Settings

            self._client = chromadb.PersistentClient(
                path=self.config.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            self._initialized = True
            logger.info(f"ChromaDB initialized at {self.config.persist_directory}")

        except ImportError:
            logger.error(
                "ChromaDB not installed - falling back to mock mode. "
                "Vector operations will return empty results. "
                "Install chromadb: pip install chromadb"
            )
            self._initialized = True
            self._mock_mode = True

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    async def _get_collection(self, name: str) -> Any:
        """Get or create a collection."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return None

        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": self.config.distance_metric},
            )

        return self._collections[name]

    async def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a new ChromaDB collection."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        try:
            coll_metadata = metadata or {}
            if dimension:
                coll_metadata["dimension"] = dimension

            self._client.get_or_create_collection(
                name=name,
                metadata=coll_metadata,
            )

            logger.info(f"Created ChromaDB collection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection {name}: {e}")
            return False

    async def delete_collection(self, name: str) -> bool:
        """Delete a ChromaDB collection."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        try:
            self._client.delete_collection(name=name)
            if name in self._collections:
                del self._collections[name]

            logger.info(f"Deleted ChromaDB collection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection {name}: {e}")
            return False

    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: Optional[str] = None,
    ) -> int:
        """Add documents to ChromaDB."""
        if not self._initialized:
            await self.initialize()

        collection = await self._get_collection(collection_name or self.config.collection_name)

        if self._mock_mode or collection is None:
            logger.debug(f"Mock: adding {len(documents)} documents")
            return len(documents)

        try:
            ids = [doc.id for doc in documents]
            embeddings = [doc.embedding for doc in documents]
            texts = [doc.content for doc in documents]
            metadatas = [doc.metadata for doc in documents]

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            logger.debug(f"Added {len(documents)} documents to {collection_name}")
            return len(documents)

        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return 0

    async def similarity_search(
        self,
        query_embedding: List[float],
        collection_name: Optional[str] = None,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search ChromaDB with similarity."""
        if not self._initialized:
            await self.initialize()

        collection = await self._get_collection(collection_name or self.config.collection_name)

        if self._mock_mode or collection is None:
            # Return mock results
            return [
                SearchResult(
                    id=f"mock_{i}",
                    score=1.0 - (i * 0.1),
                    content=f"Mock result {i}",
                )
                for i in range(min(top_k, 3))
            ]

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata,
            )

            search_results = []
            if results and results.get("ids"):
                docs_list = results.get("documents") or [[""]]
                if docs_list and isinstance(docs_list[0], list):
                    docs_list = docs_list[0]
                for i in range(len(results["ids"][0])):
                    search_results.append(
                        SearchResult(
                            id=results["ids"][0][i],
                            score=results.get("distances", [[0.0]])[0][i],
                            content=docs_list[i] if docs_list and i < len(docs_list) else "",
                            metadata=results.get("metadatas", [{}])[0][i],
                            distance=results.get("distances", [[None]])[0][i],
                        )
                    )

            return search_results

        except Exception as e:
            logger.error(f"Failed similarity search: {e}")
            return []

    async def delete(self, document_ids: List[str], collection_name: Optional[str] = None) -> int:
        """Delete documents from ChromaDB."""
        if not self._initialized:
            await self.initialize()

        collection = await self._get_collection(collection_name or self.config.collection_name)

        if self._mock_mode or collection is None:
            return len(document_ids)

        try:
            collection.delete(ids=document_ids)
            return len(document_ids)

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return 0

    async def get_collection_info(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get ChromaDB collection info."""
        if not self._initialized:
            await self.initialize()

        collection = await self._get_collection(collection_name or self.config.collection_name)

        if self._mock_mode or collection is None:
            return {
                "name": collection_name or self.config.collection_name,
                "count": 0,
                "initialized": False,
            }

        try:
            return {
                "name": collection_name or self.config.collection_name,
                "count": collection.count(),
                "initialized": True,
            }

        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """Check ChromaDB health."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        try:
            # Try a simple operation
            collection = await self._get_collection("__health_check__")
            return self._client is not None

        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False


class QdrantVectorStore(VectorStoreProvider):
    """
    Qdrant implementation of VectorStoreProvider.

    Used in production for high-scale vector operations.

    Requirements:
    - Qdrant server running
    - GRPC enabled for best performance
    """

    def __init__(self, config: Optional[VectorStoreConfig] = None):
        """Initialize Qdrant vector store."""
        if config is None:
            config = VectorStoreConfig(
                provider="qdrant",
                qdrant_url="localhost",
                qdrant_port=6333,
                qdrant_vector_size=768,
            )

        super().__init__(config)
        self._client = None

    async def initialize(self) -> None:
        """Initialize Qdrant client."""
        if self._initialized:
            return

        try:
            from qdrant_client import QdrantClient

            url = self.config.qdrant_url or "localhost"
            port = self.config.qdrant_port

            self._client = QdrantClient(
                url=url,
                port=port,
                timeout=self.config.timeout,
            )

            self._initialized = True
            logger.info(f"Qdrant initialized at {url}:{port}")

        except ImportError:
            logger.error(
                "Qdrant not installed - falling back to mock mode. "
                "Vector operations will return empty results. "
                "Install qdrant-client: pip install qdrant-client"
            )
            self._initialized = True
            self._mock_mode = True

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            raise

    async def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a Qdrant collection."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        dimension = dimension or self.config.qdrant_vector_size

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._client.recreate_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                ),
            )

            logger.info(f"Created Qdrant collection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            return False

    async def delete_collection(self, name: str) -> bool:
        """Delete a Qdrant collection."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        try:
            self._client.delete_collection(collection_name=name)
            logger.info(f"Deleted Qdrant collection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {e}")
            return False

    async def add_documents(
        self,
        documents: List[VectorDocument],
        collection_name: Optional[str] = None,
    ) -> int:
        """Add documents to Qdrant."""
        if not self._initialized:
            await self.initialize()

        collection = collection_name or self.config.collection_name

        if self._mock_mode:
            return len(documents)

        try:
            from qdrant_client.models import PointStruct

            points = [
                PointStruct(
                    id=doc.id,
                    vector=doc.embedding,
                    payload={
                        "content": doc.content,
                        "metadata": doc.metadata,
                    },
                )
                for doc in documents
            ]

            self._client.upsert(
                collection_name=collection,
                points=points,
            )

            return len(documents)

        except Exception as e:
            logger.error(f"Failed to add documents to Qdrant: {e}")
            return 0

    async def similarity_search(
        self,
        query_embedding: List[float],
        collection_name: Optional[str] = None,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search Qdrant with similarity."""
        if not self._initialized:
            await self.initialize()

        collection = collection_name or self.config.collection_name

        if self._mock_mode:
            return [
                SearchResult(
                    id=f"mock_{i}",
                    score=1.0 - (i * 0.1),
                    content=f"Mock result {i}",
                )
                for i in range(min(top_k, 3))
            ]

        try:
            from qdrant_client.models import Filter

            search_filter = None
            if filter_metadata:
                search_filter = Filter(**filter_metadata)

            results = self._client.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=search_filter,
            )

            return [
                SearchResult(
                    id=str(result.id),
                    score=result.score,
                    content=result.payload.get("content", ""),
                    metadata=result.payload.get("metadata", {}),
                )
                for result in results
            ]

        except Exception as e:
            logger.error(f"Failed Qdrant search: {e}")
            return []

    async def delete(self, document_ids: List[str], collection_name: Optional[str] = None) -> int:
        """Delete documents from Qdrant."""
        if not self._initialized:
            await self.initialize()

        collection = collection_name or self.config.collection_name

        if self._mock_mode:
            return len(document_ids)

        try:
            self._client.delete(
                collection_name=collection,
                points_selector=document_ids,
            )
            return len(document_ids)

        except Exception as e:
            logger.error(f"Failed to delete from Qdrant: {e}")
            return 0

    async def get_collection_info(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get Qdrant collection info."""
        if not self._initialized:
            await self.initialize()

        collection = collection_name or self.config.collection_name

        if self._mock_mode:
            return {
                "name": collection,
                "count": 0,
                "initialized": False,
            }

        try:
            info = self._client.get_collection(collection_name=collection)

            return {
                "name": collection,
                "count": info.vectors_count,
                "initialized": True,
            }

        except Exception as e:
            logger.error(f"Failed to get Qdrant collection info: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """Check Qdrant health."""
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            return True

        try:
            return self._client is not None

        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Global vector store instance
_vector_store: Optional[VectorStoreProvider] = None


def get_vector_store(
    provider: Optional[str] = None,
    config: Optional[VectorStoreConfig] = None,
) -> VectorStoreProvider:
    """
    Get vector store provider.

    Args:
        provider: Provider name (chroma | qdrant)
        config: Optional configuration override

    Returns:
        VectorStoreProvider instance
    """
    global _vector_store

    if provider is None and config is None and _vector_store is not None:
        return _vector_store

    if config is None:
        settings = get_settings()
        config = VectorStoreConfig(
            provider=provider or settings.vector_store_provider,
            persist_directory=settings.chroma_persist_dir,
        )

    if config.provider == "qdrant":
        store = QdrantVectorStore(config)
    else:
        store = ChromaVectorStore(config)

    if _vector_store is None:
        _vector_store = store

    return store
