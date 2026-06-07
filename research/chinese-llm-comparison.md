# Chinese-Capable LLMs on Ollama — Comparison (June 2026)

> **Updated**: Focus on **Ollama Cloud** — no local RAM constraints. Any size model runnable via cloud.

## TL;DR — Best Chinese Models on Ollama Cloud

| Rank | Model | Ollama Command | Chinese Quality | Context | Cloud Usage Level |
|---|---|---|---|---|---|
| 🥇 | **Qwen3.5-122B (MoE)** | `ollama run qwen3.5:122b` | ★★★★★ | 128K+ | High |
| 🥈 | **DeepSeek-V4-Flash** | `ollama run deepseek-v4-flash:cloud` | ★★★★★ | 1M | Medium |
| 🥉 | **DeepSeek-V4-Pro** | `ollama run deepseek-v4-pro:cloud` | ★★★★★ | 1M | Extra Heavy |
| 4 | **GLM-5.1** | `ollama run glm-5.1:cloud` | ★★★★★ | 128K+ | High |
| 5 | **Qwen3-235B (MoE)** | `ollama run qwen3:235b` | ★★★★★ | 128K | Very High |
| 6 | **GLM-5** | `ollama run glm-5:cloud` | ★★★★☆ | 128K+ | High |
| 7 | **DeepSeek-V3.2** | `ollama run deepseek-v3.2:cloud` | ★★★★☆ | 160K | High |
| 8 | **MiniMax M3** | `ollama run minimax-m3:cloud` | ★★★★☆ | 512K–1M | High |
| 9 | **Kimi K2.6** | `ollama run kimi-k2.6:cloud` | ★★★★☆ | 256K | High |
| 10 | **Qwen3.5-35B** | `ollama run qwen3.5:35b` | ★★★★☆ | 128K+ | Medium |

---

## Ollama Cloud — How It Works

### Pricing (as of June 2026)

| Plan | Price | Concurrent Cloud Models | Usage | Best For |
|---|---|---|---|---|
| **Free** | $0 | 1 | Light | Chatting, evaluating models, small models |
| **Pro** | ~$20/mo (est.) | 3 | 50x Free | Day-to-day work, larger models, coding |
| **Max** | $100/mo | 10 | 5x Pro (250x Free) | Continuous agents, sustained heavy use |

- Usage is measured by **GPU time** (not tokens) — shorter prompts and cached context cost less
- Session limits reset every 5 hours; weekly limits reset every 7 days
- Models have **usage levels** from 1 (lightest) to 4 (heaviest), affecting how fast you burn through your quota

### Cloud Usage Levels by Model

| Level | Examples |
|---|---|
| **1 — Small** | gpt-oss:20b, small local models |
| **2 — Medium** | deepseek-v4-flash, qwen3.5:27b |
| **3 — High** | qwen3.5:122b, glm-5.1, deepseek-v3.2, qwen3:235b, minimax-m3, kimi-k2.6 |
| **4 — Extra Heavy** | deepseek-v4-pro |

---

## All Chinese-Capable Cloud Models on Ollama

### Tier 1: Best Chinese (Native Chinese training, top benchmarks)

#### Qwen3.5-122B (MoE) — 🏆 Best Chinese on Ollama Cloud
- **Command**: `ollama run qwen3.5:122b`
- **Architecture**: MoE, 122B total params
- **Context**: 128K+
- **Cloud usage**: High
- **Chinese**: C-Eval **93.0** (from official blog)
- **Multimodal**: Yes (vision)
- **Languages**: 201 languages/dialects
- **Thinking mode**: Yes
- **Why #1**: Latest Qwen generation, highest Chinese benchmark among Ollama cloud models, multimodal, 201 languages

#### DeepSeek-V4-Flash — Best for Long Chinese Context
- **Command**: `ollama run deepseek-v4-flash:cloud`
- **Architecture**: MoE, 284B total / 13B active
- **Context**: **1M tokens** 🏆
- **Cloud usage**: Medium (cheapest tier for this quality!)
- **Chinese**: Chinese-SimpleQA **78.9** (max thinking), **73.2** (high thinking)
- **3 Thinking modes**: No thinking / Thinking / Max thinking
- **Why notable**: 1M context window + medium usage tier = best value for long Chinese documents

#### DeepSeek-V4-Pro — Maximum Reasoning Power
- **Command**: `ollama run deepseek-v4-pro:cloud`
- **Architecture**: MoE (frontier class)
- **Context**: 1M tokens
- **Cloud usage**: Extra Heavy (level 4 — most expensive)
- **Chinese**: Chinese-SimpleQA **84.4** (max thinking) — highest Chinese QA score available
- **3 Thinking modes**: Same as V4-Flash
- **Caveat**: Burns through usage fast; best for Max plan users

