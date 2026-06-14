"""Notebook Guide generation — auto-summary, topics, and suggested questions"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
import json
import httpx
from .sampling import stratified_sample, head_sample
from .llm import LLMUsage, call_ollama


@dataclass
class NotebookGuide:
    """Auto-generated guide for a notebook (collection of documents)"""
    title: str
    summary: str
    key_topics: List[str] = field(default_factory=list)
    suggested_questions: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "summary": self.summary,
            "key_topics": self.key_topics,
            "suggested_questions": self.suggested_questions,
            "sources": self.sources,
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        lines = [
            f"# 📓 {self.title}",
            "",
            "## 概述 (Summary)",
            "",
            self.summary,
            "",
        ]
        
        if self.key_topics:
            lines.extend([
                "## 🎯 关键主题 (Key Topics)",
                "",
            ])
            for topic in self.key_topics:
                lines.append(f"- {topic}")
            lines.append("")
        
        if self.suggested_questions:
            lines.extend([
                "## 💡 建议问题 (Suggested Questions)",
                "",
            ])
            for i, q in enumerate(self.suggested_questions, 1):
                lines.append(f"{i}. {q}")
            lines.append("")
        
        if self.sources:
            lines.extend([
                "---",
                "",
                f"*Sources: {len(self.sources)} document(s) — {', '.join(self.sources)}*",
            ])
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class GuideGenerator:
    """Generate notebook guides from document text using LLM"""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # See mindmap.py for the rationale on 600s timeout
        self.client = httpx.Client(timeout=600.0)
    
    def generate(
        self,
        text: str,
        title: str = "Notebook Guide",
        sources: List[str] = None,
        num_questions: int = 5,
        use_full: bool = False,
    ) -> Tuple[NotebookGuide, LLMUsage]:
        """
        Generate a notebook guide from text.

        Args:
            text: Combined text from all documents in the notebook
            title: Title for the guide (usually notebook name)
            sources: List of source document names
            num_questions: Number of suggested questions to generate
            use_full: If True, use a larger prompt (50K chars) for
                higher-fidelity generation on large documents.

        Returns:
            (guide, usage) tuple. `guide` is a NotebookGuide object;
            `usage` is LLMUsage with token counts.
        """
        sources = sources or []

        # Truncate if too long. Default 12K uses stratified sampling
        # (start + middle + end) so long books don't just sample the
        # intro. --full uses 50K chars in head_sample mode.
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = (stratified_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))
        
        prompt = f"""You are a research assistant. Analyze the following documents and generate a notebook guide.

## Instructions:
- Write a 2-3 paragraph summary capturing the main themes and insights
- List 5-8 key topics (concepts, themes, or important entities)
- Suggest {num_questions} thoughtful questions a reader might want to explore
- Questions should be specific enough to guide exploration, not generic
- Output ONLY valid JSON, no other text

## Output Format:
```json
{{
  "summary": "2-3 paragraph summary...",
  "key_topics": ["Topic 1", "Topic 2", "Topic 3"],
  "suggested_questions": [
    "Specific question 1?",
    "Specific question 2?",
    "Specific question 3?"
  ]
}}
```

## Documents to Analyze:
{text}

## Notebook Guide JSON:
"""

        output, usage = call_ollama(
            base_url=self.base_url,
            model=self.chat_model,
            prompt=prompt,
            client=self.client,
        )

        # Extract JSON from markdown code blocks
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()

        try:
            data = json.loads(json_str)
            return (
                NotebookGuide(
                    title=title,
                    summary=data.get("summary", ""),
                    key_topics=data.get("key_topics", []),
                    suggested_questions=data.get("suggested_questions", []),
                    sources=sources,
                ),
                usage,
            )
        except json.JSONDecodeError:
            # Fallback: return minimal guide (and the usage we have)
            return (
                NotebookGuide(
                    title=title,
                    summary="Failed to generate guide from documents.",
                    key_topics=[],
                    suggested_questions=[],
                    sources=sources,
                ),
                usage,
            )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
