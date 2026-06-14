"""Integration tests for CLI guide command"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from shoothighlm.cli import main
from shoothighlm.guide import NotebookGuide


@pytest.fixture
def runner():
    """Create CLI test runner"""
    return CliRunner()


@pytest.fixture
def temp_notebook_with_pdfs():
    """Create a temporary notebook with multiple fake PDFs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        
        # Create fake PDF files
        (notebook / "book1.pdf").write_bytes(b"%PDF-1.4 fake pdf 1")
        (notebook / "book2.pdf").write_bytes(b"%PDF-1.4 fake pdf 2")
        
        yield notebook


@pytest.fixture
def mock_guide():
    """Sample guide for mocking"""
    return NotebookGuide(
        title="Test Notebook",
        summary="This is a test summary of the documents.",
        key_topics=["Topic A", "Topic B", "Topic C"],
        suggested_questions=[
            "What is Topic A?",
            "How does Topic B relate to Topic C?",
        ],
        sources=["book1.pdf", "book2.pdf"],
    )


def test_guide_markdown_output(runner, temp_notebook_with_pdfs, mock_guide):
    """Test guide command with Markdown output (default)"""
    with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_guide
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Sample text content from PDF."])
            
            result = runner.invoke(main, ["guide", str(temp_notebook_with_pdfs)])
            
            assert result.exit_code == 0
            assert "Guide saved to" in result.output


def test_guide_json_output(runner, temp_notebook_with_pdfs, mock_guide):
    """Test guide command with JSON output"""
    with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_guide
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Sample text"])
            
            result = runner.invoke(main, [
                "guide",
                str(temp_notebook_with_pdfs),
                "--format", "json",
            ])
            
            assert result.exit_code == 0
            assert "Guide saved to" in result.output


def test_guide_custom_questions_count(runner, temp_notebook_with_pdfs, mock_guide):
    """Test guide command with custom number of questions"""
    with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_guide
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Sample text"])
            
            result = runner.invoke(main, [
                "guide",
                str(temp_notebook_with_pdfs),
                "--questions", "8",
            ])
            
            assert result.exit_code == 0
            # Verify num_questions=8 was passed
            call_args = mock_gen.generate.call_args
            assert call_args[1]["num_questions"] == 8


@pytest.fixture
def temp_notebook_with_single_pdf():
    """Create a temporary notebook with a single fake PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()

        # Create a single fake PDF file
        (notebook / "book1.pdf").write_bytes(b"%PDF-1.4 fake pdf 1")

        yield notebook


def test_guide_custom_output_path(runner, temp_notebook_with_single_pdf, mock_guide):
    """Test guide command with custom output path (single PDF)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom-guide.md"

        with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = mock_guide
            mock_gen_class.return_value = mock_gen

            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Sample text"])

                result = runner.invoke(main, [
                    "guide",
                    str(temp_notebook_with_single_pdf),
                    "--output", str(output_path),
                ])

                assert result.exit_code == 0
                # Strip whitespace to handle rich's terminal-width line wrapping
                assert str(output_path) in result.output.replace("\n", "")
                assert output_path.exists()
                # Verify content
                content = output_path.read_text()
                assert "Test Notebook" in content


def test_guide_output_dir_flag(runner, temp_notebook_with_pdfs, mock_guide):
    """Test guide command with --output-dir flag (works for any # of PDFs)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "my-guides"

        with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = mock_guide
            mock_gen_class.return_value = mock_gen

            with patch('shoothighlm.pdf.parse_pdf', side_effect=[
                iter(["Text from book 1"]),
                iter(["Text from book 2"]),
            ]):
                result = runner.invoke(main, [
                    "guide",
                    str(temp_notebook_with_pdfs),
                    "--output-dir", str(output_dir),
                ])

                assert result.exit_code == 0
                assert output_dir.is_dir()
                # The file should be created with the default pattern: {title}-guide.md
                out_file = output_dir / "test-notebook-guide.md"
                assert out_file.exists()
                content = out_file.read_text()
                assert "Test Notebook" in content


def test_guide_custom_name_pattern(runner, temp_notebook_with_single_pdf, mock_guide):
    """Test guide command with --name-pattern flag (single PDF)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "out"

        with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = mock_guide
            mock_gen_class.return_value = mock_gen

            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Sample text"])

                result = runner.invoke(main, [
                    "guide",
                    str(temp_notebook_with_single_pdf),
                    "--output-dir", str(output_dir),
                    "--name-pattern", "my-{kind}-custom{ext}",
                ])

                assert result.exit_code == 0
                assert (output_dir / "my-guide-custom.md").exists()


def test_guide_no_pdfs(runner):
    """Test guide command when notebook has no PDFs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "empty-notebook"
        notebook.mkdir()
        
        result = runner.invoke(main, ["guide", str(notebook)])
        
        assert result.exit_code == 0
        assert "No PDFs found" in result.output


def test_guide_no_text_extracted(runner, temp_notebook_with_pdfs):
    """Test guide when all PDFs return empty text"""
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])
        
        result = runner.invoke(main, ["guide", str(temp_notebook_with_pdfs)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output


def test_guide_combines_multiple_pdfs(runner, temp_notebook_with_pdfs, mock_guide):
    """Test that guide combines text from all PDFs and tracks sources"""
    with patch('shoothighlm.guide.GuideGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = mock_guide
        mock_gen_class.return_value = mock_gen
        
        # parse_pdf is called once per PDF; return text for each
        with patch('shoothighlm.pdf.parse_pdf', side_effect=[
            iter(["Text from book 1"]),
            iter(["Text from book 2"]),
        ]):
            result = runner.invoke(main, ["guide", str(temp_notebook_with_pdfs)])
            
            assert result.exit_code == 0
            # Verify all sources were passed
            call_args = mock_gen.generate.call_args
            # text is positional, sources/num_questions are kwargs
            sources = call_args[1]["sources"]
            assert "book1.pdf" in sources
            assert "book2.pdf" in sources
            # Verify text was combined (positional arg)
            text = call_args[0][0]
            assert "Text from book 1" in text
            assert "Text from book 2" in text
