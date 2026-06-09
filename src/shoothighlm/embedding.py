"""Embedding generation via Ollama"""

import httpx
from typing import List


# Per-model character budget. bge-m3 has an 8K-token context but Chinese
# tokenizes inefficiently (often 1 char ≈ 1.5–2 tokens), so we cap raw
# characters at ~6K to stay safely under the limit. Other models use a
# more generous 28K-char cap (≈8K tokens for English-dense text).
_MAX_CHARS_BY_MODEL = {
    "bge-m3": 6_000,        # 8192 tokens, dense Chinese is unsafe above ~6K chars
    "qwen3-embedding": 28_000,
    "nomic-embed-text": 28_000,
    "mxbai-embed-large": 12_000,
}
_DEFAULT_MAX_CHARS = 16_000


def _char_limit_for(model: str) -> int:
    # Match by substring so "bge-m3:latest" or "bge-m3-f16" all hit the cap
    for key, limit in _MAX_CHARS_BY_MODEL.items():
        if key in model:
            return limit
    return _DEFAULT_MAX_CHARS


class Embedder:
    """Generate embeddings using Ollama (local or cloud)"""

    def __init__(self, model: str = "bge-m3", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.base_url = base_url
        self.max_chars = _char_limit_for(model)
        self.client = httpx.Client(timeout=120.0)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        # Cut at the last sentence/paragraph boundary before the limit,
        # falling back to a hard cut. This preserves semantic coherence
        # better than chopping mid-word.
        truncated = text[: self.max_chars]
        for sep in ("\n\n", "。", "！", "？", ". ", "\n"):
            idx = truncated.rfind(sep)
            if idx > self.max_chars * 0.7:
                return truncated[: idx + len(sep)]
        return truncated

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Truncates input to a model-specific character budget to avoid
        Ollama returning 500 'input length exceeds the context length'.
        """
        truncated = self._truncate(text)
        try:
            response = self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": truncated,
                },
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except httpx.HTTPStatusError as e:
            # If the model still complains, try once more with a hard
            # 50% cut, then give up.
            if e.response.status_code == 500 and len(truncated) > 500:
                hard_cut = truncated[: len(truncated) // 2]
                response = self.client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": hard_cut},
                )
                response.raise_for_status()
                return response.json()["embedding"]
            raise

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for text in batch:
                embeddings.append(self.embed(text))
        return embeddings


def get_embedder(model: str = "bge-m3", use_cloud: bool = False) -> Embedder:
    """Get embedder instance"""
    if use_cloud:
        # Ollama Cloud doesn't support embeddings, always local
        pass
    return Embedder(model=model)
