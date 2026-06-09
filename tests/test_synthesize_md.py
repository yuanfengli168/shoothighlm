"""Tests for the synthesize command accepting .md files (not just .json)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from shoothighlm.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_synthesize_loads_json_file(runner):
    """Existing JSON path: the natural output of `podcast --format json`."""
    script = {
        "title": "Test",
        "host_a_name": "A",
        "host_b_name": "B",
        "segments": [
            {"speaker": "A", "text": "Hello."},
            {"speaker": "B", "text": "Hi."},
        ],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "script.json"
        path.write_text(json.dumps(script), encoding="utf-8")

        mock_provider = MagicMock()
        mock_provider.name.return_value = "mock-tts"
        mock_synth = MagicMock()
        mock_synth.synthesize_script.return_value = {
            "duration_seconds": 5.0,
            "segment_count": 2,
        }
        with patch("shoothighlm.tts.get_provider", return_value=mock_provider), \
             patch("shoothighlm.tts.PodcastSynthesizer", return_value=mock_synth):
            result = runner.invoke(main, ["synthesize", str(path)])
    # Should successfully load and start synthesis
    assert "Loaded 2 segments" in result.output
    assert mock_synth.synthesize_script.called


def test_synthesize_loads_markdown_file(runner):
    """NEW: synthesize can now read .md podcast scripts (parsed on the fly)."""
    md_content = """# 测试播客

**Duration:** 3 minutes
**Hosts:** 小明 & 小红

---

**小明:** 大家好。
**小红:** 你好。
**小明:** 让我们开始吧。
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "script.md"
        path.write_text(md_content, encoding="utf-8")

        mock_provider = MagicMock()
        mock_provider.name.return_value = "mock-tts"
        mock_synth = MagicMock()
        mock_synth.synthesize_script.return_value = {
            "duration_seconds": 5.0,
            "segment_count": 3,
        }
        with patch("shoothighlm.tts.get_provider", return_value=mock_provider), \
             patch("shoothighlm.tts.PodcastSynthesizer", return_value=mock_synth):
            result = runner.invoke(main, ["synthesize", str(path)])
    # 3 segments parsed from the .md
    assert "Loaded 3 segments" in result.output
    # Host names extracted from the markdown
    assert "小明" in result.output
    assert "小红" in result.output
    # Title also extracted
    assert "测试播客" in result.output
    # And synthesis started
    assert mock_synth.synthesize_script.called


def test_synthesize_rejects_invalid_json(runner):
    """If .json file is malformed, print a clear error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        result = runner.invoke(main, ["synthesize", str(path)])
    assert "Invalid JSON" in result.output
