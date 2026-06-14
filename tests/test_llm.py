"""Tests for the shared LLM client + token usage tracker."""

import json
from unittest.mock import Mock, patch

import httpx
import pytest

from shoothighlm.llm import LLMError, LLMUsage, call_ollama


def _make_mock_response(
    response_text: str = "Hello world",
    status_code: int = 200,
    prompt_eval_count: int = 100,
    eval_count: int = 50,
    body_extra: dict | None = None,
) -> Mock:
    """Build a mock httpx.Response for an Ollama /api/generate call."""
    body = {"response": response_text, "prompt_eval_count": prompt_eval_count, "eval_count": eval_count}
    if body_extra:
        body.update(body_extra)
    mock = Mock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = body
    mock.raise_for_status = Mock()
    return mock


def test_call_ollama_returns_text_and_usage():
    """Happy path: text + token usage both returned."""
    mock_client = Mock()
    mock_client.post.return_value = _make_mock_response(
        response_text="Extracted mindmap...",
        prompt_eval_count=6500,
        eval_count=1800,
    )

    text, usage = call_ollama(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:cloud",
        prompt="Extract a mindmap",
        client=mock_client,
    )

    assert text == "Extracted mindmap..."
    assert usage.input_tokens == 6500
    assert usage.output_tokens == 1800
    assert usage.total == 8300


def test_call_ollama_missing_token_fields_uses_zero():
    """If the provider doesn't return token counts, we get zeros.

    This handles proxies or older Ollama versions that don't
    include `prompt_eval_count` / `eval_count`. Callers can
    always do arithmetic on the usage fields without None-checks.
    """
    mock_client = Mock()
    mock_client.post.return_value = _make_mock_response(
        response_text="x", prompt_eval_count=0, eval_count=0
    )
    # Simulate: the body is missing the token fields entirely
    mock_client.post.return_value.json.return_value = {"response": "x"}

    text, usage = call_ollama(
        base_url="http://x", model="m", prompt="p", client=mock_client
    )
    assert text == "x"
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0


def test_call_ollama_missing_response_field_raises():
    """Malformed response body (no `response` field) raises LLMError."""
    mock_client = Mock()
    mock_client.post.return_value = Mock(spec=httpx.Response)
    mock_client.post.return_value.status_code = 200
    mock_client.post.return_value.json.return_value = {"error": "oops"}
    mock_client.post.return_value.raise_for_status = Mock()

    with pytest.raises(LLMError) as exc_info:
        call_ollama(
            base_url="http://x", model="m", prompt="p", client=mock_client
        )
    assert "missing 'response' field" in str(exc_info.value)


def test_call_ollama_http_error_propagates():
    """HTTP errors (e.g. 500) propagate via raise_for_status."""
    mock_client = Mock()
    mock_client.post.return_value = _make_mock_response(status_code=500)
    mock_client.post.return_value.raise_for_status.side_effect = (
        httpx.HTTPStatusError("500", request=Mock(), response=Mock())
    )

    with pytest.raises(httpx.HTTPStatusError):
        call_ollama(
            base_url="http://x", model="m", prompt="p", client=mock_client
        )


def test_call_ollama_uses_correct_endpoint():
    """The POST hits /api/generate with the expected JSON body."""
    mock_client = Mock()
    mock_client.post.return_value = _make_mock_response()

    call_ollama(
        base_url="http://127.0.0.1:11434",
        model="qwen3.5:cloud",
        prompt="My prompt",
        client=mock_client,
    )

    # Verify the URL and payload
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://127.0.0.1:11434/api/generate"
    assert kwargs["json"]["model"] == "qwen3.5:cloud"
    assert kwargs["json"]["prompt"] == "My prompt"
    assert kwargs["json"]["stream"] is False


def test_llm_usage_total():
    """LLMUsage.total is the sum of input + output."""
    u = LLMUsage(input_tokens=100, output_tokens=50)
    assert u.total == 150
    u2 = LLMUsage()  # defaults
    assert u2.total == 0
