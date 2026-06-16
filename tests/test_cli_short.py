"""CLI integration tests for `shoot-high short`."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from shoothighlm.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def notebook_with_pdf(tmp_path: Path):
    """A minimal notebook with a fake PDF file (content doesn't matter — we mock LLM)."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return tmp_path


def _mock_post_response(scenes: list) -> MagicMock:
    """Build a mock httpx response that returns a JSON `scenes` array."""
    import json
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {
        "response": json.dumps({"scenes": scenes}, ensure_ascii=False),
        "prompt_eval_count": 100, "eval_count": 50,
    }
    mock.raise_for_status = MagicMock()
    return mock


PER_BOOK_6_SCENES = [
    {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
    {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
    {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
    {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
    {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
    {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
]


# ============== Help / registration ==============


def test_short_command_registered(cli_runner):
    """`shoot-high short --help` should show the command exists."""
    result = cli_runner.invoke(main, ["short", "--help"])
    assert result.exit_code == 0
    assert "Generate short-video script" in result.output
    assert "--chapter" in result.output
    assert "--per-chapter" in result.output
    assert "--style" in result.output


# ============== No PDFs / empty notebook ==============


def test_short_no_pdfs(cli_runner, tmp_path):
    """Empty notebook should fail gracefully with a clear message."""
    result = cli_runner.invoke(main, ["short", str(tmp_path)])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output


# ============== Per-book mode (default) ==============


def test_short_per_book_default_writes_markdown(cli_runner, notebook_with_pdf):
    """Default mode is per-book → 1 markdown file per sub-book (1 for single book)."""
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    # Mock the chain: parse_pdf returns text, LLM returns scenes
    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["some book content " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(main, ["short", str(notebook_with_pdf)])

    assert result.exit_code == 0, result.output
    assert "Mode:" in result.output
    assert "1 script(s) written" in result.output or "script(s) written" in result.output
    # Markdown file should be in output/
    output_dir = notebook_with_pdf / "output"
    md_files = list(output_dir.glob("short-*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "# 短视频脚本：" in content
    assert "## 🎬 冷开场" in content


def test_short_per_book_with_explicit_duration(cli_runner, notebook_with_pdf):
    """--duration overrides the default 300s."""
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(notebook_with_pdf), "--duration", "120"]
            )
    assert result.exit_code == 0, result.output
    assert "120s" in result.output


def test_short_per_book_json_output(cli_runner, notebook_with_pdf):
    """--format json should produce JSON files with the script's to_dict() shape."""
    import json as _json
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(notebook_with_pdf), "--format", "json"]
            )
    assert result.exit_code == 0, result.output
    output_dir = notebook_with_pdf / "output"
    json_files = list(output_dir.glob("short-*.json"))
    assert len(json_files) >= 1
    data = _json.loads(json_files[0].read_text(encoding="utf-8"))
    assert data["mode"] == "per_book"
    assert data["style"] == "纪录短片"
    assert data["platform"] == "xiaohongshu"
    assert len(data["scenes"]) == 6


def test_short_per_book_srt_output(cli_runner, notebook_with_pdf):
    """--format srt should produce SRT files with HH:MM:SS,mmm timestamps."""
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(notebook_with_pdf), "--format", "srt"]
            )
    assert result.exit_code == 0, result.output
    output_dir = notebook_with_pdf / "output"
    srt_files = list(output_dir.glob("short-*.srt"))
    assert len(srt_files) >= 1
    content = srt_files[0].read_text(encoding="utf-8")
    # SRT format: 1\n00:00:00,000 --> 00:00:20,000\n...
    assert "00:00:00,000" in content
    assert "-->" in content


# ============== Per-chapter mode ==============


PER_CHAPTER_4_SCENES = [
    {"id": "hook", "start_s": 0, "end_s": 3, "voiceover": "v"},
    {"id": "conflict", "start_s": 3, "end_s": 15, "voiceover": "v"},
    {"id": "turn", "start_s": 15, "end_s": 45, "voiceover": "v"},
    {"id": "payoff", "start_s": 45, "end_s": 60, "voiceover": "v"},
]


def test_short_per_chapter_with_explicit_chapter(cli_runner, tmp_path):
    """--chapter '第 1 章' should produce 1 60s 4-act script."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    text = (
        "第 1 章 磨炼灵魂，提升心志\n"
        + ("内容。" * 100)
        + "\n第 2 章 让自己喜欢上工作\n"
        + ("更多内容。" * 100)
    )
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_CHAPTER_4_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter([text])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main,
                ["short", str(tmp_path), "--chapter", "第 1 章"],
            )
    assert result.exit_code == 0, result.output
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "## 🪝 钩子" in content
    assert "## ⚡ 冲突" in content
    assert "## 💡 转折" in content
    assert "## 🎯 收尾" in content


def test_short_per_chapter_with_unknown_chapter_errors(cli_runner, tmp_path):
    """--chapter '第 99 章' (not in source) should fail with a clear error."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_client = MagicMock()  # never gets called
    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["no chapter markers here"])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main,
                ["short", str(tmp_path), "--chapter", "第 99 章 不存在"],
            )
    # Either exit 0 with error in output, or non-zero with error
    assert ("Chapter not found" in result.output
            or "not found" in result.output
            or result.exit_code != 0)


def test_short_per_chapter_iterates_all_chapters(cli_runner, tmp_path):
    """--per-chapter should produce N output files for N detected chapters."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    text = (
        "第 1 章 第一章标题\n" + ("x" * 50) + "\n"
        "第 2 章 第二章标题\n" + ("y" * 50) + "\n"
        "第 3 章 第三章标题\n" + ("z" * 50) + "\n"
    )
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_CHAPTER_4_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter([text])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main,
                ["short", str(tmp_path), "--per-chapter"],
            )
    assert result.exit_code == 0, result.output
    assert "3 chapter(s) detected" in result.output
    # 3 separate LLM calls, one per chapter
    assert mock_client.post.call_count == 3
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*.md"))
    assert len(md_files) == 3


def test_short_per_chapter_style_override(cli_runner, tmp_path):
    """--style 吐槽 (per-chapter only) should be honored."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    text = "第 1 章 测试\n" + ("x" * 200) + "\n第 2 章 测试 2\n" + ("y" * 200)
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_CHAPTER_4_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter([text])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main,
                ["short", str(tmp_path), "--chapter", "第 1 章", "--style", "吐槽"],
            )
    assert result.exit_code == 0, result.output
    # The output script should have style=吐槽
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    assert "吐槽" in content


# ============== Variants ==============


def test_short_variants_produces_n_files(cli_runner, tmp_path):
    """--variants 3 should produce 3 separate output files."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(tmp_path), "--variants", "3"]
            )
    assert result.exit_code == 0, result.output
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*-v*.md"))
    assert len(md_files) == 3
    # 3 LLM calls
    assert mock_client.post.call_count == 3


# ============== Language / platform overrides ==============


def test_short_explicit_language(cli_runner, tmp_path):
    """--language en should be passed through to the script."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(tmp_path), "--language", "en"]
            )
    assert result.exit_code == 0, result.output
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*.md"))
    assert len(md_files) >= 1
    content = md_files[0].read_text(encoding="utf-8")
    # English language note in production_notes
    assert "English" in content


def test_short_explicit_platform_douyin_for_per_book(cli_runner, tmp_path):
    """--platform douyin should override the per-book default (xiaohongshu)."""
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_client = MagicMock()
    mock_client.post.return_value = _mock_post_response(PER_BOOK_6_SCENES)

    with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text " * 100])):
        with patch("httpx.Client") as client_factory:
            client_factory.return_value = mock_client
            result = cli_runner.invoke(
                main, ["short", str(tmp_path), "--platform", "douyin"]
            )
    assert result.exit_code == 0, result.output
    output_dir = tmp_path / "output"
    md_files = list(output_dir.glob("short-*.md"))
    content = md_files[0].read_text(encoding="utf-8")
    assert "抖音" in content
