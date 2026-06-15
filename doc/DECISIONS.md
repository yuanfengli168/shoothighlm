# 书海LM (shootHighLM) — Project Decisions

> 中文优先的多LLM NotebookLM CLI 替代品，不绑定单一提供商

## Vision

CLI tool replicating Google NotebookLM's core features, multi-LLM, Chinese-first.
Drop PDFs in a folder, run commands, get output files.

## Key Differentiators vs NotebookLM

1. **中文优先** — NotebookLM 被批评美式文化扁平化，我们专注中文体验
2. **CLI only, no frontend** — 终端原生，开发者友好
3. **Multi-LLM** — 支持 Ollama / OpenAI / Anthropic / Google 等多LLM接入，不绑定单一提供商
4. **用户自选模型** — chat model / vision model / embedding model / TTS 都可配置
5. **单文件夹工作流** — 所有文件放入一个目录，执行命令返回结果文件

## 项目规范

- **语言**: 英文（命令、提示、文档）
- **技术栈**: Python（RAG/ML生态成熟，同NotebookLM后端选择）
- **开源协议**: Apache 2.0（商业友好，含专利保护）
- **配置路径**: `~/.shoothighlm/config.yaml`
- **思维导图输出**: 双输出 — TUI交互版（终端键盘导航+AI对话）+ HTML交互版（浏览器mermaid.js渲染，可点击）

## 技术栈

### LLM 选型

| 用途 | 默认方案 | 备选 | 本地/云 |
|------|---------|------|--------|
- **glm-5.1:cloud**: 清华/Z.ai 原生中文，最强中文推理能力 — 备选（纯文本，无视觉）
| Chat LLM | qwen3.5:cloud | glm-5.1:cloud, deepseek-v4-flash:cloud | 云优先 |
| Chat 本地兜底 | qwen3.5:27b | qwen3:32b | 本地 |
| Vision | qwen3.5:cloud | minimax-m3:cloud (1M上下文) | 云优先 |
| Vision 本地兜底 | qwen3.5:27b | — | 本地 |
| Embedding | bge-m3 (568M, ~2.2GB) | qwen3-embedding:8b | 本地 |
| 向量库 | sqlite-vec | ChromaDB | 本地 |

- **qwen3.5:cloud**: 阿里通义，多模态，256K上下文，中文OCR最强 — **默认首选**
- **glm-5.1:cloud**: 清华/Z.ai 原生中文，最强中文推理能力 — 备选（纯文本，无视觉）
- **deepseek-v4-flash:cloud**: 1M上下文，中等用量（更便宜）— 超长文档场景
- **bge-m3**: BAAI/FlagOpen，MIRACL 中文检索第一，支持 dense+sparse+multi-vector
- **Embedding 无云版本** — Ollama Cloud 不提供 embedding，只能本地跑
- **Ollama Cloud 用法**: 同一CLI，模型名加 `:cloud` 后缀，如 `ollama run qwen3.5:cloud`

### 信息图

| 用途 | 方案 | 成本 | 状态 |
|------|------|------|------|
| 默认信息图 | HTML/CSS 模板 + Playwright → PNG | 免费 | ✅ 已实现（`shoot-high infographic`） |
| 装饰/封面图 | FLUX.2 Flex via Replicate | ~$0.03-0.05/张 | ⏳ 待做（需 Replicate API key） |
| 中文图片 | Seedream (字节) via Replicate | 按量 | ⏳ 待做 |

- AI 生图中文文字渲染仍弱，结构化信息图用 HTML/CSS 更好
- **3 个内置模板**：`summary_card`（标题+摘要+主题）、`topic_hierarchy`（主题树）、`stats_card`（数据卡片）
- **CJK 字体兜底**：PingFang SC, Microsoft YaHei, Noto Sans CJK SC — 跨平台中文渲染稳定
- **PNG 渲染**：Playwright 优先；如未安装 `chromium`，自动 fallback 到 `/usr/bin/google-chrome` / `chromium` / `chromium-browser`

### TTS / 播客

