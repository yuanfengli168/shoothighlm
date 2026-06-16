"""Tests for mind map extraction"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from shoothighlm.mindmap import MindMapExtractor, MindMapNode


@pytest.fixture
def extractor():
    """Create a MindMapExtractor instance"""
    return MindMapExtractor(chat_model="test-model")


def test_mindmap_node_creation():
    """Test creating a MindMapNode"""
    node = MindMapNode(
        id="test-1",
        title="Test Topic",
        notes="Test notes",
        children=[],
    )
    
    assert node.id == "test-1"
    assert node.title == "Test Topic"
    assert node.notes == "Test notes"


def test_mindmap_node_to_dict():
    """Test converting node to dictionary"""
    node = MindMapNode(
        id="root",
        title="Root Topic",
        children=[
            MindMapNode(id="child-1", title="Child 1"),
            MindMapNode(id="child-2", title="Child 2"),
        ],
    )
    
    result = node.to_dict()
    
    assert result["id"] == "root"
    assert result["title"] == "Root Topic"
    assert len(result["children"]) == 2
    assert result["children"][0]["id"] == "child-1"


def test_mindmap_node_to_markdown():
    """Test converting node to Markdown"""
    node = MindMapNode(
        id="root",
        title="Root Topic",
        notes="Root notes",
        children=[
            MindMapNode(id="child-1", title="Child 1", notes="Child notes"),
        ],
    )
    
    md = node.to_markdown()
    
    assert "# Root Topic" in md
    assert "Root notes" in md
    assert "## Child 1" in md
    assert "Child notes" in md


def test_mindmap_node_to_opml():
    """Test converting node to OPML"""
    node = MindMapNode(
        id="root",
        title="Root Topic",
        children=[
            MindMapNode(id="child-1", title="Child 1"),
        ],
    )
    
    opml = node.to_opml()
    
    assert '<outline text="Root Topic">' in opml
    assert '<outline text="Child 1">' in opml


def test_mindmap_node_nested_children():
    """Test node with deeply nested children"""
    node = MindMapNode(
        id="root",
        title="Root",
        children=[
            MindMapNode(
                id="level1",
                title="Level 1",
                children=[
                    MindMapNode(
                        id="level2",
                        title="Level 2",
                        children=[
                            MindMapNode(id="level3", title="Level 3"),
                        ],
                    ),
                ],
            ),
        ],
    )
    
    md = node.to_markdown()
    
    assert "# Root" in md
    assert "## Level 1" in md
    assert "### Level 2" in md
    assert "#### Level 3" in md


def test_mindmap_extractor_init(extractor):
    """Test extractor initialization"""
    assert extractor.chat_model == "test-model"
    assert extractor.base_url == "http://127.0.0.1:11434"


def test_mindmap_extractor_extract_mock(extractor):
    """Test mind map extraction with mock"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": """```json
{
  "id": "root",
  "title": "Test Document",
  "notes": "Test notes",
  "children": [
    {
      "id": "topic-1",
      "title": "Topic 1",
      "children": []
    }
  ]
}
```"""
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, 'post', return_value=mock_response):
        result, usage = extractor.extract("Test text", title="Test Document")

        assert isinstance(result, MindMapNode)
        assert result.title == "Test Document"
        assert len(result.children) == 1
        assert result.children[0].title == "Topic 1"
        # Token usage is now returned alongside the result
        assert usage is not None
        assert isinstance(usage.input_tokens, int)
        assert isinstance(usage.output_tokens, int)


def test_mindmap_extractor_extract_no_json(extractor):
    """Test extraction when LLM doesn't return valid JSON"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I couldn't extract a mind map from this text."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, 'post', return_value=mock_response):
        result, usage = extractor.extract("Test text", title="Test Document")

        # Should return fallback node + usage
        assert isinstance(result, MindMapNode)
        assert result.title == "Test Document"
        assert "Failed to parse" in result.notes
        # Usage is still returned even on failure
        assert usage is not None


def test_mindmap_extractor_truncate_long_text(extractor):
    """Test that long text uses even sampling (10 evenly-spaced windows)."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"id": "root", "title": "Test", "children": []}'
    }
    mock_response.raise_for_status = Mock()

    # Create very long text
    long_text = "A" * 100000

    with patch.object(extractor.client, 'post', return_value=mock_response) as mock_post:
        extractor.extract(long_text, title="Test")

        # Check that even sampling was applied (not raw head truncation)
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']

        assert len(prompt) < 60000  # Should be truncated
        # Default mode uses even_sample, which emits "[... section break ...]"
        # markers between the 10 evenly-spaced windows.
        assert "[... section break ...]" in prompt
        # The legacy "[... middle of document ...]" marker is from the
        # old stratified_sample — should no longer appear in mindmap output.
        assert "[... middle of document ...]" not in prompt


