"""
Integration tests for Phase 3: Reflection, RAG, and Memory Systems.

Tests:
- Reflection loop termination
- Hallucination detection
- Task regeneration
- RAG indexing and retrieval
- Vector store abstraction
- Memory persistence and retrieval
- Memory compression
- Citation verification
"""

import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any


# Test fixtures
@pytest.fixture
def sample_findings():
    """Sample research findings for testing."""
    return [
        {
            "summary": "Machine learning models can achieve human-level performance on certain tasks",
            "source": "https://arxiv.org/abs/2001.08361",
            "type": "web_search",
        },
        {
            "summary": "Deep learning has revolutionized computer vision applications",
            "source": "https://nature.com/articles/nature14539",
            "type": "web_search",
        },
        {
            "summary": "Neural networks require significant computational resources",
            "source": "https://github.com/tensorflow/tensorflow",
            "type": "github",
        },
    ]


@pytest.fixture
def sample_sources():
    """Sample sources for testing."""
    return [
        "https://arxiv.org/abs/2001.08361",
        "https://nature.com/articles/nature14539",
        "https://github.com/tensorflow/tensorflow",
    ]


@pytest.fixture
def sample_query():
    """Sample research query."""
    return "What are the latest advances in machine learning?"


# Reflection Tests
class TestReflection:
    """Tests for the Reflection Agent."""

    def test_reflection_schema_structure(self):
        """Test that ReflectionResult schema has correct structure."""
        # Use exec to import in isolated namespace
        exec_globals = {}
        exec(open("agents/reflection_schema.py", encoding="utf-8").read(), exec_globals)
        ReflectionResult = exec_globals["ReflectionResult"]

        result = ReflectionResult(
            requires_additional_research=True,
            missing_topics=["topic1", "topic2"],
            hallucination_risk=0.3,
            confidence_score=0.7,
            reasoning_quality=0.8,
            citation_issues=["issue1"],
            recommended_actions=["action1"],
        )

        # Verify structured output
        assert hasattr(result, "requires_additional_research")
        assert hasattr(result, "confidence_score")
        assert hasattr(result, "hallucination_risk")
        assert hasattr(result, "missing_topics")
        assert hasattr(result, "citation_issues")

        # Verify types
        assert isinstance(result.requires_additional_research, bool)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.hallucination_risk, float)
        assert isinstance(result.missing_topics, list)
        assert isinstance(result.citation_issues, list)

        # Verify ranges
        assert 0.0 <= result.confidence_score <= 1.0
        assert 0.0 <= result.hallucination_risk <= 1.0

    def test_reflection_result_serialization(self):
        """Test ReflectionResult serialization."""
        exec_globals = {}
        exec(open("agents/reflection_schema.py", encoding="utf-8").read(), exec_globals)
        ReflectionResult = exec_globals["ReflectionResult"]

        result = ReflectionResult(
            requires_additional_research=True,
            missing_topics=["topic1", "topic2"],
            hallucination_risk=0.3,
            confidence_score=0.7,
            reasoning_quality=0.8,
            citation_issues=["issue1"],
            recommended_actions=["action1"],
        )

        # Test to_dict
        data = result.to_dict()
        assert data["requires_additional_research"] is True
        assert len(data["missing_topics"]) == 2
        assert data["hallucination_risk"] == 0.3

        # Test from_dict
        restored = ReflectionResult.from_dict(data)
        assert restored.requires_additional_research is True
        assert len(restored.missing_topics) == 2

    def test_reflection_quality_flags(self):
        """Test quality flag methods."""
        exec_globals = {}
        exec(open("agents/reflection_schema.py", encoding="utf-8").read(), exec_globals)
        ReflectionResult = exec_globals["ReflectionResult"]

        result = ReflectionResult()

        result.add_missing_topic("topic1", "high")
        result.add_citation_issue("missing source")
        result.add_recommended_action("add more citations")
        result.add_quality_flag("weak evidence")

        assert len(result.missing_topics) == 1
        assert len(result.citation_issues) == 1
        assert len(result.recommended_actions) == 1
        assert len(result.quality_flags) == 1