| 用途 | 方案 | 成本 | 状态 |
|------|------|------|------|
| 默认中文 TTS | Fish Audio S2 API | 免费额度+按量 | ✅ 已实现 |
| 备选 | 阿里云 CosyVoice | ¥0.01-0.04/千次 | 🚧 Stub（接口未完成） |
| 双人播客 | LLM 写对话脚本 → 两声音分别生成 → 拼接 | 同上 | ✅ 已实现（`shoot-high synthesize`） |

- TTS 输出格式：WAV（pure-stdlib 拼接，无 ffmpeg/pydub 依赖）
- 静音间隔：默认 0.4 秒（可通过 `--pause` 调整）
- API Key 配置：`FISH_AUDIO_API_KEY` 环境变量或 `~/.shoothighlm/config.yaml`

### 思维导图

- ✅ **LLM 提取** — 从 PDF 自动提取层级结构
- ✅ **导出格式** — Markdown (首选), OPML, HTML (Markmap), JSON
- ✅ **CLI 命令** — `shoot-high mindmap ./notebook --format <format>`
- 🚧 **TUI 交互** — 键盘导航树 + 分屏对话（待实现）
- **蓝海功能** — 无开源工具在 CLI 做此交互 (详见 blueOcean.md)

### 笔记本引导（Notebook Guides）

- ✅ **已实现** — `shoot-high guide ./notebook`
- 自动生成：2-3 段摘要 + 5-8 关键主题 + 5 建议问题
- 支持自定义问题数量（`--questions`）
- 导出格式：Markdown / JSON
- 跨所有 PDF 综合分析（不是单文件）

### 思维导图导出格式

| 格式 | 角色 | 说明 | 兼容软件 |
|------|------|------|---------|
| **Markdown** | **首选** | 人可读、可编辑、Git友好，不装软件也有价值 | Obsidian, XMind, MindNode, SimpleMind, iThoughts |
| OPML | 次选 | 思维导图界"CSV"，7/8工具可导入 | XMind, MindManager, MindNode, FreeMind, MindMaster, SimpleMind, iThoughts |
| FreeMind (.mm) | 三选 | 遗留但广泛支持的交换格式 | XMind, Freeplane, MindMaster, SimpleMind, iThoughts |
| HTML (Markmap) | 渲染 | 浏览器交互预览，可点击展开 | 任何浏览器 |
| JSON | 内部 | 编程用结构化数据 | 开发者 |
| XMind (.xmind) | 后续 | ZIP+JSON，生成复杂度高 | XMind, iThoughts |
| MindManager (.mmap) | ❌ 跳过 | 私有格式，无法正确生成 | — |

- **首选 Markdown** — 即使不用思维导图软件，它本身就是有价值的读书笔记
- OPML 自动随 Markdown 一起生成（不额外费事）
- HTML Markmap 版提供即时可视化

## 功能优先级

| 优先级 | 功能 | 难度 | 状态 |
|--------|------|------|------|
| P0 | RAG 聊天 + 引用 | 中 | ✅ Phase 1 完成 |
| P0 | PDF 源管理 | 中 | ✅ Phase 1 完成 |
| P1 | 思维导图（LLM 提取 + 导出） | 中 | ✅ Phase 2 完成（TUI 交互待做） |
| P1 | 闪卡/测验 | 低 | ✅ Phase 2 完成 |
| P2 | 笔记本引导问题 | 低 | ✅ Phase 3 完成（`shoot-high guide`） |
| P2 | 播客生成（脚本） | 中 | ✅ Phase 3 完成 |
| P2 | 播客生成（TTS 音频） | 高 | ✅ Phase 3 完成（`shoot-high synthesize`） |
| P3 | 信息图 (HTML + PNG) | 中 | ✅ Phase 3 完成（`shoot-high infographic`） |
| P3 | 数据表格 | 中 | ✅ Phase 3 完成（`shoot-high tables`） |
| P4 | 视频概述 | 很高 | ❌ 跳过 |
| P4 | 幻灯片 | 高 | ❌ 跳过 |

## 硬限制与能力边界

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 单文件大小 | 50MB | PDF太大解析慢 |
| 文件夹总大小 | 500MB | 避免embedding时间过长 |
| 文件数量 | 50个 | 超过影响检索质量 |
| 总token上限 | 500K tokens | 超过需分批处理 |

### 各模型能力边界与注意事项

