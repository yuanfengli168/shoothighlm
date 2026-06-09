"""Tests for the new chat() flags: --show-sources, --min-similarity.

The chat command should:
- print the active min_similarity and per-chunk similarity when --show-sources
- accept a per-call --min-similarity override (no need to edit config)
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from shoothighlm.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_notebook():
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        # Create a fake index so chat doesn't bail with "no index"
        db_dir = notebook / ".shoothighlm"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "vectors.db").write_bytes(b"")
        yield notebook


def test_chat_show_sources_prints_similarities(runner, temp_notebook):
    """--show-sources should print each chunk's similarity score."""
    fake_results = [
        MagicMock(distance=0.4, text="Top chunk text."),
        MagicMock(distance=0.6, text="Second chunk."),
    ]
    fake_rag = MagicMock()
    fake_rag.retrieve.return_value = fake_results
    fake_rag.chat.return_value = MagicMock(
        answer="Some answer.",
        citations=[],
        model="qwen3.5:cloud",
    )
    fake_rag.close = MagicMock()

    with patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag):
        result = runner.invoke(
            main, ["chat", str(temp_notebook), "test question", "--show-sources"]
        )
    # We should see similarity scores in the output (0.6 = 1-0.4)
    assert "0.600" in result.output
    assert "0.400" in result.output
    assert "Retrieved 2 chunks" in result.output


def test_chat_min_similarity_override(runner, temp_notebook):
    """--min-similarity CLI flag should override config value."""
    fake_rag = MagicMock()
    fake_rag.chat.return_value = MagicMock(
        answer="Answer.",
        citations=[],
        model="qwen3.5:cloud",
    )
    fake_rag.close = MagicMock()

    with patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag) as mock_class:
        runner.invoke(
            main, ["chat", str(temp_notebook), "q", "--min-similarity", "0.25"]
        )
    # The RAGChat should have been constructed with min_similarity=0.25
    call_kwargs = mock_class.call_args[1]
    assert call_kwargs["min_similarity"] == 0.25


def test_chat_uses_config_min_similarity_by_default(runner, temp_notebook):
    """Without --min-similarity, use the config value."""
    fake_rag = MagicMock()
    fake_rag.chat.return_value = MagicMock(
        answer="A.",
        citations=[],
        model="qwen3.5:cloud",
    )
    fake_rag.close = MagicMock()

    fake_config = MagicMock()
    fake_config.get.return_value = 0.42  # any custom value
    with patch("shoothighlm.config.Config", return_value=fake_config), \
         patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag) as mock_class:
        runner.invoke(main, ["chat", str(temp_notebook), "q"])
    call_kwargs = mock_class.call_args[1]
    assert call_kwargs["min_similarity"] == 0.42


def test_chat_passes_fallback_top_n(runner, temp_notebook):
    """The fallback_top_n config value should be passed to RAGChat."""
    fake_rag = MagicMock()
    fake_rag.chat.return_value = MagicMock(
        answer="A.",
        citations=[],
        model="qwen3.5:cloud",
    )
    fake_rag.close = MagicMock()

    fake_config = MagicMock()
    # Config.get is called for: embedding model, min_similarity, top_k,
    # fallback_top_n. Map them by argument.
    fake_config.get.side_effect = lambda *keys, **kw: {
        ("models", "embedding"): "bge-m3",
        ("rag", "min_similarity"): 0.4,
        ("rag", "top_k"): 5,
        ("rag", "fallback_top_n"): 7,
    }.get(keys, kw.get("default"))
    with patch("shoothighlm.config.Config", return_value=fake_config), \
         patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag) as mock_class:
        runner.invoke(main, ["chat", str(temp_notebook), "q"])
    call_kwargs = mock_class.call_args[1]
    assert call_kwargs["fallback_top_n"] == 7