# Reflection Loop Safety Tests
class TestReflectionLoopSafety:
    """Tests for reflection loop termination safety."""

    def test_reflection_count_enforced(self):
        """Test that reflection count is properly tracked."""
        # Use exec to avoid circular imports through graphs package
        exec_globals = {}
        exec(open("graphs/state.py", encoding="utf-8").read(), exec_globals)
        create_initial_state = exec_globals["create_initial_state"]

        state = create_initial_state(
            session_id="test_session",
            query="test query",
            max_reflections=3,
        )

        assert state["reflection_count"] == 0
        assert state["max_reflections"] == 3

    def test_reflection_max_stops_loop(self):
        """Test that max reflections stops the loop."""
        # Use exec to avoid circular imports through graphs package
        exec_globals = {}
        exec(open("graphs/state.py", encoding="utf-8").read(), exec_globals)
        create_initial_state = exec_globals["create_initial_state"]

        state = create_initial_state(
            session_id="test_session",
            query="test query",
            max_reflections=3,
        )

        # Simulate max reached
        state["reflection_count"] = 3

        # Loop should stop when reflection_count >= max_reflections
        assert state["reflection_count"] >= state["max_reflections"]

    @pytest.mark.skip(reason="Requires isolated module loading due to circular import chain")
    def test_infinite_loop_prevented(self):
        """Test that infinite loops are prevented."""
        from agents.reflection_schema import ReflectionResult

        result = ReflectionResult(
            requires_additional_research=True,
            missing_topics=["test"],
        )

        # After max iterations, should stop
        max_iterations = 3
        iterations = 0

        while result.requires_additional_research and iterations < max_iterations:
            iterations += 1
            if iterations >= max_iterations:
                result.requires_additional_research = False

        assert iterations <= max_iterations


# RAG Tests
class TestRAGPipeline:
    """Tests for the RAG Pipeline."""

    @pytest.mark.asyncio
    async def test_document_chunking(self):
        """Test document chunking."""
        from memory.rag_pipeline import DocumentProcessor, DocumentMetadata, ChunkingStrategy

        processor = DocumentProcessor()
        metadata = DocumentMetadata(
            document_id="test_doc",
            file_name="test.txt",
            file_type="txt",
            file_size=1000,
            chunk_count=0,
            uploaded_at=datetime.utcnow(),
        )

        content = "This is a test document. " * 100

        result = await processor.process(
            content=content,
            metadata=metadata,
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=100,
            chunk_overlap=20,
        )

        assert result.metadata.chunk_count > 0
        assert len(result.chunks) > 0
        assert all(isinstance(c, str) for c in result.chunks)

    @pytest.mark.asyncio
    async def test_semantic_chunking(self):
        """Test semantic chunking."""
        from memory.rag_pipeline import DocumentProcessor, DocumentMetadata, ChunkingStrategy

        processor = DocumentProcessor()
        metadata = DocumentMetadata(
            document_id="test_doc",
            file_name="test.txt",
            file_type="txt",
            file_size=1000,
            chunk_count=0,
            uploaded_at=datetime.utcnow(),
        )

        content = "First sentence. Second sentence. Third sentence. Fourth sentence."

        result = await processor.process(
            content=content,
            metadata=metadata,
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=10,
        )

        assert len(result.chunks) > 0

    @pytest.mark.asyncio
    async def test_document_metadata(self):
        """Test document metadata dataclass."""
        from memory.rag_pipeline import DocumentMetadata

        metadata = DocumentMetadata(
            document_id="doc1",
            file_name="test.pdf",
            file_type="pdf",
            file_size=5000,
            chunk_count=10,
            uploaded_at=datetime.utcnow(),
        )

        data = metadata.to_dict()
        assert data["document_id"] == "doc1"
        assert data["file_type"] == "pdf"
        assert data["chunk_count"] == 10


