# Short Video Generation (`shoot-high short`)

> **Status:** 🟡 **Design** (no code yet — see Implementation Plan at the bottom)
> **Last updated:** 2026-06-15
> **Author:** yuanfengli168 + Copilot

## Motivation

In 2026 the dominant format for "I read a book and want to share what I
learned" is no longer the blog post or even the podcast. It's the **60-90
second short video** — Douyin, Xiaohongshu, Bilibili, YouTube Shorts,
TikTok, WeChat Video. The current `shootHighLM` toolchain produces
**long-form** artifacts (podcast, notebook guide, mind map, full
infographic) but nothing in this short-video format.

The user's feedback: "我们现在都喜欢看短视频，我们可不可以把一本书，或者一个章节，做成一个1分钟左右的短视频呢？"

This doc designs the **minimal viable** version of that feature. It does
NOT aim to compete with CapCut / 剪映 / 抖音的图文成片 — those tools
already do the heavy-lifting video editing. shootHighLM's job is to
**produce the script and the visual direction**, so the user can drop
the output into their video editor and have a finished short in 5-10
minutes.

## Why not just use the existing mindmap / guide / podcast?

| Existing command | Output | Why it doesn't work for short video |
|---|---|---|
| `podcast` | 8-min 2-host script (Markdown) | Wrong length (8 min vs 60s), wrong tone (conversational vs punchy), no visual direction |
| `guide` | Summary + key topics + questions (Markdown) | Wrong length (a few pages of text vs a script), no scene-by-scene structure |
| `flashcard` | Q&A pairs (Markdown/CSV) | Cards are 1-2 sentences, not a 60s arc |
| `mindmap` | Hierarchical tree (Markdown/HTML) | Right structure, but no narration, no pacing, no visual direction |

**Short video is a different artifact**: it has a hook, a conflict, a
turn, a payoff, and a CTA. None of the existing commands produce that
shape. We need a new command.

## Scope of v1 (this design)

**In scope:**

- Script generation (text, 60-90s, scene-by-scene)
- Visual direction (per-scene: what to show, what B-roll to find, what
  text to overlay)
- Multiple styles (反常识 / 励志 / 学术 / 吐槽)
- Multiple platforms (抖音 / B 站 / YouTube Shorts — same script, different
  pacing and language)
- Per-chapter OR per-book (one short per chapter, or one short for the
  whole book)

**Out of scope (for v1):**

- TTS narration (Fish Audio integration is in the existing TTS pipeline
  but the user can do that in CapCut with the script we provide)
- Auto-generated B-roll (would need Replicate Flux or stock-image API —
  not free, slow, often off-topic for abstract concepts)
- Direct .mp4 output (would need moviepy + ffmpeg + Chinese fonts +
  字幕烧录 — large new dependency tree, and the user can do this in
  CapCut in 5 min)
- Music selection (LLM can suggest genre, not actual audio file)

If the user wants any of the out-of-scope items, that's a v2 follow-up
(see "Future" at the bottom).

## Command surface

```bash
# Default: one short video for the whole book (60s, 反常识 style, 抖音 pacing)
shoot-high short ~/my-books

# Per-chapter: one short per detected chapter (writes N output files)
shoot-high short ~/my-books --per-chapter

# Just one chapter
shoot-high short ~/my-books --chapter "第 1 章 磨炼灵魂 提升心志"
shoot-high short ~/my-books --chapter "第 1 章"        # prefix match is OK

# Style
shoot-high short ~/my-books --style 反常识           # default
shoot-high short ~/my-books --style 励志
shoot-high short ~/my-books --style 学术
shoot-high short ~/my-books --style 吐槽             # 脱口秀/单口喜剧 style

# Platform pacing
shoot-high short ~/my-books --platform douyin        # default; 快节奏
shoot-high short ~/my-books --platform bilibili      # 中长,可有几句"黑话"
shoot-high short ~/my-books --platform youtube       # 英文 Shorts

# Duration
shoot-high short ~/my-books --duration 30
shoot-high short ~/my-books --duration 60            # default
shoot-high short ~/my-books --duration 90

# Variants (output 3 versions at once, user picks the best)
shoot-high short ~/my-books --variants 3

# Output format
shoot-high short ~/my-books --format markdown        # default; human-readable
shoot-high short ~/my-books --format json            # for tooling
shoot-high short ~/my-books --format srt             # subtitle file (just the script lines)
```

## Output format (default: markdown)

