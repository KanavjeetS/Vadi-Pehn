"""
Unit tests for SentenceBoundaryChunker (`services/memory-service/tests/test_chunker.py`).
Verifies sentence-boundary preservation for child tutoring dialogue (implementation_plan.md §4A).
"""

from memory_service.chunker import SentenceBoundaryChunker


def test_sentence_boundary_chunking_preserves_whole_sentences():
    chunker = SentenceBoundaryChunker(max_chunk_chars=60, overlap_sentences=0)
    text = (
        "Hello there! My teacher scolded me today because I lost my notebook. "
        "Can you help me organize my bag? I feel really sad about what happened."
    )
    chunks = chunker.chunk_text(text)

    # Verify every chunk ends with full punctuation, no mid-word or mid-sentence truncation
    for chunk in chunks:
        assert chunk[-1] in [".", "?", "!"], f"Chunk truncated mid-sentence: {chunk}"

    assert "My teacher scolded me today because I lost my notebook." in chunks
    assert "Can you help me organize my bag?" in chunks


def test_sentence_overlap_maintains_contextual_continuity():
    chunker = SentenceBoundaryChunker(max_chunk_chars=50, overlap_sentences=1)
    text = "First sentence. Second sentence is slightly longer. Third sentence here."
    chunks = chunker.chunk_text(text)

    assert len(chunks) >= 2
    # Second chunk should start with the last sentence from the first chunk due to overlap_sentences=1
    assert chunks[0].endswith("First sentence.")
    assert chunks[1].startswith("First sentence.")


def test_empty_and_whitespace_only_text():
    chunker = SentenceBoundaryChunker()
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   \n\t  ") == []


def test_single_long_sentence_fallback():
    chunker = SentenceBoundaryChunker(max_chunk_chars=20, overlap_sentences=0)
    # Even if single sentence exceeds limit, chunker yields it as a whole unit to preserve grammar
    text = "This single sentence exceeds the twenty char limit."
    chunks = chunker.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text
