# 书海LM (shootHighLM)

> Chinese-first, multi-LLM CLI alternative to Google NotebookLM

Drop PDFs in a folder, run a command, get mind maps, flashcards, infographics, podcasts, and AI-powered Q&A — all from your terminal.

## Why shootHighLM?

Google NotebookLM is powerful, but it's:
- **American-biased** — flattens all content into a standardized US podcast format, weak Chinese experience
- **Browser-only** — no CLI, no terminal-native workflow
- **Locked to Google** — can't choose your own LLM

书海LM (shootHigh / 书海 = "sea of books") fixes all three:

| | NotebookLM | shootHighLM |
|---|---|---|
| Chinese | ⚠️ Weak | ✅ First-class |
| Interface | Browser | CLI (TUI) |
| LLM | Gemini only | Any (Ollama, OpenAI, Anthropic, ...) |
| Privacy | Cloud | Local-first + cloud optional |
| Mind map | Interactive (web) | Interactive (TUI + HTML) |
| Open source | ❌ | ✅ Apache 2.0 |

## Features

### Core (MVP)

- **RAG Chat with Citations** — Ask questions about your PDFs, get answers grounded in your sources with inline citations
- **PDF Source Management** — Drop PDFs in a folder, auto-parse, chunk, embed, index
- **Interactive Mind Map** — Keyboard-navigate a tree of key concepts (planned TUI), export to Markdown, OPML, HTML (Markmap), JSON
- **Flashcards & Quizzes** — Auto-generate study materials (Markdown / Anki CSV / JSON)
- **Notebook Guides** — Auto-generated summary, key topics, and suggested questions to start exploring
- **Podcast Generation** — Two-host conversational scripts + Fish Audio TTS → WAV audio
  - `shoot-high podcast` for the script
  - `shoot-high synthesize <script.json>` for the audio
- **Infographics** — HTML/CSS templates rendered to PNG with CJK-perfect text
  - `shoot-high infographic <notebook>` (templates: `summary_card`, `topic_hierarchy`, `stats_card`)
  - Add `--png` to also produce a PNG image (uses Playwright/Chrome)
- **Data Tables** — Extract comparisons, statistics, lists, and timelines as structured tables
  - `shoot-high tables <notebook>` (4 output formats: Markdown, CSV, JSON, HTML)
  - Use `--max N` to control how many tables to extract

### Planned

- **LLM Ranking Board** — Benchmark and compare LLMs on book-reading ability (see [ranking-board.md](ranking-board.md))
- **TUI Interactive Mind Map** — Click a node, chat with AI about it (blue ocean, see [blueOcean.md](blueOcean.md))

### Not in scope (for now)

- Video overview, slide decks — too resource-intensive for local/cloud hybrid

## Quick Start

> ✅ Phases 1-3 complete — RAG chat, mind maps, flashcards, podcast, TTS, notebook guides all working!

### Install (development mode)

The package isn't on PyPI yet. Install from a local clone:

```bash
git clone https://github.com/yuanfengli168/shoothighlm.git
cd shoothighlm
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[pdf,tts,image,dev]"
playwright install chromium   # only if you want --png for infographics
```

### Pick a model and run

The default chat model is **`qwen3.5:cloud`** (Ollama Cloud — most
powerful, requires `ollama signin`). Override per-command or globally:

```bash
# Default: cloud
shoot-high mindmap ~/my-books

# Switch to local
shoot-high mindmap ~/my-books --use-local

# Pick a specific model
shoot-high mindmap ~/my-books --model minimax-m3:cloud
shoot-high mindmap ~/my-books --model qwen3.5:27b

# Or set globally for the session
SHOOTHIGHLM_CHAT=qwen3.5:27b shoot-high mindmap ~/my-books
```

**Use `--full` for higher quality on large books** (50K-char prompt
vs 12K default — slower but covers more of the source).

### Initialize a notebook

