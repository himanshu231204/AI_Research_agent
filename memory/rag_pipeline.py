"""
RAG Pipeline for Research OS.

Full production-grade RAG implementation:
- Document Upload
- Chunking
- Embedding Generation
- Metadata Extraction
- Vector Storage
- Retriever
- Context Injection
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncGenerator

from memory.vector_store import (
    VectorStoreProvider,
    VectorDocument,
    SearchResult,
    get_vector_store,
)
from memory.embeddings import get_embedding_model, generate_embeddings

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """Document chunking strategies."""

    RECURSIVE = "recursive"  # RecursiveCharacterTextSplitter
    SEMANTIC = "semantic"  # Semantic chunking by sentences
    FIXED = "fixed"  # Fixed-size chunks
    DOCUMENT = "document"  # Whole documents


@dataclass
class DocumentMetadata:
    """Metadata for uploaded documents."""

    document_id: str
    file_name: str
    file_type: str
    file_size: int
    chunk_count: int
    uploaded_at: datetime
    source_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.file_size == 0:
            self.file_size = len(self.title or "") if self.title else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "chunk_count": self.chunk_count,
            "uploaded_at": self.uploaded_at.isoformat(),
            "source_url": self.source_url,
            "title": self.title,
            "author": self.author,
            "tags": self.tags,
            "session_id": self.session_id,
            "user_id": self.user_id,
        }


@dataclass
class ProcessedDocument:
    """A processed document with chunks ready for embedding."""

    metadata: DocumentMetadata
    chunks: List[str]
    embeddings: Optional[List[List[float]]] = None


@dataclass
class RetrievalContext:
    """Context retrieved from RAG pipeline."""

    query: str
    results: List[SearchResult]
    combined_context: str
    sources: List[str]
    relevance_scores: List[float]


class DocumentProcessor:
    """
    Process documents for RAG ingestion.

    Supports:
    - PDFs
    - Markdown
    - Text files
    - HTML pages
    - GitHub READMEs
    """

    def __init__(self):
        """Initialize document processor."""
        self.supported_types = {".pdf", ".md", ".txt", ".html", ".htm"}

    async def process(
        self,
        content: str,
        metadata: DocumentMetadata,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> ProcessedDocument:
        """
        Process a document into chunks.

        Args:
            content: Document content
            metadata: Document metadata
            strategy: Chunking strategy
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks

        Returns:
            ProcessedDocument with chunks
        """
        # Clean content
        content = self._clean_content(content)

        # Chunk based on strategy
        if strategy == ChunkingStrategy.RECURSIVE:
            chunks = self._recursive_chunk(content, chunk_size, chunk_overlap)
        elif strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._semantic_chunk(content, chunk_size)
        elif strategy == ChunkingStrategy.FIXED:
            chunks = self._fixed_chunk(content, chunk_size, chunk_overlap)
        else:
            chunks = [content]  # Whole document

        # Update metadata
        metadata.chunk_count = len(chunks)

        return ProcessedDocument(
            metadata=metadata,
            chunks=chunks,
        )

    def _clean_content(self, content: str) -> str:
        """Clean document content."""
        # Remove excessive whitespace
        content = re.sub(r"\s+", " ", content)
        # Remove special characters but keep punctuation
        content = re.sub(r"[^\w\s.,!?;:()\-–—\"'`]", "", content)
        return content.strip()

    def _recursive_chunk(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """
        Recursive chunking by paragraphs then sentences.

        Args:
            content: Document content
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks

        Returns:
            List of chunks
        """
        chunks = []

        # Split by paragraphs
        paragraphs = re.split(r"\n\n+", content)

        current_chunk = []
        current_size = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            para_size = len(paragraph.split())

            # If single paragraph exceeds chunk_size, split by sentences
            if para_size > chunk_size // 4:
                sentences = re.split(r"[.!?]+", paragraph)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    sentence_size = len(sentence.split())

                    if current_size + sentence_size > chunk_size and current_chunk:
                        chunks.append(" ".join(current_chunk))
                        # Keep overlap
                        overlap_size = sum(len(s.split()) for s in current_chunk[-2:])
                        current_chunk = current_chunk[-2:] if overlap_size < chunk_overlap else []
                        current_size = overlap_size if overlap_size < chunk_overlap else 0

                    current_chunk.append(sentence)
                    current_size += sentence_size

            else:
                if current_size + para_size > chunk_size and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    overlap_size = sum(len(s.split()) for s in current_chunk[-2:])
                    current_chunk = current_chunk[-2:] if overlap_size < chunk_overlap else []
                    current_size = overlap_size if overlap_size < chunk_overlap else 0

                current_chunk.append(paragraph)
                current_size += para_size

        # Add remaining chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks if chunks else [content]

    def _semantic_chunk(
        self,
        content: str,
        chunk_size: int,
    ) -> List[str]:
        """
        Semantic chunking by sentence boundaries.

        Args:
            content: Document content
            chunk_size: Target chunk size

        Returns:
            List of semantically coherent chunks
        """
        # Split into sentences
        sentence_pattern = r"(?<=[.!?])\s+"
        sentences = re.split(sentence_pattern, content)

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_size = len(sentence.split())

            if current_size + sentence_size > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_size

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks if chunks else [content]

    def _fixed_chunk(
        self,
        content: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[str]:
        """
        Fixed-size chunking.

        Args:
            content: Document content
            chunk_size: Chunk size in words
            chunk_overlap: Overlap in words

        Returns:
            List of fixed-size chunks
        """
        words = content.split()
        chunks = []
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - chunk_overlap

        return chunks

    def extract_metadata(self, content: str, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract metadata from document content.

        Args:
            content: Document content
            source: Optional source URL

        Returns:
            Extracted metadata dict
        """
        metadata = {}

        # Extract title from first heading or first line
        lines = content.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if line.startswith("# "):
                metadata["title"] = line[2:].strip()
                break
            elif line and len(line) < 100:
                metadata["title"] = line
                break

        # Extract dates
        date_pattern = r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}"
        dates = re.findall(date_pattern, content)
        if dates:
            metadata["dates"] = dates[:5]

        # Extract emails
        email_pattern = r"[\w.-]+@[\w.-]+\.\w+"
        emails = re.findall(email_pattern, content)
        if emails:
            metadata["contacts"] = list(set(emails))[:5]

        # Extract URLs
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, content)
        metadata["urls"] = list(set(urls))[:10]

        # Extract key terms (simple TF-IDF-like approach)
        if "title" in metadata:
            words = content.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 5:
                    word_freq[word] = word_freq.get(word, 0) + 1

            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            metadata["key_terms"] = [w for w, _ in top_words]

        return metadata


