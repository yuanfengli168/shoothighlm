# Ollama Cloud — Model Research for 书海LM (shootHighLM)

> Researched: 2026-06-07

---

## 1. Ollama Cloud Overview

### What is Ollama Cloud?
Ollama Cloud is Ollama's hosted inference service. You use the **same `ollama` CLI/API**, just append `:cloud` to any model tag. Example: `ollama run qwen3.5:cloud`. No separate API endpoint — it's transparent.

### How it works
- Models tagged `:cloud` run on Ollama's GPU infrastructure (US-based, NVIDIA Blackwell/Vera Rubin)
- Native weights (not quantized) — same as released by model providers
- Supports tool calling, thinking modes, vision (where model supports it)
- Zero data retention (per MiniMax partnership docs; likely standard)

### Pricing Model
**NOT per-token.** Usage is measured by **GPU time** (model size × request duration). Plans:

| Plan | Price | Concurrent Models | Usage Level |
|------|-------|-------------------|-------------|
| Free | $0 | 1 | Light (chatting, eval) |
| Pro | ~$20/mo (est.) | 3 | 50× Free |
| Max | $100/mo | 10 | 5× Pro (250× Free) |
| Team | Coming soon | — | — |

- Usage resets every 5 hours (session) + 7 days (weekly)
- Models have usage levels: Level 1 (small) → Level 4 (extra heavy)
- Can add extra usage balance on Pro/Max
- Cached context shares reduce usage

### How to use
```bash
# CLI
ollama run qwen3.5:cloud

# API (same endpoint, just use :cloud tag)
curl http://localhost:11434/api/chat -d '{"model":"qwen3.5:cloud","messages":[...]}'

# Launch in agent apps
ollama launch openclaw --model qwen3.5:cloud
```

### Regions
Only US-based infrastructure confirmed. No multi-region info available yet.

---

## 2. Available Chat Models on Ollama Cloud

### Tier 1 — Frontier Cloud-Only Models (no local download)

| Model | Params | Context | Vision | Thinking | Tools | Usage Level | Chinese? |
|-------|--------|---------|--------|----------|-------|-------------|----------|
| **deepseek-v4-pro** | ~685B (MoE) | 1M | ❌ | ✅ (3 modes) | ✅ | Level 4 (Extra High) | ✅ Strong |
| **deepseek-v4-flash** | 284B total / 13B active | 1M | ❌ | ✅ (3 modes) | ✅ | Level 2 (Medium) | ✅ Strong |
| **glm-5.1** | ~744B total / ~40B active | — | ❌ | ✅ | ✅ | — | ✅✅ Native Chinese |
| **glm-5** | 744B total / 40B active | — | ❌ | ✅ | ✅ | — | ✅✅ Native Chinese |
| **minimax-m3** | Large MoE | 1M (512K guaranteed) | ✅ | ✅ | ✅ | High | ✅ |
| **kimi-k2.6** | 1.04T total | 256K | ✅ | ✅ | ✅ | High | ✅ |
| **minimax-m2.7** | Large | — | ❌ | ✅ | ✅ | — | ✅ |
| **minimax-m2.5** | Large | — | ❌ | ✅ | ✅ | — | ✅ |
| **deepseek-v3.2** | Large MoE | — | ❌ | ✅ | ✅ | — | ✅ |
| **nemotron-3-ultra** | Large | — | ❌ | ✅ | ✅ | — | — (English-focused) |
| **nemotron-3-super** | 120B (12B active MoE) | — | ❌ | ✅ | ✅ | — | — |
| **glm-4.7** | Large | — | ❌ | ✅ | ✅ | — | ✅✅ |
| **qwen3-coder-next** | Large | — | ❌ | ❌ | ✅ | — | ✅ |

### Tier 2 — Cloud + Local Available Models

