# Short Video Generation (`shoot-high short`)

> **Status:** 🟡 **Design LOCKED-IN** (all open questions resolved 2026-06-16 — no code yet; see Implementation Plan at the bottom)
> **Last updated:** 2026-06-16
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

**Two product shapes, one command:**

| Mode | What it is | Default duration | Default style | Use case |
|---|---|---|---|---|
| **Per-book** (default) | 1 个连续脚本 = 1 个短视频 = 整本书的"纪录短片" | **5 分钟** (300s) | **纪录短片** (new) | "用 5 分钟给我讲完这本书" — B 站/小红书/YouTube 中视频 |
| **Per-chapter** (`--chapter` / `--per-chapter`) | 1 个 60s 脚本 = 1 个短视频 = 一章的核心 | **60-90s** | 4 种风格可选 (反常识/励志/学术/吐槽) | 抖音/快手/TikTok 短视频投放 |

**In scope:**

- Script generation (text, scene-by-scene) for both shapes
- Visual direction (per-scene: what to show, what B-roll to find, what
  text to overlay)
- Per-book style: 纪录短片 (single default for v1, more in v2)
- Per-chapter styles: 反常识 / 励志 / 学术 / 吐槽
- Multiple platforms (抖音 / B 站 / YouTube — same script, different
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
# Per-book (default): 1 个 5 分钟的"纪录短片"
shoot-high short ~/my-books
# = shoot-high short ~/my-books --book --duration 300 --style 纪录短片

# Per-book 但压到 1 分钟（"用 60s 给我讲完这本书"）
shoot-high short ~/my-books --book --duration 60

# Per-book 但压到 90s（抖音友好）
shoot-high short ~/my-books --book --duration 90

# Per-chapter: 1 个 60-90s 视频 = 一章
shoot-high short ~/my-books --chapter "第 1 章 磨炼灵魂 提升心志"
shoot-high short ~/my-books --chapter "第 1 章"        # prefix match is OK

# Per-chapter × N: 整本书每个章节一个视频
shoot-high short ~/my-books --per-chapter

# Per-chapter 风格 (4 种)
shoot-high short ~/my-books --chapter "第 1 章" --style 反常识   # default
shoot-high short ~/my-books --chapter "第 1 章" --style 励志
shoot-high short ~/my-books --chapter "第 1 章" --style 学术
shoot-high short ~/my-books --chapter "第 1 章" --style 吐槽     # 脱口秀/单口喜剧

# Platform pacing
# Per-chapter default: douyin. Per-book default: xiaohongshu.
shoot-high short ~/my-books --platform douyin        # per-chapter default; 快节奏
shoot-high short ~/my-books --platform xiaohongshu   # per-book default; 视频笔记
shoot-high short ~/my-books --platform bilibili      # 中长,可有几句"黑话"
shoot-high short ~/my-books --platform youtube       # 英文 Shorts

# Duration (default depends on mode; see above)
shoot-high short ~/my-books --book --duration 300     # explicit
shoot-high short ~/my-books --book --duration 60
shoot-high short ~/my-books --book --duration 90
shoot-high short ~/my-books --chapter "第 1 章" --duration 60
shoot-high short ~/my-books --chapter "第 1 章" --duration 90

# Variants (output 3 versions at once, user picks the best)
shoot-high short ~/my-books --variants 3

# Output format
shoot-high short ~/my-books --format markdown        # default; human-readable
shoot-high short ~/my-books --format json            # for tooling
shoot-high short ~/my-books --format srt             # subtitle file (just the script lines)
```

## Output format (default: markdown)

The output format is the same shape regardless of per-book / per-chapter
— it's always a 3-act script. The difference is in the **act structure**
and the **word count** (which controls the duration).

### Per-chapter sample (60-90s, 4 幕)

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

### Per-book sample (5 分钟, 纪录短片 风格, 6 幕)

Per-book uses a **3-act macro structure** (cold-open → arc → 收束), not
4 幕. 5 分钟可以容纳 2-3 个完整的 hook→payoff 循环（per-chapter 的 1
个不够），所以 act 数量更多。

```markdown
# 短视频脚本：干法 稻盛和夫 5 分钟讲完

## 🎬 视频元信息

- **时长：** 5 分钟（约 750 字 / 普通话 2.5 字/秒）
- **风格：** 纪录短片（中性 + 数据 + 故事 + 结论）
- **平台：** B 站（5 分钟短纪录片，目标观众耐心高一点）
- **建议配音：** 男声，中低音，30-40 岁，语速中等
- **建议背景音乐：** 前 1 分钟低沉钢琴，中段加入柔和弦乐，结尾留白
- **目标受众：** 25-40 岁职场人 + 创业者，对稻盛和夫/工作哲学有兴趣

## 🎬 冷开场（0-20 秒）｜ 钩子：1 个具体数字

> 字幕（大字）：**"1 年 / 破产 → 全球第一"**
> 配音：2010 年 2 月，日航申请破产保护。1 年零 3 个月后，它的利润率做到了全世界 727 家航空公司里的第一名。
> 视觉：黑屏 + 字幕 "2010" → 切换到日航飞机停在停机坪的远景 → 字幕浮现 "全球第一"

## 📍 段落 1：人物（20-90 秒）｜ 这个人是谁？

> 配音：接下这个烂摊子的人，叫稻盛和夫。他是个科学家，27 岁创办了京瓷，又在 52 岁时创办了 KDDI。这两家公司都做进了世界 500 强。然后他退休，去当和尚了。
> 字幕卡：稻盛和夫 / 1932- / 科学家 / 企业家 / 哲学家 / 78 岁出山
> 视觉：稻盛和夫年轻时实验室照片 → 中年西装照 → 老年僧袍照（三连拍，每张 5 秒）

## ⚡ 段落 2：方法（90-210 秒）｜ 他做了什么？

> 配音：他做的第一件事不是改革，是重新定义"工作"。他在《干法》里写：劳动是万病良药，工作能磨炼灵魂。
> 字幕卡（30 秒卡，固定不动）：**"工作 = 磨炼灵魂"**
> 视觉：书的封面特写（5 秒）→ 一段稻盛和夫讲"为什么工作"的演讲片段（带字幕，60 秒）→ 切换到员工鼓掌照片（5 秒）

> 配音：第二件事：把哲学落到每天的细节。每天晨会念公司哲学 30 分钟；每个员工必须背会"六项精进"；管理者不能比员工早下班。
> 字幕卡：**"6 项精进 / 每天晨会 30 分钟 / 管理者最后走"**
> 视觉：剪影动画（员工 → 晨会 → 朗读哲学 → 下班）配时间线（90 秒流程图）

## 🎯 段落 3：结果（210-270 秒）｜ 数据落地

> 配音：一年后，日航的营业利润从亏损 1800 亿日元，到盈利 1800 亿。员工满意度，从 2010 年的全行业最低，2013 年变成全行业最高。
> 字幕卡（数字大字）：**"-1800 亿 → +1800 亿"**（停留 8 秒）
> 字幕卡：**"员工满意度：行业最低 → 行业最高"**（停留 5 秒）
> 视觉：财务报表（黑底红字 → 黑底绿字，2 秒反转动画）

## 🧠 收束（270-300 秒）｜ 一句话总结 + 留钩

> 配音：稻盛和夫说，工作的意义不是赚钱，是磨炼灵魂。这本书叫《干法》，讲的就是这个。
> 字幕卡（最后一帧，停留 8 秒）：**"工作 = 磨炼灵魂"** + **《干法》** 封面 + **"shootHighLM 读书会"**
> 视觉：黑屏 → 字幕浮现 → 书的封面（2 秒）→ 黑屏

## 📋 后期清单（用户在 CapCut 里 30 分钟搞定）

- [ ] 找到 1 段日航破产新闻（2010，搜索："JAL bankruptcy 2010"）
- [ ] 找到 3 张稻盛和夫的照片（年轻/中年/老年，分别搜索"Kazuo Inamori young", "Kazuo Inamori KDDI", "稻盛和夫 僧袍"）
- [ ] 找到 1 段稻盛和夫演讲片段（B 站搜："稻盛和夫 工作"）
- [ ] 找到 1 段日航员工鼓掌照片（搜索："JAL employees celebration 2013"）
- [ ] 找到 1 张《干法》书籍封面
- [ ] 找到 1 段剪影动画素材（剪映搜"团队合作剪影"或"职场剪影"）
- [ ] 录制配音（750 字，5 分钟；用剪映"图文成片"也行）
- [ ] 背景音乐：剪映搜"纪录片配乐"，选 1 段（推荐 5-6 分钟的连续 BGM）
- [ ] 数字字幕：剪映"花字"模板里的"大字弹出"效果（关键 3 个数字：-1800 → +1800、最低 → 最高、1 年）
- [ ] 转场：段落间用"2 秒黑场 + 字幕卡"（这是纪录片的标志节奏）
- [ ] 字幕样式：剪映"纪录片白字黑边"，32 字号，每行 ≤ 22 字

### 为什么是 6 幕而不是 4 幕？

- 4 幕（hook/conflict/turn/payoff）适合 60s 紧凑节奏
- 5 分钟需要"人物介绍 + 方法 + 数据 + 收束"4 个独立信息块，外加开场钩子和结尾
- 6 幕 = 钩子 + 人物 + 方法 + 数据 + 收束 + 一句话总结
- 每幕 30-60s，5 分钟能容纳；压缩到 4 幕会丢掉"人物"和"数据"两块
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

### 1. Why 60-90s for per-chapter, and 5 min for per-book?

These are **two different artifacts** with different optimal lengths:

- **Per-chapter (60-90s):** 1 chapter is ~20 pages, ~6000 chars. The
  right "深度" for a 60-90s 短视频 is "1 idea, well told" — hook,
  conflict, payoff, CTA. Past 90s the completion rate on Douyin /
  Shorts / TikTok drops sharply. Past 2 min you've lost the
  short-video audience.
- **Per-book (5 min):** 1 book is ~250-1000 pages. 60s cannot do it
  justice (you'd reduce 《干法》 to "稻盛和夫说努力工作" which is
  true but useless). 5 min is the **sweet spot for "短纪录片"** —
  enough for 人物介绍 + 方法展开 + 数据落地 + 收束. Past 8 min
  we're competing with the existing `podcast` command. Past 10 min
  we're competing with Bilibili mid-form video (a different
  audience).