def test_dict_to_node_nested():
    """Test converting nested dict to node"""
    extractor = MindMapExtractor()
    
    data = {
        "id": "root",
        "title": "Root",
        "children": [
            {
                "id": "child",
                "title": "Child",
                "children": [
                    {"id": "grandchild", "title": "Grandchild"},
                ],
            },
        ],
    }
    
    node = extractor._dict_to_node(data)
    
    assert node.title == "Root"
    assert len(node.children) == 1
    assert node.children[0].title == "Child"
    assert len(node.children[0].children) == 1
    assert node.children[0].children[0].title == "Grandchild"


# ============== Sub-book detection ==============

from shoothighlm.mindmap import (
    _parse_table_of_contents,
    _find_title_page_starts,
    _detect_sub_books,
    _per_book_sample,
)


def test_parse_toc_finds_collection_subbooks():
    """TOC parser should pick up all sub-book titles from a multi-book collection."""
    # Mimics the structure of 稻盛和夫经典管理哲学收藏版
    text = (
        "管理大师稻盛和夫经典收藏版（《拯救人类的哲学》、《干法》、《领导者的资质》、"
        "《调动员工积极性的七个关键》、《阿米巴经营（实战篇）》）\n"
        "（日）稻盛和夫  著\n\n"
        "目录\n"
        "干法\n"
        "领导者的资质\n"
        "调动员工积极性的七个关键：稻盛和夫经营问答\n"
        "稻盛和夫语录 100 条\n"
        "阿米巴经营（实战篇）\n"
        "拯救人类的哲学\n\n"
        "干法\n"
        "（日）稻盛和夫  著\n"
        "曹岫云  译\n"
        "ISBN ： 978-7-111-49824-7\n"
        "本书纸版由机械工业出版社于 2014 年出版\n"
    )
    titles = _parse_table_of_contents(text)
    assert "干法" in titles
    assert "领导者的资质" in titles
    assert "调动员工积极性的七个关键" in titles
    # "稻盛和夫语录 100 条" has a space and digit; may or may not
    # be picked up depending on the line-length filter. Skip that
    # one to avoid coupling the test to format details.
    assert len(titles) >= 3


def test_parse_toc_returns_empty_for_no_toc():
    """No 目录 marker → empty list."""
    text = "This is just a single book with no table of contents.\n" * 50
    assert _parse_table_of_contents(text) == []


def test_parse_toc_filters_translator_byline():
    """Translator/author bylines should not be picked up as titles."""
    text = (
        "目录\n"
        "干法\n"
        "（日）稻盛和夫  著\n"   # author byline
        "曹岫云  译\n"             # translator byline
        "ISBN ： 978-7-111-49824-7\n"
        "本书纸版由机械工业出版社于 2014 年出版\n"
    )
    titles = _parse_table_of_contents(text)
    # 干法 should be there, but the bylines should not
    assert "干法" in titles
    assert not any("译" in t and "稻盛" not in t for t in titles)


def test_find_isbn_positions():
    """Should find one ISBN per sub-book title page."""
    text = (
        "干法\n"
        "（日）稻盛和夫  著\n"
        "曹岫云  译\n"
        "ISBN ： 978-7-111-49824-7\n"
        "本子出版于 2014\n\n"
        "领导者的资质\n"
        "ISBN ： 978-7-111-47025-0\n"
        "本子出版于 2014\n\n"
        "拯救人类的哲学\n"
        "ISBN ： 978-7-111-51021-5\n"
    )
    positions = _find_title_page_starts(text)
    assert len(positions) == 3
    # Positions should be ascending
    assert positions == sorted(positions)
    # The first ISBN should appear in the first ~200 chars
    assert positions[0] < 200


