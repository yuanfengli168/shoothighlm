"""Tests for cloud-error handling in the 6 generator commands.

Each command body wraps the LLM call in a try/except that:
- prints the cloud hint if the error is a network/5xx
- prints a generic "X failed" message otherwise
- returns without aborting the whole CLI

These tests cover those branches.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
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
        (notebook / "book.pdf").write_bytes(b"%PDF-1.4 fake")
        yield notebook


# ============== mindmap ==============

def test_mindmap_cloud_error_prints_hint(runner, temp_notebook):
    mock_ext = MagicMock()
    mock_ext.extract.side_effect = httpx.ConnectError("nope")
    with patch("shoothighlm.mindmap.MindMapExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["mindmap", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_mindmap_generic_error_prints_specific(runner, temp_notebook):
    mock_ext = MagicMock()
    mock_ext.extract.side_effect = ValueError("weird")
    with patch("shoothighlm.mindmap.MindMapExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["mindmap", str(temp_notebook)])
    assert "Mind map generation failed" in result.output


# ============== flashcard ==============

def test_flashcard_cloud_error_prints_hint(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = httpx.ReadTimeout("timeout")
    with patch("shoothighlm.flashcard.FlashcardGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["flashcard", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_flashcard_generic_error(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = ValueError("oops")
    with patch("shoothighlm.flashcard.FlashcardGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["flashcard", str(temp_notebook)])
    assert "Flashcard generation failed" in result.output


# ============== podcast ==============

def test_podcast_cloud_error_prints_hint(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = httpx.ConnectTimeout("ct")
    with patch("shoothighlm.podcast.PodcastGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["podcast", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_podcast_generic_error(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = ValueError("boom")
    with patch("shoothighlm.podcast.PodcastGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["podcast", str(temp_notebook)])
    assert "Podcast generation failed" in result.output


# ============== guide ==============

def test_guide_cloud_error_prints_hint(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = httpx.ConnectError("nope")
    with patch("shoothighlm.guide.GuideGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["guide", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_guide_generic_error(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = ValueError("oops")
    with patch("shoothighlm.guide.GuideGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["guide", str(temp_notebook)])
    assert "Guide generation failed" in result.output


# ============== infographic ==============

def test_infographic_cloud_error_prints_hint(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = httpx.ReadTimeout("t")
    with patch("shoothighlm.infographic.InfographicGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["infographic", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_infographic_generic_error(runner, temp_notebook):
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = ValueError("oops")
    with patch("shoothighlm.infographic.InfographicGenerator", return_value=mock_gen), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["infographic", str(temp_notebook)])
    assert "Generation failed" in result.output


# ============== tables ==============

def test_tables_cloud_error_prints_hint(runner, temp_notebook):
    mock_ext = MagicMock()
    mock_ext.extract.side_effect = httpx.ConnectError("nope")
    with patch("shoothighlm.tables.TableExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["tables", str(temp_notebook)])
    assert "Cloud LLM" in result.output
    assert "--use-local" in result.output


def test_tables_generic_error(runner, temp_notebook):
    mock_ext = MagicMock()
    mock_ext.extract.side_effect = ValueError("oops")
    with patch("shoothighlm.tables.TableExtractor", return_value=mock_ext), \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        result = runner.invoke(main, ["tables", str(temp_notebook)])
    assert "Tables extraction failed" in result.output
