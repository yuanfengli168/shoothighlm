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

- **LLM Ranking Board** — Benchmark and compare LLMs on book-reading ability (see [doc/ranking-board.md](doc/ranking-board.md))
- **TUI Interactive Mind Map** — Click a node, chat with AI about it (blue ocean, see [doc/blueOcean.md](doc/blueOcean.md))

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
vs 25K default for `mindmap`, 12K for the other 5 commands — slower
but covers more of the source).

### Initialize a notebook

```bash
shoot-high init ./my-books

# Add PDFs
cp ~/Downloads/*.pdf ./my-books/

# Index sources
shoot-high index ./my-books

# Chat with your books
shoot-high chat ./my-books

# Debug: see what chunks were retrieved + their similarity scores
shoot-high chat ~/my-books "可以总结一下第一章节讲了什么吗?" --show-sources

# Per-call: override the similarity threshold (no need to edit config)
shoot-high chat ~/my-books "问题" --min-similarity 0.3

# Generate mind map (primary: Markdown). Default uses 25K chars with
# uniform sampling to enumerate the whole book (NotebookLM-style TOC).
shoot-high mindmap ./my-books

# --full: 50K-char head-loaded prompt. Use this when the intro/foreword
# already summarizes the whole book (many non-fiction titles).
shoot-high mindmap ./my-books --full

# Generate mind map (interactive HTML preview). The HTML view
# opens with a smart default expand level (1 level for single
# books, 2 levels for multi-book collections like 收藏版) and
# includes custom toolbar buttons to Expand All / Collapse All.
shoot-high mindmap ./my-books --format html

# Export to specific format
shoot-high mindmap ./my-books --export opml
shoot-high mindmap ./my-books --export freemind
shoot-high mindmap ./my-books --export xmind

# Generate flashcards
shoot-high flashcard ./my-books
shoot-high flashcard ./my-books --full    # 50K-char prompt
shoot-high flashcard ./my-books -n 20    # 20 cards instead of 10

# Generate notebook guide (summary, key topics, suggested questions)
shoot-high guide ./my-books
shoot-high guide ./my-books --full        # 50K-char prompt

# Custom number of questions
shoot-high guide ./my-books --questions 8

# Export guide as JSON
shoot-high guide ./my-books --format json

# Generate podcast script (defaults to Markdown for human reading)
shoot-high podcast ./my-books
shoot-high podcast ./my-books --full      # 50K-char prompt

# The .md script is human-readable; .json is what synthesize needs.
# Pick one based on what you want to do next.
shoot-high podcast ./my-books --format json      # for synthesize
shoot-high podcast ./my-books --format markdown  # for reading / sharing

# Synthesize audio from EITHER format
shoot-high synthesize ./my-books/output/book1-podcast.json
shoot-high synthesize ./my-books/output/book1-podcast.md    # NEW: works too

# Generate an infographic (HTML by default)
shoot-high infographic ./my-books
shoot-high infographic ./my-books --full    # 50K-char prompt

# Choose a different template
shoot-high infographic ./my-books --template topic_hierarchy
shoot-high infographic ./my-books --template stats_card

# Also render to PNG (requires playwright or system Chrome)
shoot-high infographic ./my-books --png

# Extract data tables (Markdown, CSV, JSON, HTML)
shoot-high tables ./my-books
shoot-high tables ./my-books --full        # 50K-char prompt

# Limit number of tables, change format
shoot-high tables ./my-books --max 5 --format csv
shoot-high tables ./my-books --format json
shoot-high tables ./my-books --format html
```

### A note on `--full`

Add `--full` to any of the 6 LLM commands (`chat` is excluded — it uses
RAG, not direct prompting) to use a **50K-character prompt** instead of
the default.

Per-command defaults are tuned to each task:

| Command | Default | Sampling | With `--full` | Why |
|---|---|---|---|---|
| `mindmap` | 25K chars (≈ 6K tokens) | even (10 windows) | 50K chars head-loaded | Mind maps need to see the **whole** book to enumerate every chapter/principle — default uses uniform sampling to get parity with NotebookLM |
| `flashcard` | 12K | stratified (40/40/20) | 50K | Cards work best when the intro + middle + conclusion are well represented |
| `podcast` | 12K | stratified (40/40/20) | 50K | Same as flashcard |
| `guide` | 12K | stratified (40/40/20) | 50K | Notebook summaries are intro-heavy by nature |
| `infographic` | 12K | stratified (40/40/20) | 50K | Same as guide |
| `tables` | 12K | stratified (40/40/20) | 50K | Tables can be anywhere; stratified keeps context coherent |