| Model | Params | Context | Vision | Thinking | Tools | Cloud Usage | Chinese? |
|-------|--------|---------|--------|----------|-------|-------------|----------|
| **qwen3.5** | 0.8B–122B | 256K | ✅ | ✅ | ✅ | Medium (cloud tag) | ✅✅ Native |
| **gemma4** | E2B–31B | 128K–256K | ✅ | ✅ | ✅ | Cloud (31b-cloud) | ⚠️ Limited |
| **devstral-small-2** | 24B | — | ✅ | ❌ | ✅ | Cloud | ❌ |
| **nemotron-3-nano** | 4B/30B | — | ❌ | ✅ | ✅ | Cloud | — |
| **rnj-1** | 8B | — | ❌ | ❌ | ✅ | Cloud | ❌ |
| **gemini-3-flash-preview** | — | — | ✅ | ✅ | ✅ | Cloud | ⚠️ |

### Chinese-Capable Models (Best for 书海LM)
1. **GLM-5.1** — Native Chinese (Z.ai/清华), best Chinese reasoning
2. **GLM-5** — Native Chinese, slightly weaker than 5.1
3. **Qwen3.5-122B** — Alibaba, excellent Chinese + multimodal
4. **DeepSeek-V4-Pro/Flash** — Chinese company, strong Chinese benchmarks
5. **MiniMax M3/M2.7** — Chinese company, good Chinese support
6. **Kimi K2.6** — Moonshot AI, Chinese-native

---

## 3. Vision Models on Ollama Cloud

### Cloud Vision Models

| Model | Params | Context | Vision Type | Chinese OCR? | Best For |
|-------|--------|---------|-------------|-------------|----------|
| **qwen3.5:cloud** | 397B total/17B active | 256K | Native multimodal (early fusion) | ✅✅ Excellent | Chinese docs, OCR, reasoning |
| **minimax-m3:cloud** | Large MoE | 1M (512K guaranteed) | Native multimodal | ✅ Good | Long video, long docs |
| **kimi-k2.6:cloud** | 1.04T | 256K | Native multimodal | ✅ Good | Coding + vision |
| **gemma4:31b-cloud** | 31B | 256K | Text + Image | ⚠️ Limited Chinese | General vision |
| **gemini-3-flash-preview:cloud** | — | — | Text + Image | ⚠️ | Fast vision |

### PDF Page Understanding
- **Best: qwen3.5:cloud** — native multimodal, 256K context, excellent Chinese OCR
- PDFs can be sent as page images to vision models
- qwen3.5's early fusion training gives it best document understanding
- MiniMax M3 with 1M context can handle very long documents

### Local Vision Models (for 64GB M1 Max)
- **qwen3.5:27b** (17GB) — fits with room to spare, good Chinese vision
- **qwen3.5:9b** (6.6GB) — fast, decent quality
- **gemma4:26b** (4B active, MoE) — efficient, but weaker Chinese

---

## 4. Embedding Models

**No embedding models on Ollama Cloud.** Embeddings are **local-only** on Ollama. All run via `ollama pull` locally.

### Available Embedding Models

| Model | Params | Multilingual | Chinese? | Context | Best For |
|-------|--------|-------------|----------|---------|----------|
| **bge-m3** | 567M | ✅ | ✅✅ Best | 8192 | Chinese RAG (dense + sparse + colbert) |
| **qwen3-embedding** | 0.6B/4B/8B | ✅ | ✅✅ | 32K+ | Chinese RAG, latest Qwen tech |
| **nomic-embed-text-v2-moe** | MoE | ✅ | ✅ | 8192 | Multilingual retrieval |
| **snowflake-arctic-embed2** | 568M | ✅ | ✅ | — | Multilingual, good perf |
| **mxbai-embed-large** | 335M | ❌ | ❌ | 512 | English-only |
| **nomic-embed-text** | 137M | ❌ | ❌ | 8192 | English, long context |

### Recommendation for Chinese RAG
1. **bge-m3** — battle-tested, multi-function (dense+sparse+colbert), excellent Chinese
2. **qwen3-embedding:8b** — largest, newest Qwen tech, best if you have the RAM
3. **snowflake-arctic-embed2** — good multilingual alternative

---

