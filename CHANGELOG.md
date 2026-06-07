# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure with `src/shoothighlm/` package
- CLI entry point with `click` (`shoot-high` command)
- Configuration template at `config.template.yaml`
- Apache 2.0 license
- Python package configuration (`pyproject.toml`)
- Comprehensive research documentation:
  - NotebookLM feature analysis
  - Chinese LLM comparison
  - Ollama Cloud model research
  - TTS and infographic API research
  - Mind map format comparison
- Project decisions documented in `DECISIONS.md`
- Blue ocean strategy documented in `blueOcean.md`
- LLM ranking board concept in `ranking-board.md`

### Changed
- Default chat model: `qwen3.5:cloud` (multimodal, 256K context)
- CLI command style: kebab-case (`shoot-high`)

### Fixed
- Model recommendation consistency in `DECISIONS.md`

## [0.1.0-dev] - 2026-06-07

### Added
- Project initialization
- Research phase complete
- Package skeleton ready for implementation
