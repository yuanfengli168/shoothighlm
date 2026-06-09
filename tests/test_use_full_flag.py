"""Tests for use_full parameter and --full CLI flag.

The `--full` flag should propagate from CLI → generator method, and
the generator method should use a larger max_chars limit when
use_full=True.
"""

import inspect
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

import pytest
from click.testing import CliRunner

from shoothighlm.cli import main


# ============== Generator method signatures ==============

def test_mindmap_extractor_has_use_full():
    from shoothighlm.mindmap import MindMapExtractor
    sig = inspect.signature(MindMapExtractor.extract)
    assert "use_full" in sig.parameters
    assert sig.parameters["use_full"].default is False


def test_flashcard_generator_has_use_full():
    from shoothighlm.flashcard import FlashcardGenerator
    sig = inspect.signature(FlashcardGenerator.generate)
    assert "use_full" in sig.parameters


def test_podcast_generator_has_use_full():
    from shoothighlm.podcast import PodcastGenerator
    sig = inspect.signature(PodcastGenerator.generate)
    assert "use_full" in sig.parameters


def test_guide_generator_has_use_full():
    from shoothighlm.guide import GuideGenerator
    sig = inspect.signature(GuideGenerator.generate)
    assert "use_full" in sig.parameters


def test_infographic_generator_has_use_full():
    from shoothighlm.infographic import InfographicGenerator
    sig = inspect.signature(InfographicGenerator.generate)
    assert "use_full" in sig.parameters


def test_table_extractor_has_use_full():
    from shoothighlm.tables import TableExtractor
    sig = inspect.signature(TableExtractor.extract)
    assert "use_full" in sig.parameters


# ============== use_full behavior (verifies max_chars change) ==============

def test_mindmap_use_full_uses_larger_limit():
    """use_full=True should use 50K chars, default is 12K."""
    from shoothighlm.mindmap import MindMapExtractor
    ext = MindMapExtractor(chat_model="test")

    # Short text: not truncated in either case
    short = "A" * 1000
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": '{"id": "root", "title": "T", "children": []}'}
    mock_response.raise_for_status = MagicMock()
    with patch.object(ext.client, "post", return_value=mock_response):
        ext.extract(short, use_full=False)
        ext.extract(short, use_full=True)
    # Both calls succeed without truncation issues


def test_mindmap_use_full_truncation_threshold():
    """Verify that use_full=True truncates at 50K, default at 12K."""
    from shoothighlm.mindmap import MindMapExtractor
    ext = MindMapExtractor(chat_model="test")

    # Text just over 12K but under 50K
    text_15k = "A" * 15000
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": '{"id": "root", "title": "T", "children": []}'}
    mock_response.raise_for_status = MagicMock()
    with patch.object(ext.client, "post", return_value=mock_response) as mock_post:
        ext.extract(text_15k, use_full=False)
        call_no_full = mock_post.call_args
        # Default should have truncated to ~12K + "... [truncated]"
        prompt_no_full = call_no_full[1]["json"]["prompt"]
        assert "... [truncated]" in prompt_no_full
        # Check: prompt body should be < 15K chars (12K + prompt template)
        assert len(prompt_no_full) < 13000

        mock_post.reset_mock()
        ext.extract(text_15k, use_full=True)
        call_full = mock_post.call_args
        prompt_full = call_full[1]["json"]["prompt"]
        # use_full=True should NOT truncate at 15K
        assert "... [truncated]" not in prompt_full
        # The full 15K should be in the prompt
        assert "A" * 15000 in prompt_full


# ============== CLI flag propagation ==============

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


def test_mindmap_passes_use_full_to_extractor(runner, temp_notebook):
    """--full flag should reach extractor.extract(use_full=...)."""
    with patch("shoothighlm.mindmap.MindMapExtractor") as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = MagicMock(spec=["to_markdown", "to_opml", "to_dict"])
        mock_ext.extract.return_value.to_markdown.return_value = "# test"
        mock_class.return_value = mock_ext
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            runner.invoke(main, ["mindmap", str(temp_notebook), "--full"])
        # Verify use_full was passed
        call_kwargs = mock_ext.extract.call_args[1]
        assert call_kwargs.get("use_full") is True


def test_mindmap_default_use_full_false(runner, temp_notebook):
    """Without --full, use_full should be False."""
    with patch("shoothighlm.mindmap.MindMapExtractor") as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = MagicMock(spec=["to_markdown", "to_opml", "to_dict"])
        mock_ext.extract.return_value.to_markdown.return_value = "# test"
        mock_class.return_value = mock_ext
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            runner.invoke(main, ["mindmap", str(temp_notebook)])
        call_kwargs = mock_ext.extract.call_args[1]
        assert call_kwargs.get("use_full") is False


def test_tables_passes_use_full(runner, temp_notebook):
    """--full flag should reach TableExtractor.extract()."""
    with patch("shoothighlm.tables.TableExtractor") as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = []
        mock_class.return_value = mock_ext
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            runner.invoke(main, ["tables", str(temp_notebook), "--full"])
        call_kwargs = mock_ext.extract.call_args[1]
        assert call_kwargs.get("use_full") is True


def test_flashcard_passes_use_full(runner, temp_notebook):
    """--full flag should reach FlashcardGenerator.generate()."""
    with patch("shoothighlm.flashcard.FlashcardGenerator") as mock_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = []
        mock_class.return_value = mock_gen
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            runner.invoke(main, ["flashcard", str(temp_notebook), "--full"])
        call_kwargs = mock_gen.generate.call_args[1]
        assert call_kwargs.get("use_full") is True


def test_infographic_passes_use_full(runner, temp_notebook):
    """--full flag should reach InfographicGenerator.generate()."""
    from shoothighlm.infographic import Infographic
    with patch("shoothighlm.infographic.InfographicGenerator") as mock_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = Infographic(
            template="summary_card", title="T", data={}, html_content="<html></html>",
        )
        mock_class.return_value = mock_gen
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            runner.invoke(main, ["infographic", str(temp_notebook), "--full"])
        call_kwargs = mock_gen.generate.call_args[1]
        assert call_kwargs.get("use_full") is True