## 5. Other Model Types

### TTS Models
No native TTS models on Ollama. Ollama is LLM/embedding focused.

### Image Generation Models
No image generation on Ollama Cloud. Some community models exist locally (stable-diffusion etc.) but not officially supported.

### Audio Models
Gemma4 supports **audio input** (marked on its page). This is the only audio-capable model on Ollama Cloud.

### Code-Specialized Models
- **qwen3-coder-next** — coding-focused (cloud)
- **devstral-small-2** — codebase exploration, 24B (cloud)
- **rnj-1** — code & STEM, 8B

### Math/Reasoning
All the frontier models (deepseek-v4, glm-5.1, qwen3.5, gemma4) have strong math via thinking modes.

---

## 6. Default Model Recommendations for 书海LM

### Default Chat Model (Cloud) — Best Chinese + Reasoning

| Rank | Model | Why |
|------|-------|-----|
| 🥇 | **glm-5.1:cloud** | Native Chinese (清华/Z.ai), strongest agentic performance, currently in use |
| 🥈 | **qwen3.5:cloud** | Native Chinese (Alibaba), multimodal, 256K context, excellent C-Eval |
| 🥉 | **deepseek-v4-flash:cloud** | Strong Chinese, 1M context, medium usage (cheaper), good reasoning |

**Recommendation: `glm-5.1:cloud`** — already proven, native Chinese, best for Chinese book understanding.

### Default Chat Model (Local Fallback) — Best for 64GB M1 Max

| Rank | Model | Size | Why |
|------|-------|------|-----|
| 🥇 | **qwen3.5:27b** | 17GB | Fits easily, Chinese-native, vision + thinking + tools |
| 🥈 | **qwen3.5:35b** | 24GB | Tighter fit, better quality |
| 🥉 | **gemma4:31b** | ~20GB | Good reasoning but weaker Chinese |

**Recommendation: `qwen3.5:27b`** — best balance of quality + Chinese + fits with room for other models.

### Default Vision Model — PDF Page Understanding

| Rank | Model | Why |
|------|-------|-----|
| 🥇 | **qwen3.5:cloud** | Best Chinese OCR + multimodal, 256K context |
| 🥈 | **minimax-m3:cloud** | 1M context for very long PDFs, native multimodal |
| 🥉 | **qwen3.5:27b** (local) | Offline fallback, still good Chinese OCR |

**Recommendation: `qwen3.5:cloud` for vision** — early fusion training, best Chinese document understanding.

### Default Embedding Model — Chinese RAG

| Rank | Model | Why |
|------|-------|-----|
| 🥇 | **bge-m3** | Multi-function (dense+sparse+colbert), proven Chinese, small (567M) |
| 🥈 | **qwen3-embedding:8b** | Newest, best Chinese, larger (needs ~5GB) |
| 🥉 | **snowflake-arctic-embed2** | Good multilingual fallback |

**Recommendation: `bge-m3`** — proven, multi-function, tiny footprint. Upgrade to qwen3-embedding if quality isn't enough.

---

## Summary: 书海LM Default Config

```yaml
models:
  chat_cloud: "glm-5.1:cloud"        # Native Chinese, best reasoning
  chat_local: "qwen3.5:27b"           # Chinese + vision + thinking, fits 64GB
  vision: "qwen3.5:cloud"             # Best Chinese OCR + multimodal
  embedding: "bge-m3"                 # Chinese RAG, multi-function
  
  # Alternatives
  chat_cloud_alt: "qwen3.5:cloud"     # Multimodal, 256K context
  chat_cloud_fast: "deepseek-v4-flash:cloud"  # 1M context, medium usage
  vision_local: "qwen3.5:27b"         # Offline vision fallback
  embedding_large: "qwen3-embedding:8b"  # Better quality if needed
  long_context: "minimax-m3:cloud"    # 1M context for very long docs
```

---

*Note: Pricing details beyond plan tiers are not publicly documented. Usage levels (1-4) vary by model size. Check ollama.com/settings for actual usage tracking.*