The 12K default covers roughly the first 30–40 pages of a 1,000-page
book (intro, TOC, copyright); `--full` covers 4× more. For `mindmap`
the default already covers 2× the old 12K, so try it before reaching
for `--full`.

Trade-off: `--full` is **~4× slower** (3–5 min on cloud, 8–10 min
local for a 1,000-page book). Use it when you care about quality;
use the default when you want to iterate quickly.

See [`research/mindmap-comparison-vs-notebooklm.md`](research/mindmap-comparison-vs-notebooklm.md)
for the design rationale behind the mindmap-specific sampling and
prompt changes.

**Example** (mentioned in the previous user feedback, "mindmap quality
is weak on long books"):

```bash
# Default: 25K chars, uniform sampling, enumerates the whole book
# (~2-3× the node count vs the old 12K default)
shoot-high mindmap ~/my-books

# --full: 50K head-loaded, ~3-5 min cloud
shoot-high mindmap ~/my-books --full
```

## Batch automation

Run all 6 generation commands across every PDF in a notebook with one
invocation. Default: all 6 commands × all PDFs.

```bash
# Run everything (mindmap, flashcard, podcast, guide, infographic, tables)
shoot-high batch ~/my-books

# Run only a subset
shoot-high batch ~/my-books --include mindmap,flashcard

# Skip a subset (blacklist)
shoot-high batch ~/my-books --exclude podcast,infographic

# Both flags together → --include wins
shoot-high batch ~/my-books --include mindmap --exclude mindmap   # still runs mindmap

# Run 4 jobs in parallel (most LLM calls are I/O-bound)
shoot-high batch ~/my-books -w 4

# Resume a failed batch (skips jobs already in .batch-state.json with status=ok)
shoot-high batch ~/my-books --resume

# See what would run without making LLM calls
shoot-high batch ~/my-books --dry-run

# 50K-char prompt for higher fidelity
shoot-high batch ~/my-books --full
```

Each batch writes:
- `output/tokens.log` (JSONL) and `output/tokens.csv` — one row per (command, pdf) job
- `.batch-state.json` — state file for `--resume`

If a token-quota / context-length error is detected, the batch stops
cleanly (cancels in-flight jobs if running in parallel) and reports
which jobs need rerunning.

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

### TTS: how to set `FISH_AUDIO_API_KEY`

`FISH_AUDIO_API_KEY` is needed **only if you want to run `shoot-high synthesize`** (turning a podcast script into audio). Other commands (`chat`, `mindmap`, `flashcard`, `podcast`, `guide`, `infographic`, `tables`, `index`) don't need it.

#### Step 1 — Get an API key

1. Sign up at [fish.audio](https://fish.audio/) (free tier is available)
2. Go to **Settings → API Keys** and create a new key
3. Copy the key (looks like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

#### Step 2 — Set the key (pick ONE method)

**Method A — environment variable (recommended, session-scoped):**

```bash
# In your ~/.zshrc / ~/.bashrc so it persists across sessions:
export FISH_AUDIO_API_KEY="your-key-here"

# Or for a one-off command:
FISH_AUDIO_API_KEY="your-key-here" shoot-high synthesize ./my-books/output/book1-podcast.json
```

**Method B — in `~/.shoothighlm/config.yaml`:**

```yaml
tts:
  provider: "fish-audio"
  api_key: "your-key-here"     # uncomment and paste your key
```

**Method C — check the key works:**

```bash
# Quick smoke test (should not error)
shoot-high synthesize ./my-books/output/book1-podcast.md
# If you see "✗ TTS provider error: Fish Audio API key not found",
# the env var / config didn't take. See Troubleshooting below.
```

#### Alternative TTS providers

- **CosyVoice** (Alibaba, better in China): set `tts.provider: cosyvoice` in config and `COSYVOICE_API_KEY` env var
- See [TTS docs](doc/TTS.md) (planned) for the full provider list

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
| PDF Parsing | pypdf (default) + docling (opt-in OCR) | pypdf is fast for text PDFs; docling handles scanned/image-heavy files |
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

## Token Usage Logs

All 6 LLM generation commands append token usage logs under each notebook's
`output/` folder:

- `output/tokens.log` — JSONL (append-only, one record per LLM call)
- `output/tokens.csv` — spreadsheet-friendly CSV with the same records

Each record includes timestamp, command, source PDF(s), model,
input/output/total tokens, duration, status, and error text (if any).

## Blue Ocean: Interactive Mind Map → AI Chat

No open-source tool does "click mind map node → AI conversation" in the terminal. This is shootHighLM's unique differentiator.

See [doc/blueOcean.md](doc/blueOcean.md) for details.

## LLM Ranking Board (Planned)

Benchmark and rank LLMs on book-reading ability — long document understanding, citation accuracy, cross-chapter reasoning, Chinese text quality. No one does this today.

See [doc/ranking-board.md](doc/ranking-board.md) for the vision.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pip install shoothighlm` fails | Not on PyPI yet | Use `pip install -e ".[pdf,tts,image,dev]"` from a local clone (see Quick Start) |
| `sqlite3.OperationalError: not authorized` on `shoot-high index` | Python 3.13 + new SQLite needs explicit `enable_load_extension` | Already auto-fixed in current code. If you see it, update with `git pull` |
| `shoot-high mindmap` hangs 10+ min on a long PDF | Default backend was docling OCR (slow) | Already changed to `pypdf` by default. Override with `SHOOTHIGHLM_PDF_BACKEND=docling` only for scanned PDFs |
| `httpx.ReadTimeout: timed out` after 120s | Cloud model + thinking mode + long prompt = 50-100s+ | All LLM clients now use 600s timeout. If you still see this, check `ollama ps` — your model may be stuck loading |
| `500 Internal Server Error: the input length exceeds the context length` | bge-m3 has 8K-token limit; dense Chinese overflows | Embedder now auto-truncates to 6K chars with sentence-boundary cut. Your `chunk_size` config is capped to 2000 chars by default |
| `shoot-high chat` returns "couldn't find relevant information" even after indexing | `min_similarity` too high (bge-m3 + Chinese rarely exceeds 0.55) | Set `~/.shoothighlm/config.yaml` → `rag.min_similarity: 0.4` AND `rag.fallback_top_n: 3`. Or use `--min-similarity 0.3` per-call. Add `--show-sources` to debug |
| `shoot-high chat` returns an answer but says "Note: No chunk exceeded min_similarity" | All retrieved chunks were below the threshold | The answer is from the top-N fallback. Lower `min_similarity` to ~0.3 to silence the warning, or accept the fallback as best-effort |
| `shoot-high index` only stores 1 chunk per PDF | Old bug — only read first page | Fixed. If you still see it, re-run with current code (commit `ee557cc` or later) |
| Cloud model unreachable | Ollama not signed in, or rate-limited | Run `ollama signin`, or use `--use-local` / set `SHOOTHIGHLM_CHAT=qwen3.5:27b` |
| `playwright._impl._api_types.TimeoutError` when rendering PNG | Playwright Chromium not installed | `playwright install chromium` (already in install instructions) |
| Mindmap / flashcard quality is weak on a long book | `mindmap` was 12K-char intro-only; the other 5 still are | `mindmap` now defaults to 25K chars with uniform sampling and a new enumeration prompt (NotebookLM parity). For the other 5 commands, add `--full` to use 50K chars; ~4x slower but much more complete |
| `shoot-high synthesize` says "Fish Audio API key not found" | `FISH_AUDIO_API_KEY` not set | See the "TTS: how to set FISH_AUDIO_API_KEY" section above. Set via env var or in `~/.shoothighlm/config.yaml` |
| `shoot-high synthesize my-script.md` says "Invalid JSON" | Old behavior — synthesize only accepted `.json` | Fixed: now accepts both `.json` and `.md` (the human-readable default). If you have an older version, update with `git pull` |
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

- [doc/DECISIONS.md](doc/DECISIONS.md) — All project decisions, tech choices, limits
- [doc/blueOcean.md](doc/blueOcean.md) — Mind map + AI chat blue ocean analysis
- [doc/ranking-board.md](doc/ranking-board.md) — LLM ranking board concept
- [research/](research/) — Deep research on NotebookLM, LLMs, Ollama Cloud, TTS, infographics

## Status

✅ **Phase 3 (P2+P3) Complete** — Podcast, TTS, Notebook Guides, and Infographics all shipped!

**Test Coverage:** 403 tests passing, 94.06% coverage ✅

| Phase | Status | Features |
|-------|--------|----------|
| Research | ✅ Done | NotebookLM analysis, LLM comparison, API research |
| Phase 1 (P0) | ✅ Done | PDF parsing, chunking, embedding, RAG chat with citations |
| Phase 2 (P1) | ✅ Done | Mind map extraction, flashcard generation |
| Phase 3 (P2) | ✅ Done | Podcast scripts, TTS audio, Notebook guides, Infographics, Data tables |
| Phase 4 (P3+) | ⏳ Planned | Interactive TUI mind map, LLM ranking board |

## License

Apache 2.0 — See [LICENSE](LICENSE)