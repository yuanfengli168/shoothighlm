# 书海LM v2 Research Answers

**Date:** 2026-06-07
**Machine:** 64GB M1 Max MacBook Pro

---

## Q1: Cloud/Online APIs for Infographic Generation

### Major Cloud Image Generation APIs & Pricing

| API | Cost per Image | Notes |
|-----|---------------|-------|
| **Replicate - FLUX.2 Flex** | ~$0.03-0.05/image | Typography & layout specialist, good for infographics |
| **Replicate - FLUX.2 Pro** | ~$0.04/image | High fidelity, structured JSON prompting |
| **Replicate - FLUX Schnell** | $0.003/image | Fastest/cheapest, lower quality |
| **Replicate - Ideogram v3** | $0.09/image | Built for graphic design, best text rendering |
| **Replicate - GPT Image 1.5** | Token-based (~$0.05-0.15/image) | Handles infographics & UI mockups well |
| **OpenAI GPT-Image-2** | Token-based (~$0.04-0.10/image) | State-of-the-art, good text/layout |
| **OpenAI DALL-E 3** | $0.04/image (1024²) / $0.08 (HD) | Decent but weaker at text rendering than FLUX Flex/Ideogram |
| **Together AI - SDXL** | $0.002-0.004/image | Very cheap, lower quality |
| **HuggingFace Inference** | Free tier available | Rate-limited, various models |
| **Midjourney** | $10-60/mo subscription | No pay-per-image API officially; unofficial APIs exist but TOS-risky |

### Best for Infographics Specifically

1. **FLUX.2 Flex** (via Replicate) — explicitly designed for typography, text rendering, layouts, memes, posters, infographics. ~$0.03-0.05/image. **Top pick.**
2. **Ideogram v3** — graphic design specialist, precise text, clean layouts. $0.09/image.
3. **GPT Image 1.5** (via Replicate) — handles complex prompts, infographics, UI mockups.
4. **Seedream 5 Lite** (ByteDance, via Replicate) — multi-step reasoning, good for structured/scientific content.

### Can Ollama Cloud Generate Images?

**No.** Ollama (including any cloud tier at ollama.com) only runs text LLMs. There are no image generation models available through Ollama — neither locally nor via cloud. You'd need a separate image generation service.

### Chinese-Friendly Infographic APIs

- **Seedream 4.5 / 5 Lite** (ByteDance) — available on Replicate, natively handles Chinese text rendering well
- **HappyHorse 1.0** (Alibaba) — available on Replicate, Chinese-origin model
- **Alibaba Cloud Bailian** — offers image generation APIs natively in Chinese
- **Zhipu AI (CogView)** — Chinese AI company with image generation capabilities
- **Tencent Hunyuan** — image generation available via Tencent Cloud API

### HTML/CSS Infographic as Fallback

**This is actually a very viable approach and potentially better than AI-generated images for infographics:**

- **Pros:** Pixel-perfect text rendering (including CJK), responsive, searchable, accessible, editable, zero cost, deterministic output
- **Cons:** Not as visually "artistic," requires template design work upfront
- **How good can it look?** Very professional — think: Notion-style info cards, Tailwind CSS stat blocks, Mermaid.js diagrams, D3.js visualizations. With good design, HTML/CSS infographics can rival or beat AI-generated ones for structured data.
- **Recommended stack:** Handlebars/JSX templates + Tailwind CSS + Chart.js/D3.js → render to PNG via Puppeteer/Playwright
- **Verdict:** For book summaries (key stats, timelines, concept maps), HTML/CSS is likely **superior** to AI image generation. Use AI images only for "hero art" or decorative elements.

### Recommendation for 书海LM

**Hybrid approach:**
1. **Default:** HTML/CSS templates rendered to PNG (free, perfect text, deterministic)
2. **Hero images:** FLUX.2 Flex via Replicate ($0.03-0.05/image) for cover art/decorative elements
3. **Chinese text-heavy:** Seedream or HTML/CSS (AI models still struggle with Chinese character rendering)

---

## Q2: Fish-Speech / Cloud Chinese TTS

### Fish Audio (fish.audio) Cloud API

**Yes, Fish Audio has a full cloud TTS API.** Key facts:

- **Product:** Fish Audio S2 — real-time expressive voice model
- **Languages:** Chinese, English, Japanese, Korean, + more
- **Features:** Voice cloning (as little as 10 seconds), emotion control, real-time streaming, 2M+ community voices
- **API:** REST API with SDKs, supports TTS and voice cloning
- **Pricing:** Free tier available (limited monthly generations), paid plans for commercial use (exact per-character pricing not publicly listed on the website as of research date — typically pay-as-you-go)
- **Commercial use:** Requires paid plan; free tier is personal use only

### Other Cloud Chinese TTS APIs

