"""Embedding generation via Ollama"""

import httpx
from typing import List


class Embedder:
    """Generate embeddings using Ollama (local or cloud)"""
    
    def __init__(self, model: str = "bge-m3", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.base_url = base_url
        self.client = httpx.Client(timeout=60.0)
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        response = self.client.post(
            f"{self.base_url}/api/embeddings",
            json={
                "model": self.model,
                "prompt": text,
            },
        )
        response.raise_for_status()
        return response.json()["embedding"]
    
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
