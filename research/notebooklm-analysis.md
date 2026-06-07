# Google NotebookLM — Deep Feature & Technical Analysis

> Foundation research for building 书海LM (shootHighLM)
> Date: 2026-06-07

---

## 1. Complete Feature List

### 1.1 Source Management
- **Supported formats:** PDF, Google Docs, Google Slides, websites/URLs, YouTube videos (from transcripts), plain text, audio files
- **Limits (free):** Up to 50 sources per notebook, 500K words total, 200MB max per source
- **Limits (Plus):** More sources, larger documents, higher usage quotas
- **Source types can be mixed** in a single notebook
- Sources are chunked and indexed for RAG retrieval

### 1.2 Chat / Q&A Over Sources
- Conversational interface grounded **only** in uploaded sources (no hallucination from general knowledge)
- Each answer includes **inline citations** linking back to specific source passages
- Clickable citation numbers jump to the highlighted passage in the source
- "Suggested questions" / notebook guides auto-generated from source content
- Follow-up questions maintain conversation context

### 1.3 Audio Overview (Podcast Generation)
- Generates a **two-host conversational podcast** from sources
- Two AI voices (male + female) discuss the content naturally
- ~5-10 minutes long for typical documents
- **Interactive mode** (Dec 2024): users can "Join" the conversation and ask questions mid-podcast
- **80+ languages** supported (expanded 2025)
- Criticized for flattening all content into a standardized American podcast format regardless of cultural context

### 1.4 Video Overview
- Transforms source summaries into **visual slide-style videos**
- AI narration + images + diagrams + structured explanations
- **Cinematic video mode** (Jul 2025): more immersive video outputs for Plus users
- 80+ languages

### 1.5 Mind Map / Deep Mind Chart
- Auto-generated **interactive mind map** from source content
- Nodes are clickable → drill into subtopics
- Hierarchical visualization of key concepts and relationships
- Based on LLM-extracted entity/relationship graph

### 1.6 Infographic Generation
- Added **Nov 2025**, powered by Google's **Nano Banana Pro** image generation model
- Visualizes source material as detailed infographics
- Combines LLM summarization + image generation

### 1.7 Slide Deck Generation
- Added **Nov 2025** alongside Infographics
- Also powered by Nano Banana Pro
- Auto-generates presentation slides from sources

### 1.8 Data Tables
- Added **Dec 2025**
- Extracts and structures data from sources into tabular format
- Part of the broader "output format" strategy

### 1.9 Flashcards
- Generate study flashcards from source content
- Spaced repetition friendly format

### 1.10 Notebook Guides / Suggested Questions
- Auto-generated **notebook guide** summarizes all sources
- Suggested questions tailored to source content
- Helps users explore material they might not think to ask about

### 1.11 Sharing & Collaboration
- Share notebooks with others (view/comment)
- **NotebookLM Plus:** Collaborative notebooks for teams
- Real-time multiplayer support in Plus tier

### 1.12 Notes
- Users can save chat responses and key insights as **notes** within the notebook
- Notes become part of the context for future queries
- Acts as a personal annotation layer on top of sources

### 1.13 Voice Transcribe
- Convert lecture recordings and voice notes into searchable text
- Becomes a source in the notebook

---

## 2. Technical Reverse Engineering

### 2.1 LLM Backend
- **Current model: Gemini 3** (as of Mar 2026, per Wikipedia)
- Previously: Gemini 1.5 Pro → Gemini 2.0 Flash → Gemini 3
- Chat/Q&A, summarization, mind map extraction, suggested questions all powered by Gemini
- Likely uses **Gemini 3 Flash** for fast queries and **Gemini 3 Pro** for complex synthesis

### 2.2 Embedding Models
- Likely **Google's text-embedding-gecko** or newer Gemini-native embeddings
- Embeddings used for semantic search across source chunks
- Vector similarity search for RAG retrieval

### 2.3 RAG Pipeline Architecture
```
Sources → Extract/Parse → Chunk → Embed → Vector Store
                                                    ↓
Query → Embed → Vector Search → Top-K Chunks → Gemini → Response + Citations
```
- **Chunking:** Documents split into ~500-1000 token overlapping chunks
- **Retrieval:** Hybrid search (semantic + keyword) likely, given quality of citations
- **Citation tracking:** Each chunk mapped back to source + passage location
- **Multi-source synthesis:** Retrieved chunks from multiple sources combined in prompt; Gemini synthesizes across them
- **Grounding:** System prompt forces model to only use retrieved context, not general knowledge
- **Context window:** Gemini 3 likely has 1M+ token context, allowing large source sets to fit

### 2.4 Audio Overview (Podcast) Pipeline
```
Sources → RAG Retrieval → Gemini 3 (script generation) → Two-voice TTS → Audio
```
1. **Script generation:** Gemini writes a two-host conversational script based on source summaries and key points
2. **Two distinct voices:** Google's TTS (likely **SoundStorm** or **Gemini-native audio**)
3. **Interactive mode:** Real-time Gemini generates responses to user interruptions, TTS streams back
4. **Multi-language:** Script translated to target language, then TTS in that language

