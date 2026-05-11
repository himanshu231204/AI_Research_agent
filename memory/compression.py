"""
Compressed Memory System for Research OS.

Provides:
- Summarized historical context
- Condensed research history
- Rolling context windows
- Memory compression for long conversations
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from memory.base import (
    MemoryBase,
    MemoryConfig,
    MemoryEntry,
    MemoryType,
)

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Result of memory compression."""

    original_entries: int
    compressed_entries: int
    compression_ratio: float
    original_tokens: int
    compressed_tokens: int
    summary: str
    compressed_at: datetime


class CompressedMemory(MemoryBase[MemoryEntry]):
    """
    Compressed memory for summarized context.

    Reduces token usage while preserving useful information.
    Uses rolling windows and summarization.
    """

    def __init__(self, config: MemoryConfig):
        """
        Initialize compressed memory.

        Args:
            config: Memory configuration
        """
        super().__init__(config)
        self._compression_cache: Dict[str, CompressionResult] = {}

    async def store(self, entry: MemoryEntry) -> bool:
        """Store a compressed memory entry."""
        if entry.type != MemoryType.COMPRESSED:
            entry.type = MemoryType.COMPRESSED

        # In production, would store to compressed collection
        logger.debug(f"Stored compressed memory: {entry.id}")
        return True

    async def retrieve(
        self,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """Retrieve compressed memory entries."""
        # Return compressed entries for session
        return []

    async def update(self, entry: MemoryEntry) -> bool:
        """Update compressed memory."""
        return await self.store(entry)

    async def delete(self, entry_id: str) -> bool:
        """Delete compressed memory."""
        if entry_id in self._compression_cache:
            del self._compression_cache[entry_id]
        return True

    async def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count compressed memory entries."""
        return len(self._compression_cache)

    async def clear(self, session_id: Optional[str] = None) -> int:
        """Clear compressed memory."""
        if session_id:
            if session_id in self._compression_cache:
                del self._compression_cache[session_id]
        else:
            self._compression_cache.clear()
        return 1

    async def health_check(self) -> bool:
        """Check if healthy."""
        return True

    # Compression-specific methods

    async def compress_entries(
        self,
        entries: List[MemoryEntry],
        target_tokens: int = 2000,
    ) -> CompressionResult:
        """
        Compress multiple memory entries into a summary.

        Args:
            entries: Entries to compress
            target_tokens: Target token budget

        Returns:
            Compression result with summary
        """
        if not entries:
            return CompressionResult(
                original_entries=0,
                compressed_entries=0,
                compression_ratio=0.0,
                original_tokens=0,
                compressed_tokens=0,
                summary="",
                compressed_at=datetime.utcnow(),
            )

        # Calculate original size
        original_content = "\n\n".join([e.content for e in entries])
        original_tokens = len(original_content.split())

        # Generate summary
        summary = await self._generate_summary(entries)

        compressed_tokens = len(summary.split())

        # Create compressed entry
        session_ids = set(e.session_id for e in entries if e.session_id)
        session_id = list(session_ids)[0] if session_ids else None

        compressed_entry = MemoryEntry(
            id=f"compressed:{datetime.utcnow().isoformat()}",
            type=MemoryType.COMPRESSED,
            content=summary,
            metadata={
                "original_entry_count": len(entries),
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "session_ids": list(session_ids),
            },
            session_id=session_id,
        )

        await self.store(compressed_entry)

        result = CompressionResult(
            original_entries=len(entries),
            compressed_entries=1,
            compression_ratio=len(entries) / 1 if original_tokens else 0,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            summary=summary,
            compressed_at=datetime.utcnow(),
        )

        # Cache result
        if session_id:
            self._compression_cache[session_id] = result

        return result

    async def _generate_summary(self, entries: List[MemoryEntry]) -> str:
        """
        Generate summary of memory entries.

        Args:
            entries: Entries to summarize

        Returns:
            Summary text
        """
        from models.ollama_client import OllamaClient

        ollama = OllamaClient()

        # Build context
        context = "\n\n".join([e.content for e in entries[:20]])

        prompt = f"""Summarize the following research context concisely.
Preserve key findings, facts, and insights.
Remove redundant information.
Keep important citations and sources.

Context:
{context}

Provide a concise summary that captures the essential information."""

        try:
            summary = await ollama.generate(prompt)
            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Return truncated context as fallback
            return context[:2000]

    async def get_compression_result(
        self,
        session_id: str,
    ) -> Optional[CompressionResult]:
        """Get cached compression result for session."""
        return self._compression_cache.get(session_id)

    async def should_compress(
        self,
        entries: List[MemoryEntry],
        threshold: Optional[int] = None,
    ) -> bool:
        """
        Determine if entries should be compressed.

        Args:
            entries: Entries to evaluate
            threshold: Token threshold

        Returns:
            True if compression is recommended
        """
        if threshold is None:
            threshold = self.config.compression_threshold

        return len(entries) >= threshold

    async def rolling_window_compress(
        self,
        entries: List[MemoryEntry],
        window_size: int = 10,
        overlap: int = 2,
    ) -> List[MemoryEntry]:
        """
        Compress entries using rolling window approach.

        Args:
            entries: Entries to compress
            window_size: Size of each window
            overlap: Overlap between windows

        Returns:
            List of compressed entries
        """
        if len(entries) <= window_size:
            # Not enough entries to compress
            return entries

        compressed = []
        step = window_size - overlap

        for i in range(0, len(entries), step):
            window = entries[i : i + window_size]
            if len(window) >= 3:
                result = await self.compress_entries(window)
                compressed_entry = MemoryEntry(
                    id=f"window:{i}:{datetime.utcnow().isoformat()}",
                    type=MemoryType.COMPRESSED,
                    content=result.summary,
                    metadata={
                        "window_start": i,
                        "window_end": i + len(window),
                        "original_tokens": result.original_tokens,
                    },
                    session_id=window[0].session_id if window else None,
                )
                compressed.append(compressed_entry)
            else:
                compressed.extend(window)

        return compressed

    async def merge_sessions(
        self,
        session_ids: List[str],
        entries_by_session: Dict[str, List[MemoryEntry]],
    ) -> MemoryEntry:
        """
        Merge multiple sessions into one compressed memory.

        Args:
            session_ids: Session IDs to merge
            entries_by_session: Entries grouped by session

        Returns:
            Merged compressed entry
        """
        all_entries = []
        for entries in entries_by_session.values():
            all_entries.extend(entries)

        result = await self.compress_entries(all_entries)

        return MemoryEntry(
            id=f"merged:{','.join(session_ids)}",
            type=MemoryType.COMPRESSED,
            content=result.summary,
            metadata={
                "session_ids": session_ids,
                "original_session_count": len(session_ids),
                "original_entry_count": result.original_entries,
            },
        )
