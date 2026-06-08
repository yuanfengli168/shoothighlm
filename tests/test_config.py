"""Tests for shootHighLM configuration"""

import tempfile
from pathlib import Path
from shoothighlm.config import Config, init_config, DEFAULT_CONFIG_PATH


def test_config_defaults():
    """Test that default config has required keys"""
    config = Config()
    assert "models" in config._config
    assert config.get("models", "chat") == "qwen3.5:cloud"
    assert config.get("models", "embedding") == "bge-m3"


def test_config_get_nested():
    """Test nested config access"""
    config = Config()
    assert config.get("models", "chat") is not None
    assert config.get("nonexistent", "key", default="fallback") == "fallback"


def test_config_save_load():
    """Test saving and loading config"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"
        config = Config(config_path)
        config._config["test_key"] = "test_value"
        config.save()
        
        # Load again
        config2 = Config(config_path)
        assert config2._config["test_key"] == "test_value"


def test_config_get_tts():
    """Test getting TTS config"""
    config = Config()
    assert config.get("tts", "provider") == "fish-audio"


def test_config_get_image():
    """Test getting image config"""
    config = Config()
    assert config.get("image", "provider") == "replicate"
    assert config.get("image", "model") == "flux-2-flex"


def test_config_get_limits():
    """Test getting limits config"""
    config = Config()
    limits = config.get("limits")
    assert limits["max_file_size"] == "50MB"
    assert limits["max_total_size"] == "500MB"
    assert limits["max_files"] == 50
    assert limits["max_tokens"] == 500000


def test_config_get_rag():
    """Test getting RAG config"""
    config = Config()
    assert config.get("rag", "chunk_size") == 4096
    assert config.get("rag", "chunk_overlap") == 200
    assert config.get("rag", "top_k") == 5
    assert config.get("rag", "min_similarity") == 0.7


def test_config_contains():
    """Test __contains__ method"""
    config = Config()
    assert "models" in config
    assert "nonexistent" not in config


def test_config_getitem():
    """Test __getitem__ method"""
    config = Config()
    assert config["models"] is not None
    assert "chat" in config["models"]


def test_init_config_creates_file():
    """Test init_config creates config file if not exists"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config = Config(config_path)
        config.save()
        
        # init_config should work
        result = init_config()
        assert result.config_path == config_path or result.config_path == DEFAULT_CONFIG_PATH


def test_config_output_dir():
    """Test output directory config"""
    config = Config()
    assert config.get("output", "dir") == "./output"
    assert "markdown" in config.get("output", "mindmap_formats")


def test_config_deep_merge_fills_missing_keys():
    """Test that partial user config is merged with defaults"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "partial_config.yaml"
        # Write a config with only models — should still have all other defaults
        config_path.write_text("""
models:
  chat: "custom-model"
""", encoding="utf-8")
        
        config = Config(config_path)
        
        # User's override is preserved
        assert config.get("models", "chat") == "custom-model"
        # Missing keys are filled in from defaults
        assert config.get("models", "embedding") == "bge-m3"
        assert config.get("tts", "provider") == "fish-audio"
        assert config.get("image", "provider") == "replicate"
        assert config.get("rag", "chunk_size") == 4096
        assert config.get("limits", "max_file_size") == "50MB"
        assert config.get("output", "dir") == "./output"


def test_config_deep_merge_preserves_user_nested_keys():
    """Test that user-provided nested keys override defaults without losing siblings"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nested_config.yaml"
        config_path.write_text("""
models:
  chat: "custom-chat"
  embedding: "custom-embedding"
""", encoding="utf-8")
        
        config = Config(config_path)
        
        # Both user overrides applied
        assert config.get("models", "chat") == "custom-chat"
        assert config.get("models", "embedding") == "custom-embedding"
        # Other model keys still have defaults
        assert config.get("models", "vision") == "qwen3.5:cloud"
        assert config.get("models", "chat_local") == "qwen3.5:27b"


def test_config_empty_file_uses_all_defaults():
    """Test that an empty config file still gives all defaults"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "empty_config.yaml"
        config_path.write_text("", encoding="utf-8")
        
        config = Config(config_path)
        
        assert config.get("models", "chat") == "qwen3.5:cloud"
        assert config.get("rag", "chunk_size") == 4096