The 5-min cap is intentional — v1 doesn't try to replace the
`podcast` command's 8-min 2-host format or Bilibili's 20-min review
videos. We sit **between** them.

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

### Step 1 — `src/shoothighlm/short.py` (~4-5 hours)

```python
class ShortVideoGenerator:
    def __init__(self, chat_model="qwen3.5:cloud", base_url=...):
        ...

    def generate(
        self,
        text: str,
        *,
        title: str = "Document",
        mode: str = "per_book",  # "per_book" (default) or "per_chapter"
        chapter: Optional[str] = None,  # only for per_chapter
        style: str = "纪录短片",  # per_book: 纪录短片; per_chapter: 反常识/励志/学术/吐槽
        language: str = "auto",  # auto-detect | "zh" | "en" (resolved per book)
        platform: Optional[str] = None,  # None → "xiaohongshu" for per_book, "douyin" for per_chapter
        duration_s: Optional[int] = None,  # None → 300 for per_book, 60 for per_chapter
        variants: int = 1,
    ) -> List[ShortVideoScript]:
        ...
```

The `generate()` method:
1. **Detect language** (if `language == "auto"`): scan the text for
   CJK vs Latin character ratio. >30% CJK → "zh", else "en". This
   becomes the script's output language and the LLM is told.
2. **Detect sub-books** (via `_detect_sub_books` from `mindmap.py`).
   If `mode == "per_book"` AND `len(sub_books) > 1`, recurse: for
   each sub-book, slice the text to that sub-book's
   `[start, end)` range and emit one 5-min video per sub-book.
   Output filenames: `output/short-{subbook-stem}-book.md`.
