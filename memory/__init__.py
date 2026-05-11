"""
Memory subsystem for Research OS.

Provides long-term memory with:
- Episodic memory: session history and workflows
- Semantic memory: embeddings and knowledge
- Compressed memory: summarized context
- Vector store: semantic search
- Summarization: context compression
- RAG pipeline: document processing and retrieval
- Memory retrieval: semantic search engine

Architecture:
- Abstraction layer for vector DB (ChromaDB for dev, Qdrant for production)
- Async operations throughout
- Redis for session cache
- PostgreSQL for persistent storage
"""

# Note: Import directly from submodules to avoid circular imports
# Example: from memory.base import MemoryEntry
# instead of: from memory import MemoryEntry