```bash
shoot-high init ./my-books

# Add PDFs
cp ~/Downloads/*.pdf ./my-books/

# Index sources
shoot-high index ./my-books

# Chat with your books
shoot-high chat ./my-books

# Generate mind map (primary: Markdown)
shoot-high mindmap ./my-books

# Generate mind map (interactive HTML preview)
shoot-high mindmap ./my-books --format html

# Export to specific format
shoot-high mindmap ./my-books --export opml
shoot-high mindmap ./my-books --export freemind
shoot-high mindmap ./my-books --export xmind

# Generate flashcards
shoot-high flashcard ./my-books

# Generate notebook guide (summary, key topics, suggested questions)
shoot-high guide ./my-books

# Custom number of questions
shoot-high guide ./my-books --questions 8

# Export guide as JSON
shoot-high guide ./my-books --format json

# Generate podcast script (defaults to Markdown for human reading)
shoot-high podcast ./my-books

# To synthesize audio, generate the script as JSON first
shoot-high podcast ./my-books --format json
shoot-high synthesize ./my-books/output/book1-podcast.json

# Generate an infographic (HTML by default)
shoot-high infographic ./my-books

# Choose a different template
shoot-high infographic ./my-books --template topic_hierarchy
shoot-high infographic ./my-books --template stats_card

# Also render to PNG (requires playwright or system Chrome)
shoot-high infographic ./my-books --png

# Extract data tables (Markdown, CSV, JSON, HTML)
shoot-high tables ./my-books

# Limit number of tables, change format
shoot-high tables ./my-books --max 5 --format csv
shoot-high tables ./my-books --format json
shoot-high tables ./my-books --format html
```

## Configuration

Config file: `~/.shoothighlm/config.yaml`

```yaml
models:
  chat: "qwen3.5:cloud"           # Default chat model
  chat_local: "qwen3.5:27b"       # Local fallback
  vision: "qwen3.5:cloud"          # PDF OCR / vision
  embedding: "bge-m3"             # Local embedding model

tts:
  provider: "fish-audio"          # Fish Audio S2
  # provider: "cosyvoice"         # Alibaba Cloud alternative

image:
  provider: "replicate"           # FLUX.2 Flex for hero art
  model: "flux-2-flex"

limits:
  max_file_size: 50MB
  max_total_size: 500MB
  max_files: 50
  max_tokens: 500K
```

## Supported LLM Providers

| Provider | Chat | Vision | Embedding | Notes |
|----------|------|--------|-----------|-------|
| **Ollama Cloud** | ✅ qwen3.5, glm-5.1, deepseek-v4 | ✅ qwen3.5 | ❌ (local only) | Default, easy setup |
| **Ollama Local** | ✅ qwen3.5:27b, qwen3:32b | ✅ qwen3.5:27b | ✅ bge-m3 | Offline fallback |
| **OpenAI** | ✅ GPT-5 | ✅ GPT-5 | ✅ text-embedding-3 | Cloud |
| **Anthropic** | ✅ Claude 4.5 | ✅ Claude 4.5 | ❌ | Cloud |
| **Google** | ✅ Gemini 3 | ✅ Gemini 3 | ✅ | Cloud |
| **Alibaba Cloud** | ✅ Qwen-Max | ✅ Qwen-VL | ✅ | Chinese-native |
| **Zhipu AI** | ✅ GLM-5.1 | ✅ | ✅ | Chinese-native |

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python | RAG/ML ecosystem (LangChain, docling, chromadb) |
| CLI Framework | Textual (TUI) + Click | Interactive mind map + standard CLI |
| Embedding | bge-m3 | Best Chinese retrieval, 568M params, runs anywhere |
| Vector DB | sqlite-vec | Lightweight, no server needed |
| PDF Parsing | docling + marker | Battle-tested, handles complex layouts |
| Mind Map (TUI) | Textual tree + split-pane chat | Unique CLI interactive experience |
| Mind Map (HTML) | Markmap.js | Click-to-explore in browser |
| Mind Map (Export) | OPML, Markdown, XMind, FreeMind, MindManager | Interoperable with all major mind map apps |
| Infographic | HTML/CSS + Playwright (or system Chrome) | Free, perfect CJK text rendering |
| TTS | Fish Audio S2 (default), CosyVoice (planned) | Best Chinese voice quality; pure-stdlib WAV join |
| Image Gen | _Planned_ — FLUX.2 Flex (Replicate) | $0.03-0.05/image, good for decorative art (not yet implemented) |
| License | Apache 2.0 | Commercial-friendly, patent protection |

## Hard Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Single file | 50MB | Large PDFs slow to parse |
| Total folder | 500MB | Avoid excessive embedding time |
| File count | 50 | Beyond this, retrieval quality degrades |
| Total tokens | 500K | Beyond this, need batch processing |

## Blue Ocean: Interactive Mind Map → AI Chat

