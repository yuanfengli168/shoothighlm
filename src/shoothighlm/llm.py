"""Shared LLM client + token usage tracking.

Six modules (mindmap, flashcard, guide, infographic, podcast, tables)
all hit the Ollama /api/generate endpoint with the same pattern.
This module centralizes that call so we can:

  1. Capture token usage (`prompt_eval_count`, `eval_count`) from
     the Ollama response, which the bare HTTP call drops on the
     floor.
  2. Optionally route the call through a custom base_url (e.g. a
     proxy or a different port).
  3. Keep the same exception/timeout behavior every existing
     caller already handles.

The shape is intentionally simple: `call_ollama()` returns
`(text, usage)`. The text is the `response` field from Ollama
(the LLM's output). The usage is a small dataclass with the
token counts (or zeros if the provider doesn't return them).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class LLMUsage:
    """Token usage for a single LLM call.

    Ollama returns `prompt_eval_count` (input tokens) and
    `eval_count` (output tokens) in the response body. Other
    providers may or may not — we fall back to `0` for any
    field that's missing, so callers can always do arithmetic
    on these without None-checks.
    """

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMError(Exception):
    """Base class for LLM client errors."""


def call_ollama(
    base_url: str,
    model: str,
    prompt: str,
    *,
    timeout_s: float = 600.0,
    client: Optional[httpx.Client] = None,
) -> tuple[str, LLMUsage]:
    """Call the Ollama /api/generate endpoint and return (text, usage).

    This is a thin wrapper that handles three things every caller
    needs:

      1. The POST + raise_for_status, with a configurable timeout.
      2. Extracting the `response` field from the JSON body.
      3. Extracting `prompt_eval_count` and `eval_count` for
         token tracking.

    Args:
        base_url: Ollama API base (e.g. "http://127.0.0.1:11434").
        model: Model name (e.g. "qwen3.5:cloud").
        prompt: The full prompt string.
        timeout_s: Request timeout in seconds. Default 600s (10 min)
            because cloud models with thinking mode can take
            3-5 min on first call.
        client: Optional pre-existing httpx.Client. If None, we
            create one for this call. Useful for tests where you
            want to share a mocked client.

    Returns:
        A tuple `(text, usage)`:
          - text: the LLM's response text (the `response` field).
          - usage: token counts (input + output).

    Raises:
        httpx.HTTPError: on connection / HTTP errors. (The existing
            6 callers already catch this; we don't translate it.)
        LLMError: if the response body is malformed (no `response`
            field).
    """
    # We use a managed client unless the caller passed one. This
    # keeps the API simple (one call = one HTTP round trip) and
    # matches the existing 6 call sites' behavior.
    if client is None:
        client = httpx.Client(timeout=timeout_s)

    start = time.monotonic()
    response = client.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
    )
    response.raise_for_status()
    duration_s = time.monotonic() - start

    body = response.json()

    # The `response` field is the actual LLM text. If it's missing,
    # the response body is malformed (e.g. a 200 with an error).
    if "response" not in body:
        raise LLMError(
            f"Ollama response missing 'response' field. "
            f"Status {response.status_code}, body: {body!r}"
        )
    text = body["response"]

    # Token usage. Ollama returns these as int; some proxies may
    # omit them. We fall back to 0 in that case.
    usage = LLMUsage(
        input_tokens=int(body.get("prompt_eval_count", 0) or 0),
        output_tokens=int(body.get("eval_count", 0) or 0),
    )

    return text, usage
