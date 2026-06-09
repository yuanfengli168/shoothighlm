# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Index pipeline hardening + cloud-fallback policy

#### Added
- `--use-local` and `--model TEXT` flags on all 6 LLM-using commands
  (chat, mindmap, flashcard, podcast, guide, infographic, tables).
  Lets the user switch to local model or specify a custom model name
  per-invocation, without editing config.
- `--full` flag on the same 6 commands. Uses a 50K-char prompt instead
  of the 12K default for higher-fidelity generation on large books.
  Default 12K keeps cloud calls under 1 min; `--full` may take 3-5 min.
- `SHOOTHIGHLM_CHAT` env var as third-way override (after `--model` and
  `--use-local`). Sets the active chat model for the session.
- New shared helpers in `cli.py`:
  - `resolve_chat_model(config, use_local, model_override)` —
    priority chain: --model > --use-local > env > config > "qwen3.5:cloud"
  - `_is_cloud_error(exc)` — detects httpx timeouts, connection
    errors, and 5xx so the cloud-failure hint only fires for network
    issues, not normal LLM parsing errors
  - `_OLLAMA_CLOUD_HINT` — the message shown to the user when the
    cloud LLM is unreachable, listing 3 ways to switch to local
- `enable_load_extension(True)` call in `vectorstore.py` to fix
  "not authorized" error on Python 3.13 / SQLite 3.53+ file-backed
  connections (sqlite-vec requires explicit opt-in for new SQLite
  builds)
- `SHOOTHIGHLM_PDF_BACKEND` env var. Default: `pypdf` (fast text-layer
  extraction). Set to `docling` to opt into the heavyweight OCR
  pipeline for scanned/image-only PDFs. (50-100x faster default.)
- Defensive truncation in `embedding.py`: model-aware char budget
  (bge-m3: 6,000 chars), smart truncation at sentence boundary,
  automatic 50% retry on 500 "input length exceeds context length"
  errors from Ollama.
- Per-chunk `try/except` in `shoot-high index` so one bad chunk
  doesn't abort the whole PDF indexing run; reports `(ok/N, M skipped)`.
- `--use-local` and `--model` flags integrated into all 6 LLM commands.
- **New docs**:
  - `doc/Todo.md` — living doc of strategy + planned work (sampling,
    multi-provider, shell prompt, coverage)
  - `doc/gitCommitDetails.md` — per-commit metadata log
  - `doc/ChallengesInChinese.md` — real-world issues hit while
    building (was empty placeholder, now has content)

#### Changed
- **PDF backend default**: from `docling` (OCR, 50-100x slower on
  CPU) to `pypdf` (instant text-layer extraction). Opt-in to docling
  via `SHOOTHIGHLM_PDF_BACKEND=docling` for scanned PDFs.
- **Chunk size default**: from 4096 chars to 2000 chars (bge-m3 has an
  8K-token context; dense Chinese is unsafe above ~2K chars).
- **min_similarity default**: from 0.7 to 0.5 (0.7 was too strict;
  observed max cosine sim for Chinese text with bge-m3 is ~0.65).
- **HTTP timeouts**: all 7 LLM clients (mindmap, flashcard, podcast,
  guide, infographic, tables, rag) bumped from 120s to 600s. Cloud
  models with thinking mode + 50K-char prompts can take 3-5 min.
- **Prompt truncation limits**: 30-50K chars → 12K chars in all
  LLM-using modules. Smaller prompts ≈ 4x faster inference.
- `~/.shoothighlm/config.yaml` now defaults `models.chat` to
  `qwen3.5:cloud` (was: local); `qwen3.5:27b` kept as `chat_local`
  fallback. Cloud is primary; local is opt-in only.
- `shoot-high index`: now reads all pages of the PDF (was: only
  first page via `next()`). Bug fix; previously only 1 chunk was
  indexed per book.
- `shoot-high {mindmap,flashcard,podcast,guide,infographic,tables}`:
  all read all pages now too (was: only first page). Same fix.