3. If `mode == "per_chapter"` and `chapter` is set, slice the text
   to that chapter's range (reuse `_detect_chapters` from
   `mindmap.py`). If `per_chapter` and no `chapter` set, error.
4. Sample the text (use `even_sample` / `head_sample` from
   `sampling.py`). For per-book 5 min, the 50K-char full sample is
   enough (matches mindmap); for per-chapter 60s, even smaller.
5. Build the prompt — use **per-chapter template** or **per-book
   template** (see "What the LLM needs to know" above).
6. Call `call_ollama()` (deterministic, temperature=0, seed=42).
7. Parse the response into `ShortVideoScript` (Pydantic model).
8. Repeat for `variants` (N times — LLM will produce different
   ones thanks to its own internal randomness, even with
   temperature=0, due to model-load-time variations).

Two different prompt templates means two different LLM-call functions:
- `generate_per_chapter(...)` → 4-act script
- `generate_per_book(...)` → 6-act script

Both share the same parsing + output-format code; only the prompt
template and the act-count validation differ.

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

The prompt differs by **mode** (per-book vs per-chapter). Per-chapter
is the original 4-act shape; per-book is a 6-act documentary shape.

### Per-chapter prompt (60-90s)

```
You are a Chinese short-video script writer. Your job is to compress
ONE CHAPTER of the source text into a {duration_s}-second script with
a hook, conflict, turn, and payoff.

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

SOURCE TEXT (this chapter only):
{text}
```

