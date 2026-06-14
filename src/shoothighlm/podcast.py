"""Podcast script generation from PDF content"""

from typing import List, Dict, Any
from dataclasses import dataclass
import json
import httpx
from .sampling import stratified_sample, head_sample
from .llm import LLMUsage, call_ollama


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


def _parse_markdown_script(md_text: str) -> dict:
    """Parse a markdown podcast script back into a dict.

    Inverse of `PodcastScript.to_markdown()`. Used by `shoot-high
    synthesize` so users can feed it either a `.json` (the natural
    format) or a `.md` (the human-readable default) without having
    to regenerate the script.

    Markdown shape:
        # Title
        **Duration:** 5 minutes
        **Hosts:** Alex & Jamie
        ---
        **Alex:** Hello ...
        **Jamie:** Hi ...

    Returns: dict with keys `title`, `host_a_name`, `host_b_name`,
    `segments: [{speaker, text}, ...]`.
    """
    import re

    title = ""
    host_a_name = "Alex"
    host_b_name = "Jamie"
    segments: list[dict] = []

    # Title: first "# ..." line
    title_match = re.search(r"^#\s+(.+?)\s*$", md_text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()

    # Hosts line: **Hosts:** A & B
    hosts_match = re.search(
        r"\*\*Hosts:\*\*\s*(.+?)\s*$", md_text, re.MULTILINE
    )
    if hosts_match:
        hosts_str = hosts_match.group(1).strip()
        # Split on " & " (the format we use)
        parts = re.split(r"\s*[&&]\s*", hosts_str, maxsplit=1)
        if len(parts) == 2:
            host_a_name, host_b_name = parts[0].strip(), parts[1].strip()

    # Segments: **Speaker:** text  (multiline, until next **Speaker:** or EOF)
    # Skip lines whose label is a known metadata field (Duration, Hosts, etc.)
    meta_labels = {"duration", "hosts", "title", "date", "source", "language"}

    seg_pattern = re.compile(
        r"^\*\*([^*]+?):\*\*\s*(.*?)(?=^\*\*[^*]+?:\*\*|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for m in seg_pattern.finditer(md_text):
        speaker = m.group(1).strip()
        if speaker.lower() in meta_labels:
            continue
        text = m.group(2).strip()
        # Collapse multiple newlines into single spaces
        text = re.sub(r"\s*\n\s*", " ", text)
        if text:
            segments.append({"speaker": speaker, "text": text})

    return {
        "title": title,
        "host_a_name": host_a_name,
        "host_b_name": host_b_name,
        "segments": segments,
    }


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
        # See mindmap.py for the rationale on 600s timeout
        self.client = httpx.Client(timeout=600.0)
    
    def generate(
        self,
        text: str,
        title: str = "Document Summary",
        duration_minutes: int = 5,
        use_full: bool = False,
    ) -> PodcastScript:
        """
        Generate a two-voice podcast script from text.

        Args:
            text: Text content to generate script from
            title: Title for the podcast
            duration_minutes: Target duration (affects script length)
            use_full: If True, use a larger prompt (50K chars) for
                higher-fidelity generation on large documents.

        Returns:
            PodcastScript object
        """
        # Truncate if too long. Default 12K uses stratified sampling
        # (start + middle + end) so long books don't just sample the
        # intro. --full uses 50K chars in head_sample mode.
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = (stratified_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))
        
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