- Each LLM-using command now prints the active model name and
  prompt-size in its "Extracting..." status line for visibility.

#### Fixed
- `sqlite3.OperationalError: not authorized` on Python 3.13 / SQLite
  3.53+ (vectorstore now enables extension loading before calling
  `sqlite_vec.load()`)
- Mindmap/flashcard/podcast/guide/infographic/tables all only saw
  page 1 of the PDF (was: `next(parse_pdf(pdf), "")`).
- bge-m3 returning 500 "input length exceeds context length" on
  dense Chinese chunks of 4K+ chars (now truncates to 6K safe limit).
- Index crash on first embedding 500 killed the whole batch (now
  per-chunk try/except).
- `shoot-high chat` always returned "couldn't find relevant
  information" because `min_similarity=0.7` filtered everything
  (config now defaults to 0.5).
- 3 test fragilities exposed by these changes: config default tests
  using user config (now use `_NONEXISTENT` path), 4 tests with
  rich line-wrap on long paths (now strip newlines before check).

#### Policy

**Cloud is primary; local is opt-in fallback.** Resolution order:

1. `--model <name>` CLI flag (explicit override always wins)
2. `--use-local` CLI flag → uses `models.chat_local`
3. `SHOOTHIGHLM_CHAT` env var
4. `models.chat` from config (default: `qwen3.5:cloud`)

When the cloud is unreachable, the user gets a hint listing all 3
escape hatches. We do NOT auto-fallback — user explicitly wants
explicit control.

#### Test Coverage

- **302 tests passing, 1 skipped**
- Coverage at **94.23%** ✅ (above the 93% threshold)
- New test files:
  - `tests/test_cli_helpers.py` (16) — `_is_cloud_error` and
    `resolve_chat_model` priority chain
  - `tests/test_use_full_flag.py` (14) — `--full` flag propagation
    and 12K→50K prompt-size switch
  - `tests/test_pdf_embedding_edges.py` (14) — docling fallback,
    50% retry on 500, sentence-boundary truncation
  - `tests/test_cli_cloud_errors.py` (9) — chat cloud / non-cloud
    / HTTP 500 error paths
  - `tests/test_cli_generator_errors.py` (12) — cloud + generic
    error paths in mindmap, flashcard, podcast, guide, infographic,
    tables
- Per-file coverage: `embedding.py` 100%, `vectorstore.py` 100%,
  `pdf.py` 95%, all generators 96-98%

---

## [Unreleased] (continued — to be moved to next release)

### Bug fix: CLI exception handlers now catch httpx errors

The `infographic` and `tables` commands only caught
`(ValueError, RuntimeError)` from their LLM calls. A real
`httpx.ConnectError` / `httpx.ReadTimeout` from a cloud outage
would propagate as a Click exception and crash the command.
Now catches `httpx.HTTPError` (and its subclasses) too — same
pattern as the other 4 LLM commands.

---

### Phase 3 P3 — Data Table Extraction

#### Added
- `tables.py`: Extract structured tabular data from PDFs
  - `DataTable` dataclass with name, description, columns, rows, source
  - `TableExtractor` class: LLM-based extraction with strict JSON validation
  - 4 output formats: **Markdown** (default), **CSV**, **JSON**, **HTML**
  - Robust to malformed LLM output (skips bad entries, keeps good ones)
  - CSV output correctly quotes special chars (commas, quotes, newlines)
  - 98% test coverage
- CLI command: `shoot-high tables`
  - `--max` / `-m`: Limit number of tables (default 3)
  - `--format` / `-f`: markdown / csv / json / html
  - `--output` / `-o`: Custom output path
  - Multi-PDF support: extracts tables from every PDF in the notebook
  - Graceful error handling: if one PDF fails, others still process
- 30 unit tests + 12 CLI integration tests
- Total tests: **239 passing**
- Test coverage: **95% overall** ✅

#### Changed
- Coverage: 94% → **95%** (1224 stmts, 66 miss)

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