def test_detect_sub_books_collection():
    """End-to-end: should detect all 6 sub-books in a realistic
    收藏版 text with proper (title, start, end) ranges.
    """
    # Build a fake 收藏版 text with TOC + 6 title pages + body
    body_chunk = "这是一段测试文本。稻盛先生讲了很多关于工作的道理。" * 100
    title_pages = []
    books = [
        ("干法", "978-7-111-49824-7"),
        ("领导者的资质", "978-7-111-47025-0"),
        ("调动员工积极性的七个关键", "978-7-111-48914-6"),
        ("稻盛和夫语录 100 条", "978-7-111-49146-0"),
        ("阿米巴经营（实战篇）", "978-7-111-50219-7"),
        ("拯救人类的哲学", "978-7-111-51021-5"),
    ]
    for title, isbn in books:
        title_pages.append(
            f"{title}\n（日）稻盛和夫  著\n曹岫云  译\nISBN ： {isbn}\n"
            f"本书纸版由机械工业出版社于 2015 年出版\n\n"
        )
    text = (
        "管理大师稻盛和夫经典收藏版\n\n"
        "目录\n"
        + "\n".join(b[0] for b in books)
        + "\n\n"
        + ("\n".join(title_pages))
        + (body_chunk * 6)  # 6 body chunks, one per sub-book
    )

    detected = _detect_sub_books(text)
    assert len(detected) == 6, f"expected 6, got {len(detected)}: {detected}"
    titles = [t for t, _, _ in detected]
    for expected_title, _ in books:
        assert expected_title in titles, f"missing {expected_title!r}"


def test_detect_sub_books_single_book():
    """A text without a TOC + ISBN structure should fall back to one whole-book entry."""
    text = "This is just a single book with no table of contents and no ISBNs.\n" * 100
    detected = _detect_sub_books(text)
    assert len(detected) == 1
    assert detected[0][0] == "__whole_book__"


def test_per_book_sample_even_distribution():
    """Per-book sampler should give each sub-book a fair share of the budget."""
    books = [
        ("Book A", 0, 1000),
        ("Book B", 1000, 2000),
        ("Book C", 2000, 3000),
    ]
    text = "A" * 1000 + "B" * 1000 + "C" * 1000
    sampled, _ = _per_book_sample(text, 3000, books)
    # Each book gets ~1000 chars + a marker line
    assert "=== 书名: 《Book A》 ===" in sampled
    assert "=== 书名: 《Book B》 ===" in sampled
    assert "=== 书名: 《Book C》 ===" in sampled
    # Total length should be roughly 3000 + 3 markers
    assert 2900 < len(sampled) < 3500


def test_per_book_sample_single_book_passthrough():
    """A single-book range should pass through unchanged."""
    books = [("Only Book", 0, 5000)]
    text = "Hello world " * 500
    sampled, _ = _per_book_sample(text, 2500, books)
    assert sampled == text


def test_extract_with_collection_uses_per_book_sampling(extractor):
    """When sub-books are detected, the prompt should include per-book markers."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"id": "root", "title": "Test", "children": []}'
    }
    mock_response.raise_for_status = Mock()

    # Build a fake collection text
    text = (
        "管理大师稻盛和夫经典收藏版\n\n"
        "目录\n干法\n领导者的资质\n拯救人类的哲学\n\n"
        "干法\nISBN ： 978-7-111-49824-7\n"
        + ("干法内容。" * 5000)
        + "\n领导者的资质\nISBN ： 978-7-111-47025-0\n"
        + ("资质内容。" * 5000)
        + "\n拯救人类的哲学\nISBN ： 978-7-111-51021-5\n"
        + ("哲学内容。" * 5000)
    )

    with patch.object(extractor.client, 'post', return_value=mock_response) as mock_post:
        extractor.extract(text, title="Test Collection")

        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']

        # The prompt should include per-book markers
        assert "=== 书名: 《干法》 ===" in prompt
        assert "=== 书名: 《领导者的资质》 ===" in prompt
        assert "=== 书名: 《拯救人类的哲学》 ===" in prompt
        # The "Detected sub-books" dynamic block (with the heading)
        # should also be present
        assert "## Detected sub-books in this collection" in prompt


def test_extract_with_single_book_no_per_book_markers(extractor):
    """A regular single-book text should NOT include per-book markers."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"id": "root", "title": "Test", "children": []}'
    }
    mock_response.raise_for_status = Mock()

    # No TOC, no ISBN, just plain book text
    text = "This is a regular single book about leadership and management. " * 1000

    with patch.object(extractor.client, 'post', return_value=mock_response) as mock_post:
        extractor.extract(text, title="Test")

        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']

        # No per-book markers (the actual book-name marker format).
        # The static prompt mentions "Detected sub-books" as a reference
        # phrase in the inner CRITICAL section, but only the dynamic
        # `## Detected sub-books in this collection` block is emitted
        # for collections.
        assert "=== 书名:" not in prompt
        assert "## Detected sub-books in this collection" not in prompt


# ============== HTML rendering tests ==============

from shoothighlm.mindmap import (
    _default_initial_expand_level,
    render_mindmap_html,
)


