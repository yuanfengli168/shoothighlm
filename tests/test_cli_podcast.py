"""Integration tests for CLI podcast command"""

import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from shoothighlm.cli import main
from shoothighlm.podcast import PodcastScript
from shoothighlm.llm import LLMUsage


@pytest.fixture
def runner():
    """Create CLI test runner"""
    return CliRunner()


@pytest.fixture
def temp_notebook_with_pdf():
    """Create a temporary notebook with a fake PDF"""
    with tempfile.TemporaryDirectory() as tmpdir:
        notebook = Path(tmpdir) / "test-notebook"
        notebook.mkdir()
        
        # Create a fake PDF file
        pdf_file = notebook / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")
        
        yield notebook


def test_podcast_markdown_output(runner, temp_notebook_with_pdf):
    """Test podcast command with Markdown output"""
    mock_script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[
            {"speaker": "Alex", "text": "Welcome!"},
            {"speaker": "Jamie", "text": "Thanks!"},
        ],
    )
    
    with patch('shoothighlm.podcast.PodcastGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_script, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "podcast",
                str(temp_notebook_with_pdf),
                "--format", "markdown",
            ])
            
            assert result.exit_code == 0
            assert "Podcast script saved to" in result.output


def test_podcast_json_output(runner, temp_notebook_with_pdf):
    """Test podcast command with JSON output"""
    mock_script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[{"speaker": "Alex", "text": "Welcome!"}],
    )
    
    with patch('shoothighlm.podcast.PodcastGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_script, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "podcast",
                str(temp_notebook_with_pdf),
                "--format", "json",
            ])
            
            assert result.exit_code == 0
            assert "Podcast script saved to" in result.output


def test_podcast_custom_duration(runner, temp_notebook_with_pdf):
    """Test podcast command with custom duration"""
    mock_script = PodcastScript(
        title="Test Podcast",
        duration_minutes=10,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[{"speaker": "Alex", "text": "Welcome!"}],
    )
    
    with patch('shoothighlm.podcast.PodcastGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_script, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "podcast",
                str(temp_notebook_with_pdf),
                "--duration", "10",
            ])
            
            assert result.exit_code == 0
            assert "Podcast script saved to" in result.output


def test_podcast_custom_hosts(runner, temp_notebook_with_pdf):
    """Test podcast command with custom host names"""
    mock_script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Host A",
        host_b_name="Host B",
        segments=[{"speaker": "Host A", "text": "Welcome!"}],
    )
    
    with patch('shoothighlm.podcast.PodcastGenerator') as mock_gen_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (mock_script, LLMUsage())
        mock_gen_class.return_value = mock_gen
        
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["Test content"])
            
            result = runner.invoke(main, [
                "podcast",
                str(temp_notebook_with_pdf),
                "--host-a", "Host A",
                "--host-b", "Host B",
            ])
            
            assert result.exit_code == 0
            assert "Podcast script saved to" in result.output


def test_podcast_custom_output_path(runner, temp_notebook_with_pdf):
    """Test podcast command with custom output path"""
    mock_script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[{"speaker": "Alex", "text": "Welcome!"}],
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "custom-podcast.md"
        
        with patch('shoothighlm.podcast.PodcastGenerator') as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = (mock_script, LLMUsage())
            mock_gen_class.return_value = mock_gen
            
            with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
                mock_parse.return_value = iter(["Test content"])
                
                result = runner.invoke(main, [
                    "podcast",
                    str(temp_notebook_with_pdf),
                    "--format", "markdown",
                    "--output", str(output_path),
                ])
                
                assert result.exit_code == 0
                # Strip whitespace to handle rich's terminal-width line wrapping
                assert str(output_path) in result.output.replace("\n", "")
                assert output_path.exists()


def test_podcast_no_text_extracted(runner, temp_notebook_with_pdf):
    """Test podcast when PDF parsing returns no text"""
    with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
        mock_parse.return_value = iter([""])  # Empty text
        
        result = runner.invoke(main, ["podcast", str(temp_notebook_with_pdf)])
        
        assert result.exit_code == 0
        assert "No text extracted" in result.output