| 模型 | 上下文 | 已知限制 | 注意事项 |
|------|--------|---------|---------|
| **qwen3.5:cloud** (默认chat) | 256K tokens | 多模态（文字+图片），中文OCR强 | 超过256K需分批；用量中等 |
| **qwen3.5:27b** (本地兜底) | 256K tokens | 本地跑，中文+视觉 | M1 Max 64GB可用，但长上下文会吃内存，建议<128K |
| **glm-5.1:cloud** (备选chat) | 未知(估计128K+) | 中文推理极强，纯文本 | 无视觉能力，PDF需先提取文字；用量高 |
- **glm-5.1:cloud**: 清华/Z.ai 原生中文，最强中文推理能力 — 备选（纯文本，无视觉）
| **deepseek-v4-flash:cloud** (便宜版) | 1M tokens | 超长上下文，推理强 | 用量低（便宜），适合超长文档场景 |
| **qwen3.5:cloud** (默认vision) | 256K tokens | 中文OCR最强 | 同chat模型，双用途 |
| **minimax-m3:cloud** (长文档) | 1M (512K保底) | 超长文档/视频 | 用量高，按需启用 |
| **bge-m3** (embedding) | 8192 tokens/chunk | dense+sparse+colbert | 单chunk限8192，长文档需切分；chunk间重叠200 tokens |

### 测试验证清单（待完成）
- [ ] qwen3.5:cloud 中文长文档问答质量测试
- [ ] qwen3.5:cloud PDF OCR 中文准确率测试
- [ ] bge-m3 中文embedding检索召回率测试
- [ ] 各模型实际token消耗与用量统计
- [ ] 单文件50MB / 总500MB 压力测试

## 云优先原则

- 能用云端 API 就用云端（Ollama Cloud, Replicate, Fish Audio）
- 只有云端太贵或不可用时才走本地
- 本地能力有限，不做超出 M1 Max 能力的事

## Status

### 已完成 ✅
- [x] NotebookLM 功能研究
- [x] 技术选型研究
- [x] 中文 LLM 对比
- [x] TTS/API 可行性
- [x] 思维导图蓝海分析
- [x] 架构设计文档
- [x] Phase 1 — RAG 聊天 + PDF 源管理
- [x] Phase 2 — 思维导图提取 + 闪卡
- [x] Phase 3 — 播客脚本 + TTS 音频合成 + 笔记本引导
- [x] Phase 3 P3 — 信息图生成（3 模板 + HTML/PNG 输出）
- [x] Phase 3 P3 — 数据表格提取（Markdown / CSV / JSON / HTML 输出）
- [x] CI 覆盖门 + GitHub Actions workflow（239 测试，95% 覆盖）

### 待完成 ⏳
- [ ] 思维导图 TUI 交互（蓝海功能）
- [ ] LLM 排名榜
- [ ] Codecov 集成（已上传但 token 未配）

### 测试验证清单（待完成）
- [ ] qwen3.5:cloud 中文长文档问答质量测试
- [ ] qwen3.5:cloud PDF OCR 中文准确率测试
- [ ] bge-m3 中文embedding检索召回率测试
- [ ] 各模型实际token消耗与用量统计
- [ ] 单文件50MB / 总500MB 压力测试
- [ ] Fish Audio S2 真实端到端测试（需 API key）
## 云端优先、本地兜底策略（Cloud-Primary, Local-Fallback）

> 更新于 2026-06-09（伴随 commit `5d9eb84`）

**规则：云端是默认 chat 模型；本地是用户显式 opt-in 的兜底。**

### 模型解析顺序（`cli.py:resolve_chat_model`）

1. `--model <name>` CLI 标志（用户显式覆盖，永远赢）
2. `--use-local` CLI 标志 → 使用 `models.chat_local`
3. `SHOOTHIGHLM_CHAT` 环境变量
4. 配置文件中的 `models.chat`（默认：`qwen3.5:cloud`）

### 用户切换到本地的 3 种方式

```bash
# 1. 一次性（仅本次命令）
shoot-high mindmap ~/my-books --use-local

# 2. 一次性（任意模型名）
shoot-high mindmap ~/my-books --model qwen3.5:27b
shoot-high mindmap ~/my-books --model minimax-m3:cloud

# 3. 整个会话
SHOOTHIGHLM_CHAT=qwen3.5:27b shoot-high mindmap ~/my-books
```

