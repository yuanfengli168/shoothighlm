"""Tests for podcast generation"""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
from shoothighlm.podcast import PodcastGenerator, PodcastScript


@pytest.fixture
def generator():
    """Create a PodcastGenerator instance"""
    return PodcastGenerator(chat_model="test-model")


def test_podcast_script_creation():
    """Test creating a PodcastScript"""
    script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[
            {"speaker": "Alex", "text": "Welcome!"},
            {"speaker": "Jamie", "text": "Thanks!"},
        ],
    )
    
    assert script.title == "Test Podcast"
    assert script.duration_minutes == 5
    assert script.host_a_name == "Alex"
    assert script.host_b_name == "Jamie"
    assert len(script.segments) == 2


def test_podcast_script_to_dict():
    """Test converting script to dictionary"""
    script = PodcastScript(
        title="Test",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[{"speaker": "Alex", "text": "Hello"}],
    )
    
    result = script.to_dict()
    
    assert result["title"] == "Test"
    assert result["duration_minutes"] == 5
    assert result["host_a_name"] == "Alex"
    assert len(result["segments"]) == 1


def test_podcast_script_to_markdown():
    """Test converting script to Markdown"""
    script = PodcastScript(
        title="Test Podcast",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[
            {"speaker": "Alex", "text": "Welcome to the show!"},
            {"speaker": "Jamie", "text": "Thanks for having me!"},
        ],
    )
    
    md = script.to_markdown()
    
    assert "# Test Podcast" in md
    assert "**Duration:** 5 minutes" in md
    assert "**Hosts:** Alex & Jamie" in md
    assert "**Alex:** Welcome to the show!" in md
    assert "**Jamie:** Thanks for having me!" in md


def test_podcast_script_to_json():
    """Test converting script to JSON"""
    import json
    
    script = PodcastScript(
        title="Test",
        duration_minutes=5,
        host_a_name="Alex",
        host_b_name="Jamie",
        segments=[{"speaker": "Alex", "text": "Hello"}],
    )
    
    json_str = script.to_json()
    data = json.loads(json_str)
    
    assert data["title"] == "Test"
    assert data["duration_minutes"] == 5
    assert len(data["segments"]) == 1


def test_podcast_generator_init(generator):
    """Test generator initialization"""
    assert generator.chat_model == "test-model"
    assert generator.base_url == "http://127.0.0.1:11434"
    assert generator.host_a_name == "Alex"
    assert generator.host_b_name == "Jamie"


def test_podcast_generator_custom_hosts():
    """Test generator with custom host names"""
    generator = PodcastGenerator(
        chat_model="test-model",
        host_a_name="Host A",
        host_b_name="Host B",
    )
    
    assert generator.host_a_name == "Host A"
    assert generator.host_b_name == "Host B"


def test_podcast_generator_generate_mock(generator):
    """Test podcast generation with mock"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": """```json
{
  "title": "Test Podcast",
  "duration_minutes": 5,
  "host_a_name": "Alex",
  "host_b_name": "Jamie",
  "segments": [
    {"speaker": "Alex", "text": "Welcome!"},
    {"speaker": "Jamie", "text": "Thanks!"}
  ]
}
```"""
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        script, usage = generator.generate("Test text about AI", title="AI Discussion")
        
        assert isinstance(script, PodcastScript)
        assert script.title == "Test Podcast"
        assert len(script.segments) == 2
        assert script.segments[0]["speaker"] == "Alex"
        assert usage.total == 0


def test_podcast_generator_generate_no_json(generator):
    """Test generation when LLM doesn't return valid JSON"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": "Sorry, I couldn't generate a podcast script."
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response):
        script, usage = generator.generate("Test text", title="Test")
        
        # Should return fallback script
        assert isinstance(script, PodcastScript)
        assert script.title == "Test"
        assert "Failed to generate" in script.segments[0]["text"]
        assert usage.total == 0


def test_podcast_generator_truncate_long_text(generator):
    """Test that long text uses stratified sampling (start + middle + end)."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"title": "Test", "duration_minutes": 5, "host_a_name": "Alex", "host_b_name": "Jamie", "segments": []}'
    }
    mock_response.raise_for_status = Mock()

    # Create very long text
    long_text = "A" * 100000

    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        generator.generate(long_text, title="Test")

        # Check that stratified sampling was applied (not raw head truncation)
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']

        assert len(prompt) < 40000  # Should be truncated
        # Default mode uses stratified_sample, not the legacy
        # "... [truncated]" head-cut marker.
        assert "[... middle of document ...]" in prompt
        assert "[... end of document ...]" in prompt

def test_podcast_generator_duration_affects_dialogues(generator):
    """Test that duration affects number of dialogues"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "response": '{"title": "Test", "duration_minutes": 10, "host_a_name": "Alex", "host_b_name": "Jamie", "segments": []}'
    }
    mock_response.raise_for_status = Mock()
    
    with patch.object(generator.client, 'post', return_value=mock_response) as mock_post:
        # 10 minutes should generate more dialogues than 5 minutes
        generator.generate("Test text", title="Test", duration_minutes=10)
        
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        
        # Check that prompt mentions the duration
        assert "10 minutes" in prompt
        assert "approximately" in prompt
