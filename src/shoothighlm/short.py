"""Short-video script generation from book / chapter content.

This is the v1 of the feature designed in `doc/feature-short-video.md`.
It produces a **script + visual direction** as Markdown (default),
JSON, or SRT — but no audio or video. The user finishes the
editing in CapCut / 剪映 / Shorts editor.

Two modes, two prompt templates:

- **per-book** (default, 5 min 纪录短片) — one continuous
  6-act documentary script: 冷开场 → 人物 → 方法 → 数据 → 收束 →
  一句话总结.
- **per-chapter** (60-90s 短视频) — one 4-act script per
  chapter: 钩子 → 冲突 → 转折 → 收尾. 4 styles supported:
  反常识 / 励志 / 学术 / 吐槽.

Both modes return the same `ShortVideoScript` dataclass (with a
list of `Scene` objects) so the CLI can render them through the
same Markdown/JSON/SRT writers.

Why a separate module (not added to mindmap.py or podcast.py)?
- Different prompt template (script-shaped, not TOC-shaped)
- Different output (visual direction, not mindmap nodes or
  dialog turns)
- Different cadence (per-book 5 min vs per-chapter 60s — vastly
  different word counts and structure)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from rich import print as rprint

from .llm import LLMUsage, call_ollama


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Visual:
    """Visual direction for a single scene."""

    type: str = "photo"  # "photo" | "video" | "graphic" | "animation"
    description: str = ""
    search_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "description": self.description,
            "search_keywords": list(self.search_keywords),
        }


@dataclass
class Scene:
    """One scene in the short-video script.

    In per-chapter mode, scenes are 钩子/冲突/转折/收尾.
    In per-book mode, scenes are 冷开场/人物/方法/数据/收束/一句话总结.
    """

    id: str  # "hook" | "conflict" | "turn" | "payoff" (per-chapter)
    # or "cold-open" | "person" | "method" | "data" | "wrap" | "one-liner" (per-book)
    start_s: float
    end_s: float
    voiceover: str = ""  # the narration text
    caption: str = ""  # on-screen subtitle text (may be shorter than voiceover)
    visual: Visual = field(default_factory=Visual)
    bgm: str = ""  # mood/mood-cue, not actual audio

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "voiceover": self.voiceover,
            "caption": self.caption,
            "visual": self.visual.to_dict(),
            "bgm": self.bgm,
        }


@dataclass
class ShortVideoScript:
    """One short-video script (per-book or per-chapter)."""

    title: str
    mode: str  # "per_book" | "per_chapter"
    duration_s: int
    style: str
    platform: str
    language: str
    scenes: List[Scene] = field(default_factory=list)
    production_notes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "mode": self.mode,
            "duration_s": self.duration_s,
            "style": self.style,
            "platform": self.platform,
            "language": self.language,
            "scenes": [s.to_dict() for s in self.scenes],
            "production_notes": dict(self.production_notes),
        }

    def to_markdown(self) -> str:
        """Render to human-readable Markdown matching the design doc sample."""
        lines = [f"# 短视频脚本：{self.title}", ""]
        lines.append("## 🎬 视频元信息")
        lines.append("")
        lines.append(f"- **时长：** {self.duration_s} 秒")
        if self.mode == "per_chapter":
            word_count = sum(len(s.voiceover) for s in self.scenes)
            lines.append(
                f"- **风格：** {self.style}（约 {word_count} 字 / 普通话正常语速）"
            )
        else:
            word_count = sum(len(s.voiceover) for s in self.scenes)
            lines.append(
                f"- **风格：** {self.style}（约 {word_count} 字 / 5 分钟纪录短片）"
            )
        lines.append(f"- **平台：** {self._platform_label()}")
        for k, v in self.production_notes.items():
            lines.append(f"- **{k}：** {v}")
        lines.append("")

        # Per-chapter: 4 幕 with 钩子/冲突/转折/收尾 labels
        # Per-book: 6 幕 with 冷开场/人物/方法/数据/收束/一句话总结 labels
        if self.mode == "per_chapter":
            labels = {
                "hook": "🪝 钩子",
                "conflict": "⚡ 冲突",
                "turn": "💡 转折",
                "payoff": "🎯 收尾 + CTA",
            }
        else:
            labels = {
                "cold-open": "🎬 冷开场",
                "person": "📍 段落 1：人物",
                "method": "⚡ 段落 2：方法",
                "data": "🎯 段落 3：结果",
                "wrap": "🧠 收束",
                "one-liner": "一句话总结",
            }
        for s in self.scenes:
            label = labels.get(s.id, s.id)
            dur = f"（{int(s.start_s)}-{int(s.end_s)} 秒）"
            lines.append(f"## {label} {dur}")
            lines.append("")
            if s.caption:
                lines.append(f"> 字幕：**\"{s.caption}\"**")
                lines.append(">")
            if s.voiceover:
                lines.append(f"> 配音：{s.voiceover}")
            if s.visual.description:
                lines.append(f"> 视觉：{s.visual.description}")
            if s.visual.search_keywords:
                kw = " / ".join(s.visual.search_keywords)
                lines.append(f"> 搜索关键词：`{kw}`")
            if s.bgm:
                lines.append(f"> 背景音乐：{s.bgm}")
            lines.append("")

        # Production checklist
        lines.append("## 📋 后期清单（用户在 CapCut / 剪映里搞定）")
        lines.append("")
        for s in self.scenes:
            if s.visual.search_keywords:
                kw = " / ".join(s.visual.search_keywords)
                lines.append(f"- [ ] {s.id} 镜头：搜索 `{kw}`")
        lines.append(f"- [ ] 录制配音（{word_count} 字，{self.duration_s} 秒）")
        lines.append(
            f"- [ ] 背景音乐：剪映搜\"{self._bgm_genre()}\"配乐，选 1 段"
        )
        lines.append(
            f"- [ ] 字幕样式：剪映默认字幕 + 关键 3-4 个数字用\"花字\"模板大字"
        )
        lines.append(f"- [ ] 转场：段落间用\"2 秒黑场 + 字幕卡\"（{self.platform} 节奏）")
        lines.append("")
        return "\n".join(lines)

    def to_srt(self) -> str:
        """Render voiceover lines as SRT (subtitles)."""
        lines = []
        for i, s in enumerate(self.scenes, 1):
            start = self._fmt_srt_ts(s.start_s)
            end = self._fmt_srt_ts(s.end_s)
            text = s.voiceover or s.caption or ""
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    # ---- helpers ----

    def _platform_label(self) -> str:
        labels = {
            "douyin": "抖音（快节奏，1.2-1.5× 剪辑）",
            "xiaohongshu": "小红书（视频笔记，5 分钟中长内容）",
            "bilibili": "B 站（中长，可有几句\"黑话\"）",
            "youtube": "YouTube Shorts（英文 Shorts）",
        }
        return labels.get(self.platform, self.platform)

    def _bgm_genre(self) -> str:
        if self.mode == "per_book":
            return "纪录片"
        if self.style == "反常识":
            return "低沉钢琴"
        if self.style == "励志":
            return "温暖弦乐"
        if self.style == "吐槽":
            return "轻快喜剧"
        if self.style == "学术":
            return "环境音乐"
        return "通用"

    @staticmethod
    def _fmt_srt_ts(sec: float) -> str:
        """Format seconds as SRT timestamp HH:MM:SS,mmm"""
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


VALID_STYLES_PER_CHAPTER = ["反常识", "励志", "学术", "吐槽"]
VALID_STYLES_PER_BOOK = ["纪录短片"]
VALID_PLATFORMS = ["douyin", "xiaohongshu", "bilibili", "youtube"]


# ---------------------------------------------------------------------------
# Helper: language detection
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Auto-detect the dominant script of `text`.

    Counts CJK characters (Chinese / Japanese kanji / Korean hanja)
    vs Latin characters in a sample of the first 5000 chars. If CJK
    >= 30% of (CJK + Latin), returns "zh"; else "en". Falls back
    to "zh" for empty / whitespace-only input (the user's books
    are mostly Chinese).
    """
    if not text or not text.strip():
        return "zh"
    sample = text[:5000]
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", sample))
    latin = len(re.findall(r"[A-Za-z]", sample))
    if cjk + latin == 0:
        return "zh"
    if cjk / (cjk + latin) >= 0.30:
        return "zh"
    return "en"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class ShortVideoGenerator:
    """Generate short-video scripts from text via LLM.

    Two modes:
      - "per_book"  (default, 5 min 纪录短片) — 6 acts
      - "per_chapter" (60-90s) — 4 acts

    Usage:
        gen = ShortVideoGenerator(chat_model="qwen3.5:cloud")
        scripts = gen.generate(text, title="My Book", mode="per_book")
        for s in scripts:
            print(s.to_markdown())
    """

    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # 600s timeout for cloud LLM with thinking mode + 50K prompt
        self.client = httpx.Client(timeout=600.0)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    # --------------------------------------------------------------- public

    def generate(
        self,
        text: str,
        *,
        title: str = "Document",
        mode: str = "per_book",
        chapter: Optional[str] = None,
        style: str = "纪录短片",
        language: str = "auto",
        platform: Optional[str] = None,
        duration_s: Optional[int] = None,
        variants: int = 1,
    ) -> List[Tuple[ShortVideoScript, LLMUsage]]:
        """Generate one or more short-video scripts.

        Returns a list of (script, usage) tuples. `variants` is
        honored by varying the prompt angle — same input, slightly
        different LLM call (we vary the prompt's "approach" hint
        per variant so the LLM actually diversifies).

        For per-book mode, if the source contains multiple
        sub-books (e.g. a 6-book collection), this method returns
        one script per sub-book × variants (so up to N*variants
        total). The caller can pick one or write all to disk.
        """
        # ---- validate inputs
        mode = self._resolve_mode(mode)
        style = self._resolve_style(mode, style)
        platform = self._resolve_platform(mode, platform)
        if duration_s is None:
            duration_s = 300 if mode == "per_book" else 60
        if language == "auto":
            language = detect_language(text)

        # ---- per-book + multi-book collection: emit one script per sub-book
        if mode == "per_book":
            from .mindmap import _detect_sub_books
            sub_books = _detect_sub_books(text)
            is_collection = (
                len(sub_books) > 1 and sub_books[0][0] != "__whole_book__"
            )
            if is_collection:
                results: List[Tuple[ShortVideoScript, LLMUsage]] = []
                for sub_title, start, end in sub_books:
                    sub_text = text[start:end]
                    sub_title_full = f"{title} — {sub_title}"
                    results.extend(
                        self._generate_one(
                            sub_text,
                            title=sub_title_full,
                            mode=mode,
                            style=style,
                            language=language,
                            platform=platform,
                            duration_s=duration_s,
                            variants=variants,
                        )
                    )
                return results

        # ---- per-chapter: optional slice to the chapter's range
        if mode == "per_chapter":
            if not chapter:
                raise ValueError(
                    "mode='per_chapter' requires the `chapter` argument "
                    "(e.g. chapter='第 1 章 磨炼灵魂'). "
                    "Or use --per-chapter in the CLI to run for all chapters."
                )
            from .mindmap import _detect_chapters
            chapter_titles = _detect_chapters(text, max_titles=200)
            # Find the chapter by prefix match (e.g. user says "第 1 章"
            # and we have "第 1 章 磨炼灵魂 提升心志" in the list)
            match = None
            for ct in chapter_titles:
                if ct.startswith(chapter) or chapter in ct:
                    match = ct
                    break
            if not match:
                raise ValueError(
                    f"Chapter not found: {chapter!r}. "
                    f"Detected chapters: {chapter_titles[:5]}..."
                )
            # Naive: find the marker in text and slice to the next chapter
            idx = text.find(match)
            if idx == -1:
                # Fallback to full text
                pass
            else:
                # Find the next 第N章 marker after this one
                rest = text[idx + len(match):]
                next_match = re.search(
                    r"第\s*[0-9一二三四五六七八九十]+\s*章",
                    rest,
                )
                end_idx = (
                    idx + len(match) + next_match.start()
                    if next_match
                    else len(text)
                )
                text = text[idx:end_idx]
                title = f"{title} — {match}"

        # ---- single-script path
        return self._generate_one(
            text,
            title=title,
            mode=mode,
            style=style,
            language=language,
            platform=platform,
            duration_s=duration_s,
            variants=variants,
        )

    # --------------------------------------------------------------- internal

    def _generate_one(
        self,
        text: str,
        *,
        title: str,
        mode: str,
        style: str,
        language: str,
        platform: str,
        duration_s: int,
        variants: int,
    ) -> List[Tuple[ShortVideoScript, LLMUsage]]:
        """Build prompt + call LLM `variants` times, return list of (script, usage)."""
        results: List[Tuple[ShortVideoScript, LLMUsage]] = []
        for variant_idx in range(variants):
            prompt = self._build_prompt(
                text=text,
                title=title,
                mode=mode,
                style=style,
                language=language,
                platform=platform,
                duration_s=duration_s,
                variant_idx=variant_idx,
                total_variants=variants,
            )
            output, usage = call_ollama(
                base_url=self.base_url,
                model=self.chat_model,
                prompt=prompt,
                client=self.client,
            )
            try:
                script = self._parse_response(
                    output,
                    title=title,
                    mode=mode,
                    style=style,
                    platform=platform,
                    language=language,
                    duration_s=duration_s,
                )
                results.append((script, usage))
            except (json.JSONDecodeError, ValueError) as e:
                # On parse error, return a stub with the raw output in
                # production_notes so the user can see what went wrong
                stub = ShortVideoScript(
                    title=title,
                    mode=mode,
                    duration_s=duration_s,
                    style=style,
                    platform=platform,
                    language=language,
                    production_notes={
                        "parse_error": str(e),
                        "raw_output": output[:500],
                    },
                )
                results.append((stub, usage))
        return results

    def _build_prompt(
        self,
        *,
        text: str,
        title: str,
        mode: str,
        style: str,
        language: str,
        platform: str,
        duration_s: int,
        variant_idx: int,
        total_variants: int,
    ) -> str:
        """Build the LLM prompt for the given mode.

        Two templates, switched on `mode`. Per-chapter is 4-act;
        per-book is 6-act.
        """
        if mode == "per_chapter":
            return self._build_per_chapter_prompt(
                text=text,
                title=title,
                style=style,
                language=language,
                platform=platform,
                duration_s=duration_s,
                variant_idx=variant_idx,
                total_variants=total_variants,
            )
        return self._build_per_book_prompt(
            text=text,
            title=title,
            style=style,
            language=language,
            platform=platform,
            duration_s=duration_s,
            variant_idx=variant_idx,
            total_variants=total_variants,
        )

    def _build_per_chapter_prompt(
        self,
        *,
        text: str,
        title: str,
        style: str,
        language: str,
        platform: str,
        duration_s: int,
        variant_idx: int,
        total_variants: int,
    ) -> str:
        style_desc = {
            "反常识": (
                "open with a counterintuitive fact. 'Most people think "
                "X. Actually Y.' The hook IS the surprise."
            ),
            "励志": (
                "open with a struggle. 'He was broke / fired / "
                "rejected. Then he did X.' The hook IS the underdog "
                "story."
            ),
            "学术": (
                "open with a question. 'Why do some people succeed "
                "where others fail?' The hook IS the curiosity gap."
            ),
            "吐槽": (
                "open with a hot take. 'Popular advice says X. "
                "That's wrong.' The hook IS the controversy."
            ),
        }
        platform_desc = {
            "douyin": (
                "hook in 1.5s, scenes 3-5s each, subtitles 12-20 "
                "字/行, 1.2-1.5× cut speed"
            ),
            "xiaohongshu": (
                "hook in 2s, scenes 4-6s each, subtitles 15-25 "
                "字/行, 1.0× cut speed, can use 小红书 hot-keywords"
            ),
            "bilibili": (
                "hook in 3s, scenes 5-8s each, subtitles 20-35 "
                "字/行, 1.0× cut speed, can use 术语 / 黑话"
            ),
            "youtube": (
                "hook in 3s, scenes 5-7s each, captions 8-15 "
                "words/line, 1.0× cut, English narration"
            ),
        }
        word_target = int(duration_s * 2.5)
        variant_hint = ""
        if total_variants > 1:
            approach_angles = [
                "data-driven approach (lead with a specific number, then explain why)",
                "story-driven approach (lead with a personal anecdote, then generalize)",
                "contrarian approach (challenge a popular belief, then defend the book's view)",
                "curiosity-gap approach (open with a question, then reveal the answer)",
                "first-person approach ('I read this book and…' reflective tone)",
            ]
            angle = approach_angles[variant_idx % len(approach_angles)]
            variant_hint = (
                f"\nVARIANT: This is variant {variant_idx + 1} of "
                f"{total_variants}. Use a **{angle}** for this "
                f"version — make it genuinely different from the "
                f"other variants, not just a paraphrase.\n"
            )

        lang_instruction = {
            "zh": "Write all narration and captions in 简体中文.",
            "en": "Write all narration and captions in English.",
        }.get(language, "Write in the book's language.")

        return f"""You are a Chinese short-video script writer. Your job is to compress ONE CHAPTER of the source text into a {duration_s}-second script with a hook, conflict, turn, and payoff.
{variant_hint}
## LANGUAGE
{lang_instruction}

## STYLE: {style}
{style_desc.get(style, style_desc["反常识"])}

## PLATFORM: {platform}
{platform_desc.get(platform, platform_desc["douyin"])}

## DURATION
{duration_s} seconds. Target word count = duration × 2.5
(Chinese: 2.5 字/秒 normal pace). For {duration_s}s that is ~{word_target} 字 total.

## OUTPUT FORMAT (strict JSON, no other text)
```json
{{
  "scenes": [
    {{
      "id": "hook",
      "start_s": 0,
      "end_s": 3,
      "voiceover": "narration text here",
      "caption": "on-screen subtitle text (shorter than voiceover)",
      "visual": {{
        "type": "photo",
        "description": "specific visual description a video editor can find in 5 min",
        "search_keywords": ["keyword1", "keyword2", "keyword3"]
      }},
      "bgm": "music mood cue"
    }},
    {{
      "id": "conflict",
      "start_s": 3,
      "end_s": 15,
      "voiceover": "...",
      "caption": "...",
      "visual": {{ "type": "photo", "description": "...", "search_keywords": ["..."] }},
      "bgm": "..."
    }},
    {{
      "id": "turn",
      "start_s": 15,
      "end_s": 45,
      "voiceover": "...",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }},
    {{
      "id": "payoff",
      "start_s": 45,
      "end_s": 60,
      "voiceover": "...",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }}
  ]
}}
```

The 4 scene ids MUST be exactly: "hook", "conflict", "turn", "payoff".
start_s / end_s should be cumulative (hook ends where conflict starts, etc.).

## RULES
- The first 3 seconds of the hook MUST be a self-contained sentence the viewer can read/understand without context.
- Each scene's voiceover MUST be 15-60 字. Going over 60 means the structure is wrong.
- Captions MUST be < 15 字 for douyin/xiaohongshu, < 20 字 for bilibili, < 15 words for youtube.
- The visual.description MUST be specific enough that a 剪辑 (video editor) can find or create the shot in 5 minutes. "Some pretty image" is BAD. "稻盛和夫 78 岁在新闻发布会上的照片" is GOOD.
- Do NOT use words that don't appear in the source text. If the book doesn't mention a number, don't make up a number.

## SOURCE TEXT (this chapter only)
{text}

## JSON output
"""

    def _build_per_book_prompt(
        self,
        *,
        text: str,
        title: str,
        style: str,
        language: str,
        platform: str,
        duration_s: int,
        variant_idx: int,
        total_variants: int,
    ) -> str:
        platform_desc = {
            "douyin": (
                "5 min exceeds 抖音's sweet spot. Use this only if "
                "explicitly requested — otherwise default to xiaohongshu "
                "or bilibili. Scenes 30-60s each, subtitles 15-20 "
                "字/行, 1.2× cut speed."
            ),
            "xiaohongshu": (
                "video-笔记 5 min format. Scenes 30-60s each, "
                "subtitles 18-28 字/行, 1.0× cut speed, can use "
                "小红书 hot-keywords."
            ),
            "bilibili": (
                "scenes 30-60s each, subtitles 20-35 字/行, 1.0× "
                "cut speed, 2-second black-card transitions between "
                "acts."
            ),
            "youtube": (
                "scenes 45-90s each, captions 10-18 words/line, "
                "1.0× cut, English narration."
            ),
        }
        word_target = int(duration_s * 2.5)
        variant_hint = ""
        if total_variants > 1:
            approach_angles = [
                "the protagonist (lead with the person's life arc)",
                "the idea (lead with the book's core concept, then who invented it)",
                "the data (lead with the most surprising number, then explain the system behind it)",
                "the reader (lead with 'if you only remember one thing from this book…')",
            ]
            angle = approach_angles[variant_idx % len(approach_angles)]
            variant_hint = (
                f"\nVARIANT: This is variant {variant_idx + 1} of "
                f"{total_variants}. Open with **{angle}** — make it "
                f"genuinely different from the other variants, not "
                f"just a paraphrase.\n"
            )

        lang_instruction = {
            "zh": "Write all narration and captions in 简体中文.",
            "en": "Write all narration and captions in English.",
        }.get(language, "Write in the book's language.")

        return f"""You are a Chinese short-documentary script writer. Your job is to compress the SOURCE TEXT (a full book) into a {duration_s}-second script with a 3-act documentary structure: cold-open + arc + 收束.
{variant_hint}
## LANGUAGE
{lang_instruction}

## STYLE: 纪录短片
- Tone: neutral, observational, with data + story + conclusion. Think 《纽约时报》The Daily condensed to 5 min, or a Vox explainer.
- No hot takes, no controversy, no "you'll never believe". This is NOT a YouTube thumbnail — it's a thoughtful summary for someone who has 5 minutes and wants to actually understand the book.
- Voice: third person, "稻盛和夫做了 X" / "数据显示 Y". Not "你应该 X".

## PLATFORM: {platform}
{platform_desc.get(platform, platform_desc["xiaohongshu"])}

## DURATION
{duration_s} seconds. Target word count = duration × 2.5
(Chinese: 2.5 字/秒 normal pace). For {duration_s}s that is ~{word_target} 字 total.

## OUTPUT FORMAT (strict JSON, no other text)
```json
{{
  "scenes": [
    {{
      "id": "cold-open",
      "start_s": 0,
      "end_s": 20,
      "voiceover": "single specific number, ~50 字",
      "caption": "big bold text for the hook",
      "visual": {{ "type": "photo", "description": "...", "search_keywords": ["..."] }},
      "bgm": "..."
    }},
    {{
      "id": "person",
      "start_s": 20,
      "end_s": 90,
      "voiceover": "who is this person? ~175 字",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }},
    {{
      "id": "method",
      "start_s": 90,
      "end_s": 210,
      "voiceover": "what did they actually DO? ~300 字 (longest act)",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }},
    {{
      "id": "data",
      "start_s": 210,
      "end_s": 270,
      "voiceover": "measurable outcomes, ~150 字",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }},
    {{
      "id": "wrap",
      "start_s": 270,
      "end_s": 290,
      "voiceover": "one sentence takeaway connecting back to the cold-open, ~50 字",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }},
    {{
      "id": "one-liner",
      "start_s": 290,
      "end_s": 300,
      "voiceover": "ONE quotable sentence the viewer will remember, ~25 字",
      "caption": "...",
      "visual": {{ ... }},
      "bgm": "..."
    }}
  ]
}}
```

The 6 scene ids MUST be exactly: "cold-open", "person", "method", "data", "wrap", "one-liner". start_s / end_s should be cumulative.

## RULES
- The cold-open MUST lead with a specific number, not a story. "1 年 / 破产 → 全球第一" is GOOD. "他做了一件不可思议的事" is BAD.
- Each scene's voiceover MUST be 25-300 字. The method act MUST be the longest.
- Use the book's actual numbers. "公司员工从 1000 增加到 5000" is GOOD if that's in the book. "公司员工增长 5 倍" is BAD unless the book says that exact phrasing.
- The one-liner MUST be a quotable, screenshot-able sentence. "工作不是为钱，是磨炼灵魂" is GOOD. "这本书告诉我们很多关于工作的道理" is BAD.

## SOURCE TEXT (the book)
{text}

## JSON output
"""

    # ---- response parsing ----

    def _parse_response(
        self,
        output: str,
        *,
        title: str,
        mode: str,
        style: str,
        platform: str,
        language: str,
        duration_s: int,
    ) -> ShortVideoScript:
        """Parse the LLM's JSON response into a ShortVideoScript."""
        # Extract JSON from markdown code blocks if present
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()

        data = json.loads(json_str)
        scenes_data = data.get("scenes", [])
        if not scenes_data:
            raise ValueError("LLM returned no scenes")

        scenes: List[Scene] = []
        for sd in scenes_data:
            visual_data = sd.get("visual", {})
            visual = Visual(
                type=visual_data.get("type", "photo"),
                description=visual_data.get("description", ""),
                search_keywords=list(visual_data.get("search_keywords", [])),
            )
            scene = Scene(
                id=sd.get("id", ""),
                start_s=float(sd.get("start_s", 0)),
                end_s=float(sd.get("end_s", 0)),
                voiceover=sd.get("voiceover", ""),
                caption=sd.get("caption", ""),
                visual=visual,
                bgm=sd.get("bgm", ""),
            )
            scenes.append(scene)

        return ShortVideoScript(
            title=title,
            mode=mode,
            duration_s=duration_s,
            style=style,
            platform=platform,
            language=language,
            scenes=scenes,
            production_notes={
                "voice": (
                    "男声，沉稳，30-40 岁" if language == "zh"
                    else "English male, calm, 30-40 yrs"
                ),
                "bgm_genre": "纪录短片 BGM" if mode == "per_book" else f"{style} BGM",
                "total_word_count": sum(len(s.voiceover) for s in scenes),
                "estimated_speech_duration_s": duration_s,
            },
        )

    # ---- input resolvers ----

    @staticmethod
    def _resolve_mode(mode: str) -> str:
        m = mode.lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "per_book": "per_book",
            "perbook": "per_book",
            "book": "per_book",
            "per_chapter": "per_chapter",
            "perchapter": "per_chapter",
            "chapter": "per_chapter",
        }
        resolved = aliases.get(m, m)
        if resolved not in ("per_book", "per_chapter"):
            raise ValueError(
                f"mode must be 'per_book' or 'per_chapter', got {mode!r}"
            )
        return resolved

    @staticmethod
    def _resolve_style(mode: str, style: str) -> str:
        if mode == "per_book":
            if style != "纪录短片":
                # Per-book style is locked to 纪录短片 in v1; warn but accept
                return "纪录短片"
            return style
        # per_chapter: must be one of 4
        if style not in VALID_STYLES_PER_CHAPTER:
            return "反常识"  # safe default
        return style

    @staticmethod
    def _resolve_platform(mode: str, platform: Optional[str]) -> str:
        if platform is None:
            return "xiaohongshu" if mode == "per_book" else "douyin"
        if platform not in VALID_PLATFORMS:
            return "xiaohongshu" if mode == "per_book" else "douyin"
        return platform
