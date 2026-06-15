"""Tests for token usage logging."""

from pathlib import Path

from shoothighlm.llm import LLMUsage
from shoothighlm.token_log import TokenLogger


def test_token_logger_writes_jsonl_and_csv(tmp_path: Path):
    logger = TokenLogger(tmp_path / "output")
    entry = logger.log(
        notebook="book-notebook",
        command="mindmap",
        source="book.pdf",
        model="qwen3.5:cloud",
        usage=LLMUsage(input_tokens=120, output_tokens=30),
        duration_s=1.234,
        status="ok",
    )

    assert entry.input_tokens == 120
    assert entry.output_tokens == 30

    jsonl = (tmp_path / "output" / "tokens.log").read_text(encoding="utf-8")
    csv = (tmp_path / "output" / "tokens.csv").read_text(encoding="utf-8")

    assert '"command": "mindmap"' in jsonl
    assert '"total_tokens": 150' in jsonl
    assert "command" in csv.splitlines()[0]
    assert "mindmap" in csv
    assert ",150," in csv


def test_token_logger_defaults_usage_to_zero(tmp_path: Path):
    logger = TokenLogger(tmp_path / "output")
    logger.log(
        notebook="book-notebook",
        command="guide",
        source="a.pdf,b.pdf",
        model="qwen3.5:cloud",
        usage=None,
        duration_s=0.5,
        status="error",
        error="timeout",
    )

    jsonl = (tmp_path / "output" / "tokens.log").read_text(encoding="utf-8")
    assert '"input_tokens": 0' in jsonl
    assert '"output_tokens": 0' in jsonl
    assert '"status": "error"' in jsonl
    assert '"error": "timeout"' in jsonl
