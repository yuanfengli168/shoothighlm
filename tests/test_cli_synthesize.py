"""Integration tests for CLI synthesize command (TTS)"""

import json
import pytest
from click.testing import CliRunner
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock
from shoothighlm.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def script_file():
    """Create a sample podcast script JSON file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        script = {
            "title": "Test Podcast",
            "duration_minutes": 1,
            "host_a_name": "Alex",
            "host_b_name": "Jamie",
            "segments": [
                {"speaker": "Alex", "text": "Welcome to the show."},
                {"speaker": "Jamie", "text": "Thanks for having me."},
            ],
        }
        script_path = Path(tmpdir) / "podcast.json"
        script_path.write_text(json.dumps(script), encoding="utf-8")
        yield script_path


def test_synthesize_default_output(runner, script_file):
    """Test synthesize creates WAV file next to the script"""
    # Make a fake provider to avoid real API calls
    fake_audio = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 100  # invalid but mock doesn't care
    
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.name.return_value = "fish-audio"
        mock_provider.synthesize.return_value = fake_audio
        mock_get_provider.return_value = mock_provider
        
        with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
            mock_synth = MagicMock()
            mock_synth.synthesize_script.return_value = {
                "output_path": str(script_file.parent / "podcast.wav"),
                "duration_seconds": 1.5,
                "segment_count": 2,
            }
            mock_synth_class.return_value = mock_synth
            
            result = runner.invoke(main, ["synthesize", str(script_file)])
            
            assert result.exit_code == 0
            assert "Audio saved" in result.output
            assert "fish-audio" in result.output


def test_synthesize_custom_output(runner, script_file):
    """Test synthesize with --output custom path"""
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_out = Path(tmpdir) / "my-audio.wav"
        
        with patch('shoothighlm.tts.get_provider') as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.name.return_value = "fish-audio"
            mock_get_provider.return_value = mock_provider
            
            with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
                mock_synth = MagicMock()
                mock_synth.synthesize_script.return_value = {
                    "output_path": str(custom_out),
                    "duration_seconds": 1.0,
                    "segment_count": 2,
                }
                mock_synth_class.return_value = mock_synth
                
                result = runner.invoke(main, [
                    "synthesize", str(script_file),
                    "--output", str(custom_out),
                ])
                
                assert result.exit_code == 0
                # Verify the custom output was used
                call_args = mock_synth.synthesize_script.call_args
                assert call_args[0][1] == custom_out


def test_synthesize_custom_provider(runner, script_file):
    """Test synthesize with --provider flag"""
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.name.return_value = "cosyvoice"
        mock_get_provider.return_value = mock_provider
        
        with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
            mock_synth = MagicMock()
            mock_synth.synthesize_script.return_value = {
                "output_path": "/tmp/x.wav",
                "duration_seconds": 1.0,
                "segment_count": 2,
            }
            mock_synth_class.return_value = mock_synth
            
            result = runner.invoke(main, [
                "synthesize", str(script_file),
                "--provider", "cosyvoice",
            ])
            
            assert result.exit_code == 0
            # Verify provider was set
            mock_get_provider.assert_called_with("cosyvoice")


def test_synthesize_custom_voices(runner, script_file):
    """Test synthesize with custom voice IDs"""
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.name.return_value = "fish-audio"
        mock_get_provider.return_value = mock_provider
        
        with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
            mock_synth = MagicMock()
            mock_synth.synthesize_script.return_value = {
                "output_path": "/tmp/x.wav",
                "duration_seconds": 1.0,
                "segment_count": 2,
            }
            mock_synth_class.return_value = mock_synth
            
            result = runner.invoke(main, [
                "synthesize", str(script_file),
                "--voice-a", "my-voice-a",
                "--voice-b", "my-voice-b",
            ])
            
            assert result.exit_code == 0
            call_args = mock_synth_class.call_args
            assert call_args[1]["host_a_voice"] == "my-voice-a"
            assert call_args[1]["host_b_voice"] == "my-voice-b"


def test_synthesize_custom_pause(runner, script_file):
    """Test synthesize with custom pause duration"""
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.name.return_value = "fish-audio"
        mock_get_provider.return_value = mock_provider
        
        with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
            mock_synth = MagicMock()
            mock_synth.synthesize_script.return_value = {
                "output_path": "/tmp/x.wav",
                "duration_seconds": 1.0,
                "segment_count": 2,
            }
            mock_synth_class.return_value = mock_synth
            
            result = runner.invoke(main, [
                "synthesize", str(script_file),
                "--pause", "1.5",
            ])
            
            assert result.exit_code == 0
            call_args = mock_synth.synthesize_script.call_args
            assert call_args[1]["pause_seconds"] == 1.5


def test_synthesize_invalid_json(runner):
    """Test synthesize rejects invalid JSON"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad = Path(tmpdir) / "bad.json"
        bad.write_text("not valid json{")
        
        result = runner.invoke(main, ["synthesize", str(bad)])
        
        assert result.exit_code == 0
        assert "Invalid JSON" in result.output


def test_synthesize_empty_segments(runner):
    """Test synthesize rejects script with no segments"""
    with tempfile.TemporaryDirectory() as tmpdir:
        script = {"title": "Empty", "segments": []}
        path = Path(tmpdir) / "empty.json"
        path.write_text(json.dumps(script))
        
        result = runner.invoke(main, ["synthesize", str(path)])
        
        assert result.exit_code == 0
        assert "no segments" in result.output


def test_synthesize_no_api_key(runner, script_file):
    """Test synthesize handles missing API key gracefully"""
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        from shoothighlm.tts import TTSError
        mock_get_provider.side_effect = TTSError("FISH_AUDIO_API_KEY not found")
        
        result = runner.invoke(main, ["synthesize", str(script_file)])
        
        assert result.exit_code == 0
        assert "TTS provider error" in result.output
        assert "FISH_AUDIO_API_KEY" in result.output


def test_synthesize_synthesis_failure(runner, script_file):
    """Test synthesize handles TTS errors during synthesis"""
    from shoothighlm.tts import TTSError
    
    with patch('shoothighlm.tts.get_provider') as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.name.return_value = "fish-audio"
        mock_get_provider.return_value = mock_provider
        
        with patch('shoothighlm.tts.PodcastSynthesizer') as mock_synth_class:
            mock_synth = MagicMock()
            mock_synth.synthesize_script.side_effect = TTSError("network down")
            mock_synth_class.return_value = mock_synth
            
            result = runner.invoke(main, ["synthesize", str(script_file)])
            
            assert result.exit_code == 0
            assert "Synthesis failed" in result.output
            assert "network down" in result.output