No open-source tool does "click mind map node → AI conversation" in the terminal. This is shootHighLM's unique differentiator.

See [blueOcean.md](blueOcean.md) for details.

## LLM Ranking Board (Planned)

Benchmark and rank LLMs on book-reading ability — long document understanding, citation accuracy, cross-chapter reasoning, Chinese text quality. No one does this today.

See [ranking-board.md](ranking-board.md) for the vision.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pip install shoothighlm` fails | Not on PyPI yet | Use `pip install -e ".[pdf,tts,image,dev]"` from a local clone (see Quick Start) |
| `sqlite3.OperationalError: not authorized` on `shoot-high index` | Python 3.13 + new SQLite needs explicit `enable_load_extension` | Already auto-fixed in current code. If you see it, update with `git pull` |
| `shoot-high mindmap` hangs 10+ min on a long PDF | Default backend was docling OCR (slow) | Already changed to `pypdf` by default. Override with `SHOOTHIGHLM_PDF_BACKEND=docling` only for scanned PDFs |
| `httpx.ReadTimeout: timed out` after 120s | Cloud model + thinking mode + long prompt = 50-100s+ | All LLM clients now use 600s timeout. If you still see this, check `ollama ps` — your model may be stuck loading |
| `500 Internal Server Error: the input length exceeds the context length` | bge-m3 has 8K-token limit; dense Chinese overflows | Embedder now auto-truncates to 6K chars with sentence-boundary cut. Your `chunk_size` config is capped to 2000 chars by default |
| `shoot-high chat` returns "couldn't find relevant information" even after indexing | `min_similarity` too high (0.7 was default) | Set `~/.shoothighlm/config.yaml` → `rag.min_similarity: 0.5` (bge-m3 + Chinese rarely exceeds 0.65) |
| `shoot-high index` only stores 1 chunk per PDF | Old bug — only read first page | Fixed. If you still see it, re-run with current code (commit `ee557cc` or later) |
| Cloud model unreachable | Ollama not signed in, or rate-limited | Run `ollama signin`, or use `--use-local` / set `SHOOTHIGHLM_CHAT=qwen3.5:27b` |
| `playwright._impl._api_types.TimeoutError` when rendering PNG | Playwright Chromium not installed | `playwright install chromium` (already in install instructions) |
| Mindmap / flashcard quality is weak on a long book | 12K-char prompt covers <3% of a 1,000-page book | Add `--full` to use 50K chars; ~4x slower but much more complete |
| `Could not find matching text` test failures in `tests/test_cli_*.py` | Rich's terminal-width line wrapping on long output paths | Already fixed in current tests; just pull latest |

## Cloud vs Local — How to Choose

The default is **cloud** (`qwen3.5:cloud`). Switch to local with `--use-local`
or `--model qwen3.5:27b` when:

- You want to work offline
- You have sensitive documents (data never leaves your machine)
- You want lower latency for repeated calls
- Your cloud quota is exhausted

Cloud is faster and higher quality for first-token time on small prompts
(50-100s including cold start). Local 27B is faster for warm sequential
calls but slower per call (~30s for warm 12K prompts, ~10min for 50K
prompts on M1 Max 64GB).

## Documentation

- [DECISIONS.md](DECISIONS.md) — All project decisions, tech choices, limits
- [blueOcean.md](blueOcean.md) — Mind map + AI chat blue ocean analysis
- [ranking-board.md](ranking-board.md) — LLM ranking board concept
- [research/](research/) — Deep research on NotebookLM, LLMs, Ollama Cloud, TTS, infographics

## Status

✅ **Phase 3 (P2+P3) Complete** — Podcast, TTS, Notebook Guides, and Infographics all shipped!

**Test Coverage:** 302 tests passing, 94.23% coverage ✅

| Phase | Status | Features |
|-------|--------|----------|
| Research | ✅ Done | NotebookLM analysis, LLM comparison, API research |
| Phase 1 (P0) | ✅ Done | PDF parsing, chunking, embedding, RAG chat with citations |
| Phase 2 (P1) | ✅ Done | Mind map extraction, flashcard generation |
| Phase 3 (P2) | ✅ Done | Podcast scripts, TTS audio, Notebook guides, Infographics, Data tables |
| Phase 4 (P3+) | ⏳ Planned | Interactive TUI mind map, LLM ranking board |

## License

Apache 2.0 — See [LICENSE](LICENSE)