"""Tests for the short-video script generator."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from shoothighlm.llm import LLMUsage
from shoothighlm.short import (
    Scene,
    ShortVideoGenerator,
    ShortVideoScript,
    VALID_PLATFORMS,
    VALID_STYLES_PER_CHAPTER,
    Visual,
    detect_language,
)


# ============== detect_language ==============


def test_detect_language_pure_chinese():
    """A 100% Chinese sample is 'zh'."""
    text = "今天天气真好，我们去公园里散步，看看风景。"
    assert detect_language(text) == "zh"


def test_detect_language_pure_english():
    """A 100% English sample is 'en'."""
    text = "Today is a great day, let us go to the park and enjoy the weather."
    assert detect_language(text) == "en"


def test_detect_language_empty():
    """Empty input returns the safe default ('zh')."""
    assert detect_language("") == "zh"
    assert detect_language("   ") == "zh"
    assert detect_language("\n\n") == "zh"


def test_detect_language_mixed_majority_chinese():
    """Mixed content where CJK >= 30% returns 'zh'."""
    text = "今天我们在中央公园 Central Park 见面，聊天很愉快。"
    assert detect_language(text) == "zh"


def test_detect_language_mixed_majority_english():
    """Mixed content where CJK < 30% returns 'en'."""
    text = "This book has some Chinese words like 工作 and 努力 in it."
    assert detect_language(text) == "en"


# ============== ShortVideoScript dataclass ==============


def test_script_to_dict_round_trip():
    """to_dict() should produce a JSON-serializable dict with all fields."""
    script = ShortVideoScript(
        title="test",
        mode="per_chapter",
        duration_s=60,
        style="反常识",
        platform="douyin",
        language="zh",
        scenes=[
            Scene(id="hook", start_s=0, end_s=3,
                  voiceover="x", caption="x",
                  visual=Visual(type="photo", description="d",
                                search_keywords=["a", "b"]),
                  bgm="low piano"),
        ],
        production_notes={"voice": "male"},
    )
    d = script.to_dict()
    # Must be JSON-serializable (no dataclass objects, no tuples in weird places)
    json.dumps(d)
    assert d["title"] == "test"
    assert d["scenes"][0]["visual"]["search_keywords"] == ["a", "b"]


def test_script_to_srt_format():
    """to_srt() should produce valid SRT with HH:MM:SS,mmm timestamps."""
    script = ShortVideoScript(
        title="t", mode="per_chapter", duration_s=60, style="反常识",
        platform="douyin", language="zh",
        scenes=[
            Scene(id="hook", start_s=0, end_s=3.5, voiceover="hi"),
            Scene(id="conflict", start_s=3.5, end_s=15, voiceover="world"),
        ],
    )
    srt = script.to_srt()
    lines = srt.strip().split("\n")
    # Standard SRT: "1\n00:00:00,000 --> 00:00:03,500\nhi\n\n2\n..."
    assert lines[0] == "1"
    assert lines[1].startswith("00:00:00,000")
    assert "-->" in lines[1]
    assert "00:00:03,500" in lines[1]
    assert "hi" in lines
    assert "2" in lines
    assert "00:00:03,500" in lines[5]  # second scene starts at 3.5s


def test_script_to_markdown_contains_required_sections():
    """to_markdown() output should have the meta info + all scenes + checklist."""
    script = ShortVideoScript(
        title="干法 第 1 章", mode="per_chapter", duration_s=60, style="反常识",
        platform="douyin", language="zh",
        scenes=[
            Scene(id="hook", start_s=0, end_s=3, voiceover="hi"),
            Scene(id="conflict", start_s=3, end_s=15, voiceover="world"),
            Scene(id="turn", start_s=15, end_s=45, voiceover="turn"),
            Scene(id="payoff", start_s=45, end_s=60, voiceover="payoff",
                  visual=Visual(search_keywords=["a", "b"])),
        ],
    )
    md = script.to_markdown()
    assert "# 短视频脚本：干法 第 1 章" in md
    assert "## 🎬 视频元信息" in md
    assert "## 🪝 钩子" in md
    assert "## ⚡ 冲突" in md
    assert "## 💡 转折" in md
    assert "## 🎯 收尾 + CTA" in md
    assert "## 📋 后期清单" in md
    assert "a / b" in md  # search keywords rendered


def test_script_to_markdown_per_book_uses_6_act_labels():
    """Per-book mode uses the 6-act section labels (cold-open, person, method, data, wrap, one-liner)."""
    script = ShortVideoScript(
        title="干法", mode="per_book", duration_s=300, style="纪录短片",
        platform="xiaohongshu", language="zh",
        scenes=[
            Scene(id="cold-open", start_s=0, end_s=20, voiceover="v"),
            Scene(id="person", start_s=20, end_s=90, voiceover="v"),
            Scene(id="method", start_s=90, end_s=210, voiceover="v"),
            Scene(id="data", start_s=210, end_s=270, voiceover="v"),
            Scene(id="wrap", start_s=270, end_s=290, voiceover="v"),
            Scene(id="one-liner", start_s=290, end_s=300, voiceover="v"),
        ],
    )
    md = script.to_markdown()
    assert "## 🎬 冷开场" in md
    assert "## 📍 段落 1：人物" in md
    assert "## ⚡ 段落 2：方法" in md
    assert "## 🎯 段落 3：结果" in md
    assert "## 🧠 收束" in md
    assert "## 一句话总结" in md


# ============== Generator: input validation ==============


def test_generator_rejects_invalid_mode():
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        with pytest.raises(ValueError, match="mode"):
            gen.generate("text", mode="nonsense")
    finally:
        gen.close()


def test_generator_per_chapter_requires_chapter():
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        with pytest.raises(ValueError, match="chapter"):
            gen.generate("text", mode="per_chapter")
    finally:
        gen.close()


def test_generator_per_chapter_with_unknown_chapter_errors():
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        with pytest.raises(ValueError, match="not found"):
            gen.generate(
                "Some text without chapter markers. Just regular prose.",
                mode="per_chapter",
                chapter="第 99 章 不存在",
            )
    finally:
        gen.close()


# ============== Generator: end-to-end with mocked LLM ==============


def _make_mock_llm_response(scenes_data: list) -> MagicMock:
    """Build a mock httpx response that returns the given scenes as JSON."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": json.dumps({"scenes": scenes_data}, ensure_ascii=False),
        "prompt_eval_count": 100,
        "eval_count": 50,
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.post.return_value = mock_response
    return mock_client


