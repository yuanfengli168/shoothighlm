"""Mind map extraction from PDF content"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
import json
import httpx
from .sampling import even_sample, head_sample
from .llm import LLMUsage, call_ollama


def _parse_table_of_contents(text: str) -> List[str]:
    """Extract the sub-book titles from the table of contents at the
    start of a multi-book collection PDF.

    Chinese book collections (e.g. "稻盛和夫经典管理哲学收藏版")
    list all sub-books in a clear `目录` (table of contents) section
    in the first ~1000 chars. The format is:

        目录
        干法
        领导者的资质
        调动员工积极性的七个关键：稻盛和夫经营问答
        阿米巴经营（实战篇）
        拯救人类的哲学

    Each title is on its own line, often with a short subtitle
    separated by `：` or `:`. The titles don't have `《》` brackets
    in the TOC itself.

    We look for the `目录` marker (or English equivalents like
    `Contents`, `Table of Contents`) in the first 3% of the text,
    then read forward until we hit a line that doesn't look like a
    title (chapter heading, ISBN, page numbers, etc.).

    We STOP reading titles when we see:
      - A second `目录` marker (we've hit a per-book chapter list)
      - A `第N章` / `第N部分` / `附录` marker (chapter-level)
      - A line starting with `ISBN` / `（日）` / `(` / `译者`
      - A line >= 20 chars long (title page has long lines like
        "曹岫云  稻盛和夫（北京）管理顾问有限公司董事长")
      - A line that ends in a sentence terminator (。 ! ? .)
        followed by another line (paragraph text)

    Returns a list of title strings. If no TOC is found, returns [].
    """
    if not text:
        return []
    n = len(text)
    # Look in the first 3% (where the cover and TOC live). The TOC
    # marker is usually within the first 1500 chars.
    head = text[: max(1500, n // 33)]

    # Find the FIRST TOC marker (we don't want the per-book chapter
    # lists that come later in the file)
    toc_patterns = ["目录", "目  录"]
    toc_idx = -1
    for pat in toc_patterns:
        idx = head.find(pat)
        if idx != -1:
            toc_idx = idx + len(pat)
            break
    if toc_idx == -1:
        # Try English
        for pat in ["Contents", "TABLE OF CONTENTS", "Table of Contents"]:
            idx = head.find(pat)
            if idx != -1:
                toc_idx = idx + len(pat)
                break
    if toc_idx == -1:
        return []

    # The TOC content is in the next ~2000 chars
    toc_text = head[toc_idx: toc_idx + 2000]

    titles: List[str] = []
    seen: set = set()
    for raw_line in toc_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) < 2:
            continue
        # Hard stop: very long lines are paragraph / title-page
        # text, not a title. After we've collected at least one
        # title, a long line means we've left the sub-book list.
        # Threshold: 30 chars — long enough to allow full titles
        # like "调动员工积极性的七个关键：稻盛和夫经营问答"
        # (21 chars before split) but short enough to filter out
        # publisher / translator / copyright paragraphs.
        if len(line) > 30:
            if titles:
                break
            continue
        if line.startswith("第") or line.startswith("附录"):
            # Chapter / appendix — stop. We've left the sub-book list.
            if titles:
                break
            continue
        if line.startswith("（") or line.startswith("("):
            continue  # (日) author byline
        if line.startswith("ISBN") or line.startswith("译者"):
            continue
        # Translator / author bylines: "曹岫云  译", "稻盛和夫  著"
        # Pattern: a Chinese name followed by 著/译
        if re.search(r"[著译]\s*$", line):
            continue
        # Lines with a colon followed by "著" (author byline format)
        if "著" in line and len(line) < 25 and titles:
            continue
        if line.startswith("目录") and titles:
            # Second 目录 marker = per-book chapter listing
            break
        # Page numbers: digits at the end (e.g. "干法 ........ 1")
        if re.search(r"\d\s*$", line) and len(line) < 20:
            continue
        # Subtitles: "调动员工积极性的七个关键：稻盛和夫经营问答"
        # Keep just the part before the colon
        if "：" in line:
            line = line.split("：")[0].strip()
        elif ":" in line and len(line.split(":", 1)[0]) >= 2:
            line = line.split(":", 1)[0].strip()
        if len(line) < 2:
            continue
        # Dedupe (same title can appear on adjacent lines in some
        # formats)
        if line in seen:
            continue
        seen.add(line)
        titles.append(line)

        # Safety: don't read more than 30 titles
        if len(titles) >= 30:
            break

    return titles


def _find_title_page_starts(text: str) -> List[int]:
    """Find the positions of all sub-book title pages in the text.

    A "title page" in a multi-book collection PDF is a 5-10 line
    block that contains: book title + author + translator + ISBN.
    The ISBN line (`ISBN ： 978-...`) is the most reliable marker
    because it's structured, has a fixed format, and appears
    exactly once per sub-book.

    Returns a list of positions (one per ISBN) sorted ascending.
    The positions point to the start of the title page (we
    back-track a few hundred chars to find the actual title, not
    the ISBN).
    """
    # ISBN pattern: "ISBN" followed by optional space, optional
    # full-width colon, the number, and an optional hyphen.
    isbn_re = re.compile(r"ISBN\s*[:：]?\s*[\d\-]{10,20}")
    positions: List[int] = []
    for m in isbn_re.finditer(text):
        positions.append(m.start())
    return positions


def _detect_sub_books(text: str) -> List[Tuple[str, int, int]]:
    """Detect sub-book boundaries in a multi-book collection.

    Many Chinese book collections (e.g. "稻盛和夫经典管理哲学收藏版")
    bundle 3-5 separate works into one PDF. Each sub-book has its
    own title page with a unique ISBN. The table of contents at
    the start lists the sub-book titles in order.

    Algorithm:
      1. Parse the TOC at the start of the text to get the list of
         sub-book titles in publication order.
      2. Find all ISBN positions in the body (one per sub-book
         title page).
      3. Match the N TOC titles to the first N ISBN positions
         (where N = number of TOC titles). This gives the title
         page position for each sub-book.
      4. Convert each title page position to a (start, end) range.
         `end` is the next sub-book's title page; the last one
         runs to end of text.
      5. The actual sub-book content starts ~500 chars after the
         title page (after publisher info, copyright, etc.).

    Returns a list of (title, content_start, content_end). For a
    single-book PDF (no TOC found, or TOC has 1 title, or fewer
    ISBNs than TOC titles), returns a single entry spanning the
    whole text.
    """
    if not text:
        return []

    n = len(text)
    titles = _parse_table_of_contents(text)
    isbn_positions = _find_title_page_starts(text)

    # Need at least 2 sub-books to bother with this logic
    if len(titles) < 2 or len(isbn_positions) < 2:
        return [("__whole_book__", 0, n)]

    # The number of sub-books is the smaller of the two counts.
    # (Sometimes the TOC has extras like appendices that don't have
    # their own ISBN; sometimes the body has duplicates we should
    # ignore.)
    n_books = min(len(titles), len(isbn_positions))
    titles = titles[:n_books]
    isbn_positions = isbn_positions[:n_books]

    # Build (title, content_start, content_end) ranges.
    # content_start = ISBN position + ~500 chars (skip past the
    # title page publisher info to the actual content)
    ranges: List[Tuple[str, int, int]] = []
    for i, (title, isbn_pos) in enumerate(zip(titles, isbn_positions)):
        # Skip past the title page. The title page is typically
        # 300-500 chars of metadata before the actual content
        # begins. Use 600 to be safe.
        content_start = min(n, isbn_pos + 600)
        # End is the next sub-book's content start
        if i + 1 < len(isbn_positions):
            content_end = min(n, isbn_positions[i + 1] + 600)
        else:
            content_end = n
        ranges.append((title, content_start, content_end))

    return ranges


def _per_book_sample(
    text: str,
    max_chars: int,
    books: List[Tuple[str, int, int]],
) -> Tuple[str, List[Tuple[str, int, int]]]:
    """Sample `text` with each sub-book getting a fair share of the budget.

    For a 4-book collection with `max_chars=25000`, each book gets
    ~6,250 chars via `even_sample` applied to ITS range. This is the
    key fix for "the LLM only expanded 干法" — the dominant sub-book
    no longer gets 4× the prompt budget of the others.

    Args:
        text: The full text to sample.
        max_chars: Total character budget for the output.
        books: Output of `_detect_sub_books`. A list of
            (title, start, end) tuples.

    Returns:
        (sampled_text, sampled_books) where sampled_books has the
        actual start/end offsets used (so the prompt can reference
        them).

    The output is the books concatenated with `=== 书名: 《title》 ===`
    markers, so the LLM can clearly see "this is book A", "this is
    book B", etc.
    """
    n = len(books)
    if n <= 1:
        # Single book or no detection — fall back to even_sample
        # on the whole text. The caller already chose the sampling
        # strategy (even_sample for default, head_sample for --full).
        return text, books

    per_book_budget = max_chars // n
    if per_book_budget < 1000:
        # Budget too tight to split. Just take the start of each book.
        per_book_budget = 1000
        actual_total = per_book_budget * n
    else:
        actual_total = per_book_budget * n

    parts: List[str] = []
    sampled: List[Tuple[str, int, int]] = []
    for title, start, end in books:
        book_text = text[start:end]
        # Per-book fair-share. Use even_sample so we get the
        # beginning, middle and end of THIS book (not just the
        # beginning of this book).
        if len(book_text) > per_book_budget:
            sample = even_sample(book_text, per_book_budget, slices=4)
        else:
            sample = book_text
        parts.append(f"=== 书名: 《{title}》 ===\n{sample}")
        sampled.append((title, start, start + len(book_text)))

    return "\n\n".join(parts), sampled


# Pattern: `第 N 章`, `第N部分`, `第 N 讲` — Chinese chapter markers
# that almost always appear with a colon / space / newline after the
# number, and then a title. We capture the full "第 N 章 标题" form so
# we can hand the title to the LLM as ground truth.
_CHAPTER_PATTERN = re.compile(
    r"第\s*([0-9一二三四五六七八九十百千零两]+)\s*"
    r"(章|部分|讲|节|篇)\s*"
    r"([^\n\r]{2,80})",  # the chapter title (2-80 chars, until newline)
)


def _detect_chapters(text: str, max_titles: int = 30) -> List[str]:
    """Find chapter / part / lecture titles in the source text.

    Returns a list of full titles (e.g. ``["第 1 章 磨炼灵魂 提升心志", ...]``)
    in the order they appear, deduplicated. Used to inject ground-truth
    chapter titles into the LLM prompt so the model uses them verbatim
    instead of inventing theme names from chapter content.

    Args:
        text: Source text (usually the per-book sample sent to the LLM).
        max_titles: Cap the number of detected titles to keep the prompt
            manageable for long books. 30 is enough for 99% of real books.

    Returns:
        List of detected chapter titles. Empty if none found.
    """
    if not text:
        return []
    seen: set = set()
    titles: List[str] = []
    for m in _CHAPTER_PATTERN.finditer(text):
        num, kind, title = m.group(1), m.group(2), m.group(3).strip()
        # Skip clearly false positives:
        #   - Title is just digits / punctuation
        #   - Title contains another chapter marker (nested — broken OCR)
        if not title or len(title) < 2:
            continue
        if re.search(r"第\s*[0-9一二三四五六七八九十]+\s*章", title):
            continue
        full = f"第 {num} {kind} {title}"
        # Normalize whitespace for dedup
        key = re.sub(r"\s+", " ", full)
        if key in seen:
            continue
        seen.add(key)
        titles.append(key)
        if len(titles) >= max_titles:
            break
    return titles


@dataclass
class MindMapNode:
    """A node in the mind map tree"""
    id: str
    title: str
    children: List['MindMapNode'] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "children": [child.to_dict() for child in self.children],
            "notes": self.notes,
        }
    
    def to_markdown(self, level: int = 1) -> str:
        """Convert to Markdown headings"""
        lines = []
        heading = "#" * min(level, 6)
        lines.append(f"{heading} {self.title}")
        
        if self.notes:
            lines.append(f"\n{self.notes}\n")
        
        for child in self.children:
            lines.append(child.to_markdown(level + 1))
        
        return "\n".join(lines)
    
    def to_opml(self, indent: int = 0) -> str:
        """Convert to OPML outline format"""
        indent_str = "  " * indent
        lines = []
        
        # Escape XML special characters
        title_escaped = self.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        notes_escaped = self.notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        
        if notes_escaped:
            lines.append(f'{indent_str}<outline text="{title_escaped}" _note="{notes_escaped}">')
        else:
            lines.append(f'{indent_str}<outline text="{title_escaped}">')
        
        for child in self.children:
            lines.append(child.to_opml(indent + 1))
        
        lines.append(f'{indent_str}</outline>')
        return "\n".join(lines)


class MindMapExtractor:
    """Extract mind map structure from text using LLM"""
    
    def __init__(
        self,
        chat_model: str = "qwen3.5:cloud",
        base_url: str = "http://127.0.0.1:11434",
    ):
        self.chat_model = chat_model
        self.base_url = base_url
        # 600s timeout: cloud models (qwen3.5:cloud etc.) can take 3-5 min
        # on first call with thinking mode enabled, especially for long
        # 50K-char prompts.
        self.client = httpx.Client(timeout=600.0)
    
    def extract(
        self,
        text: str,
        title: str = "Document",
        use_full: bool = False,
    ) -> tuple[MindMapNode, LLMUsage]:
        """
        Extract mind map structure from text.

        The mindmap is built by ENUMERATING the book's actual content
        (parts, chapters, named principles, arguments), not by
        summarizing it. The default prompt targets 80-150 nodes across
        3-4 levels of depth, in the same shape as a real table of
        contents — see research/mindmap-comparison-vs-notebooklm.md for
        the design rationale.

        Args:
            text: Text content to analyze
            title: Title for the root node
            use_full: If True, use a larger 50K-char budget in
                head_sample mode (front-loaded — good for medium books
                where the intro summarizes the whole). Default uses
                25K chars in even_sample mode (uniform — good for
                enumerating the whole structure of a long book).

        Returns:
            (MindMapNode, LLMUsage) tuple. The LLMUsage has the
            input/output token counts for this extraction.
        """
        # Default 25K chars (~6K tokens) with even sampling — covers
        # more of the book than the old 12K default without paying the
        # --full latency cost. --full uses 50K head_sample (faster
        # and good when the intro is representative of the whole book).
        #
        # NEW: For multi-book collections (e.g. "稻盛和夫经典管理哲学
        # 收藏版" with 5 sub-books), we detect the sub-book boundaries
        # and give EACH sub-book a fair share of the budget. Without
        # this, the dominant sub-book (e.g. 干法 at 17% of the text)
        # gets 4× the budget of the smaller ones, and the LLM only
        # expands the dominant one. This is the fix for the
        # "only 干法 has more children" bug.
        max_chars = 50000 if use_full else 25000
        sub_books = _detect_sub_books(text)
        is_collection = (
            len(sub_books) > 1 and sub_books[0][0] != "__whole_book__"
        )

        # Build the "Detected chapters" block BEFORE sampling. For
        # collections this is critical: the per-book sampling
        # truncates each sub-book's slice to ~8K chars, which
        # truncates the `第N章` markers of mid-book chapters. We want
        # the LLM to see the FULL chapter list for each sub-book as
        # ground truth, not whatever the sampling happened to keep.
        if is_collection:
            # Group detected chapters by which sub-book they belong to,
            # by checking which sub-book's [start, end) range the
            # chapter marker's offset falls into.
            full_text = text  # not yet sampled
            detected_per_book: List[List[str]] = []
            all_chapter_titles: List[str] = []
            for title, start, end in sub_books:
                book_text = full_text[start:end]
                book_chapters = _detect_chapters(book_text, max_titles=20)
                detected_per_book.append(book_chapters)
                all_chapter_titles.extend(book_chapters)
        else:
            all_chapter_titles = _detect_chapters(text, max_titles=30)
            detected_per_book = None

        if is_collection:
            text, sub_books = _per_book_sample(text, max_chars, sub_books)
        elif len(text) > max_chars:
            text = (even_sample(text, max_chars)
                    if not use_full
                    else head_sample(text, max_chars))

        # Build the "Detected sub-books" block for the prompt. This
        # gives the LLM an EXPLICIT list of sub-books to enumerate, so
        # it doesn't have to figure out the structure from the text
        # alone (which is what made the previous version produce
        # themes-from-干法 instead of the full collection structure).
        if is_collection:
            detected_block = (
                "## Detected sub-books in this collection\n"
                "The following sub-books were detected in the source. "
                "Treat EACH ONE as a level-1 child of the root. Give "
                "each roughly the SAME depth and expansion — do not "
                "let the largest sub-book dominate:\n\n"
            )
            for i, (title, start, end) in enumerate(sub_books, 1):
                pct = (end - start) * 100 // len(text) if text else 0
                detected_block += (
                    f"  {i}. 《{title}》 — appears at char {start:,}, "
                    f"~{pct}% of sampled text\n"
                )
            detected_block += (
                "\nIf you find additional sub-books in the sampled text "
                "below that aren't listed here, add them too.\n"
            )
        else:
            detected_block = ""

        # Build a "Detected chapters" block from the actual text. This
        # is the real fix for the "chapters 1-4 disappeared" regression:
        # the LLM was being asked to enumerate chapters but inventing
        # theme names from chapter content because the `第N章` markers
        # were buried in mid-book slices the model didn't see as
        # structure. Pre-extracting them and listing them as ground
        # truth forces the LLM to use the exact `第 N 章 标题` form.
        if is_collection and detected_per_book is not None:
            # Group chapters under their sub-book so the LLM can map
            # them directly. Without grouping, the LLM has to guess
            # which chapter belongs to which sub-book.
            chapters_block = (
                "## Detected chapters per sub-book\n"
                "The following `第N章` / `第N部分` / `第N讲` markers were "
                "found in the source. For EACH sub-book below, use the "
                "listed chapter titles VERBATIM as level-2 node titles. "
                "Do NOT paraphrase, summarize, or invent a new theme "
                "name. If the source has '第 1 章 磨炼灵魂 提升心志', the "
                "mind-map node title for that chapter MUST be exactly "
                "'第 1 章 磨炼灵魂 提升心志' — not '磨炼灵魂' or '为什么要工作'.\n\n"
            )
            for (title, start, end), book_chapters in zip(
                sub_books, detected_per_book
            ):
                if not book_chapters:
                    chapters_block += (
                        f"- 《{title}》: (no `第N章` markers found — "
                        "infer chapters from this sub-book's content "
                        "or use the sub-book's own section headings)\n"
                    )
                    continue
                chapters_block += f"- 《{title}》:\n"
                for t in book_chapters:
                    chapters_block += f"    - {t}\n"
            chapters_block += (
                "\nEvery chapter listed here MUST appear as a level-2 "
                "node under its parent sub-book. Do NOT collapse multiple "
                "chapters into one node. Do NOT split one chapter into "
                "multiple nodes. The user wants to see the actual chapter "
                "list, not your interpretation of it.\n"
            )
        elif all_chapter_titles:
            chapters_block = (
                "## Detected chapters in the source text\n"
                "The following `第N章` / `第N部分` / `第N讲` markers were "
                "found in the source. You MUST use these titles VERBATIM "
                "as level-2 (or deeper) node titles. Do NOT paraphrase, "
                "summarize, or invent a new theme name. If the source has "
                "'第 1 章 磨炼灵魂 提升心志', the node title in the mind "
                "map must be exactly '第 1 章 磨炼灵魂 提升心志' — not "
                "'磨炼灵魂' or '为什么要工作'.\n\n"
            )
            for i, t in enumerate(all_chapter_titles, 1):
                chapters_block += f"  {i}. {t}\n"
            chapters_block += (
                "\nMap each detected chapter to a level-2 node. If a "
                "chapter number appears twice (rare — same number in "
                "different parts of a book), they're different nodes "
                "with the same human-readable title.\n"
            )
        else:
            chapters_block = ""

        prompt = f"""You are a book table-of-contents extractor. Extract a HIERARCHICAL, COMPREHENSIVE mind map of the book — NOT a summary.

## CRITICAL: This is often a multi-book collection
NotebookLM's mind map for the source material here is multi-book. If the text
is a collection / anthology / 收藏版 / 全集 / 选集 / 作品集 (e.g.
"稻盛和夫经典管理哲学收藏版"), the first level of the map MUST be every
major work in the collection, NOT a single book. Examples of multi-book
collections and how to handle them:

  "稻盛和夫经典管理哲学收藏版" → 干法, 领导者的资质, 调动员工积极性的七个关键, 阿米巴经营, 盛和塾, 拯救人类的哲学 (each as a level-1 node)
  "Cixin Liu's Three-Body Trilogy" → 三体, 黑暗森林, 死神永生 (3 separate novels, each as a level-1 node)
  "Shakespeare's Complete Works" → Tragedies, Comedies, Histories (each a level-1 node)

Look for explicit section / part / 书 / 作品 / 篇 / 卷 / 部 / 册 markers
in the text — these indicate separate works that should each get their own
top-level node.

{detected_block}{chapters_block}## Approach
- ENUMERATE, do not summarize. If the book has 12 chapters, the map has 12 level-2 nodes under that book's level-1 entry.
- Each leaf should be a SPECIFIC named principle, method, story, definition, or argument from the book — never a vague theme like "工作态度" (work attitude). Prefer the book's own terminology: if the book calls a concept "极度认真工作", use that exact phrasing.
- CHAPTERS MUST BE COPIED VERBATIM. If a chapter in the source is
  "第 1 章 磨炼灵魂 提升心志", the mind-map node title for that chapter
  MUST be exactly "第 1 章 磨炼灵魂 提升心志" — including the "第 1 章"
  prefix. Do NOT drop the prefix ("磨炼灵魂 提升心志" is WRONG). Do NOT
  replace it with a theme ("为什么要工作" is WRONG). Do NOT split one
  chapter into multiple nodes. The user wants to see the actual chapter
  list, not your interpretation of it.
- Aim for 80–150 total nodes. A 1,000-page book deserves a rich map, not a 10-bullet list. A multi-book collection can easily reach 200+ nodes — that's correct.
- Use the book's own language (Chinese stays Chinese, English stays English, etc.).
- CRITICAL: For a collection, EVERY sub-book listed in the
  "Detected sub-books" block above MUST appear as a level-1 child of
  the root, with roughly the SAME depth and node count. If the
  detected list says there are 5 sub-books, your output MUST have 5
  level-1 children — not 1, not 2. Do not put one sub-book at level-1
  and the other 4 as leaves of that one sub-book.

## Structure (3–4 levels of depth)
- Level 1: parts / sections / major themes / individual books in a collection (5–15 nodes — the upper end if it's a multi-book collection)
- Level 2: chapters or major arguments (3–12 per level-1 node)
- Level 3: key concepts under each chapter (2–5 per level-2 node)
- Level 4 (optional): concrete examples, named people, formulas, quotable phrases
- Every node has a short title (3–12 words, in the book's language).
- Use the `notes` field for a 1-sentence explanation ONLY when the title alone is ambiguous.

## Output Format (strict)
```json
{{
  "id": "root",
  "title": "<book title>",
  "notes": "",
  "children": [
    {{
      "id": "book-1",
      "title": "《干法》",
      "notes": "",
      "children": [
        {{
          "id": "ch-1",
          "title": "第1章 磨练灵魂 提升心志",
          "notes": "",
          "children": [
            {{"id": "concept-1", "title": "Named principle or argument", "notes": "", "children": []}}
          ]
        }}
      ]
    }},
    {{
      "id": "book-2",
      "title": "《领导者的资质》",
      "notes": "",
      "children": [...]
    }}
  ]
}}
```

## Document Title: {title}

## Text to Analyze:
{text}

## Mind Map JSON:
"""

        output, usage = call_ollama(
            base_url=self.base_url,
            model=self.chat_model,
            prompt=prompt,
            client=self.client,
        )

        # Extract JSON from markdown code blocks if present
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()

        try:
            data = json.loads(json_str)
            return self._dict_to_node(data), usage
        except json.JSONDecodeError as e:
            # Fallback: create simple structure
            return (
                MindMapNode(
                    id="root",
                    title=title,
                    notes=f"Failed to parse mind map: {e}\n\nOutput was:\n{output[:500]}",
                    children=[],
                ),
                usage,
            )
    
    def _dict_to_node(self, data: Dict[str, Any], parent_id: str = "") -> MindMapNode:
        """Convert dictionary to MindMapNode"""
        node_id = data.get("id", f"node-{parent_id}-{len(parent_id)}")
        title = data.get("title", "Untitled")
        notes = data.get("notes", "")
        children_data = data.get("children", [])
        
        children = []
        for i, child_data in enumerate(children_data):
            child = self._dict_to_node(child_data, node_id)
            children.append(child)
        
        return MindMapNode(
            id=node_id,
            title=title,
            children=children,
            notes=notes,
        )
    
    def close(self):
        """Close HTTP client"""
        self.client.close()



# ============== HTML rendering (Markmap + custom toolbar) ==============


def _default_initial_expand_level(tree, is_collection):
    """Decide how many levels to expand on initial render.

    The default markmap behavior is `initialExpandLevel: -1` (expand
    all). For a 100+ node mind map that's a wall of text — the user
    can't see the structure.

    We pick a sensible default based on the tree shape:

    - Collection (multi-book): expand level 2 by default. Level 1
      shows the book titles, level 2 shows the chapters. Users can
      click "Expand all" to see the full depth.

    - Single book: expand level 1 by default. Level 1 shows the
      chapter / part titles.

    Returns the initialExpandLevel value (positive = expand up to
    that depth; -1 = expand all).
    """
    if is_collection:
        return 2
    return 1


# JavaScript that registers custom Expand All / Collapse All
# toolbar buttons.
#
# Strategy: We MONKEY-PATCH `markmap.Markmap.create` BEFORE the
# autoloader runs. The autoloader's `render()` function calls
# `Markmap.create(svg, ...)` and uses the resulting markmap instance
# internally — but it does NOT expose that instance on `window` or
# on the DOM element. So we wrap `Markmap.create` to capture every
# instance in a global registry (`window.__markmapInstances`).
#
# Then `onReady` (which fires AFTER the autoloader has set up the
# toolbar) can iterate that registry, find the existing toolbar DOM
# on each `.markmap` container, remove it, and re-attach a new
# toolbar with our custom buttons.
_TOOLBAR_INIT_JS = r"""
  <script>
    // Pre-autoloader setup: monkey-patch Markmap.create to capture
    // every markmap instance the autoloader creates. We don't have
    // access to the instance otherwise (autoloader's render() is
    // scope-local).
    (function () {
      const tryPatch = function () {
        if (!window.markmap || !window.markmap.Markmap) {
          // Library not loaded yet — try again in 50ms.
          setTimeout(tryPatch, 50);
          return;
        }
        if (window.__mmPatched) return; // idempotent
        window.__mmPatched = true;
        const Original = window.markmap.Markmap.create;
        window.markmap.Markmap.create = function (svg, opts, data) {
          const mm = Original.call(this, svg, opts, data);
          // Stash the instance in a global registry.
          window.__markmapInstances = window.__markmapInstances || [];
          window.__markmapInstances.push(mm);
          return mm;
        };
      };
      tryPatch();
    })();
  </script>
  <script>
    // After the autoloader has loaded markmap + dependencies AND
    // created the markmap instance + attached the toolbar, our
    // onReady runs. We replace the toolbar with a new one that
    // includes our custom Expand All / Collapse All buttons.
    (function () {
      const onReady = function () {
        const instances = (window.__markmapInstances || []);
        // Belt-and-suspenders: also check window.mm (set by
        // markmap-render, not autoloader, but harmless).
        if (!instances.length && window.mm) {
          instances.push(window.mm);
        }
        if (!instances.length || !window.markmap || !window.markmap.Toolbar) {
          return;
        }
        const Toolbar = window.markmap.Toolbar;
        instances.forEach(function (mm) {
          // The autoloader appended a `.mm-toolbar` element as a
          // child of the .markmap container. Find and remove it.
          const container = mm.svg.node().parentNode;
          const existingToolbar = container.querySelector(".mm-toolbar");
          if (existingToolbar) {
            existingToolbar.remove();
          }
          // Build a new toolbar attached to this markmap.
          const toolbar = Toolbar.create(mm);
          // Register our custom buttons.
          //   - "Expand all": re-render with initialExpandLevel: -1
          //     (markmap's "all" sentinel value).
          //   - "Collapse all": re-render with initialExpandLevel: 0
          //     (only the root is visible; user clicks to expand).
          toolbar.register({
            id: "expandAll",
            title: "Expand all",
            content: Toolbar.icon(
              "M12 5l-7 7h4v6h6v-6h4z M4 18h16v2h-16z"
            ),
            onClick: function () {
              const data = mm.state.data;
              if (!data) return;
              mm.setData(data, { initialExpandLevel: -1 }).then(function () {
                mm.fit();
              });
            },
          });
          toolbar.register({
            id: "collapseAll",
            title: "Collapse all",
            content: Toolbar.icon(
              "M12 19l7-7h-4v-6h-6v6h-4z M4 2h16v2h-16z"
            ),
            onClick: function () {
              const data = mm.state.data;
              if (!data) return;
              mm.setData(data, { initialExpandLevel: 0 }).then(function () {
                mm.fit();
              });
            },
          });
          // Replace items to put our custom buttons first.
          toolbar.setItems([
            "expandAll",
            "collapseAll",
            "zoomIn",
            "zoomOut",
            "fit",
            "recurse",
            "dark",
          ]);
          // Render and position the toolbar.
          const tEl = toolbar.render();
          tEl.style.position = "absolute";
          tEl.style.right = "20px";
          tEl.style.bottom = "20px";
          container.appendChild(tEl);
        });
      };
      window.markmap = window.markmap || {};
      window.markmap.autoLoader = window.markmap.autoLoader || {};
      // Preserve any existing onReady (defensive — none today, but
      // if markmap ever adds one, we don't want to break it).
      const existing = window.markmap.autoLoader.onReady;
      window.markmap.autoLoader.onReady = function () {
        if (existing) { try { existing(); } catch (e) {} }
        onReady();
      };
    })();
  </script>
"""


def render_mindmap_html(tree, title, is_collection=False):
    """Render a MindMapNode as a self-contained HTML file using Markmap.

    The output is a single HTML file with:
      - Markdown frontmatter that sets `initialExpandLevel` based on
        the tree shape (1 level for single-book, 2 levels for
        collection).
      - The markmap-autoloader from jsDelivr, which auto-detects the
        `.markmap` div and renders it.
      - A custom `onReady` callback that registers two extra
        toolbar buttons: "Expand all" and "Collapse all". The default
        markmap toolbar only has zoom/fit/recurse/dark — it does NOT
        have expand-all / collapse-all.

    Args:
        tree: The MindMapNode to render.
        title: Title for the `<h1>` and `<title>` tags.
        is_collection: True if the source was a multi-book
            collection. Affects the default `initialExpandLevel`.

    Returns:
        A complete HTML document as a string.

    The user can interact with the mindmap in the browser:
      - Click a node to expand/collapse its children.
      - Ctrl+click for recursive expand/collapse.
      - Use the toolbar (top-right) for zoom, fit, dark mode, and
        the custom Expand All / Collapse All buttons.
    """
    initial_level = _default_initial_expand_level(tree, is_collection)

    # Frontmatter at the top of the markdown configures the
    # initialExpandLevel via markmap's documented JSON-options
    # interface. See https://markmap.js.org/docs/json-options.
    frontmatter = (
        "---\n"
        "markmap:\n"
        f"  initialExpandLevel: {initial_level}\n"
        "---\n\n"
    )
    md_content = frontmatter + tree.to_markdown()

    # Note on the toolbar: markmap-autoloader reads
    # `window.markmap.autoLoader.toolbar` BEFORE loading
    # markmap-toolbar. Setting `toolbar: true` causes it to attach
    # the standard toolbar (zoomIn / zoomOut / fit / recurse / dark)
    # to every `.markmap` element. Our `onReady` callback (in
    # _TOOLBAR_INIT_JS) runs AFTER the toolbar has been attached, so
    # we can add custom buttons to it via the public Toolbar API.
    html = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        f"  <title>{title} - Mind Map</title>\n"
        "  <script>\n"
        "    // Enable the markmap toolbar before the autoloader\n"
        "    // initializes. Without this, the toolbar (and our\n"
        "    // custom buttons) won't appear.\n"
        "    window.markmap = window.markmap || {};\n"
        "    window.markmap.autoLoader = { toolbar: true };\n"
        "  </script>\n"
        '  <script src="https://cdn.jsdelivr.net/npm/markmap-autoloader@latest"></script>\n'
        "  <style>\n"
        "    /* Light theme (default). The markmap dark mode toggle\n"
        "       adds the .markmap-dark class to <html>; we respond by\n"
        "       flipping the page background + h1 text color. The\n"
        "       markmap itself handles its own internal colors via\n"
        "       CSS variables. */\n"
        "    html, body { background: #ffffff; color: #222; }\n"
        "    body { margin: 0; padding: 20px; font-family: system-ui, sans-serif; }\n"
        "    h1 { margin: 0 0 10px 0; font-size: 20px; color: #222; }\n"
        "    .markmap { width: 100%; height: 90vh; position: relative;\n"
        "               background: #ffffff; }\n"
        "    /* Dark theme: triggered by the markmap dark-mode toggle\n"
        "       which adds `.markmap-dark` to <html>. We override\n"
        "       our own surfaces; markmap handles the SVG colors\n"
        "       internally via its `--markmap-text-color` variable. */\n"
        "    html.markmap-dark, html.markmap-dark body { background: #1a1b26; color: #eee; }\n"
        "    html.markmap-dark h1 { color: #eee; }\n"
        "    html.markmap-dark .markmap { background: #1a1b26; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{title}</h1>\n"
        '  <div class="markmap">\n\n'
        f"{md_content}\n\n"
        "  </div>\n"
        f"{_TOOLBAR_INIT_JS}\n"
        "</body>\n"
        "</html>\n"
    )
    return html
