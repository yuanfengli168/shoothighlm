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
- **Interactive Mind Map** — Keyboard-navigate a tree of key concepts, press Enter to drill into any node and chat with AI about it. Exports to OPML, Markdown, HTML (interactive), XMind, FreeMind formats
- **Flashcards & Quizzes** — Auto-generate study materials from your documents

### Planned

- **Podcast Generation** — Two-voice Chinese podcast from your books (Fish Audio / CosyVoice TTS)
- **Notebook Guides** — Auto-generated suggested questions and topic overview
- **Infographics** — HTML/CSS templates rendered to PNG (free, perfect Chinese text) + optional AI hero art
- **Data Tables** — Extract and structure data from sources
- **LLM Ranking Board** — Benchmark and compare LLMs on book-reading ability (see [ranking-board.md](ranking-board.md))

### Not in scope (for now)

- Video overview, slide decks — too resource-intensive for local/cloud hybrid

## Quick Start

> ✅ Phase 1 MVP Complete — RAG chat with citations working!

```bash
# Install
pip install shoothighlm

# Initialize a notebook
shootHigh init ./my-books

# Add PDFs
cp ~/Downloads/*.pdf ./my-books/

# Index sources
shootHigh index ./my-books

# Chat with your books
shootHigh chat ./my-books

# Generate mind map (primary: Markdown)
shootHigh mindmap ./my-books

# Generate mind map (interactive HTML preview)
shootHigh mindmap ./my-books --format html

# Export to specific format
shootHigh mindmap ./my-books --export opml
shootHigh mindmap ./my-books --export freemind
shootHigh mindmap ./my-books --export xmind

# Generate flashcards
shootHigh flashcard ./my-books

# Generate podcast script + audio
shootHigh podcast ./my-books
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
| Mind Map (HTML) | mermaid.js | Click-to-explore in browser |
| Mind Map (Export) | OPML, Markdown, XMind, FreeMind, MindManager | Interoperable with all major mind map apps |
| Infographic | HTML/CSS + Puppeteer | Free, perfect CJK text rendering |
| TTS | Fish Audio S2 / CosyVoice | Best Chinese voice quality |
| Image Gen | FLUX.2 Flex (Replicate) | $0.03-0.05/image, good for decorative art |
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

## Documentation

- [DECISIONS.md](DECISIONS.md) — All project decisions, tech choices, limits
- [blueOcean.md](blueOcean.md) — Mind map + AI chat blue ocean analysis
- [ranking-board.md](ranking-board.md) — LLM ranking board concept
- [research/](research/) — Deep research on NotebookLM, LLMs, Ollama Cloud, TTS, infographics

## Status

✅ **Phase 2 P1 Complete** — Mind map + Flashcard generation working!

**Test Coverage:** 80 tests passing, 90% coverage ✅

| Phase | Status | Features |
|-------|--------|----------|
| Research | ✅ Done | NotebookLM analysis, LLM comparison, API research |
| Phase 1 (P0) | ✅ Done | PDF parsing, chunking, embedding, RAG chat with citations |
| Phase 2 (P1) | ✅ Done | Mind map extraction, flashcard generation |
| Phase 3 (P2) | ⏳ Planned | Podcast generation, infographics |
| Phase 4 (P3+) | ⏳ Planned | LLM ranking board, data tables |

## License

Apache 2.0 — See [LICENSE](LICENSE)