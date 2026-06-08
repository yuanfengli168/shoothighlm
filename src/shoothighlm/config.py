"""Configuration loading and management"""

import os
from pathlib import Path
from typing import Any
import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".shoothighlm" / "config.yaml"
TEMPLATE_PATH = Path(__file__).parent.parent / "config.template.yaml"


class Config:
    """Configuration manager for shootHighLM"""
    
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: dict[str, Any] = {}
        self.load()
    
    def load(self) -> None:
        """Load configuration from file, merging with defaults for missing keys"""
        # Always start with defaults
        self._config = self._get_defaults()
        
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            # Deep merge: user values override defaults, missing keys get defaults
            self._config = self._deep_merge(self._config, user_config)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dicts, override takes precedence"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _get_defaults(self) -> dict[str, Any]:
        """Get default configuration"""
        return {
            "models": {
                "chat": "qwen3.5:cloud",
                "chat_local": "qwen3.5:27b",
                "vision": "qwen3.5:cloud",
                "embedding": "bge-m3",
            },
            "tts": {
                "provider": "fish-audio",
            },
            "image": {
                "provider": "replicate",
                "model": "flux-2-flex",
            },
            "limits": {
                "max_file_size": "50MB",
                "max_total_size": "500MB",
                "max_files": 50,
                "max_tokens": 500000,
            },
            "output": {
                "dir": "./output",
                "mindmap_formats": ["markdown", "opml", "html"],
            },
            "rag": {
                "chunk_size": 4096,
                "chunk_overlap": 200,
                "top_k": 5,
                "min_similarity": 0.7,
            },
        }
    
    def save(self) -> None:
        """Save configuration to file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self._config, f, allow_unicode=True, default_flow_style=False)
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """Get nested configuration value"""
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        return self._config[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self._config


def init_config() -> Config:
    """Initialize configuration, creating default if needed"""
    config = Config()
    if not config.config_path.exists():
        config.save()
    return config
