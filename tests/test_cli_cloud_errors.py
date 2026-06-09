"""Tests for cloud-error UX paths and the chat-model-in-output feature.

These cover the error-printing branches in the 6 command bodies that
were previously only hit in real failure conditions.
"""

import tempfile
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from shoothighlm.cli import main, _OLLAMA_CLOUD_HINT


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_notebook():
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        (notebook / "book.pdf").write_bytes(b"%PDF-1.4 fake")
        yield notebook


# ============== chat() command body coverage ==============

def test_chat_cloud_error_prints_hint(runner, temp_notebook, monkeypatch):
    """When chat hits a network error, print hint with --use-local guidance."""
    # Create a fake index file so the command gets past the "no index" check
    db_dir = temp_notebook / ".shoothighlm"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "vectors.db").write_bytes(b"")

    fake_rag = MagicMock()
    fake_rag.chat.side_effect = httpx.ConnectError("connection refused")
    fake_rag.close = MagicMock()

    with patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag):
        result = runner.invoke(main, ["chat", str(temp_notebook), "question"])

    # The hint should appear in the output
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output
    assert "SHOOTHIGHLM_CHAT" in result.output


def test_chat_non_cloud_error_prints_generic_message(runner, temp_notebook):
    """Non-network errors should not show the cloud hint, just a generic message."""
    db_dir = temp_notebook / ".shoothighlm"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "vectors.db").write_bytes(b"")

    fake_rag = MagicMock()
    fake_rag.chat.side_effect = ValueError("some weird error")
    fake_rag.close = MagicMock()

    with patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag):
        result = runner.invoke(main, ["chat", str(temp_notebook), "question"])

    assert "Chat failed" in result.output
    assert "--use-local" not in result.output


def test_chat_cloud_error_500(runner, temp_notebook):
    """HTTP 500 from the LLM should also trigger the cloud hint."""
    db_dir = temp_notebook / ".shoothighlm"
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / "vectors.db").write_bytes(b"")

    err = MagicMock()
    err.status_code = 500
    real_err = httpx.HTTPStatusError(
        "server error", request=MagicMock(), response=err,
    )
    fake_rag = MagicMock()
    fake_rag.chat.side_effect = real_err
    fake_rag.close = MagicMock()

    with patch("shoothighlm.vectorstore.VectorStore"), \
         patch("shoothighlm.embedding.get_embedder"), \
         patch("shoothighlm.rag.RAGChat", return_value=fake_rag):
        result = runner.invoke(main, ["chat", str(temp_notebook), "question"])

    assert "Cloud LLM" in result.output


# ============== Command bodies print "model: X" in output ==============

def test_mindmap_prints_chat_model_in_output(runner, temp_notebook):
    """The mindmap command should announce which chat model is being used."""
    mock_ext = MagicMock()
    mock_map = MagicMock()
    mock_map.to_markdown.return_value = "# root"
    mock_ext.extract.return_value = mock_map

    with patch("shoothighlm.mindmap.MindMapExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["mindmap", str(temp_notebook)])

    # The command body should print the model name in the intro line
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()


def test_flashcard_prints_chat_model_in_output(runner, temp_notebook):
    """flashcard command should announce its model."""
    mock_gen = MagicMock()
    mock_gen.generate.return_value = []
    with patch("shoothighlm.flashcard.FlashcardGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["flashcard", str(temp_notebook)])
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()


def test_podcast_prints_chat_model_in_output(runner, temp_notebook):
    """podcast command should announce its model."""
    mock_gen = MagicMock()
    mock_gen.generate.return_value = MagicMock(
        title="T", description="D", turns=[],
        to_script=lambda: "SCRIPT",
    )
    with patch("shoothighlm.podcast.PodcastGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["podcast", str(temp_notebook)])
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()


def test_guide_prints_chat_model_in_output(runner, temp_notebook):
    """guide command should announce its model."""
    mock_gen = MagicMock()
    mock_gen.generate.return_value = MagicMock(
        title="T", sections=[], to_markdown=lambda: "# G",
    )
    with patch("shoothighlm.guide.GuideGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["guide", str(temp_notebook)])
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()


def test_infographic_prints_chat_model_in_output(runner, temp_notebook):
    """infographic command should announce its model."""
    from shoothighlm.infographic import Infographic
    mock_gen = MagicMock()
    mock_gen.generate.return_value = Infographic(
        template="summary_card", title="T", data={}, html_content="<html></html>",
    )
    with patch("shoothighlm.infographic.InfographicGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["infographic", str(temp_notebook)])
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()


def test_tables_prints_chat_model_in_output(runner, temp_notebook):
    """tables command should announce its model."""
    mock_ext = MagicMock()
    mock_ext.extract.return_value = []
    with patch("shoothighlm.tables.TableExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["tables", str(temp_notebook)])
    assert "model:" in result.output.lower() or "qwen" in result.output.lower()