| Provider | API | Chinese Quality | Pricing | Notes |
|----------|-----|----------------|---------|-------|
| **Alibaba Cloud** | 智能语音交互 (Intelligent Speech) | ★★★★★ | ~¥0.01-0.04/千次 | CosyVoice model, very natural |
| **Tencent Cloud** | 语音合成 TTS | ★★★★☆ | ~¥0.01-0.02/千次 | Good, wide voice selection |
| **Baidu Cloud** | 语音合成 | ★★★★☆ | ~¥0.01-0.03/千次 | Solid, older tech |
| **Azure** | Cognitive Services TTS | ★★★★☆ | $16/1M chars | Xiaoxiao/Zhiyu voices excellent |
| **Google Cloud** | Cloud TTS | ★★★☆☆ | $4/1M chars | Fewer Chinese voices, decent |
| **Fish Audio** | Fish Audio S2 API | ★★★★★ | Free tier + paid | Best emotion control, cloning |
| **Volcengine (ByteDance)** | 火山引擎 TTS | ★★★★☆ | ~¥0.01-0.05/千次 | Good quality, enterprise |
| **MiniMax** | Speech-02 API | ★★★★★ | ~¥0.01/千字符 | Very natural Chinese |

### Can We Generate Two-Voice Podcasts Like NotebookLM?

**Yes, but with caveats:**

- NotebookLM generates a conversation between two AI hosts with distinct voices
- **With Fish Audio API:** Clone/select two different voices, then script a conversation and render each line with the appropriate voice. Stitch audio together.
- **With Alibaba CosyVoice:** Similar approach — pick two preset voices, generate interleaved lines
- **Challenge:** Natural conversational flow (interruptions, overlaps, reactions) is hard to achieve with basic TTS stitching. NotebookLM likely uses a more sophisticated dialogue generation pipeline.
- **Practical approach for 书海LM:**
  1. Use LLM to generate a two-host dialogue script from book summary
  2. Assign Voice A (e.g., "narrator") and Voice B (e.g., "commentator")
  3. Generate each line with appropriate voice via Fish Audio or Alibaba Cloud TTS
  4. Stitch audio segments with short pauses
  5. Result: 80% of NotebookLM quality at ~10% of the engineering effort

### Recommendation

**Fish Audio S2** for best expressiveness + voice cloning, or **Alibaba CosyVoice** for best value if in China. For the two-voice podcast feature, Fish Audio is the better choice due to emotion control and voice variety.

---

## Q3: bge-m3 Deep Dive

### What Is bge-m3?

- **Full name:** BGE-M3-Embedding
- **Creator:** BAAI (Beijing Academy of Artificial Intelligence) / FlagOpen
- **Paper:** arXiv:2402.03216 (Feb 2024)
- **Architecture:** XLM-RoBERTa (large)
- **Key "M3":** **M**ulti-Functionality (dense + multi-vector + sparse retrieval), **M**ulti-Linguality (100+ languages), **M**ulti-Granularity (short sentences to 8192-token documents)
- **Embedding dimension:** 1024
- **Max sequence length:** 8192 tokens
- **Model size:** ~2.2GB (568M parameters)

### bge-m3 vs gte-Qwen2 for Chinese Text

| Aspect | bge-m3 | gte-Qwen2-7B |
|--------|--------|---------------|
| Params | 568M | 7B (also available in smaller) |
| Model size | ~2.2GB | ~15GB (7B) / ~1.5GB (1.5B) |
| Chinese quality | ★★★★★ (top-tier on MIRACL benchmark) | ★★★★☆ (very good) |
| Multi-function | Dense + sparse + multi-vector | Dense only |
| Sequence length | 8192 | 32768 |
| Speed | Much faster | Slower (larger model) |
| Ollama support | Yes | Yes |

**Verdict:** For Chinese text specifically, bge-m3 slightly edges out gte-Qwen2 on MIRACL (multilingual retrieval) benchmarks. But gte-Qwen2 has longer context. For 书海LM's use case (book chunk embedding), bge-m3 is the better pick — faster, smaller, multilingual, and hybrid retrieval built-in.

### Can bge-m3 Run on Ollama?

**Yes.** Available on Ollama registry. Search: `ollama pull bge-m3` or community variants.

- **Size on disk:** ~2.2GB
- **RAM usage at runtime:** ~3-4GB
- **On 64GB M1 Max:** Trivial. Barely touches your resources.

### Can bge-m3 Run Locally on 64GB M1 Max?

**Absolutely, very comfortably.** At ~2.2GB model size, it uses <4GB RAM at runtime. You could run bge-m3 + a 7B LLM + other services simultaneously without breaking a sweat on 64GB M1 Max. Embedding generation will be fast on Apple Silicon.

### Cloud Embedding APIs Comparison

| Provider | Model | Price | Chinese Quality |
|----------|-------|-------|----------------|
| **OpenAI** | text-embedding-3-small | $0.02/1M tokens | ★★★☆☆ |
| **OpenAI** | text-embedding-3-large | $0.13/1M tokens | ★★★★☆ |
| **Cohere** | embed-v3 | $0.10/1M tokens | ★★★★☆ |
| **Voyage** | voyage-3 | $0.06/1M tokens | ★★★★☆ |
| **Jina** | jina-embeddings-v3 | $0.02/1M tokens | ★★★★☆ (good multilingual) |