```markdown
# 短视频脚本：干法 第 1 章 磨炼灵魂，提升心志

## 🎬 视频元信息

- **时长：** 65 秒（约 165 字 / 普通话正常语速）
- **风格：** 反常识钩子
- **平台：** 抖音（快节奏，1.2-1.5× 剪辑）
- **建议配音：** 男声，沉稳，30-40 岁，语速偏慢
- **建议背景音乐：** 低音钢琴，节奏稳定
- **目标受众：** 25-35 岁职场人，被工作意义困扰的

## 🪝 钩子（0-3 秒）

> 字幕（大字居中）：**"78 岁，他重建了日航"**
> 配音：78 岁那年，他接下了一个没人敢接的烂摊子。
> 视觉：黑屏切到稻盛和夫在新闻发布会上的照片（左上角小字幕"稻盛和夫 78 岁"）

## ⚡ 冲突（3-15 秒）

> 字幕：一家亏损 2.3 万亿日元的公司 / 员工集体辞职 / 政府求他出山
> 配音：日航当时账上 2 万多亿日元的窟窿，工会上百次罢工，连日本政府都觉得没救了。
> 视觉：连续三张新闻截图（亏损数字 / 罢工现场 / 头条），每张 4 秒

## 💡 转折（15-45 秒）

> 字幕：**"他每天 12 点前最后一个离开办公室"**
> 配音：他用的方法其实很简单——每天晚上 11 点半，他会跟每一个值班的员工说"辛苦了"。他用一年时间，把日航的利润率做到了全世界第一。
> 视觉：黑白照片（凌晨办公室）→ 切换到彩色（日航飞机升空）

## 🎯 收尾 + CTA（45-60 秒）

> 字幕：**"工作，是磨炼灵魂"**
> 配音：他在《干法》第一章里说，工作不是为钱，是磨炼灵魂。
> 视觉：书的封面特写 → 渐黑 → 出现 "shootHighLM 读书会" 字样
> 字幕（小字）："关注我，下集讲：第 2 章 让自己喜欢上工作"

## 📋 后期清单（用户在 CapCut 里 5 分钟搞定）

- [ ] 找到 1 张稻盛和夫 78 岁时的发布会照片（搜索关键词："稻盛和夫 日航 2010"）
- [ ] 找到 3 张日航亏损 / 罢工 / 重建的新闻截图（同上关键词）
- [ ] 找到 1 张凌晨办公室的泛图（搜索关键词："japanese office night"）
- [ ] 找到《干法》书籍封面（搜索关键词："干法 稻盛和夫 书籍封面"）
- [ ] 录制配音（建议 165 字，60-65 秒；用剪映"图文成片"也行）
- [ ] 背景音乐：剪映搜"低沉钢琴"，选 1-2 段
- [ ] 字幕样式：剪映默认"白色加黑边"，第 1 行 36 字号、其余 28 字号
- [ ] 转场：用"闪白"或"淡入淡出"，1 秒以内
```

## Output format (JSON, for tooling)

```json
{
  "title": "干法 第 1 章 磨炼灵魂，提升心志",
  "duration_s": 65,
  "style": "反常识钩子",
  "platform": "douyin",
  "scenes": [
    {
      "id": "hook",
      "start_s": 0,
      "end_s": 3,
      "voiceover": "78 岁那年，他接下了一个没人敢接的烂摊子。",
      "caption": "78 岁，他重建了日航",
      "visual": {
        "type": "photo",
        "search_keywords": ["稻盛和夫 日航 2010", "Kazuo Inamori JAL"],
        "description": "黑屏切到稻盛和夫在新闻发布会上的照片（左上角小字幕：稻盛和夫 78 岁）"
      },
      "bgm": "低音钢琴，节奏稳定"
    },
    {
      "id": "conflict",
      "start_s": 3,
      "end_s": 15,
      "voiceover": "日航当时账上 2 万多亿日元的窟窿...",
      "caption": "一家亏损 2.3 万亿日元的公司 / 员工集体辞职 / 政府求他出山",
      "visual": {
        "type": "three_photos",
        "search_keywords": ["日航 罢工 2010", "JAL bankruptcy 2010"],
        "description": "连续三张新闻截图（亏损数字 / 罢工现场 / 头条），每张 4 秒"
      }
    }
  ],
  "production_notes": {
    "voice": "男声，沉稳，30-40 岁",
    "bgm_genre": "低沉钢琴",
    "total_word_count": 165,
    "estimated_speech_duration_s": 65
  }
}
```

## Design decisions

### 1. Why 60-90s and not 30s or 3 min?

- **30s is too short** to deliver an actual argument with hook →
  conflict → resolution. You can do a punchline but not a takeaway.
  Useful for "quote of the day" but not "I learned X from chapter Y".
