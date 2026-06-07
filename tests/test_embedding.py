"""Tests for embedding"""

import pytest
from unittest.mock import Mock, patch
from shoothighlm.embedding import Embedder, get_embedder


def test_embedder_init():
    """Test embedder initialization"""
    embedder = Embedder(model="bge-m3")
    assert embedder.model == "bge-m3"
    assert embedder.base_url == "http://127.0.0.1:11434"


def test_embedder_custom_url():
    """Test embedder with custom URL"""
    embedder = Embedder(model="bge-m3", base_url="http://localhost:11434")
    assert embedder.base_url == "http://localhost:11434"


def test_embedder_embed_mock():
    """Test embedding generation with mock"""
    embedder = Embedder(model="bge-m3")
    
    # Mock the HTTP client
    mock_response = Mock()
    mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    mock_response.raise_for_status = Mock()
    
    with patch.object(embedder.client, 'post', return_value=mock_response):
        embedding = embedder.embed("Hello world")
        
        assert embedding == [0.1, 0.2, 0.3]
        embedder.client.post.assert_called_once()


def test_embedder_embed_batch_mock():
    """Test batch embedding with mock"""
    embedder = Embedder(model="bge-m3")
    
    # Mock responses
    responses = [
        Mock(json=lambda: {"embedding": [0.1] * 1024}, raise_for_status=Mock()),
        Mock(json=lambda: {"embedding": [0.2] * 1024}, raise_for_status=Mock()),
    ]
    
    with patch.object(embedder.client, 'post', side_effect=responses):
        embeddings = embedder.embed_batch(["text1", "text2"])
        
        assert len(embeddings) == 2
        assert embeddings[0] == [0.1] * 1024
        assert embeddings[1] == [0.2] * 1024


def test_get_embedder_local():
    """Test get_embedder returns local embedder"""
    embedder = get_embedder(model="bge-m3")
    assert isinstance(embedder, Embedder)
    assert embedder.model == "bge-m3"


def test_get_embedder_cloud_still_local():
    """Test get_embedder ignores cloud flag (embeddings are local only)"""
    embedder = get_embedder(model="bge-m3", use_cloud=True)
    assert isinstance(embedder, Embedder)
    # Cloud doesn't support embeddings, so it still returns local


def test_embedder_embed_real():
    """Test actual embedding generation with Ollama"""
    embedder = Embedder(model="bge-m3")
    embedding = embedder.embed("Hello world")
    
    assert isinstance(embedding, list)
    assert len(embedding) == 1024, "bge-m3 produces 1024-dimensional embeddings"
    assert all(isinstance(x, float) for x in embedding)
    
    # Test that similar texts have similar embeddings
    emb1 = embedder.embed("Hello world")
    emb2 = embedder.embed("Hello world")
    assert emb1 == emb2, "Same text should produce same embedding"