#### GLM-5.1 — Tsinghua's Flagship for Agents
- **Command**: `ollama run glm-5.1:cloud`
- **Architecture**: MoE
- **Context**: 128K+
- **Cloud usage**: High
- **Chinese**: Native Chinese model (Tsinghua / Z.ai)
- **Strengths**: SWE-Bench Pro **58.4**, NL2Repo **42.7**, best for Chinese + coding agents
- **Thinking mode**: Yes
- **Why notable**: Sustains performance over very long agent sessions (hundreds of rounds)

#### Qwen3-235B-A22B (MoE) — Qwen3 Flagship
- **Command**: `ollama run qwen3:235b`
- **Architecture**: MoE, 235B total / 22B active
- **Context**: 128K
- **Cloud usage**: Very High
- **Chinese**: Top-tier (Qwen3 C-Eval likely 91-93)
- **Languages**: 119 languages/dialects
- **Thinking mode**: Hybrid (thinking + non-thinking)
- **Note**: Older generation than Qwen3.5; Qwen3.5-122B likely surpasses it

### Tier 2: Strong Chinese

#### GLM-5 — 744B MoE
- **Command**: `ollama run glm-5:cloud`
- **Architecture**: MoE, 744B total / 40B active
- **Context**: 128K+
- **Chinese**: Native Chinese, supports English + Chinese
- **Key scores**: AIME 2026 **92.7%**, GPQA-Diamond **86.0%**, SWE-bench Multilingual **73.3%**
- **Note**: Superseded by GLM-5.1 for most use cases

#### DeepSeek-V3.2 — Solid General Model
- **Command**: `ollama run deepseek-v3.2:cloud`
- **Context**: 160K
- **Cloud usage**: High
- **Chinese**: Strong (DeepSeek is Chinese company)
- **Note**: Pre-V4; good but V4-Flash offers 1M context at lower usage cost

#### MiniMax M3 — 1M Context + Multimodal
- **Command**: `ollama run minimax-m3:cloud`
- **Context**: 512K guaranteed, up to 1M
- **Cloud usage**: High
- **Chinese**: MiniMax is Chinese company, strong Chinese
- **Multimodal**: Yes (native vision)
- **BrowseComp**: 83.5 (beats Claude Opus 4.7)
- **US-based hosting, zero data retention**

#### Kimi K2.6 — Moonshot's Agentic Model
- **Command**: `ollama run kimi-k2.6:cloud`
- **Architecture**: MoE, 1.04T total params (!)
- **Context**: 256K
- **Cloud usage**: High
- **Chinese**: Moonshot AI is Chinese company, strong Chinese
- **Multimodal**: Yes (native vision)
- **Agent swarm**: Up to 300 sub-agents, 4000 coordinated steps

### Tier 3: Good Chinese (also available locally)

| Model | Command | Size | Context | Chinese | Cloud? |
|---|---|---|---|---|---|
| Qwen3-32B | `ollama run qwen3:32b` | 32B | 128K | ★★★★★ | ✅ |
| Qwen3-14B | `ollama run qwen3:14b` | 14B | 128K | ★★★★☆ | ✅ |
| Qwen3-8B | `ollama run qwen3:8b` | 8B | 128K | ★★★★☆ | ✅ |
| Qwen3-30B-A3B | `ollama run qwen3:30b` | 30B/3B active | 128K | ★★★☆☆ | ✅ |
| DeepSeek-R1-32B | `ollama run deepseek-r1:32b` | 32B | 128K | ★★★★☆ | ✅ |
| GLM4-9B | `ollama run glm4:9b` | 9B | 128K | ★★★★☆ | ✅ |

### ❌ Not Recommended for Chinese

| Model | Why |
|---|---|
| **Llama4 Scout/Maverick** | Chinese NOT in 12 supported languages. Weak Chinese benchmarks. |
| **Gemma 4** | Google model; English-first, weak Chinese. |
| **Nemotron 3** | NVIDIA; English-focused. |
| **Devstral** | Mistral; weak Chinese. |

---

## Chinese Benchmark Comparison

### C-Eval (Chinese evaluation, higher = better)

| Model | C-Eval |
|---|---|
| K2.5-1T-A32B | 94.0 |
| Qwen3-Max-Thinking | 93.7 |
| Gemini-3 Pro | 93.4 |
| Qwen3.5-397B-A17B | 93.0 |
| Claude 4.5 Opus | 92.2 |
| GPT-5.2 | 90.5 |

