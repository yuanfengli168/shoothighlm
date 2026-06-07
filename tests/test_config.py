"""Tests for shootHighLM configuration"""

import tempfile
from pathlib import Path
from shoothighlm.config import Config, init_config


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