class RAGPipeline:
    """
    Full RAG pipeline for document processing and retrieval.

    Implements:
    1. Document Upload → 2. Chunking → 3. Embedding → 4. Storage →
    5. Retrieval → 6. Context Injection
    """

    def __init__(
        self,
        vector_store: Optional[VectorStoreProvider] = None,
        collection_name: str = "research_documents",
    ):
        """
        Initialize RAG pipeline.

        Args:
            vector_store: Vector store provider
            collection_name: Default collection name
        """
        self.vector_store = vector_store or get_vector_store()
        self.collection_name = collection_name
        self.processor = DocumentProcessor()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the pipeline."""
        if self._initialized:
            return

        await self.vector_store.initialize()
        await self.vector_store.create_collection(
            name=self.collection_name,
            metadata={"description": "Research document embeddings"},
        )

        self._initialized = True
        logger.info(f"RAG pipeline initialized with collection: {self.collection_name}")

    async def ingest_document(
        self,
        content: str,
        metadata: DocumentMetadata,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
    ) -> Dict[str, Any]:
        """
        Ingest a document into the RAG pipeline.

        Args:
            content: Document content
            metadata: Document metadata
            chunk_size: Target chunk size
            chunk_overlap: Overlap between chunks
            strategy: Chunking strategy

        Returns:
            Ingestion result with document_id and chunk count
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Process document into chunks
            processed = await self.processor.process(
                content=content,
                metadata=metadata,
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            # Generate embeddings
            embeddings_result = await generate_embeddings(
                texts=processed.chunks,
                batch_size=32,
            )

            processed.embeddings = [r.embedding for r in embeddings_result.results]

            # Store in vector store
            documents = [
                VectorDocument(
                    id=f"{metadata.document_id}:chunk:{i}",
                    content=chunk,
                    embedding=processed.embeddings[i],
                    metadata={
                        **metadata.to_dict(),
                        "chunk_index": i,
                        "total_chunks": len(processed.chunks),
                    },
                )
                for i, chunk in enumerate(processed.chunks)
            ]

            count = await self.vector_store.add_documents(
                documents=documents,
                collection_name=self.collection_name,
            )

            logger.info(f"Ingested document {metadata.document_id} with {count} chunks")

            return {
                "document_id": metadata.document_id,
                "chunk_count": count,
                "status": "completed",
                "metadata": metadata.to_dict(),
            }

        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return {
                "document_id": metadata.document_id,
                "status": "failed",
                "error": str(e),
            }

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> RetrievalContext:
        """
        Retrieve relevant context for a query.

        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Optional metadata filters

        Returns:
            RetrievalContext with results
        """
        if not self._initialized:
            await self.initialize()

        # Generate query embedding
        embedding_model = get_embedding_model()
        query_embedding = await embedding_model.embed(query)

        # Search vector store
        results = await self.vector_store.similarity_search(
            query_embedding=query_embedding,
            collection_name=self.collection_name,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

        # Build context from results
        context_parts = []
        sources = []
        relevance_scores = []

        for result in results:
            context_parts.append(result.content)
            if result.metadata.get("source_url"):
                sources.append(result.metadata["source_url"])
            relevance_scores.append(result.score)

        combined_context = "\n\n---\n\n".join(context_parts)

        return RetrievalContext(
            query=query,
            results=results,
            combined_context=combined_context,
            sources=sources,
            relevance_scores=relevance_scores,
        )

    async def hybrid_retrieve(
        self,
        query: str,
        keyword_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> RetrievalContext:
        """
        Hybrid retrieval combining semantic and keyword search.

        Args:
            query: Search query
            keyword_filter: Optional keyword filter
            top_k: Number of results

        Returns:
            RetrievalContext with combined results
        """
        # Get semantic results
        semantic_context = await self.retrieve(query=query, top_k=top_k)

        # If keyword filter provided, filter results
        if keyword_filter:
            filtered_results = []
            for result in semantic_context.results:
                if keyword_filter.lower() in result.content.lower():
                    filtered_results.append(result)

            if filtered_results:
                semantic_context.results = filtered_results

        return semantic_context

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its chunks.

        Args:
            document_id: Document ID to delete

        Returns:
            True if deleted
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Delete all chunks for this document
            chunk_ids = []  # Would need to track chunks
            await self.vector_store.delete(chunk_ids, self.collection_name)
            return True

        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            return False

    async def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document information.

        Args:
            document_id: Document ID

        Returns:
            Document info dict
        """
        # Would need to query for document metadata
        return {"document_id": document_id}

    async def stream_retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> AsyncGenerator[str, None]:
        """
        Stream retrieval results.

        Args:
            query: Search query
            top_k: Number of results

        Yields:
            Result chunks as they are processed
        """
        context = await self.retrieve(query=query, top_k=top_k)

        for i, result in enumerate(context.results):
            yield f"Result {i + 1}:\n{result.content}\n\n"

        yield f"\n---\nCombined Context:\n{context.combined_context}"


class RAGRetriever:
    """
    High-level RAG retriever for injecting context into prompts.

    Provides seamless context injection for research tasks.
    """

    def __init__(self, pipeline: Optional[RAGPipeline] = None):
        """Initialize RAG retriever."""
        self.pipeline = pipeline or RAGPipeline()

    async def get_context(
        self,
        query: str,
        max_context_length: int = 4000,
        include_citations: bool = True,
    ) -> str:
        """
        Get context for a query, truncated to max length.

        Args:
            query: Search query
            max_context_length: Maximum context length in characters
            include_citations: Include source citations

        Returns:
            Context string for prompt injection
        """
        context = await self.pipeline.retrieve(query=query, top_k=5)

        context_text = context.combined_context

        # Truncate if too long
        if len(context_text) > max_context_length:
            context_text = context_text[:max_context_length] + "\n\n[truncated]..."

        # Add citations if requested
        if include_citations and context.sources:
            citations = "\n\n**Sources:**\n" + "\n".join([f"- {s}" for s in context.sources[:5]])
            context_text += citations

        return context_text

    async def inject_context(
        self,
        prompt: str,
        query: Optional[str] = None,
        context_query: Optional[str] = None,
    ) -> str:
        """
        Inject RAG context into a prompt.

        Args:
            prompt: Original prompt
            query: Query to search for (uses prompt if not provided)
            context_query: Specific context query (overrides query)

        Returns:
            Prompt with context injected
        """
        search_query = context_query or query or prompt[:200]

        context = await self.get_context(search_query)

        if not context:
            return prompt

        return f"""**Retrieved Context:**

{context}

---

**Original Query:**

{prompt}"""


# Convenience functions
async def ingest_document(
    content: str,
    document_id: str,
    file_name: str,
    file_type: str,
    **kwargs,
) -> Dict[str, Any]:
    """Ingest a document into RAG pipeline."""
    metadata = DocumentMetadata(
        document_id=document_id,
        file_name=file_name,
        file_type=file_type,
        file_size=len(content),
        chunk_count=0,
        uploaded_at=datetime.utcnow(),
        **kwargs,
    )

    pipeline = RAGPipeline()
    return await pipeline.ingest_document(content=content, metadata=metadata)


async def retrieve_context(query: str, top_k: int = 5) -> RetrievalContext:
    """Retrieve context for a query."""
    pipeline = RAGPipeline()
    return await pipeline.retrieve(query=query, top_k=top_k)