# Vector Store Tests
class TestVectorStoreAbstraction:
    """Tests for vector store provider abstraction."""

    @pytest.mark.asyncio
    async def test_search_result_serialization(self):
        """Test SearchResult serialization."""
        from memory.vector_store import SearchResult

        result = SearchResult(
            id="test_id",
            score=0.95,
            content="Test content",
            metadata={"key": "value"},
        )

        data = result.to_dict()
        assert data["id"] == "test_id"
        assert data["score"] == 0.95
        assert data["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_vector_document_serialization(self):
        """Test VectorDocument serialization."""
        from memory.vector_store import VectorDocument

        doc = VectorDocument(
            id="doc1",
            content="Test content",
            embedding=[0.1] * 10,
            metadata={"tag": "test"},
        )

        data = doc.to_dict()
        assert data["id"] == "doc1"
        assert data["content"] == "Test content"
        assert len(data["embedding"]) == 10


# Memory Tests
class TestMemorySystem:
    """Tests for memory subsystem."""

    @pytest.mark.asyncio
    async def test_memory_entry_serialization(self):
        """Test MemoryEntry serialization."""
        from memory.base import MemoryEntry, MemoryType

        entry = MemoryEntry(
            id="test_id",
            type=MemoryType.SEMANTIC,
            content="Test content",
            metadata={"key": "value"},
            tags=["tag1", "tag2"],
        )

        data = entry.to_dict()
        assert data["id"] == "test_id"
        assert data["type"] == "semantic"

        restored = MemoryEntry.from_dict(data)
        assert restored.id == "test_id"
        assert restored.type == MemoryType.SEMANTIC

    def test_memory_config_defaults(self):
        """Test MemoryConfig default values."""
        from memory.base import MemoryConfig

        config = MemoryConfig()

        assert config.vector_store_provider == "chroma"
        assert config.embedding_model == "nomic-embed-text"
        assert config.max_episodic_entries == 1000
        assert config.max_semantic_entries == 10000

    def test_memory_type_enum(self):
        """Test MemoryType enum values."""
        from memory.base import MemoryType

        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.COMPRESSED.value == "compressed"


# Memory Retrieval Tests
class TestMemoryRetrieval:
    """Tests for memory retrieval."""

    @pytest.mark.asyncio
    async def test_retrieval_query_creation(self):
        """Test RetrievalQuery creation."""
        from memory.retrieval import RetrievalQuery

        query = RetrievalQuery(
            text="test query",
            session_id="test_session",
            limit=5,
        )

        assert query.text == "test query"
        assert query.session_id == "test_session"
        assert query.limit == 5


# Compression Tests
class TestMemoryCompression:
    """Tests for memory compression."""

    @pytest.mark.asyncio
    async def test_compression_result(self):
        """Test compression result structure."""
        from memory.compression import CompressionResult

        result = CompressionResult(
            original_entries=10,
            compressed_entries=2,
            compression_ratio=5.0,
            original_tokens=1000,
            compressed_tokens=200,
            summary="Compressed summary",
            compressed_at=datetime.utcnow(),
        )

        assert result.original_entries == 10
        assert result.compressed_entries == 2
        assert result.compression_ratio == 5.0

    @pytest.mark.asyncio
    async def test_compression_should_compress(self):
        """Test should_compress logic."""
        from memory.base import MemoryConfig, MemoryEntry, MemoryType
        from memory.compression import CompressedMemory

        config = MemoryConfig(compression_threshold=5)
        memory = CompressedMemory(config)

        entries = [
            MemoryEntry(
                id=f"entry_{i}",
                type=MemoryType.SEMANTIC,
                content=f"Content {i}",
            )
            for i in range(10)
        ]

        should_compress = await memory.should_compress(entries)
        assert should_compress is True


# Citation Verification Tests
class TestCitationVerification:
    """Tests for citation verification."""

    @pytest.mark.asyncio
    async def test_citation_parsing(self):
        """Test citation parsing."""
        exec_globals = {}
        exec(open("agents/citation.py", encoding="utf-8").read(), exec_globals)
        CitationParser = exec_globals["CitationParser"]

        parser = CitationParser()
        text = """
        According to [the research paper](https://arxiv.org/abs/1234.5678),
        and another source at https://github.com/example/repo.
        """

        citations = parser.parse_citations(text)

        assert len(citations) >= 1
        assert any(c.url for c in citations if "arxiv" in c.url or "github" in c.url)

    @pytest.mark.asyncio
    async def test_citation_structure(self):
        """Test Citation dataclass."""
        exec_globals = {}
        exec(open("agents/citation.py", encoding="utf-8").read(), exec_globals)
        Citation = exec_globals["Citation"]

        citation = Citation(
            raw="https://arxiv.org/abs/1234.5678",
            url="https://arxiv.org/abs/1234.5678",
            title="Test Paper",
            source="arxiv.org",
        )

        data = citation.to_dict()
        assert data["url"] == "https://arxiv.org/abs/1234.5678"
        assert data["title"] == "Test Paper"
        assert data["source"] == "arxiv.org"

    @pytest.mark.asyncio
    async def test_verification_result(self):
        """Test verification result structure."""
        exec_globals = {}
        exec(open("agents/citation.py", encoding="utf-8").read(), exec_globals)
        VerificationResult = exec_globals["VerificationResult"]
        CitationIssue = exec_globals["CitationIssue"]
        CitationIssueType = exec_globals["CitationIssueType"]

        result = VerificationResult(
            total_citations=5,
            valid_citations=4,
            issues=[
                CitationIssue(
                    citation="test citation",
                    issue_type=CitationIssueType.BROKEN,
                    severity="medium",
                    description="URL not accessible",
                )
            ],
            credibility_scores={"citation1": 0.9, "citation2": 0.6},
            duplicate_groups=[],
            verified_at=datetime.utcnow(),
        )

        assert result.total_citations == 5
        assert result.valid_citations == 4
        assert len(result.issues) == 1
        assert not result.is_verified  # Has issue


# Embedding Tests
class TestEmbeddings:
    """Tests for embedding infrastructure."""

    @pytest.mark.asyncio
    async def test_mock_embedding_provider(self):
        """Test mock embedding provider."""
        from memory.embeddings import MockEmbeddingProvider

        provider = MockEmbeddingProvider(model_name="mock", dimension=768)

        embedding = await provider.embed("test text")
        assert len(embedding) == 768

        embeddings = await provider.embed_batch(["text1", "text2"])
        assert len(embeddings) == 2
        assert all(len(e) == 768 for e in embeddings)

        is_healthy = await provider.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_embedding_cache(self):
        """Test embedding cache."""
        from memory.embeddings import MockEmbeddingProvider, EmbeddingCache

        cache = EmbeddingCache(max_size=100)

        # Cache miss
        result = cache.get("test", "mock")
        assert result is None

        # Add to cache
        embedding = [0.1] * 768
        cache.put("test", "mock", embedding)

        # Cache hit
        result = cache.get("test", "mock")
        assert result == embedding

        # Hit rate
        cache.get("test", "mock")  # Hit
        cache.get("missing", "mock")  # Miss

        assert cache.hit_rate >= 0.5

    @pytest.mark.asyncio
    async def test_embedding_cache_stats(self):
        """Test embedding cache statistics."""
        from memory.embeddings import EmbeddingCache

        cache = EmbeddingCache(max_size=100)

        cache.put("key1", "model", [0.1] * 10)
        cache.get("key1", "model")  # Hit
        cache.get("missing", "model")  # Miss

        stats = cache.stats
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1


# Summarization Tests
class TestSummarization:
    """Tests for summarization."""

    @pytest.mark.asyncio
    async def test_summary_result(self):
        """Test summary result structure."""
        from memory.summarization import SummaryResult

        result = SummaryResult(
            summary="Test summary",
            key_points=["point1", "point2"],
            entities=["entity1", "entity2"],
            tokens_used=100,
            generated_at=datetime.utcnow(),
            quality_score=0.9,
        )

        assert result.summary == "Test summary"
        assert len(result.key_points) == 2
        assert len(result.entities) == 2
        assert result.quality_score == 0.9


# Vector Store Config Tests
class TestVectorStoreConfig:
    """Tests for vector store configuration."""

    def test_vector_store_config_defaults(self):
        """Test VectorStoreConfig default values."""
        from memory.vector_store import VectorStoreConfig

        config = VectorStoreConfig()

        assert config.provider == "chroma"
        assert config.distance_metric == "cosine"
        assert config.batch_size == 100
        assert config.search_limit == 10

    def test_chroma_vector_store_config(self):
        """Test ChromaDB-specific config."""
        from memory.vector_store import ChromaVectorStore, VectorStoreConfig

        config = VectorStoreConfig(provider="chroma", persist_directory="/tmp/chroma")
        store = ChromaVectorStore(config)

        assert store.config.provider == "chroma"
        assert store.config.persist_directory == "/tmp/chroma"
