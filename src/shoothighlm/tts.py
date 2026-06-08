"""Text-to-Speech generation for podcast scripts.

Supports multiple TTS providers via a simple abstraction. Currently
implemented: Fish Audio S2 (default) and Alibaba Cloud CosyVoice.

Audio is generated per-segment, then concatenated with short pauses
into a single WAV file using only the Python stdlib (wave module).
No ffmpeg or pydub dependency required.
"""

from pathlib import Path
from typing import List, Optional
import os
import io
import wave
import struct
import httpx
import json


# Fish Audio S2 reference voices (publicly available preset voices)
# These are well-known community voices; users can override with their own voice IDs
DEFAULT_FISH_VOICE_A = "zh_female_shuangkuai"  # Bright female voice
DEFAULT_FISH_VOICE_B = "zh_male_aojiaobu"        # Warm male voice


class TTSError(Exception):
    """Raised when TTS generation fails"""
    pass


class TTSProvider:
    """Base class for TTS providers"""
    
    def synthesize(self, text: str, voice_id: str = None) -> bytes:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to speak
            voice_id: Provider-specific voice identifier
        
        Returns:
            Raw audio bytes (WAV format)
        
        Raises:
            TTSError: If synthesis fails
        """
        raise NotImplementedError
    
    def name(self) -> str:
        """Return provider name"""
        raise NotImplementedError


class FishAudioProvider(TTSProvider):
    """Fish Audio S2 TTS provider
    
    API docs: https://docs.fish.audio/api-reference/overview
    Free tier available; requires FISH_AUDIO_API_KEY env var or config.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("FISH_AUDIO_API_KEY")
        if not self.api_key:
            raise TTSError(
                "Fish Audio API key not found. Set FISH_AUDIO_API_KEY "
                "environment variable or configure in ~/.shoothighlm/config.yaml"
            )
        self.client = httpx.Client(timeout=60.0)
    
    def name(self) -> str:
        return "fish-audio"
    
    def synthesize(self, text: str, voice_id: str = None) -> bytes:
        if not text.strip():
            raise TTSError("Cannot synthesize empty text")
        
        voice_id = voice_id or DEFAULT_FISH_VOICE_A
        
        # Fish Audio TTS API endpoint
        # Reference: https://docs.fish.audio/api-reference/operations/create-speech
        try:
            response = self.client.post(
                "https://api.fish.audio/v1/tts",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "model": "speech-1.6",  # Latest S2 model
                },
                json={
                    "text": text,
                    "reference_id": voice_id,
                    "format": "wav",
                },
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            raise TTSError(f"Fish Audio TTS request failed: {e}")
    
    def close(self):
        self.client.close()


class CosyVoiceProvider(TTSProvider):
    """Alibaba Cloud CosyVoice TTS provider (placeholder)
    
    Note: This is a stub. Alibaba Cloud TTS requires complex signing
    and account setup. Use FishAudioProvider unless you specifically
    need CosyVoice.
    """
    
    def __init__(self, api_key: Optional[str] = None, region: str = "cn-shanghai"):
        self.api_key = api_key or os.environ.get("ALIYUN_API_KEY")
        if not self.api_key:
            raise TTSError(
                "Aliyun API key not found. Set ALIYUN_API_KEY environment variable."
            )
        self.region = region
        self.client = httpx.Client(timeout=60.0)
    
    def name(self) -> str:
        return "cosyvoice"
    
    def synthesize(self, text: str, voice_id: str = None) -> bytes:
        # TODO: implement Aliyun CosyVoice NLS API integration
        # Reference: https://help.aliyun.com/zh/isi/getting-started/restful-api-for-text-to-speech
        raise TTSError(
            "CosyVoice provider is not yet implemented. "
            "Use FishAudioProvider (set tts.provider: fish-audio in config)."
        )
    
    def close(self):
        self.client.close()


def get_provider(provider_name: str = "fish-audio", api_key: Optional[str] = None) -> TTSProvider:
    """Factory function to get a TTS provider by name.
    
    Args:
        provider_name: One of "fish-audio", "cosyvoice"
        api_key: Optional API key (overrides env var)
    
    Returns:
        TTSProvider instance
    """
    if provider_name == "fish-audio":
        return FishAudioProvider(api_key=api_key)
    elif provider_name == "cosyvoice":
        return CosyVoiceProvider(api_key=api_key)
    else:
        raise TTSError(f"Unknown TTS provider: {provider_name}")


