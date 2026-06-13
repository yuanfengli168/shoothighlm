# Mind Map Quality: shootHighLM vs. Google NotebookLM

> **Date:** 2026-06-13
> **Subject:** Both mind maps were generated from the same source PDF: *稻盛和夫经典管理哲学收藏版* (Inamori Kazuo's collected management philosophy — a multi-book compilation).
> **Goal:** Identify why our mind map is dramatically sparser than NotebookLM's, and ship the fixes to close the gap.

## Side-by-side

| shootHighLM (current) | Google NotebookLM |
|---|---|
| ![shootHighLM mind map](mindmap-comparison-shoothighlm.png) | ![NotebookLM mind map](mindmap-comparison-notebooklm.png) |
| ~38 visible nodes · 2-3 levels deep · theme-style labels | ~110+ visible nodes · 4 levels deep · TOC-style with named principles |

The size and density difference is immediately obvious. The shootHighLM output looks like a "themes I noticed" summary; the NotebookLM output looks like an actual **table of contents** of the book — every part, every chapter, every named concept, every argument is its own node.

## Structural comparison

| Dimension | NotebookLM | shootHighLM (current) | Gap |
|---|---|---|---|
| **Total nodes** | ~110+ | ~38 | ~3× fewer |
| **Depth** | 4 levels (book → part → chapter → concept) | 2-3 levels (book → theme → concept) | One level short |
| **Branches per parent** | 4-7 | 1-3 | Sparse |
| **Leaves per branch** | 3-5 | 0-2 | Thin |
| **Concept granularity** | Atomic actions, named principles, quotable phrases | Theme labels | Generic |
| **Title language** | Uses the book's own terminology | Sometimes paraphrases | Drift |

## The 5 root causes

### 1. Schema is too shallow (biggest cause)

Our prompt asks for `id` / `title` / `notes` / `children` with 2-4 levels of depth. NotebookLM's mind map is essentially a **book table-of-contents** — every chapter, every section, every named principle gets its own node. The LLM needs explicit permission (and explicit numerical targets) to go 4 levels deep and to enumerate rather than summarize.

> **NotebookLM example:** `《干法》→ 工作的意义与目的 → 极度认真工作扭转人生 / 工作造就人格与心志`
>
> **shootHighLM example:** `《干法》→ 工作的意义与目的 → 极度认真工作扭转人生` (only 1 leaf under this theme)

### 2. Prompt says "summarize", not "enumerate"

Current prompt: *"Identify the main topics and subtopics... Create a tree structure with 2-4 levels of depth"*. This phrasing biases the model toward **abstract themes**, not concrete content. NotebookLM's underlying prompt almost certainly says something like *"extract every named principle, method, story, and key concept as separate nodes"*.

### 3. Default 12K-char budget is too tight for enumeration

Even with the new `stratified_sample`, 12K covers ~3-4K tokens — on a 1,000-page book that's the **table of contents + foreword + 2-3 chapters**. The model literally doesn't see most of the book, so it can't enumerate. NotebookLM almost certainly uses the whole book (or huge chunks).

### 4. Top-down bias in the prompt sampling

Our `stratified_sample` is **40% start / 40% middle / 20% end**. That's much better than `text[:12000]`, but it still **over-weights the intro and conclusion** (which are summaries themselves, not raw content). For mind-map extraction we want **spread across the whole book** — e.g. 10 equal slices. The current design optimizes for chat-style context (where the intro sets the topic); mind maps want enumeration of contents.

### 5. No "leaves = concrete content" instruction

The prompt says *Each node should have a clear, concise title (5-15 words)*. That's fine, but it doesn't say **"leaves should be specific named principles, methods, or stories from the book — not general topics"**. NotebookLM leaves are concrete things like *极度认真工作扭转人生* (a named argument from the book), not *关于工作的观点* (vague theme).

## The fix (3 code changes, no new dependencies)

| # | Fix | Where | Impact |
|---|---|---|---|
| **A** | Rewrite prompt to enumerate (target 80-150 nodes, 4 levels deep, "leaves = named principles") | [`src/shoothighlm/mindmap.py`](mindmap.py) | Biggest single win — 2-3× node count |
| **B** | Add `even_sample()` to [`sampling.py`](sampling.py) — N evenly-spaced windows instead of 40/40/20 | New ~25-line function | Better coverage of long books |
| **C** | Bump mindmap default budget 12K → 25K chars | [`mindmap.py`](mindmap.py) | Cheaper than `--full`, still fast |

### Detailed changes

**A. New prompt** (replaces lines 100-130 in `mindmap.py`):

```python
prompt = f"""You are a book table-of-contents extractor. Extract a HIERARCHICAL,
COMPREHENSIVE mind map of the book — NOT a summary.

## Approach
- Enumerate, do not summarize. If the book has 12 chapters, the map has 12 level-1 nodes.
- Each leaf should be a SPECIFIC named principle, method, story, definition, or
  argument from the book — never a vague theme.
- Aim for 80-150 total nodes. A 1,000-page book deserves a rich map, not a
  10-bullet list.
- Use the book's own terminology. If the book calls a concept "极度认真工作",
  do not paraphrase it to "工作态度".

## Structure (3-4 levels of depth)
- Level 1: parts / sections / major themes (5-10 nodes)
- Level 2: chapters or major arguments (3-7 per level-1 node)
- Level 3: key concepts under each chapter (2-5 per level-2 node)
- Level 4 (optional): concrete examples, named people, formulas, quotable phrases
- Every node has a short title (3-12 words, in the book's language).
- Use the `notes` field for a 1-sentence explanation ONLY when the title
  alone is ambiguous.

## Output
ONLY valid JSON. No commentary, no markdown outside the JSON block.
"""
```

**B. New `even_sample()` in `sampling.py`:**

```python
def even_sample(text: str, max_chars: int, slices: int = 10) -> str:
    """Sample `text` as `slices` evenly-spaced windows.

    Best for mind-map / table-of-contents extraction where you need
    to see the whole book, not just the start. The current default
    `stratified_sample` is biased toward the intro; `even_sample` is
    uniform.
    """
    n = len(text)
    if n <= max_chars:
        return text
    slice_size = max_chars // slices
    out = []
    for i in range(slices):
        start = (n * i) // slices
        end = min(n, start + slice_size + slice_size // 20)  # 5% overlap
        out.append(_truncate_at_boundary(text[start:end], slice_size))
    return "\n\n[... section break ...]\n\n".join(out)
```

**C. New defaults in `mindmap.py`:**

```python
# Default 25K chars (was 12K) — covers more of the book without paying
# the --full latency penalty. Uses even_sample for uniform coverage.
max_chars = 50000 if use_full else 25000
if len(text) > max_chars:
    text = (even_sample(text, max_chars)
            if not use_full
            else head_sample(text, max_chars))
```

## Why this matters

This is shootHighLM's **blue ocean differentiator** (see [blueOcean.md](../doc/blueOcean.md)) — the interactive mind map. If a NotebookLM user opens their export and sees a 110-node, 4-deep TOC-shaped mind map, then opens ours and sees a 38-node, 2-deep themes list, the perceived quality gap is huge — even if the LLM is the same model.

The fix is mostly **prompt engineering + sampling strategy** (about 50 lines, no new dependencies). After the fix, regenerating the same `dao-sheng-he-fu` mind map should produce 2-3× the node count, one extra level of depth, and leaves that match the book's own language — i.e. parity with NotebookLM's output for the same book.

## Status

- **2026-06-13:** Fixes A, B, C **shipped** in this commit. The `mindmap` default now uses 25K chars + `even_sample` and a new enumeration-focused prompt. `--full` still uses 50K chars + `head_sample`. Other commands (flashcard, podcast, guide, infographic, tables) are unchanged and still use `stratified_sample` — they have different optimization goals (depth vs. breadth) and their current 12K default works fine.