### 2.5 Mind Map Generation
```
Sources → Gemini (entity/relationship extraction) → JSON graph → Frontend rendering (D3.js or similar)
```
1. LLM extracts key concepts, entities, and relationships from sources
2. Structured as a hierarchical JSON graph
3. Frontend renders as interactive, explorable tree/network visualization
4. Clicking nodes triggers deeper extraction queries

### 2.6 Infographic / Slide Generation
```
Sources → Gemini (content outline + visual description) → Nano Banana Pro (image generation) → Layout engine → Output
```
1. **Nano Banana Pro** is Google's image generation model (mentioned in Wikipedia)
2. Gemini outlines content sections and visual descriptions
3. Image model generates visual elements
4. Layout engine assembles into infographic/slide format

### 2.7 Token & File Limits
| Feature | Free Tier | Plus Tier |
|---------|-----------|-----------|
| Sources per notebook | 50 | More |
| Total words | 500K | More |
| Max source size | 200MB | Larger |
| Notebooks | Limited | Unlimited |
| Audio overviews | Limited per day | More |
| Video overviews | Limited | More |

### 2.8 Multi-Source Synthesis
- All sources in a notebook are treated as a **unified knowledge base**
- RAG retrieves from across all sources simultaneously
- Gemini's large context window allows substantial cross-referencing
- Citations always indicate which source a claim comes from

---

## 3. Open Source Alternatives

### 3.1 Full NotebookLM Clones / Alternatives

| Project | Description | Stack | Key Features |
|---------|-------------|-------|-------------|
| **SurfSense** | Privacy-focused NotebookLM for teams, no data limits | Python, React | Podcast gen, report gen, slides, video, 25+ data sources, multiplayer, Ollama support |
| **KnowNote** | Local-first Electron desktop app | Electron, React, SQLite, sqlite-vec | RAG chat, mind maps, quiz gen, PPT gen, audio transcription, Ollama support |
| **PageLM** | Education-focused NotebookLM | Node.js, React, LangChain | Quizzes, flashcards, podcasts, notes, debate mode, Ollama support |
| **tldw_server** | API-first media analysis platform | FastAPI, Next.js, PostgreSQL | Video/audio/doc ingestion, RAG, OpenAI-compatible API, 16+ LLM providers |
| **Insights-LM** | Self-hosted NotebookLM alternative | React, Supabase, N8N | Chat with docs, audio summaries, source grounding |
| **NotebookMLX** | Port of NotebookLlama concept | Jupyter Notebook | Local MLX-based pipeline |

### 3.2 Podcast-Only Alternatives

| Project | Description |
|---------|-------------|
| **Podcastfy** | Open source Python alternative to NotebookLM's podcast feature. Multimodal → multilingual audio conversations. Supports websites, PDFs, images, YouTube. |
| **qiaomu-anything-to-notebooklm** | Multi-source content processor → NotebookLM. WeChat, web, YouTube, PDF, Markdown → Podcast/PPT/MindMap/Quiz |

### 3.3 RAG CLI / Local Tools

| Tool | Description |
|------|-------------|
| **Ollama + Open WebUI** | Local LLM + RAG web UI, supports document upload and chat |
| **LlamaIndex / LangChain** | Framework-level RAG building blocks |
| **privateGPT** | Fully local RAG document chat (LlamaIndex-based) |
| **khoj** | Self-hosted AI copilot with document chat, works with Ollama |
| **AnythingLLM** | Desktop RAG app with Ollama support |
| **docling** | IBM's document parsing library (PDF→structured text) |
| **Marker** | PDF→Markdown converter |

### 3.4 Mind Map from Documents
- **KnowNote** has one-click mind map generation
- **markmap** - Markdown → mind map renderer
- Custom approach: LLM extract entities → JSON → D3.js/mermaid rendering

### 3.5 TTS for Podcast Generation (Local)
| Tool | Description |
|------|-------------|
| **Edge TTS** | Free Microsoft TTS, good quality, multiple voices |
| **Piper** | Fast local neural TTS, runs on CPU |
| **Coqui TTS** | Open source neural TTS with voice cloning |
| **Bark** | Text-to-audio with multiple speaker voices |
| **fish-speech** | Chinese-friendly open source TTS |

---

## 4. Key Technical Challenges for Local Replication with Ollama

### 4.1 RAG Chat with Citations ⚡ MODERATE
- **Doable:** Ollama + embedding model (nomic-embed-text/mxbai-embed-large) + vector DB (sqlite-vec/chromaDB)
- **Challenge:** Citation precision — tracking which chunk an answer came from requires careful chunk↔source mapping
- **Challenge:** Grounding enforcement — preventing model from using training data vs sources only

### 4.2 Audio Overview (Podcast) 🔴 HARD
- **Script generation:** Ollama can generate conversational scripts — feasible
- **Two-voice TTS:** Biggest challenge. Local TTS (Piper/Bark) quality is significantly lower than Google's SoundStorm/Gemini audio
- **Interactive mode:** Real-time interruption + response generation requires streaming LLM + streaming TTS — complex pipeline
- **Chinese language TTS:** Limited good local options (fish-speech is best bet)
- **Recommended approach:** Generate script with Ollama → use fish-speech or Edge TTS for Chinese → combine audio tracks with pydub