def test_default_initial_expand_level_single_book():
    """Single book should default to expanding 1 level (chapters visible)."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="My Book", children=[
        MindMapNode(id="c1", title="Chapter 1", children=[
            MindMapNode(id="c1-1", title="Section 1.1"),
        ]),
    ])
    assert _default_initial_expand_level(tree, is_collection=False) == 1


def test_default_initial_expand_level_collection():
    """Collection should default to expanding 2 levels (books + chapters)."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="Collection", children=[
        MindMapNode(id="b1", title="Book 1", children=[
            MindMapNode(id="b1-1", title="Chapter A"),
        ]),
        MindMapNode(id="b2", title="Book 2", children=[
            MindMapNode(id="b2-1", title="Chapter B"),
        ]),
    ])
    assert _default_initial_expand_level(tree, is_collection=True) == 2


def test_render_mindmap_html_single_book():
    """Single-book HTML: frontmatter sets initialExpandLevel: 1, has toolbar."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="Test Book", children=[
        MindMapNode(id="c1", title="Chapter 1"),
    ])
    html = render_mindmap_html(tree, "Test Book", is_collection=False)
    # Frontmatter drives the markmap renderer's initialExpandLevel
    assert "initialExpandLevel: 1" in html
    # Toolbar: true makes autoloader attach the standard toolbar
    assert "toolbar: true" in html
    # The autoloader script tag is present
    assert "markmap-autoloader" in html
    # Our custom monkey-patch script is present
    assert "__mmPatched" in html
    assert "__markmapInstances" in html
    # Our custom buttons are registered
    assert "expandAll" in html
    assert "collapseAll" in html
    # The CSS / DOM is in place
    assert "Test Book" in html
    assert "<h1>" in html
    assert "class=\"markmap\"" in html


def test_render_mindmap_html_collection():
    """Collection HTML: frontmatter sets initialExpandLevel: 2."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="Collection", children=[
        MindMapNode(id="b1", title="Book 1", children=[
            MindMapNode(id="b1-1", title="Chapter A"),
        ]),
        MindMapNode(id="b2", title="Book 2", children=[
            MindMapNode(id="b2-1", title="Chapter B"),
        ]),
    ])
    html = render_mindmap_html(tree, "Collection", is_collection=True)
    assert "initialExpandLevel: 2" in html
    # Title is in the h1 (escaped, but our test titles have no special chars)
    assert "Collection" in html
    # Sub-book titles appear as level-1 markdown headings
    assert "# Book 1" in html
    assert "# Book 2" in html


def test_render_mindmap_html_special_chars_in_title():
    """Titles with HTML-special chars should be properly placed (text content)."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="A & B <test>", children=[])
    html = render_mindmap_html(tree, "A & B <test>", is_collection=False)
    # The h1 and title are textual, so we don't need to escape. The
    # important thing is the html parses and contains the right text.
    assert "A & B <test>" in html


def test_render_mindmap_html_includes_click_handlers():
    """The custom buttons should have working onClick handlers."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="X", children=[])
    html = render_mindmap_html(tree, "X")
    # The Expand All handler calls setData with initialExpandLevel: -1
    assert "initialExpandLevel: -1" in html
    # The Collapse All handler calls setData with initialExpandLevel: 0
    assert "initialExpandLevel: 0" in html
    # Both handlers call mm.fit() to re-center the viewport
    assert "mm.fit()" in html