def test_generator_per_chapter_produces_4_act_script():
    """Per-chapter mode should call LLM and parse 4 scenes (hook/conflict/turn/payoff)."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        scenes_data = [
            {
                "id": "hook", "start_s": 0, "end_s": 3,
                "voiceover": "78 岁他接下烂摊子",
                "caption": "78 岁重建日航",
                "visual": {
                    "type": "photo",
                    "description": "稻盛和夫 78 岁",
                    "search_keywords": ["稻盛和夫"],
                },
                "bgm": "piano",
            },
            {"id": "conflict", "start_s": 3, "end_s": 15, "voiceover": "x"},
            {"id": "turn", "start_s": 15, "end_s": 45, "voiceover": "x"},
            {"id": "payoff", "start_s": 45, "end_s": 60, "voiceover": "x"},
        ]
        mock_client = _make_mock_llm_response(scenes_data)
        # Text with real chapter markers so _detect_chapters finds it
        text = (
            "前言\n一些内容。\n"
            "第 1 章 磨炼灵魂，提升心志\n"
            + ("内容。" * 200)
            + "\n第 2 章 让自己喜欢上工作\n"
            + ("更多内容。" * 200)
        )
        with patch.object(gen, "client", mock_client):
            results = gen.generate(
                text,
                title="My Chapter",
                mode="per_chapter",
                chapter="第 1 章",
            )
        assert len(results) == 1
        script, _ = results[0]
        assert script.mode == "per_chapter"
        assert script.duration_s == 60
        assert script.style == "反常识"
        assert script.platform == "douyin"
        assert len(script.scenes) == 4
        assert [s.id for s in script.scenes] == [
            "hook", "conflict", "turn", "payoff",
        ]
        assert "第 1 章" in script.title  # chapter was added to title
    finally:
        gen.close()


def test_generator_per_book_produces_6_act_script():
    """Per-book mode with collection detection: per sub-book, 6-act script."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        scenes_data = [
            {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
            {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
            {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
            {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
            {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
            {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
        ]
        mock_client = _make_mock_llm_response(scenes_data)
        # Single-book text (no sub-book markers) → single 5-min script
        with patch.object(gen, "client", mock_client):
            results = gen.generate(
                "This is a single book about work philosophy. " * 100,
                title="My Book",
                mode="per_book",
            )
        assert len(results) == 1
        script, usage = results[0]
        assert script.mode == "per_book"
        assert script.duration_s == 300
        assert script.style == "纪录短片"
        assert script.platform == "xiaohongshu"
        assert len(script.scenes) == 6
        assert [s.id for s in script.scenes] == [
            "cold-open", "person", "method", "data", "wrap", "one-liner",
        ]
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
    finally:
        gen.close()


def test_generator_resolves_platform_default_per_mode():
    """Default platform is xiaohongshu for per_book, douyin for per_chapter."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        # per_book
        scenes_data = [
            {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
            {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
            {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
            {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
            {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
            {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
        ]
        mock_client = _make_mock_llm_response(scenes_data)
        with patch.object(gen, "client", mock_client):
            results = gen.generate(
                "Single book content. " * 100,
                mode="per_book",
            )
        assert results[0][0].platform == "xiaohongshu"
    finally:
        gen.close()


def test_generator_variants_produces_n_calls():
    """--variants N should produce N results from N LLM calls."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        scenes_data = [
            {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
            {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
            {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
            {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
            {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
            {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
        ]
        mock_client = _make_mock_llm_response(scenes_data)
        with patch.object(gen, "client", mock_client):
            results = gen.generate(
                "Single book content. " * 100,
                mode="per_book",
                variants=3,
            )
        assert len(results) == 3
        # 3 separate LLM calls
        assert mock_client.post.call_count == 3
    finally:
        gen.close()


def test_generator_handles_malformed_json():
    """If LLM returns invalid JSON, the parser should raise, and we wrap it in a stub."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "This is not JSON at all. Just prose from the LLM.",
            "prompt_eval_count": 0, "eval_count": 0,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(gen, "client", mock_client):
            results = gen.generate(
                "Single book content. " * 100,
                mode="per_book",
            )
        # We get a stub with parse_error in production_notes
        assert len(results) == 1
        script, _ = results[0]
        assert "parse_error" in script.production_notes
    finally:
        gen.close()


def test_generator_extracts_json_from_code_block():
    """LLM response with ```json ... ``` should be parsed correctly."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        scenes_data = [
            {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
            {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
            {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
            {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
            {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
            {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
        ]
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": f"```json\n{json.dumps({'scenes': scenes_data})}\n```",
            "prompt_eval_count": 0, "eval_count": 0,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch.object(gen, "client", mock_client):
            results = gen.generate("Single book. " * 100, mode="per_book")
        assert len(results[0][0].scenes) == 6
    finally:
        gen.close()


def test_generator_returns_llm_usage():
    """Each result should include the LLMUsage from the call."""
    gen = ShortVideoGenerator(chat_model="test-model")
    try:
        scenes_data = [
            {"id": "cold-open", "start_s": 0, "end_s": 20, "voiceover": "v"},
            {"id": "person", "start_s": 20, "end_s": 90, "voiceover": "v"},
            {"id": "method", "start_s": 90, "end_s": 210, "voiceover": "v"},
            {"id": "data", "start_s": 210, "end_s": 270, "voiceover": "v"},
            {"id": "wrap", "start_s": 270, "end_s": 290, "voiceover": "v"},
            {"id": "one-liner", "start_s": 290, "end_s": 300, "voiceover": "v"},
        ]
        mock_client = _make_mock_llm_response(scenes_data)
        with patch.object(gen, "client", mock_client):
            results = gen.generate("Single book. " * 100, mode="per_book")
        _, usage = results[0]
        assert isinstance(usage, LLMUsage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
    finally:
        gen.close()


# ============== Constants ==============


def test_valid_styles_per_chapter_has_4_entries():
    assert set(VALID_STYLES_PER_CHAPTER) == {"反常识", "励志", "学术", "吐槽"}


def test_valid_platforms_includes_xiaohongshu():
    """xiaohongshu is the per-book default platform (locked-in 2026-06-16)."""
    assert "xiaohongshu" in VALID_PLATFORMS
    assert "douyin" in VALID_PLATFORMS
    assert "bilibili" in VALID_PLATFORMS
    assert "youtube" in VALID_PLATFORMS