- **3 min is too long** for short-video platforms. The completion rate
  drops past 90s on every major platform (Douyin, Shorts, TikTok).
- **60-90s is the sweet spot** for "one idea, well told".

### 2. Why not just use the podcast script and trim it?

Podcast scripts are **conversational** (host A, host B, "yeah", "hmm"),
**meandering** (8 minutes of exploration, not 60s of argument), and
**have no visual direction** (audio-only medium). Trimming to 60s
loses the conversational charm but keeps the meandering, which is the
worst of both worlds. A short video is a different rhetorical form:
it has a **hook → conflict → turn → payoff** arc that's absent from
podcasts.

### 3. Why not auto-generate the .mp4?

- CapCut / 剪映 / 抖音的图文成片 / Shorts editor all do this in 5 min
  with better results than we could ship in 2 days of moviepy work
- Adds heavy deps: moviepy + Pillow + ffmpeg + Chinese fonts + SRT
  burn-in
- LLM-generated B-roll keywords are 90% accurate; auto-fetched stock
  photos are 60% on-topic (the gap is huge for abstract Chinese
  philosophical concepts)
- Better v1: produce the **script + visual keywords + production
  checklist**, let the user (who already has their favorite video
  editor) finish the video in 5 min. Better than 30 min of
  auto-generated slop.

### 4. Why multiple styles? Why multiple platforms?

- **Style** (`反常识 / 励志 / 学术 / 吐槽`) is a different rhetorical
  appeal. The same book chapter can become 4 different shorts, each
  good for a different audience segment. `--variants 3` outputs 3
  versions at once so the user can A/B test.
- **Platform** (抖音 / B 站 / YouTube) is different pacing + tone:
  - 抖音: 1.2-1.5× 剪辑速度，钩子必须在前 1.5 秒，否则划走
  - B 站: 1.0× 速度，可以使用术语和"黑话"，目标观众更耐心
  - YouTube Shorts: English, slightly slower pacing, can have
    captions-only videos
  - The script body is the same; the pacing notes and the
    `caption` field change

### 5. Why not just produce English for everyone?

Because the user's notebook is 干法 (Chinese philosophy). The LLM has
to write the script **in the book's language** to preserve nuance.
For an English book, the script is in English; for a Chinese book,
Chinese. Platform is a separate axis (you can produce a Chinese
script for YouTube Shorts if you're targeting Chinese-diaspora
audiences).

### 6. Why per-chapter AND per-book?

A 1000-page book doesn't compress into 60s well. Per-chapter is
usually the right granularity: each chapter is ~20 pages, ~6000 chars,
which is exactly the right depth for a 60s script. Per-book is for
"summary" style shorts ("Here's what 《干法》 is about in 60 seconds")
which is a different artifact.

## Implementation plan (when the user says "go")

### Step 1 — `src/shoothighlm/short.py` (~3-4 hours)

```python
class ShortVideoGenerator:
    def __init__(self, chat_model="qwen3.5:cloud", base_url=...):
        ...

    def generate(
        self,
        text: str,
        *,
        title: str = "Document",
        chapter: Optional[str] = None,  # e.g. "第 1 章 磨炼灵魂..."
        style: str = "反常识钩子",  # or 励志 / 学术 / 吐槽
        platform: str = "douyin",  # or bilibili / youtube
        duration_s: int = 60,
        variants: int = 1,
    ) -> List[ShortVideoScript]:
        ...
```

The `generate()` method:
1. Sample the text (use existing `even_sample` / `head_sample` from
   `sampling.py`).
2. If `chapter` is set, slice the text to roughly that chapter's
   range (reuse the `_detect_chapters` helper from `mindmap.py`).
3. Build a prompt with style + platform instructions + the
   sample text.
4. Call `call_ollama()` (the deterministic one we just made).
5. Parse the response into `ShortVideoScript` (Pydantic model).
6. Repeat for `variants` (just call N times — LLM will produce
   different ones thanks to its own internal sampling).

### Step 2 — `shoot-high short` CLI command in `cli.py` (~30 min)

```python
@main.command()
@click.argument("notebook", type=click.Path(exists=True))
@click.option("--chapter", default=None, help="Limit to one chapter (prefix match OK)")
@click.option("--per-chapter", is_flag=True, help="Output one short per chapter")
@click.option("--style", default="反常识", type=click.Choice(["反常识", "励志", "学术", "吐槽"]))
@click.option("--platform", default="douyin", type=click.Choice(["douyin", "bilibili", "youtube"]))
@click.option("--duration", default=60, type=click.IntRange(30, 180))
@click.option("--variants", default=1, type=click.IntRange(1, 5))
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "json", "srt"]))
def short(notebook, chapter, per_chapter, style, platform, duration, variants, fmt):
    """Generate short-video script + visual direction from notebook PDFs."""
    ...
```

