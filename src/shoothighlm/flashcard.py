"""Flashcard generation from PDF content"""

from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
import json
import httpx
from .sampling import stratified_sample, head_sample
from .llm import LLMUsage, call_ollama


@dataclass
class Flashcard:
    """A flashcard with question and answer"""
    id: str
    question: str
    answer: str
    source: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "source": self.source,
            "tags": self.tags,
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        lines = [
            f"### {self.question}",
            "",
            f"**Answer:** {self.answer}",
        ]
        
        if self.source:
            lines.append(f"\n*Source: {self.source}*")
        
        if self.tags:
            lines.append(f"\nTags: {', '.join(self.tags)}")
        
        return "\n".join(lines)
    
    def to_anki_csv(self) -> str:
        """Convert to Anki CSV format (question, answer, tags)"""
        tags_str = " ".join(self.tags) if self.tags else ""
        # Escape quotes and commas
        question = self.question.replace('"', '""')
        answer = self.answer.replace('"', '""')
        return f'"{question}","{answer}","{tags_str}"'


class FlashcardGenerator:
    """Generate flashcards from text using LLM"""
    
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
        num_cards: int = 10,
        source: str = "",
        use_full: bool = False,
    ) -> Tuple[List[Flashcard], LLMUsage]:
        """
        Generate flashcards from text.

        Args:
            text: Text content to generate cards from
            num_cards: Number of flashcards to generate
            source: Source document name
            use_full: If True, use a larger prompt (50K chars) for
                higher-fidelity generation on large documents.

        Returns:
            (cards, usage) tuple. `cards` is a list of Flashcard
            objects; `usage` is LLMUsage with token counts.
        """
        # Truncate if too long. Default 12K uses stratified sampling
        # (start + middle + end) so long books don't just sample the
        # intro. --full uses 50K chars in head_sample mode.
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = (stratified_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))
        
        prompt = f"""You are a flashcard generation expert. Create study flashcards from the following text.

## Instructions:
- Generate exactly {num_cards} flashcards
- Questions should test understanding, not just memorization
- Answers should be concise but complete (1-3 sentences)
- Focus on key concepts, definitions, and relationships
- Avoid yes/no questions
- Output ONLY valid JSON array, no other text

## Output Format:
```json
[
  {{
    "id": "card-1",
    "question": "What is...?",
    "answer": "The answer...",
    "tags": ["topic1", "topic2"]
  }}
]
```

## Text to Generate Cards From:
{text}

## Flashcards JSON:
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
            cards_data = json.loads(json_str)
            cards = [
                Flashcard(
                    id=card.get("id", f"card-{i}"),
                    question=card.get("question", ""),
                    answer=card.get("answer", ""),
                    source=source,
                    tags=card.get("tags", []),
                )
                for i, card in enumerate(cards_data)
            ]
            return cards, usage
        except json.JSONDecodeError:
            # Fallback: return empty list (and the usage we still have)
            return [], usage
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
