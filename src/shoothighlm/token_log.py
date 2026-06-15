"""Token usage logging helpers.

Writes per-call usage records to both:
- JSONL: output/tokens.log (append-only)
- CSV:   output/tokens.csv (spreadsheet-friendly)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .llm import LLMUsage


@dataclass
class TokenLogEntry:
    """Single LLM call accounting record."""

    ts: str
    notebook: str
    command: str
    source: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_s: float
    status: str
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "notebook": self.notebook,
            "command": self.command,
            "source": self.source,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "duration_s": self.duration_s,
            "status": self.status,
            "error": self.error,
        }


class TokenLogger:
    """Append token usage records under a notebook output directory."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.output_dir / "tokens.log"
        self.csv_path = self.output_dir / "tokens.csv"

    def log(
        self,
        *,
        notebook: str,
        command: str,
        source: str,
        model: str,
        usage: Optional[LLMUsage],
        duration_s: float,
        status: str,
        error: str = "",
    ) -> TokenLogEntry:
        """Persist one record to JSONL + CSV and return the entry."""
        usage = usage or LLMUsage()
        entry = TokenLogEntry(
            ts=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            notebook=notebook,
            command=command,
            source=source,
            model=model,
            input_tokens=int(usage.input_tokens),
            output_tokens=int(usage.output_tokens),
            duration_s=round(float(duration_s), 3),
            status=status,
            error=error,
        )

        self._append_jsonl(entry)
        self._append_csv(entry)
        return entry

    def _append_jsonl(self, entry: TokenLogEntry) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def _append_csv(self, entry: TokenLogEntry) -> None:
        fieldnames = [
            "ts",
            "notebook",
            "command",
            "source",
            "model",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_s",
            "status",
            "error",
        ]
        write_header = not self.csv_path.exists()
        with self.csv_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(entry.to_dict())
