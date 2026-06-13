"""Smart text sampling for LLM prompts.

Replaces the naive `text[:max_chars]` truncation that the six
LLM-using modules (mindmap, flashcard, podcast, guide, infographic,
tables) all used to do. That approach takes only the **start** of a
document, so for a 1,200-page book it over-samples the intro / TOC and
misses the conclusion and synthesis.

Three sampling strategies are exposed:

- `head_sample(text, max_chars)` — kept for `--full` and tests. Takes
  the first N chars. Fast, but biased toward the start.

- `stratified_sample(text, max_chars, start_pct=0.4, mid_pct=0.4, end_pct=0.2)`
  — the default for **summary** tasks (flashcard, podcast, guide,
  infographic, tables). Splits the budget into three windows (start,
  middle, end) and concatenates them. Covers the whole book while
  still preferring the introduction, which is what you want for
  generating coherent prose from a long source.

- `even_sample(text, max_chars, slices=10)` — the default for the
  **mindmap** command. Takes N evenly-spaced windows through the text
  with a small overlap. Best for table-of-contents extraction, where
  you need to enumerate the whole book, not just the start.

All three helpers truncate at the last sentence/paragraph boundary
before the cut, to avoid chopping mid-word. This is the same logic
the embedding module uses, factored into a shared helper.

See doc/Todo.md § "Smarter LLM prompt sampling" for the design
discussion.
"""

# Sentence/paragraph boundaries we try to break on, in order of
# preference. We pick the latest one that is past 70% of the budget.
_SENTENCE_SEPARATORS = ("\n\n", "。", "！", "？", ". ", "\n")


def _truncate_at_boundary(text: str, limit: int) -> str:
    """Cut `text` to <= `limit` chars, breaking at the latest sentence
    or paragraph boundary before the limit. Falls back to a hard cut
    if no boundary is found in the last 30% of the window.
    """
    if len(text) <= limit:
        return text
    window = text[:limit]
    for sep in _SENTENCE_SEPARATORS:
        idx = window.rfind(sep)
        if idx > limit * 0.7:
            return window[: idx + len(sep)]
    return window


def head_sample(text: str, max_chars: int) -> str:
    """Take the first `max_chars` of `text`, breaking at a sentence
    boundary when possible.

    This is the historical behavior; preserved for `--full` and as a
    fast fallback when `stratified_sample` is overkill (e.g. very
    short text where all three windows would overlap anyway).
    """
    if len(text) <= max_chars:
        return text
    return _truncate_at_boundary(text, max_chars) + "... [truncated]"


def stratified_sample(
    text: str,
    max_chars: int,
    start_pct: float = 0.4,
    mid_pct: float = 0.4,
    end_pct: float = 0.2,
) -> str:
    """Sample `text` using three windows: start, middle, end.

    Splits the budget `max_chars` into three blocks according to
    `start_pct` / `mid_pct` / `end_pct` (must sum to 1.0), then
    concatenates them with clear section markers. Each block is
    truncated at a sentence boundary.

    This gives the LLM a representative slice of the whole document
    instead of just the intro. For a 1,200-page book, default split
    (40 / 40 / 20) means ~5K chars of intro, ~5K chars from the
    middle, ~2.5K chars from the end — enough to capture the
    conclusion while keeping the intro as the dominant context.

    Args:
        text: The full text to sample from.
        max_chars: Total character budget for the output.
        start_pct: Fraction of budget taken from the start of the
            document. Default 0.4.
        mid_pct: Fraction of budget taken from the middle.
            Default 0.4.
        end_pct: Fraction of budget taken from the end.
            Default 0.2.

    Returns:
        A string of at most `max_chars` characters, with clear
        `[...]` markers between the three windows.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    total = start_pct + mid_pct + end_pct
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"start_pct + mid_pct + end_pct must sum to 1.0, got {total}"
        )

    n = len(text)
    start_budget = int(max_chars * start_pct)
    mid_budget = int(max_chars * mid_pct)
    end_budget = max_chars - start_budget - mid_budget

    # Each window sits at: start of doc, middle of doc, end of doc.
    # For short docs where windows would overlap heavily, fall back
    # to head_sample so we don't duplicate the same range three times.
    if start_budget + mid_budget + end_budget > n:
        return head_sample(text, max_chars)

    start_block = _truncate_at_boundary(text[:start_budget], start_budget)

    mid_start = (n - mid_budget) // 2
    mid_window = text[mid_start : mid_start + mid_budget]
    mid_block = _truncate_at_boundary(mid_window, mid_budget)

    end_window = text[-end_budget:]
    end_block = _truncate_at_boundary(end_window, end_budget)

    return (
        f"{start_block}"
        f"\n\n[... middle of document ...]\n\n"
        f"{mid_block}"
        f"\n\n[... end of document ...]\n\n"
        f"{end_block}"
    )


def even_sample(text: str, max_chars: int, slices: int = 10) -> str:
    """Sample `text` as `slices` evenly-spaced windows.

    Best for mind-map / table-of-contents extraction where you need
    to see the whole book, not just the start. Unlike
    `stratified_sample`, which over-weights the intro and conclusion,
    `even_sample` is uniform: every slice of the book gets the same
    amount of budget.

    A small overlap (5%) between adjacent slices keeps sentences from
    being chopped at slice boundaries. Each slice is itself truncated
    at a sentence boundary.

    Args:
        text: The full text to sample from.
        max_chars: Total character budget for the output.
        slices: Number of evenly-spaced windows. Default 10, which
            gives good coverage for a 1,000-page book at a 25K-char
            budget (~2.5K chars per slice, ~625 tokens per slice).

    Returns:
        A string of at most `max_chars` characters, with clear
        `[... section break ...]` markers between the slices.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    if slices < 1:
        raise ValueError(f"slices must be >= 1, got {slices}")
    n = len(text)
    slice_size = max_chars // slices
    if slice_size < 1:
        # Degenerate: more slices than characters. Fall back to
        # head_sample so the caller still gets a sensible result.
        return head_sample(text, max_chars)

    out = []
    for i in range(slices):
        start = (n * i) // slices
        end = min(n, start + slice_size + slice_size // 20)  # 5% overlap
        out.append(_truncate_at_boundary(text[start:end], slice_size))
    return "\n\n[... section break ...]\n\n".join(out)
