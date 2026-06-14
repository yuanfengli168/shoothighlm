"""Regression tests for multi-PDF processing.

Before the multi-PDF fix, `mindmap`, `flashcard`, and `podcast` all did
`pdf = pdfs[0]`, silently dropping books 2..N. These tests verify the
loop now produces one output file per PDF, and that a failure on one
PDF doesn't abort the whole batch.
"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

from shoothighlm.cli import main
from shoothighlm.mindmap import MindMapNode
from shoothighlm.flashcard import Flashcard
from shoothighlm.podcast import PodcastScript


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def temp_notebook_with_3_pdfs():
    """A notebook with 3 fake PDFs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "notebook"
        notebook.mkdir()
        (notebook / "book-one.pdf").write_bytes(b"%PDF-1.4 one")
        (notebook / "book-two.pdf").write_bytes(b"%PDF-1.4 two")
        (notebook / "book-three.pdf").write_bytes(b"%PDF-1.4 three")
        yield notebook


# ============== mindmap: one output per PDF ==============

def test_mindmap_processes_all_pdfs(runner, temp_notebook_with_3_pdfs):
    """Should write one .md per PDF, not just the first one."""
    mock_node = MindMapNode(id="root", title="X", children=[])
    with patch("shoothighlm.mindmap.MindMapExtractor") as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = mock_node
        mock_class.return_value = mock_ext
        # side_effect=lambda returns a fresh iter on every call, so
        # all 3 PDFs each get "text" extracted.
        with patch(
            "shoothighlm.pdf.parse_pdf",
            side_effect=lambda *a, **kw: iter(["text"]),
        ):
            result = runner.invoke(
                main, ["mindmap", str(temp_notebook_with_3_pdfs)]
            )

    assert result.exit_code == 0, result.output
    out_dir = temp_notebook_with_3_pdfs / "output"
    md_files = sorted(out_dir.glob("*-mindmap.md"))
    names = [f.stem.replace("-mindmap", "") for f in md_files]
    assert "book-one" in names, f"missing in {names}"
    assert "book-two" in names, f"missing in {names}"
    assert "book-three" in names, f"missing in {names}"


def test_mindmap_output_dir_with_multiple_pdfs(runner, temp_notebook_with_3_pdfs):
    """--output as a path is treated as a directory when there are multiple PDFs.

    The new --resolve_output_paths helper intentionally allows this:
    it's a friendlier experience than rejecting the command. Each PDF
    still gets its own per-PDF file inside that directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir) / "mindmaps"
        mock_node = MindMapNode(id="root", title="X", children=[])
        with patch("shoothighlm.mindmap.MindMapExtractor") as mock_class:
            mock_ext = MagicMock()
            mock_ext.extract.return_value = mock_node
            mock_class.return_value = mock_ext
            with patch(
                "shoothighlm.pdf.parse_pdf",
                side_effect=lambda *a, **kw: iter(["text"]),
            ):
                result = runner.invoke(
                    main,
                    [
                        "mindmap",
                        str(temp_notebook_with_3_pdfs),
                        "--output", str(target_dir),
                    ],
                )
        assert result.exit_code == 0, result.output
        assert target_dir.is_dir()
        md_files = sorted(target_dir.glob("*-mindmap.md"))
        assert len(md_files) == 3, f"expected 3 files, got {md_files}"


def test_mindmap_per_pdf_error_resilience(runner, temp_notebook_with_3_pdfs):
    """If one PDF fails, the others should still get outputs.

    We don't assert which specific book fails — pathlib.glob order is
    filesystem-dependent. We just verify that exactly 2 of the 3 books
    produce output, and that the failure message surfaces in the
    command's stdout.
    """
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated LLM failure")
        return MindMapNode(id="root", title="X", children=[])

    with patch("shoothighlm.mindmap.MindMapExtractor") as mock_class:
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = side_effect
        mock_class.return_value = mock_ext
        with patch(
            "shoothighlm.pdf.parse_pdf",
            side_effect=lambda *a, **kw: iter(["text"]),
        ):
            result = runner.invoke(
                main, ["mindmap", str(temp_notebook_with_3_pdfs)]
            )

    assert result.exit_code == 0, result.output
    out_dir = temp_notebook_with_3_pdfs / "output"
    md_files = sorted(out_dir.glob("*-mindmap.md"))
    # Exactly 2 of the 3 books should produce output
    assert len(md_files) == 2, f"expected 2 outputs, got {md_files}"
    # And the simulated failure should be visible to the user
    assert "simulated LLM failure" in result.output


# ============== flashcard: one output per PDF ==============

def test_flashcard_processes_all_pdfs(runner, temp_notebook_with_3_pdfs):
    """Should write one .md per PDF."""
    card = Flashcard(id="c1", question="Q", answer="A")
    with patch("shoothighlm.flashcard.FlashcardGenerator") as mock_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = [card]
        mock_class.return_value = mock_gen
        with patch(
            "shoothighlm.pdf.parse_pdf",
            side_effect=lambda *a, **kw: iter(["text"]),
        ):
            result = runner.invoke(
                main, ["flashcard", str(temp_notebook_with_3_pdfs)]
            )

    assert result.exit_code == 0
    out_dir = temp_notebook_with_3_pdfs / "output"
    files = sorted(out_dir.glob("*-flashcards.md"))
    names = [f.stem.replace("-flashcards", "") for f in files]
    assert "book-one" in names
    assert "book-two" in names
    assert "book-three" in names


# ============== podcast: one output per PDF ==============

def test_podcast_processes_all_pdfs(runner, temp_notebook_with_3_pdfs):
    """Should write one .md per PDF."""
    script = PodcastScript(
        title="T", duration_minutes=5,
        host_a_name="A", host_b_name="B",
        segments=[{"speaker": "A", "text": "hi"}],
    )
    with patch("shoothighlm.podcast.PodcastGenerator") as mock_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = script
        mock_class.return_value = mock_gen
        with patch(
            "shoothighlm.pdf.parse_pdf",
            side_effect=lambda *a, **kw: iter(["text"]),
        ):
            result = runner.invoke(
                main, ["podcast", str(temp_notebook_with_3_pdfs)]
            )

    assert result.exit_code == 0
    out_dir = temp_notebook_with_3_pdfs / "output"
    files = sorted(out_dir.glob("*-podcast.md"))
    names = [f.stem.replace("-podcast", "") for f in files]
    assert "book-one" in names
    assert "book-two" in names
    assert "book-three" in names
