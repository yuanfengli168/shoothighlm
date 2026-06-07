"""Tests for RAG chat"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from shoothighlm.rag import RAGChat, Citation, ChatResponse
from shoothighlm.vectorstore import VectorStore


class MockEmbedder:
    """Mock embedder that returns predictable embeddings"""
    
    def embed(self, text: str) -> list[float]:
        """Return a simple embedding based on text content"""
        # Return different embeddings for different queries
        if "France" in text or "Paris" in text:
            return [1.0, 0.0, 0.0] + [0.0] * 1021
        elif "Germany" in text or "Berlin" in text:
            return [0.0, 1.0, 0.0] + [0.0] * 1021
        else:
            return [0.0, 0.0, 1.0] + [0.0] * 1021


@pytest.fixture
def rag_chat():
    """Create a RAG chat instance with test data"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = VectorStore(db_path)
        embedder = MockEmbedder()
        
        # Add test chunks
        store.add(
            "test-1",
            "The capital of France is Paris. It is known for the Eiffel Tower.",
            "france.pdf",
            [1.0, 0.0, 0.0] + [0.0] * 1021,
        )
        store.add(
            "test-2",
            "Germany's capital is Berlin. The Berlin Wall fell in 1989.",
            "germany.pdf",
            [0.0, 1.0, 0.0] + [0.0] * 1021,
        )
        
        rag = RAGChat(
            vectorstore=store,
            embedder=embedder,
            chat_model="test-model",
            top_k=2,
            min_similarity=0.5,
        )
        yield rag
        store.close()


def test_rag_retrieve(rag_chat):
    """Test retrieval"""
    # Query similar to test-1 embedding
    results = rag_chat.retrieve("What is the capital of France?")
    assert len(results) > 0
    assert results[0].chunk_id == "test-1"


def test_rag_build_context(rag_chat):
    """Test context building"""
    results = rag_chat.retrieve("What is the capital of France?")
    context, citations = rag_chat.build_context(results)
    
    assert "Paris" in context
    assert len(citations) > 0
    assert isinstance(citations[0], Citation)
    assert citations[0].source == "france.pdf"


def test_rag_chat_response_structure(rag_chat):
    """Test chat response structure"""
    # Mock the LLM call to avoid actual API
    import httpx
    from unittest.mock import patch
    
    with patch.object(httpx.Client, 'post') as mock_post:
        mock_post.return_value.json.return_value = {"response": "The capital is Paris [1]."}
        
        response = rag_chat.chat("What is the capital of France?")
        
        assert isinstance(response, ChatResponse)
        assert "Paris" in response.answer
        assert len(response.citations) > 0
        assert response.model == "test-model"


def test_rag_no_results(rag_chat):
    """Test when no relevant results found"""
    # Set very high min_similarity to get no results
    rag_chat.min_similarity = 0.99
    response = rag_chat.chat("Random question")
    
    assert "couldn't find relevant information" in response.answer
    assert len(response.citations) == 0
