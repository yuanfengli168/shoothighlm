"""Tests for PDF parsing and chunking"""

import pytest
from pathlib import Path
from shoothighlm.pdf import chunk_text, Chunk


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
