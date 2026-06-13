"""Mind map extraction from PDF content"""

from typing import List, Dict, Any
from dataclasses import dataclass, field
import json
import httpx
from .sampling import even_sample, head_sample


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

        The mindmap is built by ENUMERATING the book's actual content
        (parts, chapters, named principles, arguments), not by
        summarizing it. The default prompt targets 80-150 nodes across
        3-4 levels of depth, in the same shape as a real table of
        contents — see research/mindmap-comparison-vs-notebooklm.md for
        the design rationale.

        Args:
            text: Text content to analyze
            title: Title for the root node
            use_full: If True, use a larger 50K-char budget in
                head_sample mode (front-loaded — good for medium books
                where the intro summarizes the whole). Default uses
                25K chars in even_sample mode (uniform — good for
                enumerating the whole structure of a long book).

        Returns:
            MindMapNode tree structure
        """
        # Default 25K chars (~6K tokens) with even sampling — covers
        # more of the book than the old 12K default without paying the
        # --full latency cost. --full uses 50K head_sample (faster
        # and good when the intro is representative of the whole book).
        max_chars = 50000 if use_full else 25000
        if len(text) > max_chars:
            text = (even_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))

        prompt = f"""You are a book table-of-contents extractor. Extract a HIERARCHICAL, COMPREHENSIVE mind map of the book — NOT a summary.

## Approach
- ENUMERATE, do not summarize. If the book has 12 chapters, the map has 12 level-1 nodes.
- Each leaf should be a SPECIFIC named principle, method, story, definition, or argument from the book — never a vague theme like "工作态度" (work attitude). Prefer the book's own terminology: if the book calls a concept "极度认真工作", use that exact phrasing.
- Aim for 80–150 total nodes. A 1,000-page book deserves a rich map, not a 10-bullet list.
- Use the book's own language (Chinese stays Chinese, English stays English, etc.).

## Structure (3–4 levels of depth)
- Level 1: parts / sections / major themes (5–10 nodes)
- Level 2: chapters or major arguments (3–7 per level-1 node)
- Level 3: key concepts under each chapter (2–5 per level-2 node)
- Level 4 (optional): concrete examples, named people, formulas, quotable phrases
- Every node has a short title (3–12 words, in the book's language).
- Use the `notes` field for a 1-sentence explanation ONLY when the title alone is ambiguous.

## Output Format (strict)
```json
{{
  "id": "root",
  "title": "<book title>",
  "notes": "",
  "children": [
    {{
      "id": "part-1",
      "title": "Part 1 Name",
      "notes": "",
      "children": [
        {{
          "id": "ch-1",
          "title": "Chapter 1 Name",
          "notes": "",
          "children": [
            {{"id": "concept-1", "title": "Named principle or argument", "notes": "", "children": []}}
          ]
        }}
      ]
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