*Note: C-Eval scores above are from Qwen3.5's official comparison table. Local/cloud Qwen3.5-122B is the smaller sibling of the 397B cloud-only model.*

### Chinese-SimpleQA (from DeepSeek-V4 benchmarks)

| Model | Non-Think | High Thinking | Max Thinking |
|---|---|---|---|
| DeepSeek-V4-Pro | 75.8 | 77.7 | **84.4** |
| DeepSeek-V4-Flash | 71.5 | 73.2 | 78.9 |

### Community Consensus Rankings (Chinese Quality)

1. **Qwen3.5** — Best Chinese among all models, including closed-source
2. **DeepSeek V4** — Very strong, especially with thinking modes
3. **GLM-5/5.1** — Native Chinese (Tsinghua), strong for Chinese coding tasks
4. **Qwen3** — Previous gen, still excellent Chinese
5. **DeepSeek V3.2** — Solid but overshadowed by V4
6. **MiniMax M3** — Strong Chinese, unique 1M context
7. **Kimi K2.6** — Moonshot's Chinese-native agentic model
8. **Llama 4** — Weak Chinese despite 200-lang pretraining

---

## Recommendations by Use Case

### 🎯 Best Chinese Overall
**Qwen3.5-122B** — Highest Chinese benchmarks, multimodal, 201 languages, thinking mode. Run: `ollama run qwen3.5:122b`

### 📚 Long Chinese Documents (1M context)
**DeepSeek-V4-Flash** — 1M tokens context at only medium usage tier. Unbeatable for processing long Chinese PDFs, books, codebases. Run: `ollama run deepseek-v4-flash:cloud`

### 🧠 Hardest Chinese Reasoning
**DeepSeek-V4-Pro** — Chinese-SimpleQA 84.4 (max thinking), but burns usage fast. Run: `ollama run deepseek-v4-pro:cloud`

### 💻 Chinese + Coding/Agents
**GLM-5.1** — Tsinghua's flagship for agentic engineering, native Chinese. Run: `ollama run glm-5.1:cloud`

### 🖼️ Chinese + Vision (image understanding)
**Qwen3.5-122B** — Native multimodal with best Chinese quality. Run: `ollama run qwen3.5:122b`

### 💰 Best Value (medium usage tier)
**DeepSeek-V4-Flash** — 1M context + strong Chinese at the cheapest cloud tier for this quality class. Run: `ollama run deepseek-v4-flash:cloud`

### 🏠 Also Runs Locally on 64GB M1 Max
**Qwen3-32B** — Best Chinese model that also runs locally. Use cloud when you need it fast, local when offline. Run: `ollama run qwen3:32b`

---

## Quick Start Commands

```bash
# Best Chinese overall (cloud)
ollama run qwen3.5:122b

# Best value + 1M context (cloud)
ollama run deepseek-v4-flash:cloud

# Maximum reasoning (cloud, expensive)
ollama run deepseek-v4-pro:cloud

# Chinese + coding agents (cloud)
ollama run glm-5.1:cloud

# Qwen3 flagship (cloud)
ollama run qwen3:235b

# GLM-5 744B MoE (cloud)
ollama run glm-5:cloud

# 1M context + multimodal (cloud)
ollama run minimax-m3:cloud

# Moonshot Chinese agentic (cloud)
ollama run kimi-k2.6:cloud

# Also runs locally on 64GB M1 Max
ollama run qwen3:32b
ollama run qwen3:14b
ollama run deepseek-r1:32b
ollama run glm4:9b
```

---

## Key Takeaways

1. **Qwen3.5-122B is the best Chinese model on Ollama Cloud** — C-Eval 93.0, 201 languages, multimodal, thinking mode, MoE architecture
2. **DeepSeek-V4-Flash is the best value** — 1M context window at medium usage tier, Chinese-SimpleQA 78.9
3. **DeepSeek-V4-Pro has the highest Chinese QA score** — 84.4 on Chinese-SimpleQA, but extra heavy usage
4. **GLM-5.1 is the best Chinese+coding agent** — Tsinghua's native Chinese model, excels at long agentic sessions
5. **There are now 4 Chinese-native model families on Ollama Cloud**: Qwen3.5, DeepSeek V4, GLM-5.x, and MiniMax M3/Kimi K2.6
6. **Llama 4 is still not recommended for Chinese** — Chinese not in supported languages
7. **Qwen3-235B is available but overshadowed by Qwen3.5-122B** — newer generation at lower usage cost

---

*Research date: June 7, 2026. Model availability, pricing, and benchmarks may have changed.*