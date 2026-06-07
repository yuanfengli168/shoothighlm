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
    ):
        self.vectorstore = vectorstore
        self.embedder = embedder
        self.chat_model = chat_model
        self.base_url = base_url
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.client = httpx.Client(timeout=120.0)
    
    def retrieve(self, query: str) -> List[SearchResult]:
        """Retrieve relevant chunks for a query"""
        query_embedding = self.embedder.embed(query)
        return self.vectorstore.search(query_embedding, top_k=self.top_k)
    
    def build_context(self, results: List[SearchResult]) -> Tuple[str, List[Citation]]:
        """Build context string from search results"""
        citations = []
        context_parts = []
        
        for i, result in enumerate(results, 1):
            # Filter by similarity (distance is 1 - similarity for cosine)
            similarity = 1 - result.distance
            if similarity < self.min_similarity:
                continue
            
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
        
        # Add citations to answer
        if citations:
            citation_list = "\n\n---\n**Sources:**\n"
            for i, cit in enumerate(citations, 1):
                citation_list += f"\n[{i}] {cit.source} (relevance: {cit.relevance_score:.2f})"
            answer += citation_list
        
        return ChatResponse(
            answer=answer,
            citations=citations,
            model=self.chat_model,
        )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
