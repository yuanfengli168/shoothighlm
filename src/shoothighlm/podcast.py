"""Podcast script generation from PDF content"""

from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
import json
import httpx


@dataclass
class PodcastScript:
    """A podcast script with two hosts"""
    title: str
    duration_minutes: int
    host_a_name: str
    host_b_name: str
    segments: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "duration_minutes": self.duration_minutes,
            "host_a_name": self.host_a_name,
            "host_b_name": self.host_b_name,
            "segments": self.segments,
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        lines = [
            f"# {self.title}",
            "",
            f"**Duration:** {self.duration_minutes} minutes",
            f"**Hosts:** {self.host_a_name} & {self.host_b_name}",
            "",
            "---",
            "",
        ]
        
        for segment in self.segments:
            speaker = segment["speaker"]
            text = segment["text"]
            lines.append(f"**{speaker}:** {text}")
            lines.append("")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


class PodcastGenerator:
    """Generate podcast scripts from text using LLM"""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
        host_a_name: str = "Alex",
        host_b_name: str = "Jamie",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        self.host_a_name = host_a_name
        self.host_b_name = host_b_name
        self.client = httpx.Client(timeout=120.0)
    
    def generate(
        self,
        text: str,
        title: str = "Document Summary",
        duration_minutes: int = 5,
    ) -> PodcastScript:
        """
        Generate a two-voice podcast script from text.
        
        Args:
            text: Text content to generate script from
            title: Title for the podcast
            duration_minutes: Target duration (affects script length)
        
        Returns:
            PodcastScript object
        """
        # Truncate if too long
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars] + "... [truncated]"
        
        # Estimate number of dialogues based on duration
        # ~150 words per minute, ~20 words per dialogue line
        num_dialogues = int((duration_minutes * 150) / 20)
        
        prompt = f"""You are a podcast script writer. Create an engaging two-host podcast script based on the following text.

## Instructions:
- Create a natural, conversational script between two hosts
- Host A ({self.host_a_name}) leads the discussion
- Host B ({self.host_b_name}) asks questions and adds insights
- Make it engaging and easy to understand
- Include a brief intro and conclusion
- Generate approximately {num_dialogues} dialogue exchanges
- Output ONLY valid JSON, no other text

## Output Format:
```json
{{
  "title": "Podcast Title",
  "duration_minutes": 5,
  "host_a_name": "Alex",
  "host_b_name": "Jamie",
  "segments": [
    {{"speaker": "Alex", "text": "Welcome to the show..."}},
    {{"speaker": "Jamie", "text": "Thanks for having me..."}},
    ...
  ]
}}
```

## Source Material:
- Title: {title}
- Duration: {duration_minutes} minutes

## Text to Adapt:
{text}

## Podcast Script JSON:
"""
        
        response = self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        
        # Parse JSON from response
        output = response.json()["response"]
        
        # Extract JSON from markdown code blocks
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()
        
        try:
            data = json.loads(json_str)
            return PodcastScript(
                title=data.get("title", title),
                duration_minutes=data.get("duration_minutes", duration_minutes),
                host_a_name=data.get("host_a_name", self.host_a_name),
                host_b_name=data.get("host_b_name", self.host_b_name),
                segments=data.get("segments", []),
            )
        except json.JSONDecodeError:
            # Fallback: return empty script
            return PodcastScript(
                title=title,
                duration_minutes=duration_minutes,
                host_a_name=self.host_a_name,
                host_b_name=self.host_b_name,
                segments=[
                    {"speaker": self.host_a_name, "text": "Failed to generate script."},
                ],
            )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
