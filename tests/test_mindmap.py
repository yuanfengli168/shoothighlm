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
        result = extractor.extract("Test text", title="Test Document")
        
        assert isinstance(result, MindMapNode)
        assert result.title == "Test Document"
        assert len(result.children) == 1
        assert result.children[0].title == "Topic 1"


def test_mindmap_extractor_extract_no_json(extractor):
    """Test extraction when LLM doesn't return valid JSON"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I couldn't extract a mind map from this text."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(extractor.client, 'post', return_value=mock_response):
        result = extractor.extract("Test text", title="Test Document")
        
        # Should return fallback node
        assert isinstance(result, MindMapNode)
        assert result.title == "Test Document"
        assert "Failed to parse" in result.notes


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
