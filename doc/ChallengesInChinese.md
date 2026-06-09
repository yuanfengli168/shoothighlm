# 中文 PDF / 中文 LLM 实战踩坑记录 (Challenges in Chinese)

> 2026-06-09 真实跑中文 PDF 遇到的问题及解决方案。后续若有新发现
> 持续追加。

---

## 1. `sqlite-vec` 加载失败：`sqlite3.OperationalError: not authorized`

**症状：** 在 Python 3.13 / macOS 上首次运行 `shoot-high index`：

```
File "vectorstore.py", line 27, in __init__
    sqlite_vec.load(self.conn)
sqlite3.OperationalError: not authorized
```

**根因：** SQLite ≥ 3.41 强制要求每个连接**显式**调用
`conn.enable_load_extension(True)`，然后才能 `load_extension()`。Python
3.13 自带 SQLite 3.53.1，触发了这个新安全策略。

**修复（已 commit `7ce28a5`）：**

```python
self.conn = sqlite3.connect(str(db_path))
self.conn.enable_load_extension(True)   # ← 这一行是新加的
sqlite_vec.load(self.conn)
```

**教训：** 不要假设 `load_extension` 默认开启——这是 SQLite 的安全
默认值，跟 Python 版本绑得很紧。

---

## 2. Docling OCR 极慢：1,221 页 PDF 跑 10+ 小时

**症状：** 用默认的 `docling` 后端跑 `shoot-high index`，进度卡在
"Processing: dao-sheng-he-fu.pdf" 不动。看了日志发现
`RapidOCR` 在用 CPU 加载 3 个 PyTorch 模型（det / cls / rec），然后
逐页 OCR。

**估算：** 30-90 秒/页 × 1,221 页 = **10-30 小时**。

**根因：** Docling 的默认 OCR 流水线是 CPU 跑的，对 Apple Silicon
也没用 Metal 加速。

**修复（已 commit `7ce28a5`）：** 把 PDF 后端默认从 `docling` 改成
`pypdf`，跑完同样 1,221 页只用了 **几秒**。

**判断标准：** 先用 `python3 -c "from pypdf import PdfReader; ..."` 测试
能否提取文本。如果能，就不需要 OCR。扫描版 PDF 才用：

```bash
SHOOTHIGHLM_PDF_BACKEND=docling shoot-high index ~/books
```

---

## 3. bge-m3 报 500：`the input length exceeds the context length`

**症状：** 索引跑前几个 chunk 就失败：

```
httpcore.ReadTimeout
httpx.HTTPStatusError: 500 Internal Server Error
  "error": "the input length exceeds the context length"
```

**根因：** bge-m3 的 context 是 8,192 tokens。但**中文 tokenize
非常低效**（BERT-style tokenizer 对中文基本是 1 char ≈ 1.5-2 token）。
我们的 chunk size 是 4,096 chars，密集中文段落直接撑爆 8K token 限制。

**修复（已 commit `7ce28a5`）：**

1. Embedder 加 model-aware char budget：
   ```python
   _MAX_CHARS_BY_MODEL = {
       "bge-m3": 6_000,         # 8192 tokens; dense Chinese is unsafe above ~6K chars
       "qwen3-embedding": 28_000,
   }
   ```
2. 用户配置把 `chunk_size` 从 4096 → **2000**（更安全）
3. 智能截断——在句号 / 句边界处切，而不是硬切

**教训：** 中文 LLM 上下文的实际可用字符数 ≈ 英文的 50-65%。估算
时必须打折。

---

## 4. `shoot-high index` 只索引了 1 个 chunk

**症状：** 跑完 `shoot-high index` 后 `vectors.db` 里有 254 个
chunk，但 `shoot-high mindmap` 仍然报错说找不到内容。

**根因：** `cli.py:index` 里这段代码：

```python
text_gen = parse_pdf(pdf)
text = next(text_gen, "")   # ← 只取第一个 yielded page！
```

只读了 PDF 的第 1 页。其余 1,220 页被丢掉，4 个 chunk 全来自那 1 页。

**修复（已 commit `7ce28a5` + `ee557cc`）：**

```python
all_text = "\n\n".join(page_text for page_text in parse_pdf(pdf) if page_text)
```

**教训：** 用 `next(generator, default)` 时，**永远是临时的方案**。
当默认是"读第一项"时，几乎一定意味着你漏读了剩下的。

---

## 5. RAG chat 总返回 "couldn't find relevant information"

**症状：** 索引成功后，`shoot-high chat` 总说找不到。

**根因：** 默认 `min_similarity=0.7`。但 bge-m3 + 中文文本的实测
最大 cosine similarity 约 **0.65**——0.7 把所有结果都过滤掉了。

**修复（已 commit `7ce28a5`）：** 把用户配置改成
`min_similarity: 0.5`。

**教训：** "合理"的相似度阈值高度依赖 embedding 模型 + 语种。
中文 bge-m3 应该用 0.4-0.55，英文 text-embedding-3 才会用 0.7+。

---

## 6. `shoot-high mindmap` 撞 120s HTTP 超时

**症状：** 跑 mindmap，60-120 秒后：

```
httpcore.ReadTimeout: timed out
```

**根因：** 默认 120s 超时，但 `qwen3.5:cloud` 在 12K-50K char prompt
+ thinking mode 下需要 50-100 秒（cold start 更久）。

**修复（已 commit `ee557cc`）：** 把所有 7 个 LLM client 的 timeout
从 120s 提到 **600s**。本地 `qwen3.5:27b` 跑 50K prompt 大概要 10+ 分钟，
所以 600s 也不算多。

**教训：** 对带 thinking mode 的模型，**120s 远远不够**。宁可设置
过大超时再调小，不要让用户看到莫名其妙的 timeout。

---

## 7. 用户配置被测试污染

**症状：** 跑 `pytest tests/test_config.py` 失败：

```
assert 2000 == 4096
+  where 2000 = get('rag', 'chunk_size')
```

**根因：** `Config()` 无参数时读 `~/.shoothighlm/config.yaml`。
用户已经在那个文件里设了 `chunk_size: 2000`（我们刚做调优时改的），
测试就以为默认值是 2000 了。

**修复（已 commit `ee557cc`）：** 所有 "默认值"测试改用
`Config(_NONEXISTENT)` 路径，确保读到的是代码里的 `_get_defaults()`。

**教训：** 测试用 singleton（无参 `Config()`）很容易被环境配置
污染。要么用 temp config 路径，要么显式 monkey-patch `HOME` /
`XDG_CONFIG_HOME`。

---

## 共同模式：中文 LLM 应用的 4 个隐性坑

1. **Token 预算打 5 折** — 中文 tokenize 比英文贵 1.5-2x
2. **相似度阈值降低** — bge-m3 中文场景 0.4-0.55 是合理值
3. **超时设大不设小** — thinking mode + cloud 冷启动都要时间
4. **truncate 要在句边界** — 不要硬切中文，会破坏语义

---

## 待补充

- [ ] Playwright 在 Apple Silicon 上的 PNG 渲染稳定性
- [ ] Fish Audio S2 在 TTS 长段（>30 分钟）时的稳定性
- [ ] `--full` 50K prompt 在不同模型上的实际效果对比
- [ ] OpenRouter 接入测试
