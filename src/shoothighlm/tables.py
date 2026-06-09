"""Data table extraction from PDF content using LLM.

Extracts structured tabular data — useful for comparison tables, statistics
with categories, lists with consistent attributes, and event timelines.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class DataTable:
    """A single extracted data table."""
    
    name: str
    description: str
    columns: List[str]
    rows: List[List[str]]
    source: str = ""
    
    def __post_init__(self) -> None:
        # Normalize: every row must have the same length as columns
        ncols = len(self.columns)
        normalized: List[List[str]] = []
        for row in self.rows:
            row = list(row) + [""] * max(0, ncols - len(row))
            row = [str(cell) if cell is not None else "" for cell in row[:ncols]]
            normalized.append(row)
        self.rows = normalized
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "columns": list(self.columns),
            "rows": [list(r) for r in self.rows],
            "source": self.source,
        }
    
    def to_markdown(self) -> str:
        if not self.columns:
            return f"### {self.name}\n\n_{self.description}_\n\n_(no columns)_\n"
        
        header = "| " + " | ".join(self.columns) + " |"
        sep = "|" + "|".join(["---"] * len(self.columns)) + "|"
        body_lines = [
            "| " + " | ".join(str(c) for c in row) + " |"
            for row in self.rows
        ]
        
        out = f"### {self.name}\n\n"
        if self.description:
            out += f"_{self.description}_\n\n"
        out += header + "\n" + sep + "\n" + "\n".join(body_lines) + "\n"
        return out
    
    def to_csv(self) -> str:
        """Render as CSV. Quotes values containing commas or newlines."""
        def esc(v: str) -> str:
            s = str(v)
            if "," in s or "\n" in s or '"' in s:
                return '"' + s.replace('"', '""') + '"'
            return s
        
        lines = [",".join(esc(c) for c in self.columns)]
        for row in self.rows:
            lines.append(",".join(esc(c) for c in row))
        return "\n".join(lines)
    
    def to_html(self) -> str:
        if not self.columns:
            return (
                f'<table class="data-table">\n'
                f"  <caption>{self.name}</caption>\n"
                f"  <tr><td><em>{self.description}</em></td></tr>\n"
                f"</table>\n"
            )
        
        th = "".join(f"<th>{c}</th>" for c in self.columns)
        body = "\n".join(
            "    <tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in self.rows
        )
        cap = f"  <caption>{self.name}</caption>\n" if self.name else ""
        desc = f"  <p class='desc'><em>{self.description}</em></p>\n" if self.description else ""
        return (
            f"<table class='data-table'>\n"
            f"{cap}{desc}"
            f"  <thead>\n    <tr>{th}</tr>\n  </thead>\n"
            f"  <tbody>\n{body}\n  </tbody>\n"
            f"</table>\n"
        )


class TableExtractor:
    """Extract structured data tables from text using LLM."""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # See mindmap.py for the rationale on 600s timeout
        self.client = httpx.Client(timeout=600.0)
    
    def close(self) -> None:
        self.client.close()
    
    def _extract_json(self, output: str) -> Any:
        """Pull a JSON object/array out of an LLM response that may wrap it in markdown."""
        output = output.strip()
        # ```json ... ``` block
        m = re.search(r"```json\s*(.*?)\s*```", output, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        # ``` ... ``` block (no language)
        m = re.search(r"```\s*(.*?)\s*```", output, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        # Try direct parse
        return json.loads(output)
    
    def extract(
        self,
        text: str,
        max_tables: int = 3,
        source: str = "",
        use_full: bool = False,
    ) -> List[DataTable]:
        """Extract up to `max_tables` data tables from text.

        Args:
            text: Source text (PDF content)
            max_tables: Maximum number of tables to return
            source: Source document name for attribution
            use_full: If True, use a larger prompt (50K chars) for
                higher-fidelity extraction on large documents.

        Returns:
            List of DataTable objects (may be empty)

        Raises:
            RuntimeError: If LLM call fails or returns invalid JSON
        """
        if not text or not text.strip():
            return []

        # Truncate very long text. Default 12K chars keeps extraction
        # fast; --full uses 50K to cover more of the source.
        max_chars = 50000 if use_full else 12000
        if len(text) > max_chars:
            text = text[:max_chars] + "... [truncated]"
        
        prompt = f"""You are a data extraction expert. Extract structured tabular data from the following text.

## Instructions:
- Identify up to {max_tables} meaningful tables in the text (comparisons, statistics, lists with attributes, timelines)
- Skip tables that would be trivial (1 row, 1 column, or just repeating the same value)
- Column names should be concise and descriptive
- Row data should be the actual values from the text (paraphrase if needed for clarity)
- Output ONLY a valid JSON array, no other text

## Output Format:
```json
[
  {{
    "name": "Short title for the table",
    "description": "1-sentence caption explaining what the table shows",
    "columns": ["Column 1", "Column 2", "Column 3"],
    "rows": [
      ["value1", "value2", "value3"],
      ["value4", "value5", "value6"]
    ]
  }}
]
```

## Source Text:
{text}

## JSON Output:"""
        
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.chat_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(f"LLM request failed: {e}") from e
        
        raw = response.json().get("response", "")
        
        try:
            data = self._extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise RuntimeError(
                f"LLM returned invalid JSON for tables: {e}\n"
                f"Raw response: {raw[:500]}"
            ) from e
        
        if not isinstance(data, list):
            raise RuntimeError(
                f"LLM returned {type(data).__name__}, expected JSON array"
            )
        
        # First: collect all valid tables (filter malformed entries).
        # Then truncate to max_tables.
        # Doing it in this order ensures we don't lose good tables
        # because they came after malformed ones in the LLM response.
        valid_tables: List[DataTable] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                table = DataTable(
                    name=str(item.get("name", "Untitled")).strip() or "Untitled",
                    description=str(item.get("description", "")).strip(),
                    columns=list(item.get("columns", [])),
                    rows=list(item.get("rows", [])),
                    source=source,
                )
            except (TypeError, ValueError):
                # Skip malformed entries
                continue
            if not table.columns:
                continue
            valid_tables.append(table)
        
        return valid_tables[:max_tables]
