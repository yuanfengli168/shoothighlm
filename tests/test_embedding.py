"""Tests for embedding"""

import pytest
from shoothighlm.embedding import Embedder


def test_embedder_init():
    """Test embedder initialization"""
    embedder = Embedder(model="bge-m3")
    assert embedder.model == "bge-m3"
    assert embedder.base_url == "http://127.0.0.1:11434"


def test_embedder_custom_url():
    """Test embedder with custom URL"""
    embedder = Embedder(model="bge-m3", base_url="http://localhost:11434")
    assert embedder.base_url == "http://localhost:11434"


@pytest.mark.skip(reason="Requires running Ollama instance")
def test_embedder_embed():
    """Test actual embedding generation"""
    embedder = Embedder(model="bge-m3")
    embedding = embedder.embed("Hello world")
    
    assert isinstance(embedding, list)
    assert len(embedding) > 0
    assert all(isinstance(x, float) for x in embedding)
