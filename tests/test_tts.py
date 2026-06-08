"""Tests for TTS (text-to-speech) module"""

import pytest
import io
import wave
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from shoothighlm.tts import (
    TTSProvider,
    TTSError,
    FishAudioProvider,
    CosyVoiceProvider,
    get_provider,
    concatenate_wav,
    wav_to_mp3_bytes,
    PodcastSynthesizer,
    DEFAULT_FISH_VOICE_A,
    DEFAULT_FISH_VOICE_B,
)


def _make_wav_bytes(duration_seconds: float = 0.5, framerate: int = 16000) -> bytes:
    """Helper: generate a simple WAV file in memory (sine wave silence)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(framerate)
        frames = int(duration_seconds * framerate)
        # Generate a simple sine wave at 440Hz
        import math
        data = b"".join(
            struct_pack_sample(int(32767 * 0.1 * math.sin(2 * math.pi * 440 * i / framerate)))
            for i in range(frames)
        )
        w.writeframes(data)
    return buf.getvalue()


def struct_pack_sample(value: int) -> bytes:
    """Pack a 16-bit signed sample"""
    import struct
    return struct.pack("<h", value)


# ============== Provider tests ==============

def test_tts_provider_is_abstract():
    """Test that TTSProvider.synthesize raises NotImplementedError when called directly"""
    provider = TTSProvider()
    with pytest.raises(NotImplementedError):
        provider.synthesize("test")
    with pytest.raises(NotImplementedError):
        provider.name()


def test_fish_audio_provider_init_with_key():
    """Test Fish Audio provider with explicit API key"""
    provider = FishAudioProvider(api_key="test-key-123")
    assert provider.api_key == "test-key-123"
    provider.close()


def test_fish_audio_provider_init_from_env():
    """Test Fish Audio provider reads API key from env"""
    with patch.dict("os.environ", {"FISH_AUDIO_API_KEY": "env-key"}):
        provider = FishAudioProvider()
        assert provider.api_key == "env-key"
        provider.close()


def test_fish_audio_provider_no_key_raises():
    """Test Fish Audio provider raises when no API key is set"""
    with patch.dict("os.environ", {}, clear=True):
        # Also clear the env var if it was set
        with pytest.raises(TTSError) as exc_info:
            FishAudioProvider()
        assert "FISH_AUDIO_API_KEY" in str(exc_info.value)


def test_fish_audio_provider_name():
    """Test provider name"""
    provider = FishAudioProvider(api_key="test")
    assert provider.name() == "fish-audio"
    provider.close()


def test_fish_audio_provider_synthesize_success():
    """Test successful TTS synthesis"""
    provider = FishAudioProvider(api_key="test-key")
    
    mock_response = Mock()
    mock_response.content = b"fake-wav-bytes"
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
        result = provider.synthesize("Hello world", voice_id="voice-1")
        
        assert result == b"fake-wav-bytes"
        # Verify API call
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.fish.audio/v1/tts"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
        assert call_args[1]["json"]["text"] == "Hello world"
        assert call_args[1]["json"]["reference_id"] == "voice-1"
    
    provider.close()


def test_fish_audio_provider_synthesize_http_error():
    """Test TTS synthesis handles HTTP errors"""
    import httpx
    
    provider = FishAudioProvider(api_key="test-key")
    
    with patch.object(provider.client, "post", side_effect=httpx.HTTPError("network down")):
        with pytest.raises(TTSError) as exc_info:
            provider.synthesize("Hello")
        assert "Fish Audio TTS request failed" in str(exc_info.value)
    
    provider.close()


def test_fish_audio_provider_synthesize_empty_text():
    """Test that empty text raises TTSError"""
    provider = FishAudioProvider(api_key="test-key")
    
    with pytest.raises(TTSError) as exc_info:
        provider.synthesize("   ")
    assert "empty text" in str(exc_info.value)
    
    provider.close()


def test_cosyvoice_provider_not_implemented():
    """Test that CosyVoice raises not-implemented (it's a stub)"""
    provider = CosyVoiceProvider(api_key="test")
    with pytest.raises(TTSError) as exc_info:
        provider.synthesize("Hello")
    assert "not yet implemented" in str(exc_info.value)


def test_cosyvoice_provider_no_key_raises():
    """Test CosyVoice requires API key"""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(TTSError):
            CosyVoiceProvider()


# ============== Factory tests ==============

def test_get_provider_fish_audio():
    """Test factory returns FishAudioProvider"""
    provider = get_provider("fish-audio", api_key="test")
    assert isinstance(provider, FishAudioProvider)
    assert provider.api_key == "test"
    provider.close()


def test_get_provider_cosyvoice():
    """Test factory returns CosyVoiceProvider"""
    provider = get_provider("cosyvoice", api_key="test")
    assert isinstance(provider, CosyVoiceProvider)
    provider.close()


def test_get_provider_unknown_raises():
    """Test factory rejects unknown provider"""
    with pytest.raises(TTSError) as exc_info:
        get_provider("nonexistent")
    assert "Unknown TTS provider" in str(exc_info.value)


# ============== WAV concatenation tests ==============

def test_concatenate_wav_empty_raises():
    """Test concatenate_wav rejects empty list"""
    with pytest.raises(TTSError) as exc_info:
        concatenate_wav([])
    assert "No audio segments" in str(exc_info.value)


def test_concatenate_wav_single_segment():
    """Test concatenating a single WAV returns valid output"""
    wav = _make_wav_bytes(duration_seconds=0.2)
    result = concatenate_wav([wav])
    
    # Should be valid WAV
    with wave.open(io.BytesIO(result), "rb") as w:
        assert w.getnframes() > 0
        assert w.getframerate() == 16000


def test_concatenate_wav_multiple_segments():
    """Test concatenating multiple WAVs adds silence between them"""
    wav1 = _make_wav_bytes(duration_seconds=0.2, framerate=16000)
    wav2 = _make_wav_bytes(duration_seconds=0.2, framerate=16000)
    wav3 = _make_wav_bytes(duration_seconds=0.2, framerate=16000)
    
    result = concatenate_wav([wav1, wav2, wav3], pause_seconds=0.5)
    
    # Compute expected duration: 3 * 0.2 + 2 * 0.5 (silence between, not after)
    expected_seconds = 0.2 * 3 + 0.5 * 2
    with wave.open(io.BytesIO(result), "rb") as w:
        actual_seconds = w.getnframes() / w.getframerate()
        assert abs(actual_seconds - expected_seconds) < 0.05


def test_concatenate_wav_no_silence_after_last():
    """Test that no silence is added after the last segment"""
    wav = _make_wav_bytes(duration_seconds=0.1, framerate=16000)
    result = concatenate_wav([wav], pause_seconds=1.0)
    
    # Duration should be exactly 0.1s, not 0.1 + 1.0
    with wave.open(io.BytesIO(result), "rb") as w:
        actual_seconds = w.getnframes() / w.getframerate()
        assert actual_seconds < 0.2


def test_concatenate_wav_invalid_data_raises():
    """Test that invalid WAV data raises TTSError"""
    with pytest.raises(TTSError) as exc_info:
        concatenate_wav([b"not a wav file"])
    assert "Invalid WAV" in str(exc_info.value)


def test_concatenate_wav_mismatched_format_raises():
    """Test that segments with different sample rates raise TTSError"""
    wav_16k = _make_wav_bytes(duration_seconds=0.1, framerate=16000)
    wav_8k = _make_wav_bytes(duration_seconds=0.1, framerate=8000)
    
    with pytest.raises(TTSError) as exc_info:
        concatenate_wav([wav_16k, wav_8k])
    assert "mismatched audio format" in str(exc_info.value)


# ============== wav_to_mp3 tests ==============

def test_wav_to_mp3_passthrough():
    """Test that wav_to_mp3 currently returns WAV (placeholder)"""
    wav = _make_wav_bytes()
    result = wav_to_mp3_bytes(wav)
    assert result == wav


# ============== PodcastSynthesizer tests ==============

def test_synthesizer_init():
    """Test PodcastSynthesizer initialization"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider, host_a_voice="voice-a", host_b_voice="voice-b")
    assert synth.host_a_voice == "voice-a"
    assert synth.host_b_voice == "voice-b"
    synth.close()


def test_synthesizer_default_voices():
    """Test default voices are set when not provided"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider)
    assert synth.host_a_voice == DEFAULT_FISH_VOICE_A
    assert synth.host_b_voice == DEFAULT_FISH_VOICE_B
    synth.close()


def test_synthesizer_empty_script_raises():
    """Test that empty script raises TTSError"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "out.wav"
        with pytest.raises(TTSError):
            synth.synthesize_script([], output)
    synth.close()


def test_synthesizer_routes_to_correct_voice():
    """Test that segments route to host_a or host_b voice based on speaker name"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider, host_a_voice="VOICE_A", host_b_voice="VOICE_B")
    
    mock_response = Mock()
    mock_response.content = _make_wav_bytes()
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.wav"
            result = synth.synthesize_script([
                {"speaker": "Alex", "text": "Hello"},
                {"speaker": "Jamie", "text": "Hi there"},
                {"speaker": "Alex", "text": "Welcome"},
            ], output)
            
            # Assertions inside the with-block so temp dir is still alive
            # Verify voice routing
            calls = mock_post.call_args_list
            assert calls[0][1]["json"]["reference_id"] == "VOICE_A"  # Alex
            assert calls[1][1]["json"]["reference_id"] == "VOICE_B"  # Jamie
            assert calls[2][1]["json"]["reference_id"] == "VOICE_A"  # Alex
            
            assert result["segment_count"] == 3
            assert Path(result["output_path"]).exists()
    
    synth.close()


def test_synthesizer_skips_empty_segments():
    """Test that empty text segments are skipped"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider)
    
    mock_response = Mock()
    mock_response.content = _make_wav_bytes()
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.wav"
            result = synth.synthesize_script([
                {"speaker": "Alex", "text": "Real content"},
                {"speaker": "Jamie", "text": ""},  # Empty
                {"speaker": "Alex", "text": "   "},  # Whitespace
                {"speaker": "Jamie", "text": "More content"},
            ], output)
    
    # Only 2 segments should have been sent
    assert mock_post.call_count == 2
    assert result["segment_count"] == 2
    synth.close()


def test_synthesizer_returns_duration_info():
    """Test that synthesizer returns duration and segment count"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider)
    
    mock_response = Mock()
    mock_response.content = _make_wav_bytes(duration_seconds=0.1, framerate=16000)
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.wav"
            result = synth.synthesize_script([
                {"speaker": "Alex", "text": "First line"},
                {"speaker": "Jamie", "text": "Second line"},
            ], output, pause_seconds=0.2)
    
    assert "output_path" in result
    assert "duration_seconds" in result
    assert "segment_count" in result
    assert result["segment_count"] == 2
    # 2 * 0.1 + 1 * 0.2 = 0.4s
    assert result["duration_seconds"] > 0.3
    synth.close()


def test_synthesizer_creates_output_directory():
    """Test that synthesizer creates output dir if missing"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider)
    
    mock_response = Mock()
    mock_response.content = _make_wav_bytes()
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Nested dir that doesn't exist
            output = Path(tmpdir) / "nested" / "subdir" / "out.wav"
            synth.synthesize_script([{"speaker": "Alex", "text": "Test"}], output)
            assert output.exists()
    synth.close()


def test_synthesizer_voice_case_insensitive():
    """Test that speaker matching handles case and common variants"""
    provider = FishAudioProvider(api_key="test")
    synth = PodcastSynthesizer(provider, host_a_voice="A", host_b_voice="B")
    
    mock_response = Mock()
    mock_response.content = _make_wav_bytes()
    mock_response.raise_for_status = Mock()
    
    with patch.object(provider.client, "post", return_value=mock_response) as mock_post:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "out.wav"
            synth.synthesize_script([
                {"speaker": "ALEX", "text": "1"},  # uppercase
                {"speaker": "host a", "text": "2"},  # with space
                {"speaker": "host_a", "text": "3"},  # with underscore
            ], output)
    
    calls = mock_post.call_args_list
    assert all(c[1]["json"]["reference_id"] == "A" for c in calls)
    synth.close()
