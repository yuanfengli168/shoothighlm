"""Tests for the CLI helper functions: _is_cloud_error and resolve_chat_model.

These are not directly covered by command tests because they live in cli.py
but aren't called via the command surface. Adding direct tests here
restores the 93% coverage gate.
"""

import os
from unittest.mock import Mock

import httpx
import pytest

from shoothighlm.cli import _is_cloud_error, resolve_chat_model


# ============== _is_cloud_error ===============

def test_is_cloud_error_read_timeout():
    """ReadTimeout from Ollama is a cloud-side issue (cold start)."""
    assert _is_cloud_error(httpx.ReadTimeout("timed out")) is True


def test_is_cloud_error_connect_error():
    """ConnectError means we couldn't reach Ollama at all."""
    assert _is_cloud_error(httpx.ConnectError("connection refused")) is True


def test_is_cloud_error_connect_timeout():
    """ConnectTimeout is also a cloud-side issue."""
    assert _is_cloud_error(httpx.ConnectTimeout("connect timed out")) is True


def test_is_cloud_error_5xx():
    """5xx HTTP responses are server-side issues."""
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
    response = httpx.Response(503, request=request)
    err = httpx.HTTPStatusError("Service Unavailable", request=request, response=response)
    assert _is_cloud_error(err) is True


def test_is_cloud_error_500():
    """500 (internal server error) is a cloud error."""
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
    response = httpx.Response(500, request=request)
    err = httpx.HTTPStatusError("Server Error", request=request, response=response)
    assert _is_cloud_error(err) is True


def test_is_cloud_error_400_not_cloud():
    """4xx is a client error (bad request, etc.) — not a cloud issue."""
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
    response = httpx.Response(400, request=request)
    err = httpx.HTTPStatusError("Bad Request", request=request, response=response)
    assert _is_cloud_error(err) is False


def test_is_cloud_error_normal_exception():
    """Non-HTTP exceptions (e.g. JSON parse errors) are NOT cloud issues."""
    assert _is_cloud_error(ValueError("bad json from model")) is False
    assert _is_cloud_error(RuntimeError("LLM returned unexpected")) is False
    assert _is_cloud_error(KeyError("missing_key")) is False


# ============== resolve_chat_model ==============

def test_resolve_chat_model_model_override_wins():
    """Priority 1: --model CLI flag wins over everything else."""
    config = {"models": {"chat": "default-model", "chat_local": "local-model"}}
    result = resolve_chat_model(config, use_local=False, model_override="explicit-model")
    assert result == "explicit-model"


def test_resolve_chat_model_use_local_flag():
    """Priority 2: --use-local uses chat_local."""
    config = {"models": {"chat": "default-model", "chat_local": "local-model"}}
    result = resolve_chat_model(config, use_local=True, model_override=None)
    assert result == "local-model"


def test_resolve_chat_model_use_local_overrides_env():
    """--use-local beats SHOOTHIGHLM_CHAT env var."""
    config = {"models": {"chat": "default-model", "chat_local": "local-model"}}
    os.environ["SHOOTHIGHLM_CHAT"] = "env-model"
    try:
        result = resolve_chat_model(config, use_local=True, model_override=None)
        assert result == "local-model"
    finally:
        del os.environ["SHOOTHIGHLM_CHAT"]


def test_resolve_chat_model_env_var(monkeypatch):
    """Priority 3: SHOOTHIGHLM_CHAT env var beats config."""
    monkeypatch.setenv("SHOOTHIGHLM_CHAT", "env-model")
    config = {"models": {"chat": "default-model", "chat_local": "local-model"}}
    result = resolve_chat_model(config, use_local=False, model_override=None)
    assert result == "env-model"


def test_resolve_chat_model_config_default():
    """Priority 4: models.chat from config."""
    config = {"models": {"chat": "default-model", "chat_local": "local-model"}}
    result = resolve_chat_model(config, use_local=False, model_override=None)
    assert result == "default-model"


def test_resolve_chat_model_hardcoded_fallback():
    """Priority 5: hardcoded qwen3.5:cloud when config is empty."""
    # Clear env var to ensure it's not picked up
    os.environ.pop("SHOOTHIGHLM_CHAT", None)
    result = resolve_chat_model({}, use_local=False, model_override=None)
    assert result == "qwen3.5:cloud"


def test_resolve_chat_model_hardcoded_local_fallback():
    """Priority 5: hardcoded qwen3.5:27b when use_local and no chat_local."""
    os.environ.pop("SHOOTHIGHLM_CHAT", None)
    result = resolve_chat_model({}, use_local=True, model_override=None)
    assert result == "qwen3.5:27b"


def test_resolve_chat_model_partial_config():
    """User config may have some keys but not others — merge with defaults."""
    config = {"models": {"chat": "custom-cloud"}}  # missing chat_local
    result = resolve_chat_model(config, use_local=True, model_override=None)
    # Should fall through to hardcoded local fallback
    assert result == "qwen3.5:27b"


def test_resolve_chat_model_all_priorities(monkeypatch):
    """Integration: all 4 priorities in one call, --model wins."""
    monkeypatch.setenv("SHOOTHIGHLM_CHAT", "env-model")
    config = {"models": {"chat": "config-model", "chat_local": "local-model"}}
    # With override, override wins
    assert resolve_chat_model(config, use_local=True, model_override="override") == "override"
    # Without override, --use-local wins
    assert resolve_chat_model(config, use_local=True, model_override=None) == "local-model"
    # Without use_local, env wins
    assert resolve_chat_model(config, use_local=False, model_override=None) == "env-model"
    # Without env, config wins
    monkeypatch.delenv("SHOOTHIGHLM_CHAT", raising=False)
    assert resolve_chat_model(config, use_local=False, model_override=None) == "config-model"
