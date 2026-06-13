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
