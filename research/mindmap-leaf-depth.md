# Mindmap Depth: Can We Go Deeper to Leaf-Level Concepts?

> **Date:** 2026-06-14
> **Context:** User asked whether the mindmap can go deeper than the current 2-3 levels, down to the level of individual named principles / quotes / examples (the "leaves" of the table-of-contents tree).
> **Conclusion:** **Yes, mostly.** 3-4 levels of depth is feasible with the current setup. 5+ levels is possible but starts to hit diminishing returns due to (a) token-budget pressure on the LLM, (b) the LLM's tendency to summarize rather than enumerate at the leaves, and (c) the rendering cost (a 500-node markmap is visually overwhelming).
>
> **Recommendation:** Ship a `--depth {1,2,3,4}` flag that lets the user pick how deep to go. Default to 2 (current behavior with the new smart default). The flag is cheap to add because all the plumbing is already there — it's just a prompt-level change.

---

## What "leaf-level" means

For 稻盛和夫管理哲学经典收藏版, the **leaf-level** is things like:

- *极度认真工作能扭转人生* (a specific argument from 干法 chapter 1)
- *倾听产品的哭泣声* (a specific principle from 干法 chapter 2)
- *定价即经营* (a specific tenet of 阿米巴经营)
- *谦虚是福* (a specific aphorism from 领导者的资质)

These are the **named principles / arguments / stories** that the book actually contains. They are the things the LLM is supposed to enumerate (per the prompt's "ENUMERATE, do not summarize" instruction), but in practice the LLM often falls back to summary-level abstractions at the leaves because:

1. **The prompt budget is limited.** Even with 50K chars (`--full`), the LLM only sees 1-2% of a 1,200-page book. The leaves of "philosophy" are easy to invent from context, but the leaves of "named quote" require the LLM to remember exact phrasing — which it can't, because the source text isn't in the prompt.

2. **The LLM is biased toward summary.** Default behavior of any chat-style LLM is to produce nice paragraphs. Even with our "ENUMERATE" instruction, it tends to drift back to theme-level naming for the deepest level.

3. **There's no enforcement.** The current prompt says "leaves should be named principles" but doesn't penalize the LLM for ignoring that.

## How deep can we actually go?

Let me measure the corpus:

```
Total text: 456,269 chars (the 收藏版 PDF)
Chapter headings (第N章) found: 106
  - 6 sub-books × ~17 chapters each ≈ 100 chapter headings
  - (some are duplicates from TOC and per-book chapter listings)

Sample chapter titles:
  第 1 章  磨炼灵魂，提升心志：为什么要工作    (干法 ch.1)
  第 2 章  让自己喜欢上所从事的工作：如何投入工作 (干法 ch.2)
  ...
  第一章  领导者的资质                        (领导者的资质 ch.1)
  第二章  领导者的人格                        (领导者的资质 ch.2)
  ...
```

So the corpus has **~6 sub-books × ~17 chapters × ~3-5 named principles = ~300-500 leaf-level named concepts** waiting to be extracted.

**Realistic depth targets:**

| Depth | Example | Achievable? | Cost |
|---|---|---|---|
| 1 | Book titles only | ✅ Already works | 5-10K tokens |
| 2 | Book → chapter (current smart default) | ✅ Already works | 15-25K tokens |
| 3 | Book → chapter → named principle | ✅ Feasible | 25-40K tokens |
| 4 | Book → chapter → principle → quote/example | ⚠️ Possible but flaky | 40-60K tokens |
| 5+ | Adds "supporting concept" or "named person" | ❌ Diminishing returns | 60K+ tokens |

The reason 4+ is flaky: the LLM doesn't have the actual quote text in the prompt (it's elsewhere in the book, beyond the 50K-char budget). So the LLM has to **invent** quotes, and any invention is a hallucination.

## What's the gap between current and ideal?

Looking at the current mindmap for 收藏版:

```
# 稻盛和夫管理哲学经典收藏版内容
## 工作的根本意义与人生观             (level 2 theme, not a chapter title)
### 磨炼灵魂提升心志修行               (level 3 sub-theme)
### 劳动是万病良药观点                 (level 3 sub-theme)
```

**Current leaf**: "磨炼灵魂提升心志修行" — this is a **theme**, not a named principle.

**What we want at the leaf**: "极度认真工作能扭转人生" (a named argument from 干法 chapter 1) — this is a **specific, citable claim**.

The gap is **named vs. thematic**. The current LLM output uses generic Chinese phrases that summarize; we want it to extract the book's own terminology.

## Why does the LLM produce themes instead of named principles?

Three reasons, in order of impact:

### 1. The LLM doesn't see enough of the book

`even_sample(25K)` for a 456K-char book covers **5.5%** of the text. Most named principles are buried in chapters the LLM never sees. The LLM falls back to "common-sense" 稻盛和夫 topics ("工作态度", "心志提升") because it has read summaries of his work elsewhere in its training data.