**For 书海LM:** Running bge-m3 locally is **free and superior** for Chinese text. Cloud APIs are a backup if you need to offload from the Mac, but at ~2.2GB, there's no reason not to run it locally.

---

## Q4: NotebookLM's Interactive Mind Map

### How It Works

NotebookLM introduced an interactive mind map feature (Dec 2024) that auto-generates a visual mind map from your uploaded sources. Here's the UX flow:

1. **Generation:** After uploading sources, click "Mind Map" — NotebookLM auto-generates a hierarchical mind map of key concepts from your documents
2. **Layout:** Force-directed graph with nodes (topics) and edges (relationships). Central node radiates outward to sub-topics
3. **Click interaction:** Clicking a node **opens a chat panel / conversation about that topic**. It pre-fills the chat with a question about the clicked node, and NotebookLM answers based on your sources
4. **Expansion:** You can expand/collapse branches. Clicking deeper nodes drills into more specific sub-topics
5. **Transition:** The mind map slides/resize to make room for a chat panel that appears alongside it (split view). The chat is contextual — it knows which node you clicked
6. **No separate detail panel:** There's no static "info card." The interaction goes directly to the conversational AI interface, with the clicked node as context

### UX Flow Summary

```
View Mind Map → Click Node → Chat panel opens (split view) → 
  Node topic auto-populated as question → AI answers from sources → 
  Continue conversation naturally → Click another node to switch context
```

### Replicating in a CLI Tool

**Approach: Interactive TUI (Terminal UI)**

```
┌─────────────────────────────────────────────────┐
│ 书海LM Mind Map                                  │
│                                                  │
│  📖 人类简史                                      │
│  ├── 🧠 认知革命                                  │
│  │   ├── 语言起源                                 │
│  │   └── 虚构故事 ← [ENTER to explore]            │
│  ├── 🌾 农业革命                                  │
│  │   └── 定居生活                                  │
│  └── 💰 资本主义                                  │
│                                                  │
├──────────────────────────────────────────────────┤
│ > 虚构故事:                                       │
│ 书中提到，人类通过"虚构故事"实现大规模协作...        │
│ 智人能相信不存在的事物（神、国家、货币），            │
│ 这是区别于其他物种的关键能力。                      │
│                                                  │
│ 追问: 1. 虚构故事如何影响宗教?  2. 现代公司是虚构?   │
│ [数字选择追问 / 输入自定义问题 / ESC返回地图]       │
└──────────────────────────────────────────────────┘
```

**Implementation stack:**
- **TUI framework:** Ink (React for CLI), Blessed, or Textual (Python)
- **Navigation:** Arrow keys to browse nodes, Enter to drill into a topic
- **Chat mode:** Bottom panel shows LLM response + suggested follow-up questions (numbered, press 1/2/3 to select)
- **ESC** returns to mind map view
- **Two-panel layout** like NotebookLM's split view

### Open Source Interactive Mind Map Tools with Click-to-Chat

| Tool | Click-to-Chat? | Notes |
|------|---------------|-------|
| **Obsidian + Canvas** | Via plugins (Copilot) | Closest analogue — graph view + AI chat plugin |
| **Logseq** | Via AI plugins | Outliner + graph, can integrate LLM |
| **Markmap** | No | Just renders markdown as interactive mind map |
| **Mermaid.js** | No | Static diagram generation only |
| **react-flow** | Custom | Build your own — click-to-chat is trivial to add |
| **D3.js force graph** | Custom | Most flexible, most work |
| **Tree-of-thought CLI** | Experimental | Research project, not production |

**No turnkey open-source tool does "click mind map node → chat with AI about that topic" out of the box.** This is a greenfield opportunity for 书海LM to differentiate.

### Recommendation for 书海LM

Build a **Textual (Python) or Ink (Node.js) TUI** with:
1. Tree-style mind map (not force-graph — trees work better in terminals)
2. Arrow-key navigation + Enter to drill into a topic
3. Split-pane: tree on left, chat on right
4. Chat auto-populates with node context, suggests 2-3 follow-up questions
5. Data comes from bge-m3 embeddings + LLM summarization pipeline

This would be a genuinely unique CLI tool. Nobody is doing mind-map-to-chat in the terminal.

---

## Summary Recommendations

| Component | Recommendation | Why |
|-----------|--------------|-----|
| Infographic generation | HTML/CSS templates + Puppeteer → PNG (free), FLUX.2 Flex for hero art ($0.03-0.05) | Deterministic, perfect CJK text, zero cost for structured data |
| Chinese TTS | Fish Audio S2 API | Best expressiveness, voice cloning, Chinese native |
| Two-voice podcast | Fish Audio + LLM dialogue script | 80% of NotebookLM quality, practical |
| Embeddings | bge-m3 running locally on M1 Max | Free, best Chinese performance, tiny model (~2.2GB) |
| Mind map | Custom TUI with tree + chat split pane | Unique differentiator, no competition in CLI space |