### Step 3 — Tests in `tests/test_short.py` (~1 hour, 12-15 tests)

- `--per-chapter` produces N files for N chapters
- `--variants 3` produces 3 distinct outputs
- `--format json` produces valid JSON with all scenes
- `--format srt` produces valid SRT timing
- Empty text → graceful error
- Prompt contains the style + platform + duration

### Step 4 — Doc updates (~20 min)

- README: add `shoot-high short` to the Quick Start with one example
- CHANGELOG: new entry
- gitCommitDetails: new row

### Total: ~6-8 hours, ~15 tests, 1 new file, 1 new CLI command

## What the LLM needs to know (the prompt)

```
You are a Chinese short-video script writer. Your job is to compress
the source text into a 60-second script with a hook, conflict, turn,
and payoff.

STYLE: {style}
  - 反常识: open with a counterintuitive fact. "Most people think X.
    Actually Y." The hook IS the surprise.
  - 励志: open with a struggle. "He was broke / fired / rejected.
    Then he did X." The hook IS the underdog story.
  - 学术: open with a question. "Why do some people succeed where
    others fail?" The hook IS the curiosity gap.
  - 吐槽: open with a hot take. "Popular advice says X. That's
    wrong." The hook IS the controversy.

PLATFORM: {platform}
  - douyin: hook in 1.5s, scenes 3-5s each, subtitles 12-20 字/行,
    1.2-1.5× cut speed
  - bilibili: hook in 3s, scenes 5-8s each, subtitles 20-35 字/行,
    1.0× cut speed, can use 术语 / 黑话
  - youtube (English): hook in 3s, scenes 5-7s each, captions
    8-15 words/line, 1.0× cut, English narration

DURATION: {duration_s} seconds. Target word count = duration × 2.5
  (Chinese: 2.5 字/秒 normal pace).

OUTPUT FORMAT: 4 scenes (hook, conflict, turn, payoff). Each scene
  has voiceover (narration text), caption (subtitle text), visual
  (description + image search keywords), bgm (mood).

RULES:
- The first 3 seconds of the hook MUST be a self-contained sentence
  the viewer can read/understand without context.
- Every scene's voiceover MUST be < 20 字 if duration is 60s, or
  you will run out of time.
- Captions MUST be < 15 字 for douyin, < 20 字 for bilibili.
- The visual description MUST be specific enough that a 剪辑
  (video editor) can find or create the shot in 5 minutes. "Some
  pretty image" is BAD. "稻盛和夫 78 岁在新闻发布会上的照片"
  is GOOD.
- Do NOT use words that don't appear in the source text. If the
  book doesn't mention a number, don't make up a number.

SOURCE TEXT:
{text}
```

## Future (v2+, after v1 ships)

| Feature | Effort | When |
|---|---|---|
| TTS integration (auto-generate .wav per scene) | ~1 day | After v1 is stable, use existing Fish Audio integration |
| Auto-B-roll via Replicate Flux (generate images from `visual.description`) | ~2 days | Replicate key in `~/.shoothighlm/config.yaml`; rate-limited |
| Auto-.mp4 via moviepy + ffmpeg | ~3 days | Drop in last; depends on TTS + B-roll |
| Stock music picker (Free Music Archive / Pixabay) | ~1 day | Just need a list of (mood, track_url) pairs |
| Multi-language output (same script, English + Chinese side-by-side) | ~1 day | Useful for 海外华人 audience |
| "Trending topic" suggestions (LLM suggests hooks that match current trends) | ~1 day | Needs access to trending data — research only for now |
| Per-character breakdown (assign scenes to specific characters in the book, e.g. "稻盛和夫", "曹岫云", "松下幸之助") | ~2 days | Book-specific; needs character detection |

## Open questions for the user

1. **Is "60-90s" the right target?** Or do you want 30s / 2 min / longer?
2. **Do you want per-chapter default or per-book default?** I'm leaning
   per-chapter (better compression), but per-book is what most people
   search for ("1 minute summary of X").
3. **Do you want auto-TTS in v1, or is the script-only v1 enough?**
4. **English or Chinese as the default target language?** I'd default
   to "the book's language" (auto-detect), but if you have a strong
   preference I can hard-code it.
5. **Should we add `shoot-high short` to the `shoot-high batch`
   default?** That is, should `shoot-high batch` include `short` in
   its command registry? Probably **no** (short is a different
   artifact, often you only want 1-2 of them, not all 6+1 per book),
   but worth confirming.
