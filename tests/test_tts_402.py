"""Test that Fish Audio's 402 (Insufficient Credit) gives a clear, actionable error.

Previously the user would see "Fish Audio TTS request failed: 402 Payment
Required" with no hint that this means "you have $0 API credit" or how to
fix it. Now the error message should explain the situation and point to
the credit page or CosyVoice as an alternative.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from shoothighlm.tts import FishAudioProvider, TTSError


def test_fish_audio_402_gives_actionable_error():
    """When Fish Audio returns 402, the error should mention
    'Insufficient API credit' and link to the credit page."""
    provider = FishAudioProvider(api_key="fake-key")

    mock_response = MagicMock()
    mock_response.status_code = 402
    # raise_for_status would normally be called, but we short-circuit on 402

    with patch.object(provider.client, "post", return_value=mock_response):
        with pytest.raises(TTSError) as exc_info:
            provider.synthesize("hello world")

    msg = str(exc_info.value)
    assert "Insufficient API credit" in msg
    assert "fish.audio/app/developers" in msg
    assert "CosyVoice" in msg


def test_fish_audio_500_wraps_with_generic_error():
    """Non-402 errors should still produce a clean error message."""
    provider = FishAudioProvider(api_key="fake-key")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "server error",
        request=MagicMock(),
        response=MagicMock(status_code=500),
    )

    with patch.object(provider.client, "post", return_value=mock_response):
        with pytest.raises(TTSError) as exc_info:
            provider.synthesize("hello world")

    assert "Fish Audio TTS request failed" in str(exc_info.value)
