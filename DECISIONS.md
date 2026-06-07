# 书海LM (shootHighLM) — Project Decisions

> 中文优先的本地+云混合 NotebookLM CLI 替代品

## Vision

CLI 工具，复刻 Google NotebookLM 核心功能，Ollama 驱动，中文优先。
放 PDF 进文件夹，跑命令，出结果文件。

## Key Differentiators vs NotebookLM

1. **中文优先** — NotebookLM 被批评美式文化扁平化，我们专注中文体验
2. **CLI only, no frontend** — 终端原生，开发者友好
3. **Local-first + Cloud 混合** — Ollama 本地 + 按需云端 API
4. **用户自选模型** — chat model / embedding model / TTS 都可配置
5. **单文件夹工作流** — 所有文件放入一个目录，执行命令返回结果文件

## 技术栈

### LLM 选型

| 用途 | 默认方案 | 备选 | 本地/云 |
|------|---------|------|--------|
| Chat LLM | qwen3.5:cloud | glm-5.1:cloud, deepseek-v4-flash:cloud | 云优先 |
| Chat 本地兜底 | qwen3.5:27b | qwen3:32b | 本地 |
| Vision | qwen3.5:cloud | minimax-m3:cloud (1M上下文) | 云优先 |
| Vision 本地兜底 | qwen3.5:27b | — | 本地 |
| Embedding | bge-m3 (568M, ~2.2GB) | qwen3-embedding:8b | 本地 |
| 向量库 | sqlite-vec | ChromaDB | 本地 |

- **glm-5.1**: 清华/Z.ai 原生中文，最强中文推理能力
- **qwen3.5:cloud**: 阿里通义，多模态，256K上下文，中文OCR最强
- **deepseek-v4-flash:cloud**: 1M上下文，中等用量（更便宜）
- **bge-m3**: BAAI/FlagOpen，MIRACL 中文检索第一，支持 dense+sparse+multi-vector
- **Embedding 无云版本** — Ollama Cloud 不提供 embedding，只能本地跑
- **Ollama Cloud 用法**: 同一CLI，模型名加 `:cloud` 后缀，如 `ollama run glm-5.1:cloud`

### 信息图

| 用途 | 方案 | 成本 |
|------|------|------|
| 默认信息图 | HTML/CSS 模板 + Puppeteer → PNG | 免费 |
| 装饰/封面图 | FLUX.2 Flex via Replicate | ~$0.03-0.05/张 |
| 中文图片 | Seedream (字节) via Replicate | 按量 |

- AI 生图中文文字渲染仍弱，结构化信息图用 HTML/CSS 更好

### TTS / 播客

| 用途 | 方案 | 成本 |
|------|------|------|
| 默认中文 TTS | Fish Audio S2 API | 免费额度+按量 |
| 备选 | 阿里云 CosyVoice | ¥0.01-0.04/千次 |
| 双人播客 | LLM 写对话脚本 → 两声音分别生成 → 拼接 | 同上 |

### 思维导图

- 自建 TUI (Textual/Ink)
- 键盘导航树形结构 + 回车探索节点 + 分屏 AI 对话
- **蓝海功能** — 无开源工具在 CLI 做此交互 (详见 blueOcean.md)

## 功能优先级

| 优先级 | 功能 | 难度 | 方案 |
|--------|------|------|------|
| P0 | RAG 聊天 + 引用 | 中 | Ollama + bge-m3 + sqlite-vec |
| P0 | PDF 源管理 | 中 | docling/marker 解析 → chunk → embed |
| P1 | 交互式思维导图 | 中 | LLM 提取实体关系 → TUI 树 + 分屏对话 |
| P1 | 闪卡/测验 | 低 | 纯 LLM prompt |
| P2 | 播客生成 | 高 | LLM 脚本 + Fish Audio 双声音 |
| P2 | 笔记本引导问题 | 低 | LLM 自动生成 |
| P3 | 信息图 (HTML) | 中 | 模板 + Puppeteer → PNG |
| P3 | 数据表格 | 中 | LLM 提取结构化数据 |
| P4 | 视频概述 | 很高 | 先跳过 |
| P4 | 幻灯片 | 高 | 先跳过 |

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

- [x] NotebookLM 功能研究
- [x] 技术选型研究
- [x] 中文 LLM 对比
- [x] TTS/API 可行性
- [x] 思维导图蓝海分析
- [ ] 架构设计文档
- [ ] 实现（待讨论确认）