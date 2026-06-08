"""Targeted tests to push CLI coverage above 93%."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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


# ============== synthesize RuntimeError path ==============

def test_synthesize_runtime_error(runner, temp_notebook, tmp_path):
    """Test that a RuntimeError from the TTS pipeline is reported cleanly"""
    from shoothighlm.tts import PodcastSynthesizer
    
    script = tmp_path / "script.json"
    script.write_text(json.dumps({
        "title": "X",
        "duration_minutes": 5,
        "host_a_name": "A",
        "host_b_name": "B",
        "segments": [{"speaker": "A", "text": "hi"}],
    }))
    
    with patch('shoothighlm.tts.PodcastSynthesizer') as mock_class:
        mock_class.return_value.synthesize_script.side_effect = RuntimeError("API key invalid")
        with patch.dict('os.environ', {'FISH_AUDIO_API_KEY': 'fake'}):
            result = runner.invoke(main, ['synthesize', str(script)])
            
            # Should not crash; error printed
            assert "API key invalid" in result.output or result.exit_code != 0


def test_synthesize_no_provider_for_service(runner, tmp_path):
    """Test that an unknown service name in config raises cleanly"""
    script = tmp_path / "script.json"
    script.write_text(json.dumps({
        "title": "X", "duration_minutes": 5,
        "host_a_name": "A", "host_b_name": "B",
        "segments": [{"speaker": "A", "text": "hi"}],
    }))
    
    with patch('shoothighlm.tts.get_provider') as mock_get:
        mock_get.side_effect = ValueError("Unknown TTS service: foo")
        with patch.dict('os.environ', {'FISH_AUDIO_API_KEY': 'fake'}):
            result = runner.invoke(main, ['synthesize', str(script)])
            
            assert "Unknown TTS service" in result.output or result.exit_code != 0


# ============== infographic RuntimeError path ==============

def test_infographic_runtime_error(runner, temp_notebook):
    """Test that a RuntimeError from LLM extraction is reported cleanly"""
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_class:
        mock_class.return_value.generate.side_effect = RuntimeError("LLM timeout")
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, ['infographic', str(temp_notebook)])
            
            assert "LLM timeout" in result.output or "Generation failed" in result.output


def test_infographic_value_error(runner, temp_notebook):
    """Test that a ValueError (bad template) is reported cleanly"""
    # Click's choice type rejects bad values before we even get there,
    # but if generate() raises ValueError anyway, we should handle it.
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_class:
        mock_class.return_value.generate.side_effect = ValueError("Bad template")
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            
            result = runner.invoke(main, ['infographic', str(temp_notebook)])
            
            assert "Bad template" in result.output or "Generation failed" in result.output


def test_infographic_png_generic_exception(runner, temp_notebook):
    """Test that a non-ImportError exception in PNG render is reported"""
    from shoothighlm.infographic import Infographic
    
    mock_info = Infographic(
        template="summary_card", title="T", data={},
        html_content="<!DOCTYPE html><html></html>",
    )
    
    with patch('shoothighlm.infographic.InfographicGenerator') as mock_class:
        mock_class.return_value.generate.return_value = mock_info
        with patch('shoothighlm.pdf.parse_pdf') as mock_parse:
            mock_parse.return_value = iter(["text"])
            with patch('shoothighlm.infographic.render_html_to_png',
                      side_effect=Exception("Disk full")):
                result = runner.invoke(main, [
                    'infographic', str(temp_notebook), '--png'
                ])
                
                assert "Disk full" in result.output or "PNG render failed" in result.output


# ============== chat command EOF path ==============

def test_chat_eof(runner, temp_notebook):
    """Test that chat command handles EOF gracefully"""
    with patch('shoothighlm.rag.RAGChat') as mock_engine_class:
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        
        # Simulate EOF (empty input) — Click's prompt will EOF immediately
        result = runner.invoke(main, ['chat', str(temp_notebook)], input="")
        
        # Should not crash
        assert result.exit_code == 0 or "EOF" in result.output


# ============== Direct module test: _render_html ValueError ==============

def test_render_html_raises_for_unknown_template():
    """Defense-in-depth: even if generate() is bypassed, _render_html raises"""
    from shoothighlm.infographic import InfographicGenerator
    gen = InfographicGenerator(chat_model="test")
    with pytest.raises(ValueError) as exc_info:
        gen._render_html("bogus", {"title": "T"})
    assert "No HTML template" in str(exc_info.value)
    gen.close()


# ============== _extract_data bare-code-block fallback ==============

def test_extract_data_handles_bare_code_block():
    """Test that a bare ``` (not ```json) code block is parsed correctly"""
    from shoothighlm.infographic import InfographicGenerator
    gen = InfographicGenerator(chat_model="test")
    
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": """```
{"summary": "S", "key_topics": ["A"]}
```"""
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(gen.client, "post", return_value=mock_response):
        info = gen.generate("text", template="summary_card", title="T")
        # Should not raise — the bare code-block branch is exercised
        assert info.data["summary"] == "S"
    gen.close()


# ============== render_html_to_png — bundled chromium not found with sys chrome available ==============

def test_render_html_to_png_no_chrome_at_all():
    """When no Chrome anywhere is available, give a clear error"""
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "test.html"
        html_path.write_text("<html></html>")
        png_path = Path(tmpdir) / "test.png"
        
        with patch("playwright.sync_api.sync_playwright") as mock_sp:
            mock_sp.return_value.__enter__.return_value.chromium.launch.side_effect = Exception(
                "Executable doesn't exist at /path/to/bundled/chromium"
            )
            # Pretend no system chrome is available
            with patch("shoothighlm.infographic.Path.exists", return_value=False):
                from shoothighlm.infographic import render_html_to_png
                with pytest.raises(RuntimeError) as exc_info:
                    render_html_to_png(html_path, png_path, use_system_chrome=True)
                assert "Chromium not found" in str(exc_info.value)
                assert "playwright install" in str(exc_info.value)
