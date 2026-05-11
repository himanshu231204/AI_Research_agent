"""
Base classes and interfaces for the memory subsystem.

Defines:
- Memory types (episodic, semantic, compressed)
- Memory entry schema
- Base memory interface
- Configuration
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Generic, TypeVar

T = TypeVar("T")


class MemoryType(Enum):
    """Types of memory in the system."""

    EPISODIC = "episodic"  # Session history, workflows
    SEMANTIC = "semantic"  # Embeddings, extracted knowledge
    COMPRESSED = "compressed"  # Summarized context


@dataclass
class MemoryConfig:
    """Configuration for memory subsystem."""

    # Vector store settings
    vector_store_provider: str = "chroma"  # chroma | qdrant
    vector_store_url: Optional[str] = None
    vector_store_persist_dir: str = "./chroma_data"

    # Embedding settings
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_batch_size: int = 32

    # Memory settings
    max_episodic_entries: int = 1000
    max_semantic_entries: int = 10000
    compression_threshold: int = 50  # Compress after N entries
    summarization_batch_size: int = 10

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # TTL settings
    session_ttl: int = 86400 * 7  # 7 days
    cache_ttl: int = 3600  # 1 hour

    # Performance
    async_workers: int = 4
    batch_timeout: float = 30.0


@dataclass
class MemoryEntry:
    """
    Represents a single memory entry.

    Attributes:
        id: Unique identifier
        type: Type of memory (episodic, semantic, compressed)
        content: The memory content
        metadata: Additional metadata
        embedding: Vector embedding (for semantic memory)
        session_id: Associated session ID
        user_id: Associated user ID
        created_at: Creation timestamp
        updated_at: Last update timestamp
        access_count: Number of times accessed
        importance_score: Relevance score for retrieval
        tags: Categorization tags
    """

    id: str
    type: MemoryType
    content: str

    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    session_id: Optional[str] = None
    user_id: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    importance_score: float = 1.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
            "embedding": self.embedding,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "importance_score": self.importance_score,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        type_value = data.get("type", "episodic")
        if isinstance(type_value, str):
            memory_type = MemoryType(type_value)
        else:
            memory_type = type_value

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.utcnow()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.utcnow()

        return cls(
            id=data["id"],
            type=memory_type,
            content=data["content"],
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            created_at=created_at,
            updated_at=updated_at,
            access_count=data.get("access_count", 0),
            importance_score=data.get("importance_score", 1.0),
            tags=data.get("tags", []),
        )


class MemoryBase(ABC, Generic[T]):
    """
    Abstract base class for memory systems.

    Defines the interface that all memory implementations must follow.
    """

    def __init__(self, config: MemoryConfig):
        """
        Initialize memory base.

        Args:
            config: Memory configuration
        """
        self.config = config

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> bool:
        """
        Store a memory entry.

        Args:
            entry: Memory entry to store

        Returns:
            True if stored successfully
        """
        pass

    @abstractmethod
    async def retrieve(
        self,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """
        Retrieve memory entries.

        Args:
            query: Text query for semantic search
            session_id: Filter by session
            limit: Maximum number of entries
            memory_type: Filter by memory type

        Returns:
            List of matching memory entries
        """
        pass

    @abstractmethod
    async def update(self, entry: MemoryEntry) -> bool:
        """
        Update a memory entry.

        Args:
            entry: Updated memory entry

        Returns:
            True if updated successfully
        """
        pass

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            entry_id: ID of entry to delete

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """
        Count memory entries.

        Args:
            memory_type: Filter by type

        Returns:
            Number of entries
        """
        pass

    @abstractmethod
    async def clear(self, session_id: Optional[str] = None) -> int:
        """
        Clear memory entries.

        Args:
            session_id: Clear entries for specific session (None = all)

        Returns:
            Number of entries cleared
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if memory system is healthy.

        Returns:
            True if healthy
        """
        pass


class MemoryStats:
    """Statistics about memory usage."""

    def __init__(self):
        self.total_entries: int = 0
        self.episodic_count: int = 0
        self.semantic_count: int = 0
        self.compressed_count: int = 0
        self.total_tokens: int = 0
        self.last_compression: Optional[datetime] = None
        self.cache_hit_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_entries": self.total_entries,
            "episodic_count": self.episodic_count,
            "semantic_count": self.semantic_count,
            "compressed_count": self.compressed_count,
            "total_tokens": self.total_tokens,
            "last_compression": (
                self.last_compression.isoformat() if self.last_compression else None
            ),
            "cache_hit_rate": self.cache_hit_rate,
        }