def concatenate_wav(segments: List[bytes], pause_seconds: float = 0.4) -> bytes:
    """Concatenate multiple WAV byte streams into a single WAV file.
    
    Args:
        segments: List of WAV file bytes (each must be a valid WAV file)
        pause_seconds: Silence duration between segments
    
    Returns:
        WAV file bytes (concatenated)
    
    Raises:
        TTSError: If audio data is invalid
    """
    if not segments:
        raise TTSError("No audio segments to concatenate")
    
    # Read first segment to get audio parameters
    try:
        first_wav = wave.open(io.BytesIO(segments[0]), "rb")
    except wave.Error as e:
        raise TTSError(f"Invalid WAV data in segment 0: {e}")
    
    params = first_wav.getparams()
    sample_width = params.sampwidth
    framerate = params.framerate
    n_channels = params.nchannels
    first_wav.close()
    
    # Build output buffer
    output = io.BytesIO()
    out_wav = wave.open(output, "wb")
    out_wav.setnchannels(n_channels)
    out_wav.setsampwidth(sample_width)
    out_wav.setframerate(framerate)
    
    # Compute silence frame
    silence_frames = int(framerate * pause_seconds)
    silence_bytes = b"\x00" * (silence_frames * n_channels * sample_width)
    
    for i, seg_bytes in enumerate(segments):
        try:
            w = wave.open(io.BytesIO(seg_bytes), "rb")
        except wave.Error as e:
            out_wav.close()
            raise TTSError(f"Invalid WAV data in segment {i}: {e}")
        
        # Verify all segments have matching format
        if w.getnchannels() != n_channels or w.getsampwidth() != sample_width or w.getframerate() != framerate:
            w.close()
            out_wav.close()
            raise TTSError(
                f"Segment {i} has mismatched audio format. "
                f"All segments must use the same sample rate, channels, and bit depth."
            )
        
        out_wav.writeframes(w.readframes(w.getnframes()))
        w.close()
        
        # Add silence between segments (not after the last one)
        if i < len(segments) - 1:
            out_wav.writeframes(silence_bytes)
    
    out_wav.close()
    return output.getvalue()


def wav_to_mp3_bytes(wav_bytes: bytes, bitrate: str = "128k") -> bytes:
    """Convert WAV bytes to MP3 bytes.
    
    Note: Requires ffmpeg installed on system. Returns WAV if ffmpeg not available.
    For now, this is a no-op wrapper that returns WAV — actual MP3 conversion
    can be added when ffmpeg is available.
    
    Args:
        wav_bytes: WAV file bytes
        bitrate: MP3 bitrate (unused for now)
    
    Returns:
        Audio bytes (WAV for now, MP3 in future)
    """
    # Future: use subprocess to call ffmpeg
    # For now, just return WAV — keeps it dependency-free
    return wav_bytes


class PodcastSynthesizer:
    """High-level podcast synthesizer: script + provider + voice mapping"""
    
    def __init__(self, provider: TTSProvider, host_a_voice: str = None, host_b_voice: str = None):
        self.provider = provider
        self.host_a_voice = host_a_voice or DEFAULT_FISH_VOICE_A
        self.host_b_voice = host_b_voice or DEFAULT_FISH_VOICE_B
    
    def synthesize_script(
        self,
        script_segments: List[dict],
        output_path: Path,
        pause_seconds: float = 0.4,
    ) -> dict:
        """
        Synthesize audio for a podcast script.
        
        Args:
            script_segments: List of {"speaker": str, "text": str} dicts
            output_path: Where to write the output WAV file
            pause_seconds: Silence between segments
        
        Returns:
            Dict with "output_path", "duration_seconds", "segment_count"
        
        Raises:
            TTSError: If synthesis or concatenation fails
        """
        if not script_segments:
            raise TTSError("Script has no segments to synthesize")
        
        audio_segments = []
        for i, seg in enumerate(script_segments):
            speaker = seg.get("speaker", "")
            text = seg.get("text", "")
            if not text.strip():
                continue
            
            voice = self.host_a_voice if speaker.lower() in ("alex", "host a", "host_a") else self.host_b_voice
            
            try:
                audio = self.provider.synthesize(text, voice_id=voice)
                audio_segments.append(audio)
            except TTSError as e:
                raise TTSError(f"Failed to synthesize segment {i} ({speaker}): {e}")
        
        if not audio_segments:
            raise TTSError("No audio segments were generated")
        
        # Concatenate
        combined = concatenate_wav(audio_segments, pause_seconds=pause_seconds)
        
        # Write output
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(combined)
        
        # Compute duration
        with wave.open(io.BytesIO(combined), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration = frames / rate
        
        return {
            "output_path": str(output_path),
            "duration_seconds": round(duration, 2),
            "segment_count": len(audio_segments),
        }
    
    def close(self):
        self.provider.close()
