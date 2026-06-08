# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Docs cleanup (2026-06-08)

#### Changed
- `README.md`: standardized all 18 CLI command examples from `shootHigh` → `shoot-high` to match the actual `pyproject.toml` entry point
- `README.md`: corrected mind-map-HTML library from `mermaid.js` → `Markmap.js`
- `README.md`: marked Image Gen (Replicate FLUX.2 Flex) as planned, not implemented
- `DECISIONS.md`: marked 信息图 (Infographics) as ✅ in P3 row
- `DECISIONS.md`: added 3-template details + CJK font fallbacks to 信息图 section
- `DECISIONS.md`: added Phase 3 P3 + CI work to 已完成 list
- `DECISIONS.md`: removed 信息图 from 待完成 list (now done)

### CI: green ✅

- `4c4b719` — `Skip live OLLAMA test in CI (test_embedder_embed_real)`
- `758217e` — `Fix CI: remove phantom markmap-cli dep, bump actions to v5/v6`

### Coverage improvements

#### Added
- **Coverage gate** (`pyproject.toml`): `--cov-fail-under=93` so CI blocks regressions
- **GitHub Actions workflow** (`.github/workflows/tests.yml`): runs full test suite with coverage on push/PR; installs poppler + Playwright; uploads to Codecov
- **9 targeted tests** in `tests/test_coverage_boost.py`:
  - `synthesize` runtime-error and unknown-service paths
  - `infographic` runtime-error, value-error, and generic PNG-render-failure paths
  - `chat` EOF path
  - `_render_html` defense-in-depth for unknown templates
  - Bare-code-block fallback in `_extract_data`
  - "No Chrome anywhere" error path in `render_html_to_png`

#### Changed
- **Test coverage**: 93% → **94%** (1046 stmts, 62 miss)
- **Test count**: 188 → **197 passing**

### Phase 3 P3 — Infographic Generation

#### Added
- `infographic.py`: HTML/CSS template-based infographic generator
  - 3 built-in templates: `summary_card`, `topic_hierarchy`, `stats_card`
  - LLM extracts structured data, Jinja2 renders HTML
  - Built-in CJK font fallbacks (PingFang SC, Microsoft YaHei, Noto Sans CJK SC)
  - Optional PNG render via Playwright (auto-falls back to system Chrome)
  - 94% test coverage
- CLI command: `shoot-high infographic`
  - `--template` / `-t`: summary_card / topic_hierarchy / stats_card
  - `--output` / `-o`: Custom HTML output path
  - `--png`: Also render to PNG (requires playwright)
  - `--width` / `--height`: PNG viewport dimensions
- 20 unit tests + 10 CLI integration tests
- Total tests: 188 passing
- Test coverage: **93% overall** ✅

#### Changed
- CLI coverage improved from 88% to 89%

### Phase 3 P2 — TTS Audio Synthesis (Podcast)

#### Added
- `tts.py`: Multi-provider TTS for podcast audio
  - `FishAudioProvider`: Fish Audio S2 API (default)
  - `CosyVoiceProvider`: Alibaba Cloud CosyVoice (stub, not yet implemented)
  - `PodcastSynthesizer`: Routes segments to host_a/host_b voices, concatenates with silence
  - `concatenate_wav`: Pure-stdlib WAV joining (no ffmpeg/pydub needed)
  - 94% test coverage
- CLI command: `shoot-high synthesize <script.json>`
  - `--provider`: TTS provider override
  - `--voice-a` / `--voice-b`: Custom voice IDs
  - `--output` / `-o`: Output WAV path
  - `--pause`: Silence between segments (default 0.4s)
- 28 unit tests + 9 CLI integration tests
- Total tests: 158 passing
- Test coverage: **93% overall** ✅

#### Changed
- CLI coverage improved from 87% to 88%

### Phase 3 P2 — Notebook Guide Generation

#### Added
- `guide.py`: Notebook guide generation from PDF collections
  - Auto-generates summary, key topics, and suggested questions
  - Configurable number of questions (default: 5)
  - Combines text from all PDFs in notebook
  - Exports: Markdown, JSON
  - 98% test coverage
- CLI command: `shoot-high guide`
  - `--format`: markdown/json
  - `--questions` / `-q`: Number of suggested questions
  - `--output` / `-o`: Custom output path
- CLI integration tests: 7 new tests for guide command
- Total tests: 113 passing
- Test coverage: **93% overall** ✅

#### Changed
- CLI coverage improved from 84% to 87%

### Phase 3 P2 — Podcast Script Generation

#### Added
- `podcast.py`: Two-voice podcast script generation from PDFs
  - LLM writes conversational script between two hosts
  - Configurable duration (affects script length)
  - Custom host names (default: Alex & Jamie)
  - Exports: Markdown, JSON
  - 98% test coverage
- CLI command: `shoot-high podcast`
  - `--duration`: Target duration in minutes (default: 5)
  - `--host-a/--host-b`: Custom host names
  - `--format`: markdown/json
  - `--output`: Custom output path
- CLI integration tests: 6 new tests for podcast command
- Total tests: 96 passing
- Test coverage: **92% overall** ✅

#### Changed
- README updated to reflect Phase 3 progress
- `cli.py` coverage improved from 81% to 84%

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
