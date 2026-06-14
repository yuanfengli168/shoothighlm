"""Integration tests for CLI infographic command"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from shoothighlm.cli import main
from shoothighlm.infographic import Infographic
from shoothighlm.llm import LLMUsage


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


@pytest.fixture
def mock_info():
    return Infographic(
        template="summary_card",
        title="Test",
        data={"summary": "S", "key_topics": ["A"]},
        html_content="<!DOCTYPE html><html><body><h1>Test</h1></body></html>",
    )


def test_infographic_default_template(runner, temp_notebook, mock_info):
    """Test infographic with default summary_card template"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, ["infographic", str(temp_notebook)])
            
            assert result.exit_code == 0
            assert "HTML saved" in result.output


def test_infographic_custom_template(runner, temp_notebook, mock_info):
    """Test infographic with custom template"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Content"])
            
            result = runner.invoke(main, [
                "infographic", str(temp_notebook),
                "--template", "topic_hierarchy",
            ])
            
            assert result.exit_code == 0
            # Verify template was passed
            call_args = mock_gen.generate.call_args
            assert call_args[1]["template"] == "topic_hierarchy"


def test_infographic_custom_output(runner, temp_notebook, mock_info):
    """Test infographic with custom output path"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom.html"
        
        with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = (mock_info, LLMUsage())
            mock_gen_class.return_value = mock_gen
            
            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Content"])
                
                result = runner.invoke(main, [
                    "infographic", str(temp_notebook),
                    "--output", str(output_path),
                ])
                
                assert result.exit_code == 0
                assert output_path.exists()
                content = output_path.read_text()
                assert "Test" in content


def test_infographic_png_flag(runner, temp_notebook, mock_info):
    """Test infographic with --png flag triggers PNG render"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Content"])
            
            with patch('shoothighlm.infographic.render_html_to_png') as mock_render:
                result = runner.invoke(main, [
                    "infographic", str(temp_notebook),
                    "--png",
                ])
                
                assert result.exit_code == 0
                # Verify render was called
                mock_render.assert_called_once()
                assert "PNG saved" in result.output


def test_infographic_png_render_import_error(runner, temp_notebook, mock_info):
    """Test infographic handles missing playwright gracefully"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Content"])
            
            with patch('shoothighlm.infographic.render_html_to_png',
                      side_effect=ImportError("playwright not installed")):
                result = runner.invoke(main, [
                    "infographic", str(temp_notebook),
                    "--png",
                ])
                
                assert result.exit_code == 0
                assert "PNG render failed" in result.output
                assert "playwright" in result.output.lower()


def test_infographic_png_custom_dimensions(runner, temp_notebook, mock_info):
    """Test infographic with custom PNG dimensions"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Content"])
            
            with patch('shoothighlm.infographic.render_html_to_png') as mock_render:
                result = runner.invoke(main, [
                    "infographic", str(temp_notebook),
                    "--png",
                    "--width", "800",
                    "--height", "1000",
                ])
                
                assert result.exit_code == 0
                call_args = mock_render.call_args
                assert call_args[1]["width"] == 800
                assert call_args[1]["height"] == 1000


def test_infographic_no_pdfs(runner):
    """Test infographic with empty notebook"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "empty"
        notebook.mkdir()
        
        result = runner.invoke(main, ["infographic", str(notebook)])
        
        assert result.exit_code == 0
        assert "No PDFs found" in result.output


def test_infographic_no_text_extracted(runner, temp_notebook):
    """Test infographic when PDFs return no text"""
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])
        
        result = runner.invoke(main, ["infographic", str(temp_notebook)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output


def test_infographic_invalid_template(runner, temp_notebook, mock_info):
    """Test infographic with unknown template"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.side_effect = ValueError("Unknown template: foo")
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Content"])
            
            result = runner.invoke(main, [
                "infographic", str(temp_notebook),
                "--template", "foo",
            ])
            
            # Click will reject unknown choice before we even get to generate
            # But if it slipped through, we handle the error
            # Either way, exit code should be non-zero or error message shown
            assert result.exit_code != 0 or "Unknown template" in result.output or "Invalid value" in result.output


def test_infographic_passes_sources(runner, temp_notebook, mock_info):
    """Test that sources from PDFs are passed to generator"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_info, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf', side_effect=[
            iter(["Text from book"]),
        ]):
            result = runner.invoke(main, ["infographic", str(temp_notebook)])
            
            assert result.exit_code == 0
            call_args = mock_gen.generate.call_args
            sources = call_args[1]["sources"]
            assert "book.pdf" in sources
