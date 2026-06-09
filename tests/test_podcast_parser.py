"""Tests for the markdown podcast script parser.

synthesize can accept either .json (the natural output of
`podcast --format json`) or .md (the human-readable default).
This tests the .md parsing path.
"""

import pytest

from shoothighlm.podcast import _parse_markdown_script


def test_parses_basic_chinese_script():
    text = """# 我的播客

**Duration:** 5 minutes
**Hosts:** 小明 & 小红

---

**小明:** 大家好，欢迎来到今天的节目。
**小红:** 是的，今天我们聊一聊稻盛和夫的经营哲学。
**小明:** 让我们从心性开始。
"""
    result = _parse_markdown_script(text)
    assert result["title"] == "我的播客"
    assert result["host_a_name"] == "小明"
    assert result["host_b_name"] == "小红"
    assert len(result["segments"]) == 3
    assert result["segments"][0]["speaker"] == "小明"
    assert result["segments"][0]["text"] == "大家好，欢迎来到今天的节目。"
    assert result["segments"][1]["speaker"] == "小红"
    assert result["segments"][2]["speaker"] == "小明"


def test_parses_english_script():
    text = """# My Podcast

**Duration:** 5 minutes
**Hosts:** Alex & Jamie

---

**Alex:** Welcome to the show.
**Jamie:** Thanks for having me.
"""
    result = _parse_markdown_script(text)
    assert result["title"] == "My Podcast"
    assert result["host_a_name"] == "Alex"
    assert result["host_b_name"] == "Jamie"
    assert len(result["segments"]) == 2
    assert result["segments"][0]["text"] == "Welcome to the show."


def test_skips_metadata_lines():
    """Lines like **Duration:** and **Hosts:** should not become segments."""
    text = """# Title

**Duration:** 5 minutes
**Hosts:** A & B
**Date:** 2026-01-01
**Source:** some-book.pdf

---

**A:** Hello.
**B:** Hi.
"""
    result = _parse_markdown_script(text)
    # None of the metadata lines should be segments
    speakers = [s["speaker"] for s in result["segments"]]
    assert "Duration" not in speakers
    assert "Hosts" not in speakers
    assert "Date" not in speakers
    assert "Source" not in speakers
    assert speakers == ["A", "B"]


def test_handles_multiline_speaker_text():
    """A speaker's turn may span multiple lines until the next speaker."""
    text = """# Title

**Duration:** 5 minutes
**Hosts:** A & B

---

**A:** This is a longer
turn that spans multiple
lines of text.
**B:** And then I respond.
"""
    result = _parse_markdown_script(text)
    assert len(result["segments"]) == 2
    # Multi-line text should be collapsed to a single line
    assert "longer turn that spans multiple lines" in result["segments"][0]["text"]
    assert result["segments"][1]["text"] == "And then I respond."


def test_handles_missing_metadata():
    """If metadata lines are absent, use defaults."""
    text = """# Title

**A:** Just one turn.
"""
    result = _parse_markdown_script(text)
    assert result["title"] == "Title"
    assert result["host_a_name"] == "Alex"  # default
    assert result["host_b_name"] == "Jamie"  # default
    assert len(result["segments"]) == 1


def test_handles_empty_script():
    text = """# Empty

**Duration:** 0 minutes
**Hosts:** A & B
"""
    result = _parse_markdown_script(text)
    assert result["title"] == "Empty"
    assert result["segments"] == []


def test_roundtrip_json_to_md_and_back():
    """The JSON form, when rendered to markdown and parsed back,
    should give the same segments."""
    from shoothighlm.podcast import PodcastScript

    original = PodcastScript(
        title="Test",
        duration_minutes=3,
        host_a_name="Alice",
        host_b_name="Bob",
        segments=[
            {"speaker": "Alice", "text": "First turn."},
            {"speaker": "Bob", "text": "Second turn."},
            {"speaker": "Alice", "text": "Third turn with 中文."},
        ],
    )
    md = original.to_markdown()
    parsed = _parse_markdown_script(md)
    assert parsed["title"] == "Test"
    assert parsed["host_a_name"] == "Alice"
    assert parsed["host_b_name"] == "Bob"
    assert len(parsed["segments"]) == 3
    assert parsed["segments"][0] == {"speaker": "Alice", "text": "First turn."}
    assert parsed["segments"][2]["text"] == "Third turn with 中文."
