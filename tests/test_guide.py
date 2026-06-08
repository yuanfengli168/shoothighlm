"""Tests for notebook guide generation"""

import pytest
from unittest.mock import Mock, patch
from shoothighlm.guide import GuideGenerator, NotebookGuide


@pytest.fixture
def generator():
    """Create a GuideGenerator instance"""
    return GuideGenerator(chat_model="test-model")


def test_guide_creation():
    """Test creating a NotebookGuide"""
    guide = NotebookGuide(
        title="Test Notebook",
        summary="A test summary",
        key_topics=["AI", "ML"],
        suggested_questions=["What is AI?"],
        sources=["test.pdf"],
    )
    
    assert guide.title == "Test Notebook"
    assert guide.summary == "A test summary"
    assert guide.key_topics == ["AI", "ML"]
    assert guide.suggested_questions == ["What is AI?"]
    assert guide.sources == ["test.pdf"]


def test_guide_default_collections():
    """Test that collections default to empty lists"""
    guide = NotebookGuide(title="Test", summary="Sum")
    
    assert guide.key_topics == []
    assert guide.suggested_questions == []
    assert guide.sources == []


def test_guide_to_dict():
    """Test converting guide to dictionary"""
    guide = NotebookGuide(
        title="Test",
        summary="Summary",
        key_topics=["A"],
        suggested_questions=["Q?"],
        sources=["s.pdf"],
    )
    
    result = guide.to_dict()
    
    assert result["title"] == "Test"
    assert result["summary"] == "Summary"
    assert result["key_topics"] == ["A"]
    assert result["suggested_questions"] == ["Q?"]
    assert result["sources"] == ["s.pdf"]


def test_guide_to_markdown_full():
    """Test converting guide to Markdown with all sections"""
    guide = NotebookGuide(
        title="Machine Learning 101",
        summary="This notebook covers the basics of ML.",
        key_topics=["Supervised Learning", "Neural Networks", "Training"],
        suggested_questions=["What is overfitting?", "How do neural networks work?"],
        sources=["ml.pdf", "intro.pdf"],
    )
    
    md = guide.to_markdown()
    
    assert "# 📓 Machine Learning 101" in md
    assert "## 概述 (Summary)" in md
    assert "This notebook covers the basics of ML." in md
    assert "## 🎯 关键主题 (Key Topics)" in md
    assert "- Supervised Learning" in md
    assert "- Neural Networks" in md
    assert "## 💡 建议问题 (Suggested Questions)" in md
    assert "1. What is overfitting?" in md
    assert "2. How do neural networks work?" in md
    assert "*Sources: 2 document(s)" in md
    assert "ml.pdf" in md


def test_guide_to_markdown_minimal():
    """Test converting minimal guide to Markdown"""
    guide = NotebookGuide(title="Empty", summary="Nothing here")
    
    md = guide.to_markdown()
    
    assert "# 📓 Empty" in md
    assert "## 概述 (Summary)" in md
    assert "Nothing here" in md
    # Optional sections should not appear
    assert "Key Topics" not in md
    assert "Suggested Questions" not in md
    assert "Sources" not in md


def test_guide_to_json():
    """Test converting guide to JSON"""
    guide = NotebookGuide(
        title="Test",
        summary="Sum",
        key_topics=["T1"],
        suggested_questions=["Q?"],
    )
    
    json_str = guide.to_json()
    
    # Should be valid JSON
    import json
    data = json.loads(json_str)
    assert data["title"] == "Test"
    assert data["key_topics"] == ["T1"]
    # ensure_ascii=False means Chinese chars are preserved
    assert "建议问题" not in json_str  # Title was English, no Chinese


def test_generator_init(generator):
    """Test generator initialization"""
    assert generator.chat_model == "test-model"
    assert generator.base_url == "http://127.0.0.1:11434"


def test_generator_generate_mock(generator):
    """Test guide generation with mock response"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": """```json
{
  "summary": "This is a summary of the documents.",
  "key_topics": ["AI", "Machine Learning", "Deep Learning"],
  "suggested_questions": [
    "What is the difference between AI and ML?",
    "How do neural networks learn?",
    "What are the main challenges in deep learning?"
  ]
}
```"""
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        guide = generator.generate(
            "Test text about AI and ML",
            title="AI Notebook",
            sources=["ai.pdf", "ml.pdf"],
            num_questions=3,
        )
        
        assert guide.title == "AI Notebook"
        assert "summary" in guide.summary.lower()
        assert len(guide.key_topics) == 3
        assert "AI" in guide.key_topics
        assert len(guide.suggested_questions) == 3
        assert guide.sources == ["ai.pdf", "ml.pdf"]


def test_generator_generate_no_code_block(generator):
    """Test generation when LLM returns raw JSON without code blocks"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"summary": "Direct JSON.", "key_topics": ["X"], "suggested_questions": ["Q?"]}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        guide = generator.generate("Some text", title="Test")
        
        assert guide.summary == "Direct JSON."
        assert guide.key_topics == ["X"]


def test_generator_generate_invalid_json(generator):
    """Test generation when LLM returns invalid JSON"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I cannot analyze these documents."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        guide = generator.generate("Some text", title="Test", sources=["x.pdf"])
        
        # Should return fallback guide
        assert guide.title == "Test"
        assert "Failed" in guide.summary
        assert guide.key_topics == []
        assert guide.suggested_questions == []
        assert guide.sources == ["x.pdf"]


def test_generator_generate_truncate_long_text(generator):
    """Test that long text is truncated"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"summary": "S", "key_topics": [], "suggested_questions": []}'
    }
    mock_response.raise_for_status = Mock()
    
    long_text = "B" * 100000
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate(long_text, title="T")
        
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        
        assert len(prompt) < 40000
        assert "... [truncated]" in prompt


def test_generator_custom_num_questions(generator):
    """Test that custom num_questions is used in prompt"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"summary": "S", "key_topics": [], "suggested_questions": []}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate("text", title="T", num_questions=8)
        
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        
        assert "8" in prompt
        assert "Suggest" in prompt


def test_generator_uses_correct_model(generator):
    """Test that the configured model is sent to API"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"summary": "S", "key_topics": [], "suggested_questions": []}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate("text", title="T")
        
        call_args = mock_post.call_args
        assert call_args[1]['json']['model'] == "test-model"


def test_generator_default_sources_empty(generator):
    """Test that sources defaults to empty list"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"summary": "S", "key_topics": [], "suggested_questions": []}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        guide = generator.generate("text", title="T")
        
        assert guide.sources == []


def test_generator_close(generator):
    """Test that close shuts down the client"""
    with patch.object(generator.client, 'close') as mock_close:
        generator.close()
        mock_close.assert_called_once()
