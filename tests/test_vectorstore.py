"""Tests for vector store"""

import pytest
import tempfile
from pathlib import Path
from shoothighlm.vectorstore import VectorStore, SearchResult


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = VectorStore(db_path)
        yield store
        store.close()


def test_vectorstore_init(temp_db):
    """Test vector store initialization"""
    assert temp_db.db_path.exists()


def test_vectorstore_add(temp_db):
    """Test adding a chunk"""
    temp_db.add(
        chunk_id="test-1",
        text="Test chunk text",
        source="test.pdf",
        embedding=[0.1] * 1024,
    )
    # Should not raise


def test_vectorstore_search(temp_db):
    """Test searching"""
    # Add some chunks
    temp_db.add("test-1", "Hello world", "test.pdf", [1.0] + [0.0] * 1023)
    temp_db.add("test-2", "Goodbye world", "test.pdf", [0.0] + [1.0] + [0.0] * 1022)
    
    # Search
    results = temp_db.search([1.0] + [0.0] * 1023, top_k=1)
    
    assert len(results) > 0
    assert isinstance(results[0], SearchResult)
    assert results[0].chunk_id == "test-1"


def test_vectorstore_search_top_k(temp_db):
    """Test search respects top_k"""
    for i in range(10):
        temp_db.add(
            f"test-{i}",
            f"Chunk {i}",
            "test.pdf",
            [float(i)] + [0.0] * 1023,
        )
    
    results = temp_db.search([0.5] + [0.0] * 1023, top_k=3)
    assert len(results) == 3
