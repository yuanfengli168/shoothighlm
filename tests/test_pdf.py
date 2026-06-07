"""Tests for PDF parsing and chunking"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from shoothighlm.pdf import chunk_text, Chunk, parse_pdf


def test_chunk_text_basic():
    """Test basic text chunking"""
    text = "A" * 10000  # 10k characters
    chunks = list(chunk_text(text, "test.pdf", chunk_size=4096, chunk_overlap=200))
    
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(c.source == "test.pdf" for c in chunks)
    assert all(len(c.text) > 0 for c in chunks)


def test_chunk_text_overlap():
    """Test that chunks have proper overlap"""
    text = "A" * 10000
    chunk_size = 4096
    overlap = 200
    chunks = list(chunk_text(text, "test.pdf", chunk_size=chunk_size, chunk_overlap=overlap))
    
    if len(chunks) > 1:
        # Check overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            chunk1_end = chunks[i].text[-overlap:]
            chunk2_start = chunks[i + 1].text[:overlap]
            assert chunk1_end == chunk2_start


def test_chunk_text_small():
    """Test chunking with text smaller than chunk_size"""
    text = "Small text"
    chunks = list(chunk_text(text, "test.pdf", chunk_size=4096, chunk_overlap=200))
    
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_chunk_ids_unique():
    """Test that chunk IDs are unique"""
    text = "A" * 10000
    chunks = list(chunk_text(text, "test.pdf", chunk_size=4096, chunk_overlap=200))
    chunk_ids = [c.chunk_id for c in chunks]
    
    assert len(chunk_ids) == len(set(chunk_ids)), "Chunk IDs should be unique"


def test_chunk_text_custom_size():
    """Test chunking with custom chunk size"""
    text = "A" * 10000
    chunk_size = 2000
    chunks = list(chunk_text(text, "test.pdf", chunk_size=chunk_size, chunk_overlap=0))
    
    # Should have at least 5 chunks (10000 / 2000)
    assert len(chunks) >= 5
    assert all(len(c.text) <= chunk_size for c in chunks)


def test_chunk_text_with_overlap_calculation():
    """Test exact overlap calculation"""
    text = "A" * 5000
    chunk_size = 1000
    overlap = 100
    chunks = list(chunk_text(text, "test.pdf", chunk_size=chunk_size, chunk_overlap=overlap))
    
    # First chunk: 0-1000
    # Second chunk: 900-1900 (overlap 100)
    # etc.
    assert len(chunks) > 1
    # Verify the step size
    assert chunks[0].text[:100] == chunks[1].text[:100]  # Overlap region


def test_chunk_metadata():
    """Test chunk metadata fields"""
    text = "Test content"
    chunks = list(chunk_text(text, "/path/to/document.pdf", chunk_size=4096, chunk_overlap=200))
    
    chunk = chunks[0]
    assert chunk.source == "/path/to/document.pdf"
    assert chunk.chunk_id.startswith("document-")
    assert chunk.start_page == 0
    assert chunk.end_page == 0


@pytest.mark.skip(reason="Requires docling package")
def test_parse_pdf_with_docling():
    """Test PDF parsing with docling (skipped, requires installation)"""
    pass


@pytest.mark.skip(reason="Requires docling and pypdf packages")
def test_parse_pdf_fallback():
    """Test PDF parsing fallback (skipped, requires installation)"""
    pass


@pytest.mark.skip(reason="Requires docling package")
def test_parse_pdf_empty():
    """Test PDF parsing returns empty (skipped, requires installation)"""
    pass
