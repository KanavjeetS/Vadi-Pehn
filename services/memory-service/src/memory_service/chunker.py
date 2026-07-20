"""
Sentence-boundary-aware chunking utility for Vadi-Pehn memory ingestion (`services/memory-service/chunker.py`).
Implements: PRD §4.1, SD §3.2, implementation_plan.md §4A.
Preserves natural sentence boundaries (`.`, `?`, `!`, `\n`) rather than arbitrary token slicing
to maintain semantic completeness for child dialogue and tutoring contexts.
"""
from __future__ import annotations

import re


class SentenceBoundaryChunker:
    """
    Splits raw conversation or document text along natural sentence endings.
    Groups consecutive sentences into semantic chunks up to `max_chunk_chars`,
    retaining `overlap_sentences` between adjacent chunks for contextual continuity.
    """

    def __init__(self, max_chunk_chars: int = 300, overlap_sentences: int = 1) -> None:
        if max_chunk_chars <= 0:
            raise ValueError("max_chunk_chars must be positive")
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences cannot be negative")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_sentences = overlap_sentences
        # Regex splits on terminal punctuation followed by space or newline, while keeping punctuation
        self._split_pattern = re.compile(r"(?<=[.?!])\s+|\n+")

    def chunk_text(self, text: str) -> list[str]:
        """Split text into sentence-aware chunks."""
        if not text or not text.strip():
            return []

        cleaned = text.strip()
        raw_sentences = [s.strip() for s in self._split_pattern.split(cleaned) if s.strip()]
        if not raw_sentences:
            return []

        chunks: list[str] = []
        current_sentences: list[str] = []
        current_len = 0

        for sentence in raw_sentences:
            sentence_len = len(sentence) + (1 if current_sentences else 0)

            # If adding this sentence would exceed limit and we already have sentences in chunk
            if current_sentences and (current_len + sentence_len > self.max_chunk_chars):
                chunks.append(" ".join(current_sentences))
                # Keep overlap sentences for next chunk
                if self.overlap_sentences > 0 and len(current_sentences) >= self.overlap_sentences:
                    current_sentences = current_sentences[-self.overlap_sentences:]
                    current_len = sum(len(s) + 1 for s in current_sentences) - 1
                else:
                    current_sentences = []
                    current_len = 0

            current_sentences.append(sentence)
            current_len = sum(len(s) + 1 for s in current_sentences) - 1

        if current_sentences:
            chunks.append(" ".join(current_sentences))

        return chunks