### 4.3 Mind Map 🟡 MODERATE
- **Extraction:** Ollama can extract entity/relationship JSON from documents
- **Rendering:** Use mermaid.js or D3.js — straightforward
- **Challenge:** Quality of hierarchical structure extraction depends heavily on prompt engineering
- **Challenge:** Making it interactive (clickable drill-down) requires progressive extraction on click

### 4.4 Infographic / Slide Generation 🔴 HARD
- **Content layout:** Ollama can generate structured outlines for slides
- **Image generation:** Requires a local image model (SDXL/Flux) — GPU intensive, quality gap vs Nano Banana Pro
- **Layout engine:** Assembling text + images into professional-looking infographics is a significant engineering challenge
- **Alternative approach:** Generate HTML/CSS-based infographics (no image gen needed) — more feasible

### 4.5 Video Overview 🔴 VERY HARD
- Requires: script generation + slide images + TTS narration + video rendering
- **Feasible pipeline:** Ollama script → HTML slides → TTS audio → ffmpeg combine
- **Challenge:** Cinematic quality is very far from achievable locally

### 4.6 Flashcards / Quizzes 🟢 EASY
- Straightforward LLM prompt: "Generate flashcards from this content"
- Ollama handles this well
- Format as JSON, render in UI

### 4.7 Multi-Source Synthesis 🟡 MODERATE
- **Context window limit:** Most local Ollama models have 8K-128K context; Gemini has 1M+
- **Workaround:** RAG retrieval selects relevant chunks from all sources
- **Challenge:** Complex cross-source reasoning (e.g., "compare author A's view vs author B's") requires retrieved chunks from both to fit in context

### 4.8 Source Management 🟡 MODERATE
- **PDF parsing:** Use docling, marker, or pdfjs-dist — mature tooling
- **YouTube transcripts:** Use youtube-transcript-api — easy
- **URL scraping:** Use trafilatura or readability — easy
- **Audio transcription:** Use Whisper (local) — moderate GPU requirement
- **Challenge:** Consistent chunking across heterogeneous formats

### 4.9 Chinese Language Support 🟡 MODERATE
- **Chat/Q&A:** Qwen2.5, GLM-4 handle Chinese very well on Ollama
- **Embeddings:** nomic-embed-text has limited Chinese quality; bge-m3 or gte-Qwen2 are better for Chinese
- **TTS:** fish-speech is the best open-source Chinese TTS option
- **Mind maps / UI:** No language barrier

### 4.10 Sharing & Collaboration 🟡 MODERATE
- Purely an app-layer feature, not an AI challenge
- Requires auth, real-time sync (WebSockets), conflict resolution
- Can be built incrementally

---

## 5. Recommended Architecture for 书海LM

### Priority Feature Ordering (by feasibility × value)

| Priority | Feature | Feasibility | Value |
|----------|---------|-------------|-------|
| P0 | RAG chat with citations | High | Critical |
| P0 | Source management (PDF, URL, YouTube, text) | High | Critical |
| P1 | Mind map generation | High | High |
| P1 | Flashcards / quizzes | Very High | High |
| P2 | Audio podcast generation | Medium | High (differentiator) |
| P2 | Notebook guides / suggested questions | Very High | Medium |
| P3 | Infographic (HTML-based) | Medium | Medium |
| P3 | Data tables | High | Medium |
| P4 | Video overview | Low | Low (skip initially) |
| P4 | Slide deck | Medium | Low (skip initially) |

### Suggested Tech Stack

```
LLM:          Ollama (Qwen2.5-72B / GLM-4 for Chinese, llama3.1 for English)
Embeddings:   bge-m3 or gte-Qwen2 (Chinese-friendly)
Vector DB:    sqlite-vec (lightweight) or ChromaDB
TTS:          fish-speech (Chinese) + Edge TTS (backup)
PDF parsing:  docling + marker
Web scraping: trafilatura
Audio STT:    Whisper (whisper.cpp for speed)
Mind map:     mermaid.js rendering
Frontend:     React/Next.js or Electron (like KnowNote)
Backend:      Python (FastAPI) or Node.js
```

### Key Differentiator for 书海LM

- **Chinese-first** experience (unlike NotebookLM's American bias)
- **Local-first** privacy with Ollama
- **Book-focused** workflow (reading notes, chapter summaries, cross-book synthesis)
- **Study tools** (flashcards, quizzes, mind maps) optimized for Chinese academic materials

---

## 6. References & Sources

- Wikipedia: https://en.wikipedia.org/wiki/NotebookLM
- SurfSense: https://github.com/MODSetter/SurfSense
- KnowNote: https://github.com/MrSibe/KnowNote
- PageLM: https://github.com/CaviraOSS/PageLM
- Podcastfy: https://github.com/souzatharsis/podcastfy
- tldw_server: https://github.com/rmusser01/tldw_server
- NotebookLM Plus: https://one.google.com/about/ai-premium