"""Tests for flashcard generation"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from shoothighlm.flashcard import FlashcardGenerator, Flashcard


@pytest.fixture
def generator():
    """Create a FlashcardGenerator instance"""
    return FlashcardGenerator(chat_model="test-model")


def test_flashcard_creation():
    """Test creating a Flashcard"""
    card = Flashcard(
        id="card-1",
        question="What is Python?",
        answer="A programming language",
        source="test.pdf",
        tags=["python", "programming"],
    )
    
    assert card.id == "card-1"
    assert card.question == "What is Python?"
    assert card.answer == "A programming language"
    assert card.source == "test.pdf"
    assert card.tags == ["python", "programming"]


def test_flashcard_default_tags():
    """Test that tags default to empty list"""
    card = Flashcard(
        id="card-1",
        question="Question?",
        answer="Answer",
    )
    
    assert card.tags == []


def test_flashcard_to_dict():
    """Test converting flashcard to dictionary"""
    card = Flashcard(
        id="card-1",
        question="Question?",
        answer="Answer",
        source="test.pdf",
        tags=["tag1"],
    )
    
    result = card.to_dict()
    
    assert result["id"] == "card-1"
    assert result["question"] == "Question?"
    assert result["answer"] == "Answer"
    assert result["source"] == "test.pdf"
    assert result["tags"] == ["tag1"]


def test_flashcard_to_markdown():
    """Test converting flashcard to Markdown"""
    card = Flashcard(
        id="card-1",
        question="What is Python?",
        answer="A programming language",
        source="test.pdf",
        tags=["python"],
    )
    
    md = card.to_markdown()
    
    assert "### What is Python?" in md
    assert "**Answer:** A programming language" in md
    assert "*Source: test.pdf*" in md
    assert "Tags: python" in md


def test_flashcard_to_anki_csv():
    """Test converting flashcard to Anki CSV"""
    card = Flashcard(
        id="card-1",
        question="Question?",
        answer="Answer",
        tags=["tag1", "tag2"],
    )
    
    csv = card.to_anki_csv()
    
    assert '"Question?"' in csv
    assert '"Answer"' in csv
    assert '"tag1 tag2"' in csv


def test_flashcard_to_anki_csv_escapes_quotes():
    """Test that CSV escaping works"""
    card = Flashcard(
        id="card-1",
        question='Question with "quotes"',
        answer="Answer",
    )
    
    csv = card.to_anki_csv()
    
    # Quotes should be escaped
    assert '""quotes""' in csv


def test_flashcard_generator_init(generator):
    """Test generator initialization"""
    assert generator.chat_model == "test-model"
    assert generator.base_url == "http://127.0.0.1:11434"


def test_flashcard_generator_generate_mock(generator):
    """Test flashcard generation with mock"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": """```json
[
  {
    "id": "card-1",
    "question": "What is AI?",
    "answer": "Artificial Intelligence",
    "tags": ["ai"]
  },
  {
    "id": "card-2",
    "question": "What is ML?",
    "answer": "Machine Learning",
    "tags": ["ml"]
  }
]
```"""
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        cards = generator.generate("Test text about AI and ML", num_cards=2)
        
        assert len(cards) == 2
        assert cards[0].question == "What is AI?"
        assert cards[0].answer == "Artificial Intelligence"
        assert cards[1].question == "What is ML?"


def test_flashcard_generator_generate_no_json(generator):
    """Test generation when LLM doesn't return valid JSON"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I couldn't generate flashcards."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        cards = generator.generate("Test text", num_cards=5)
        
        # Should return empty list
        assert len(cards) == 0


def test_flashcard_generator_truncate_long_text(generator):
    """Test that long text is truncated"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '[{"id": "card-1", "question": "Q?", "answer": "A"}]'
    }
    mock_response.raise_for_status = Mock()
    
    # Create very long text
    long_text = "A" * 100000
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate(long_text, num_cards=5)
        
        # Check that truncated text was sent
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        
        assert len(prompt) < 40000  # Should be truncated
        assert "... [truncated]" in prompt


def test_flashcard_generator_custom_num_cards(generator):
    """Test generating custom number of cards"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '[{"id": "card-1", "question": "Q1", "answer": "A1"}]'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate("Test text", num_cards=20)
        
        # Check that prompt includes the number
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        
        assert "exactly 20 flashcards" in prompt