**Fix**: `--full` bumps to 50K = 11% coverage. Not enough for a 1200-page book. We're fundamentally limited by the context window of the LLM.

### 2. The prompt asks for named principles, but the LLM is lazy

Our prompt says:

> Each leaf should be a SPECIFIC named principle, method, story, definition, or argument from the book — never a vague theme like "工作态度" (work attitude). Prefer the book's own terminology.

This is in the prompt. But the LLM still produces "磨炼灵魂提升心志修行" because:

- "工作态度" is a hypothetical bad example. The LLM doesn't generalize from this to "all my generic phrases are bad".
- The LLM doesn't have a built-in concept of "named principle" vs "summary".

**Fix**: Make the prompt more explicit. Instead of just "named principle", give a few positive examples from the actual book. This is a prompt engineering improvement.

### 3. The output has no validation

Currently we accept whatever the LLM produces. There's no check that the leaves are specific (e.g., "named principle" should ideally be quoted from the book).

**Fix**: Add a post-processing step that:
- Identifies "thematic" leaves (single CJK words like "工作态度" or "心态转变") and flags them
- Either rejects them or asks the LLM to replace them

This is more work but produces noticeably better output.

## Three implementation paths, ranked

### Path 1: `--depth` flag (recommended, do this first) ✅

Add a `--depth {1,2,3,4}` CLI option that adjusts the prompt's depth target:

- `--depth 1`: only level-1 (parts / books)
- `--depth 2`: level-1 + level-2 (chapters) — current default
- `--depth 3`: level-1 + level-2 + level-3 (named principles) — for deep dives
- `--depth 4`: level-1 through level-4 (named principles + examples) — for completeness

Implementation:
- ~30 lines in `mindmap.py` (a depth-aware prompt block)
- ~10 lines in `cli.py` (the new flag)
- 4 new tests

Cost: Low. The infrastructure is there (the `Strucutre` section of the prompt). We just need to adjust the depth target and the budget per level.

### Path 2: `per-book` two-stage extraction (more work, better quality)

For multi-book collections like 收藏版, do TWO LLM calls:

1. **Stage 1** (per sub-book, in parallel): Extract the level-1/2/3 mind map for THIS sub-book, using only the sub-book's text. ~5K chars per sub-book.
2. **Stage 2** (merge): Combine the per-sub-book trees into one tree, with the sub-book titles as level-1 nodes.

This is better because:
- Each sub-book's LLM call has 100% of its context window dedicated to that sub-book (not 5% of the whole collection).
- The named principles are in the LLM's prompt for the relevant sub-book.
- The LLM is much more likely to extract the book's own terminology.

Cost: 2× the API calls (but in parallel, so wall-clock time stays the same). Better quality at the leaves. Still doesn't help for single books (where the issue is prompt budget, not multi-book splitting).

### Path 3: RAG-driven extraction (most ambitious, biggest payoff)

Use the vectorstore (we already have it!) to do RAG-augmented mindmap generation:

1. **Generate a candidate mindmap** with the current LLM call (works for level 1-2).
2. **For each leaf**, query the vectorstore for chunks that mention the leaf's concept. Get the actual quote / example.
3. **Re-prompt the LLM** with the retrieved chunks and ask it to refine the leaf into a more specific named principle.

This gives us:
- Leaves that are guaranteed to be backed by source text (no hallucinations)
- 4-5 levels of depth, with the deepest level being actual quotes
- A click-through from the mindmap leaf to the source PDF page (huge for the interactive mindmap use case)

Cost: 10-20× the API calls. Much slower. But the leaves become **trustworthy**, which is the most important property for a study tool.

## Recommendation

**Ship Path 1 (--depth flag) NOW.** It's a 1-hour change that gives users explicit control over depth vs. detail trade-off.

**Plan Path 2 (per-book two-stage) for Phase 4.** This requires restructuring the mindmap pipeline and adding a new "per-book extraction" mode, but the quality win for collections like 收藏版 is huge.

**Don't ship Path 3 (RAG-driven) yet.** It's a big architectural change and we should validate the demand for click-through-to-source first via Path 1.

## What about specific sub-trees?

Beyond "depth", the user might also want per-sub-tree depth control — e.g., "go 4 levels deep on 干法 chapter 1, but only 1 level everywhere else". This is a follow-up feature, not on the roadmap yet.

## What I won't change (yet)

**Visual rendering depth.** Even if we extract a 4-level mindmap with 500 nodes, **rendering** it is its own problem:
- Markmap (the lib we use) becomes hard to navigate past ~200 nodes
- The interactive TUI (planned) would need virtualization to handle 500+ nodes
- Print/export of a 500-node mindmap is unwieldy

So: extraction depth can grow, but rendering depth should stay at 2-3 for the default view. The "Expand all" button (just shipped) lets users opt into the full depth when they want it.