### Per-book prompt (5 min, 纪录短片)

```
You are a Chinese short-documentary script writer. Your job is to
compress the SOURCE TEXT (a full book) into a {duration_s}-second
script with a 3-act documentary structure: cold-open + arc + 收束.

STYLE: 纪录短片 (default, only option for per-book in v1)
  - Tone: neutral, observational, with data + story + conclusion.
    Think 《纽约时报》The Daily condensed to 5 min, or a
    Vox explainer.
  - No hot takes, no controversy, no "you'll never believe".
    This is NOT a YouTube thumbnail — it's a thoughtful summary
    for someone who has 5 minutes and wants to actually
    understand the book.
  - Voice: third person, "稻盛和夫做了 X" / "数据显示 Y". Not
    "你应该 X".

PLATFORM: {platform}
  - douyin: not recommended for 5 min (5 min exceeds 抖音's
    sweet spot). Use bilibili or youtube.
  - bilibili: scenes 30-60s each, subtitles 20-35 字/行, 1.0×
    cut speed, 2-second black-card transitions between acts
  - youtube (English): scenes 45-90s each, captions
    10-18 words/line, 1.0× cut, English narration

DURATION: {duration_s} seconds. Target word count = duration × 2.5
  (Chinese: 2.5 字/秒 normal pace). For 300s, that's ~750 字.

OUTPUT FORMAT: 6 acts (cold-open, 人物, 方法, 数据, 收束, 一句话总结).
  Each act has voiceover (narration text), caption (字幕卡 text),
  visual (description + image search keywords), bgm (mood).

ACT-BY-ACT STRUCTURE (for 5 min):
- 冷开场 (0-20s, ~50 字): a single specific number / concrete
  fact that grabs attention. The hook IS the data, not a story.
  Example: "2010 年 2 月，日航申请破产保护。1 年零 3 个月后，
  它的利润率做到了全世界 727 家航空公司里的第一名。"
- 人物 (20-90s, ~175 字): who is this person? 3 key facts.
  Establish credibility without biography dump.
- 方法 (90-210s, ~300 字): what did they actually DO? The
  concrete steps / philosophy / methodology. This is the longest
  act because it's the value delivery.
- 数据 (210-270s, ~150 字): what were the measurable outcomes?
  Specific numbers, before/after. Show don't tell.
- 收束 (270-290s, ~50 字): one sentence takeaway that connects
  back to the cold-open's data point. Symmetry.
- 一句话总结 (290-300s, ~25 字): the ONE thing the viewer should
  remember. Make it quotable, screenshot-able.

RULES:
- The cold-open MUST lead with a specific number, not a story.
  "1 年 / 破产 → 全球第一" is GOOD. "他做了一件不可思议的事"
  is BAD.
- Every act's voiceover MUST be 50-300 字. Going over 300 in a
  single act means the structure is wrong (you tried to fit 2 acts
  in 1).
- The 方法 act is the longest. If another act is longer, the
  script is wrong.
- Use the book's actual numbers. "公司员工从 1000 增加到 5000"
  is GOOD if that's in the book. "公司员工增长 5 倍" is BAD
  unless the book says that exact phrasing.
- The 一句话总结 MUST be a quotable, screenshot-able sentence.
  "工作不是为钱，是磨炼灵魂" is GOOD. "这本书告诉我们很多
  关于工作的道理" is BAD.

SOURCE TEXT (the full book, may be summarized):
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

(Updated 2026-06-16 — all open questions resolved by user.)

~~1. Is "60-90s" the right target?~~ — **Resolved: 60-90s for
per-chapter, 5min for per-book.**

~~2. Per-chapter default or per-book default?~~ — **Resolved:
per-book is default (5min 纪录短片), per-chapter via `--chapter`
or `--per-chapter`. User chose this on 2026-06-15.**

~~3. Auto-TTS in v1?~~ — **Resolved: NO TTS in v1. User produces
audio in CapCut from the script we provide.**

All 5 open questions answered by user on 2026-06-16:

1. **Default target language** — **AUTO-DETECT from the book's
   language.** The `ShortVideoGenerator.detect_language()` helper
   will scan the source text for CJK vs Latin character ratio and
   pick Chinese (zh) or English (en) accordingly. The LLM is then
   told to write the script in the detected language. `--language`
   flag lets the user override.

2. **`shoot-high short` in `shoot-high batch`?** — **NO.** Short
   video is a deliberately-paced artifact (one per book or one
   per chapter), not a "run all 6 commands" candidate. The user
   confirmed. The batch registry stays at 6 commands
   (mindmap/flashcard/podcast/guide/infographic/tables).

3. **5 min output for collections** — **ONE 5-min video PER
   sub-book, not one for the whole collection.** Reasoning: a
   6-book 收藏版 doesn't compress to 5 min without losing every
   book's identity. Better to emit 6 separate 5-min videos (one
   per sub-book) and let the user pick which to publish.
   Implementation: when `_detect_sub_books()` returns > 1 book,
   the per-book mode loops over each sub-book range, slices the
   text to that sub-book's characters, and produces one 5-min
   script per sub-book. Output files:
   `output/short-{subbook}-book.md` × N.

4. **Default 纪录短片 platform** — **小红书 (xiaohongshu).**
   Reasoning: 小红书 is the sweet spot for 5 min — same audience
   as 抖音 but more patient (avg watch time on 小红书 is higher
   for 3-5 min content), and 小红书's "视频笔记" format
   explicitly supports 5 min essays. The per-chapter mode stays
   on 抖音 (60-90s short-video is 抖音's wheelhouse). The
   `--platform` flag still accepts douyin / bilibili / xiaohongshu
   / youtube for explicit override.

5. **Variant reproducibility** — **Defer until v1 ships; will
   test empirically.** Implementation note for the coder: if
   `temperature=0 + seed=42` produces 3 identical outputs
   (likely), the LLM call needs to vary the prompt per variant
   (e.g. "approach 1: data-driven", "approach 2: story-driven",
   "approach 3: contrarian"). Build the prompt-template
   variation in, but don't over-engineer before measuring.

## Final v1 spec (locked-in, 2026-06-16)

| Item | Value |
|---|---|
| Default mode | per-book (5 min, 纪录短片) |
| Sub-book handling | ONE 5-min video per sub-book (loops over `_detect_sub_books`) |
| Default language | auto-detect (CJK vs Latin) |
| Per-chapter default platform | 抖音 |
| Per-book default platform | 小红书 |
| Styles (per-chapter only) | 反常识 / 励志 / 学术 / 吐槽 |
| Per-book style | 纪录短片 (single option in v1) |
| TTS | NOT in v1 |
| B-roll auto-gen | NOT in v1 |
| .mp4 auto-gen | NOT in v1 |
| Output formats | markdown / json / srt |
| Variants | `--variants N` (1-5), each variant tries a different prompt angle |
| Default duration | per-book=300s, per-chapter=60s |
| Allowed duration range | per-book=60-600s, per-chapter=30-180s |