def test_render_mindmap_html_toolbar_items_order():
    """The toolbar.setItems call should put our buttons first, then defaults."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="X", children=[])
    html = render_mindmap_html(tree, "X")
    # Verify the setItems call lists our buttons first
    assert '"expandAll"' in html
    assert '"collapseAll"' in html
    # Then the standard markmap controls
    assert '"zoomIn"' in html
    assert '"zoomOut"' in html
    assert '"fit"' in html
    assert '"recurse"' in html
    assert '"dark"' in html


def test_render_mindmap_html_idempotent_patching():
    """The monkey-patch must be idempotent — running onReady twice should
    not double-register buttons."""
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="X", children=[])
    html = render_mindmap_html(tree, "X")
    # The __mmPatched flag is set before patching
    assert "window.__mmPatched = true" in html
    # And we check it before patching again
    assert "if (window.__mmPatched) return" in html


def test_render_mindmap_html_has_dark_mode_css():
    """Dark mode should set body / h1 / .markmap backgrounds and text colors.

    The markmap dark-mode toggle adds `.markmap-dark` to <html>. Our
    CSS rules need to respond to that class so the page background,
    h1 text, and the markmap container all flip to dark. Without
    these rules, the markmap's internal text color flips to white
    but the surrounding surfaces stay white — producing white text
    on white background (invisible).
    """
    from shoothighlm.mindmap import MindMapNode
    tree = MindMapNode(id="root", title="X", children=[])
    html = render_mindmap_html(tree, "X")
    # Light theme defaults: explicit white background on html/body
    assert "background: #ffffff" in html
    # Dark theme: html.markmap-dark flips body + markmap + h1
    assert "html.markmap-dark" in html
    assert "background: #1a1b26" in html
    # The h1 should also have an explicit color (not inherited)
    assert "h1" in html and "color" in html


# ============== _detect_chapters ==============
# Regression tests for the "chapters 1-4 of 干法 disappeared" bug.
# _detect_chapters pre-extracts `第N章` markers from the source text
# so the LLM prompt can list them as ground truth. Without this, the
# LLM invents theme names (e.g. "热爱导致成功") instead of using
# "第 2 章 让自己喜欢上所从事的工作" verbatim.


def test_detect_chapters_finds_arabic_numbered():
    """Arabic-numbered chapter markers like '第 1 章 标题' should match."""
    from shoothighlm.mindmap import _detect_chapters

    text = (
        "译者序\n"
        "前言\n"
        "第 1 章 磨炼灵魂，提升心志：为什么要工作\n"
        "我们为什么而工作\n"
        "第 2 章 让自己喜欢上所从事的工作：如何投入工作\n"
        "改变心态\n"
        "第 3 章 以高目标为动力\n"
        "第 4 章 持续就是力量\n"
        "第 5 章 追求完美主义\n"
        "第 6 章 创造性地工作\n"
        "结语\n"
    )
    titles = _detect_chapters(text)
    assert len(titles) == 6
    assert titles[0] == "第 1 章 磨炼灵魂，提升心志：为什么要工作"
    assert titles[1] == "第 2 章 让自己喜欢上所从事的工作：如何投入工作"
    assert titles[5] == "第 6 章 创造性地工作"


def test_detect_chapters_finds_chinese_numbered():
    """Chinese-numbered markers like '第 一 章' should also match."""
    from shoothighlm.mindmap import _detect_chapters

    text = (
        "第 一 章 领导者的资质\n"
        "内容...\n"
        "第 二 章 领导者的人格\n"
        "内容...\n"
        "第 三 章 领导者的十项职责\n"
    )
    titles = _detect_chapters(text)
    assert len(titles) == 3
    assert "第 一 章" in titles[0]
    assert "领导者的人格" in titles[1]


def test_detect_chapters_handles_part_and_lecture():
    """'第N部分' and '第N讲' are also valid chapter-like markers."""
    from shoothighlm.mindmap import _detect_chapters

    text = (
        "第一部分 概述\n"
        "第二部分 详细论述\n"
        "第 1 讲 开篇\n"
        "第 2 讲 进阶\n"
    )
    titles = _detect_chapters(text)
    # At least 4 titles found
    assert len(titles) >= 4
    assert any("部分" in t for t in titles)
    assert any("讲" in t for t in titles)


def test_detect_chapters_dedupes():
    """Same chapter marker appearing twice (e.g. in TOC + body) is one entry."""
    from shoothighlm.mindmap import _detect_chapters

    text = (
        "目录\n"
        "第 1 章 标题\n"
        "...\n"
        "第 1 章 标题\n"
        "正文开始\n"
    )
    titles = _detect_chapters(text)
    assert len(titles) == 1


def test_detect_chapters_respects_max_titles():
    """Long books: cap the number of detected titles."""
    from shoothighlm.mindmap import _detect_chapters

    text = "\n".join(f"第 {i} 章 标题{i}" for i in range(1, 100))
    titles = _detect_chapters(text, max_titles=10)
    assert len(titles) == 10


def test_detect_chapters_empty_input():
    """No text → empty list, no crash."""
    from shoothighlm.mindmap import _detect_chapters

    assert _detect_chapters("") == []
    assert _detect_chapters("无章节标记的纯文本") == []


def test_detect_chapters_skips_nested_markers():
    """'第 1 章 第 2 章 X' (broken OCR) should not double-count."""
    from shoothighlm.mindmap import _detect_chapters

    text = "第 1 章 第 2 章 错乱\n"
    # We want at most the outer one captured.
    titles = _detect_chapters(text)
    assert len(titles) <= 1


def test_detect_chapters_chinese_numbered_title_not_filtered():
    """Regression: '第 一 章 标题' must NOT be filtered as 'nested'.

    The previous regex `[0-9一二...]` matched the Chinese numeral
    '一' in '第一章标题' and incorrectly skipped it. Should be
    kept.
    """
    from shoothighlm.mindmap import _detect_chapters

    text = "第 一 章 领导者的资质\n"
    titles = _detect_chapters(text)
    assert len(titles) == 1
    assert "领导者的资质" in titles[0]