### 为什么不自动 fallback

我们**故意不做**自动 fallback 到本地的原因：

- **可见性**：用户应该明确知道正在使用哪个模型（影响成本、质量、隐私）
- **成本意识**：云端按 token 计费；自动 fallback 可能让用户意外消耗
- **隐私**：本地 = 数据不出机器；云端 = 数据发到 Ollama 服务器
- **质量预期**：qwen3.5:cloud > qwen3.5:27b（cloud 是前沿模型）

### 错误处理

云端不可达时（超时 / 5xx / 连接错误），命令打印：

```
✗ Cloud LLM error: <错误信息>
Tip: Cloud LLM is unreachable. To switch to the local model:
  - run with --use-local
  - set SHOOTHIGHLM_CHAT=<model>
  - edit ~/.shoothighlm/config.yaml
```

`_is_cloud_error(exc)` 只匹配超时、连接错误、5xx HTTP——**不会**把正常的 LLM 解析错误（JSON 格式不对等）误报为云端故障，避免误导用户。

## 提示采样策略

> **状态**：当前是 `text[:12000]`（粗暴取前 12K），**计划改进**为分层采样

### 现状

所有 6 个 LLM-using 模块（mindmap / flashcard / podcast / guide / infographic / tables）默认 `max_chars = 12000`。对一本 1,200 页的书，这意味着：

- 只看了**前 30-40 页**
- 主要覆盖：扉页、版权页、目录
- 错过：结论、跨章节论证、6 本合集中的后 5 本

### `--full` 标志（已实现）

所有 6 个命令加上了 `--full`，使用 50K 字符（约 12-15K tokens）：

```bash
shoot-high mindmap ~/my-books --full    # 4x 慢，但覆盖更多
```

适合：精读、对质量要求高的场景。默认 `12K` 适合：日常探索、速度优先。

### 计划改进（见 `doc/Todo.md` §1）

- **分层采样**：从开头 / 中间 / 结尾各取 4K → 覆盖整本书
- **基于 embedding 的多样性采样**：从 sqlite-vec 选 top-N chunks（按与全书中心向量的距离）
- **层级摘要**：chunk → 摘要 → 摘要的摘要（保真度最高，最慢）

## PDF 后端策略

> **状态**：默认 `pypdf`（快速文本层），可通过 `SHOOTHIGHLM_PDF_BACKEND=docling` 切换到 OCR

### 决策变化（2026-06-09）

之前默认 `docling`（OCR + RapidOCR + PyTorch），在 1,221 页的《道生合符》上需要 10+ 小时。改成 `pypdf` 后：

- 文本层 PDF（大多数电子书）：**秒级**完成
- 扫描 PDF（无文本层）：pypdf 提取 0 字符 → 需要 `docling`

### 用户切换

```bash
# 默认（快，但需要 PDF 有文本层）
shoot-high index ~/my-books

# 扫描 / 影印版 PDF
SHOOTHIGHLM_PDF_BACKEND=docling shoot-high index ~/my-books
```

## 测试覆盖

| 时点 | 覆盖率 | 备注 |
|---|---|---|
| 2026-06-07 (Phase 3 完) | 95% | 239 tests |
| 2026-06-09 (新增 `--use-local`/`--model` 后) | 89% | 新增 2 个 helper 未直接测试 |
| 2026-06-09 (helper 单元测试 + 边界覆盖后) | 94.23% ✅ | 302 tests，覆盖 5 个新文件、64 个新测试 |
| 2026-06-15 (LLM call centralization + token logs) | 94.39% ✅ | 371 tests，新增 `tests/test_llm.py` (6) 和 `tests/test_token_log.py` (5) |
| 2026-06-15 (batch 自动化) | 94.06% ✅ | 403 tests，新增 `tests/test_batch.py` (32) |
| 2026-06-15 (mindmap 确定性 + 第N章 verbatim) | **93.81%** ✅ | 411 tests，新增 7 个 `_detect_chapters` 测试 + 1 个 `call_ollama` 确定性测试 |

`test_cli_helpers.py`、`test_use_full_flag.py`、`test_pdf_embedding_edges.py`、
`test_cli_cloud_errors.py`、`test_cli_generator_errors.py` 共 64 个新测试。
