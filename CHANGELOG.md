# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Phase 2 P1 — Mind Map + Flashcard Generation

#### Added
- `mindmap.py`: LLM-based mind map extraction from PDFs
  - Exports: Markdown, OPML, HTML (Markmap), JSON
  - Hierarchical tree structure with notes
  - 97% test coverage
- `flashcard.py`: Flashcard generation from PDFs
  - Exports: Markdown, CSV (Anki), JSON
  - Configurable number of cards
  - 98% test coverage
- CLI commands:
  - `shoot-high mindmap` — Generate mind maps in 4 formats
  - `shoot-high flashcard` — Generate flashcards in 3 formats
- CLI integration tests: 13 new tests for mindmap/flashcard commands
- Total tests: 80 passing
- Test coverage: **90% overall** ✅

#### Changed
- README updated to reflect Phase 2 completion
- `cli.py` coverage improved from 46% to 81%

### Phase 1 MVP — RAG Chat with Citations

#### Added
- `rag.py`: RAG retrieval, context building, LLM chat with inline citations (98% coverage)
- `vectorstore.py`: SQLite + sqlite-vec for vector storage (100% coverage)
- `embedding.py`: Ollama embedding generation (bge-m3) (100% coverage)
- `pdf.py`: PDF parsing with docling + pypdf fallback, text chunking (83% coverage)
- `config.py`: Configuration loading from `~/.shoothighlm/config.yaml` (97% coverage)
- `cli.py`: Working `index` and `chat` commands
- Dependencies: `docling`, `pypdf`, `pypdfium2`, `sqlite-vec`
- Comprehensive research documentation:
  - NotebookLM feature analysis
  - Chinese LLM comparison
  - Ollama Cloud model research
  - TTS and infographic API research
  - Mind map format comparison
- Project decisions documented in `DECISIONS.md`
- Blue ocean strategy documented in `blueOcean.md`
- LLM ranking board concept in `ranking-board.md`

#### Changed
- Default chat model: `qwen3.5:cloud` (multimodal, 256K context)
- CLI command style: kebab-case (`shoot-high`)
- Added `sqlite-vec` to core dependencies
- Added `pypdfium2` to PDF dependencies

#### Fixed
- Model recommendation consistency in `DECISIONS.md`
- sqlite-vec extension loading in vectorstore.py
- Missing `json` import in cli.py

### [0.1.0-dev] — 2026-06-07

#### Added
- Project initialization
- Research phase complete
- Package skeleton ready for implementation
- Apache 2.0 license
- Python package configuration (`pyproject.toml`)
- Configuration template at `config.template.yaml`

## [0.1.0-dev] - 2026-06-07

### Added
- Project initialization
- Research phase complete
- Package skeleton ready for implementation
