"""Mind map extraction from PDF content"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
import json
import httpx
from .sampling import even_sample, head_sample


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
    
    def extract(self, text: str, title: str = "Document", use_full: bool = False) -> MindMapNode:
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
            MindMapNode tree structure
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

{detected_block}## Approach
- ENUMERATE, do not summarize. If the book has 12 chapters, the map has 12 level-2 nodes under that book's level-1 entry.
- Each leaf should be a SPECIFIC named principle, method, story, definition, or argument from the book — never a vague theme like "工作态度" (work attitude). Prefer the book's own terminology: if the book calls a concept "极度认真工作", use that exact phrasing.
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
        
        response = self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.chat_model,
                "prompt": prompt,
                "stream": False,
            },
        )
        response.raise_for_status()
        
        # Parse JSON from response
        output = response.json()["response"]
        
        # Extract JSON from markdown code blocks if present
        if "```json" in output:
            json_str = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            json_str = output.split("```")[1].split("```")[0].strip()
        else:
            json_str = output.strip()
        
        try:
            data = json.loads(json_str)
            return self._dict_to_node(data)
        except json.JSONDecodeError as e:
            # Fallback: create simple structure
            return MindMapNode(
                id="root",
                title=title,
                notes=f"Failed to parse mind map: {e}\n\nOutput was:\n{output[:500]}",
                children=[],
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
