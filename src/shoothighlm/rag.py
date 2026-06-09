"""RAG (Retrieval Augmented Generation) for chat with citations"""

from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass
import httpx
import json

from .vectorstore import VectorStore, SearchResult
from .embedding import Embedder


@dataclass
class Citation:
    """A citation to a source chunk"""
    chunk_id: str
    source: str
    text: str
    relevance_score: float


@dataclass
class ChatResponse:
    """Chat response with citations"""
    answer: str
    citations: List[Citation]
    model: str


class RAGChat:
    """RAG-based chat with citations"""
    
    def __init__(
        self,
        vectorstore: VectorStore,
        embedder: Embedder,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
        top_k: int = 5,
        min_similarity: float = 0.7,
        fallback_top_n: int = 3,
    ):
        self.vectorstore = vectorstore
        self.embedder = embedder
        self.chat_model = chat_model
        self.base_url = base_url
        self.top_k = top_k
        self.min_similarity = min_similarity
        # When no chunk clears min_similarity, fall back to the top-N
        # results anyway. This is critical for bge-m3 + Chinese, where
        # observed max cosine sim is often 0.40–0.55 and a strict
        # threshold would return "couldn't find relevant information"
        # for valid questions whose answer IS in the corpus.
        self.fallback_top_n = max(1, fallback_top_n)
        # See mindmap.py for the rationale on 600s timeout
        self.client = httpx.Client(timeout=600.0)
    
    def retrieve(self, query: str) -> List[SearchResult]:
        """Retrieve relevant chunks for a query"""
        query_embedding = self.embedder.embed(query)
        return self.vectorstore.search(query_embedding, top_k=self.top_k)
    
    def build_context(self, results: List[SearchResult]) -> Tuple[str, List[Citation]]:
        """Build context string from search results.

        Two-stage filtering:
        1. Keep all results whose similarity clears `min_similarity`
        2. If stage 1 returned nothing, fall back to the top-N results
           regardless of threshold. Better to answer from low-similarity
           chunks than to say "couldn't find anything" when the answer
           is clearly in the corpus.
        """
        if not results:
            return "", []

        # Stage 1: threshold filter
        above_threshold = [
            r for r in results if (1 - r.distance) >= self.min_similarity
        ]
        chosen = above_threshold if above_threshold else results[: self.fallback_top_n]

        # If we fell back, mark it so the caller can tell the user
        self._used_fallback = bool(above_threshold) is False
        self._best_similarity = 1 - results[0].distance

        citations = []
        context_parts = []
        for i, result in enumerate(chosen, 1):
            similarity = 1 - result.distance
            citation = Citation(
                chunk_id=result.chunk_id,
                source=Path(result.source).name,
                text=result.text[:500] + "..." if len(result.text) > 500 else result.text,
                relevance_score=similarity,
            )
            citations.append(citation)
            context_parts.append(f"[Source {i}: {citation.source}]\n{result.text}")

        context = "\n\n".join(context_parts)
        return context, citations
    
    def chat(self, query: str) -> ChatResponse:
        """Chat with RAG-powered responses"""
        # Retrieve relevant chunks
        results = self.retrieve(query)

        # Build context
        context, citations = self.build_context(results)

        if not citations:
            return ChatResponse(
                answer="I couldn't find relevant information in your documents to answer this question.",
                citations=[],
                model=self.chat_model,
            )
        
        # Build prompt
        prompt = f"""You are a helpful assistant answering questions based on the provided documents.

## Instructions:
- Answer ONLY based on the context below
- If the context doesn't contain enough information, say so
- Include inline citations like [1], [2] when referencing sources
- Be concise but thorough
- Answer in the same language as the question

## Context:
{context}

## Question:
{query}

## Answer:
"""
        
        # Call LLM
        response = self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        answer = response.json()["response"]

        # Add a one-line note if we used the fallback (chunks were below
        # the configured min_similarity). The user should know the answer
        # is best-effort.
        prefix = ""
        if getattr(self, "_used_fallback", False):
            prefix = (
                f"[dim]Note: No chunk exceeded min_similarity="
                f"{self.min_similarity:.2f}. Answer is based on the top "
                f"{len(citations)} result(s) "
                f"(best similarity: {self._best_similarity:.2f}). "
                f"Consider lowering rag.min_similarity in your config "
                f"(e.g. 0.3–0.4 for bge-m3 + Chinese).[/dim]\n\n"
            )

        # Add citations to answer
        if citations:
            citation_list = "\n\n---\n**Sources:**\n"
            for i, cit in enumerate(citations, 1):
                citation_list += f"\n[{i}] {cit.source} (relevance: {cit.relevance_score:.2f})"
            answer = prefix + answer + citation_list
        else:
            answer = prefix + answer

        return ChatResponse(
            answer=answer,
            citations=citations,
            model=self.chat_model,
        )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
