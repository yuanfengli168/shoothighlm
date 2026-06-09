"""Mind map extraction from PDF content"""

from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field
import json
import httpx


@dataclass
class MindMapNode:
    """A node in the mind map tree"""
    id: str
    title: str
    children: List['MindMapNode'] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "children": [child.to_dict() for child in self.children],
            "notes": self.notes,
        }
    
    def to_markdown(self, level: int = 1) -> str:
        """Convert to Markdown headings"""
        lines = []
        heading = "#" * min(level, 6)
        lines.append(f"{heading} {self.title}")
        
        if self.notes:
            lines.append(f"\n{self.notes}\n")
        
        for child in self.children:
            lines.append(child.to_markdown(level + 1))
        
        return "\n".join(lines)
    
    def to_opml(self, indent: int = 0) -> str:
        """Convert to OPML outline format"""
        indent_str = "  " * indent
        lines = []
        
        # Escape XML special characters
        title_escaped = self.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        notes_escaped = self.notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        if notes_escaped:
            lines.append(f'{indent_str}<outline text="{title_escaped}" _note="{notes_escaped}">')
        else:
            lines.append(f'{indent_str}<outline text="{title_escaped}">')
        
        for child in self.children:
            lines.append(child.to_opml(indent + 1))
        
        lines.append(f'{indent_str}</outline>')
        return "\n".join(lines)


class MindMapExtractor:
    """Extract mind map structure from text using LLM"""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # 600s timeout: cloud models (qwen3.5:cloud etc.) can take 3-5 min
        # on first call with thinking mode enabled, especially for long
        # 50K-char prompts.
        self.client = httpx.Client(timeout=600.0)
    
    def extract(self, text: str, title: str = "Document", use_full: bool = False) -> MindMapNode:
        """
        Extract mind map structure from text.

        Args:
            text: Text content to analyze
            title: Title for the root node
            use_full: If True, use a larger prompt (50K chars instead of
                the 12K default) for higher-fidelity mind maps of large
                documents. Slower; costs more tokens.

        Returns:
            MindMapNode tree structure
        """
        # Truncate if too long (keep under model context limit)
        # Default 12K = ~3-4K tokens; --full uses 50K = ~12-15K tokens
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "... [truncated]"
        
        prompt = f"""You are a mind map extraction expert. Analyze the following text and extract a hierarchical mind map structure.

## Instructions:
- Identify the main topics and subtopics
- Create a tree structure with 2-4 levels of depth
- Each node should have a clear, concise title (5-15 words)
- Add brief notes (1-2 sentences) for important nodes
- Focus on key concepts, relationships, and structure
- Output ONLY valid JSON, no other text

## Output Format:
```json
{{
  "id": "root",
  "title": "Main Topic",
  "notes": "Brief description",
  "children": [
    {{
      "id": "topic-1",
      "title": "Subtopic 1",
      "notes": "...",
      "children": [...]
    }}
  ]
}}
```

## Document Title: {title}

## Text to Analyze:
{text}

## Mind Map JSON:
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
        
        # Extract JSON from markdown code blocks if present
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()
        
        try:
            data = json.loads(json_str)
            return self._dict_to_node(data)
        except json.JSONDecodeError as e:
            # Fallback: create simple structure
            return MindMapNode(
                id="root",
                title=title,
                notes=f"Failed to parse mind map: {e}\n\nOutput was:\n{output[:500]}",
                children=[],
            )
    
    def _dict_to_node(self, data: Dict[str, Any], parent_id: str = "") -> MindMapNode:
        """Convert dictionary to MindMapNode"""
        node_id = data.get("id", f"node-{parent_id}-{len(parent_id)}")
        title = data.get("title", "Untitled")
        notes = data.get("notes", "")
        children_data = data.get("children", [])
        
        children = []
        for i, child_data in enumerate(children_data):
            child = self._dict_to_node(child_data, node_id)
            children.append(child)
        
        return MindMapNode(
            id=node_id,
            title=title,
            children=children,
            notes=notes,
        )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
