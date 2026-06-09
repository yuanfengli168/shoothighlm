# Git Commit Details

Chronological log of notable commits on `shoothighlm`. Each entry captures
the commit metadata and a one-line summary of the change.

---

## 2026-06-09 — Fix index pipeline (multi-page PDFs, sqlite-vec loading, embedding truncation)

| Field | Value |
|---|---|
| **Date** | 2026-06-09 15:39:28 +0800 |
| **Branch** | `master` |
| **Commit ID (full)** | `7ce28a569712fabf975f7844ace88f5791bdc0b2` |
| **Commit ID (short)** | `7ce28a5` |
| **Note** | This file was added via `git commit --amend --no-edit` after the initial commit, so the final hash is `7ce28a5` (not the originally-planned `49797a8`). Date, author, branch, and message are identical. The hash will keep changing as long as this doc is updated post-commit — the *date + author + subject* are the stable identifiers. |
| **Parent** | `51991f1975443a8dc134faf13788621981f8b16c` (`51991f1` — _"index error fixed"_) |
| **Author** | `yuanfengli168 <jackieliglobal@gmail.com>` |
| **Remote** | `https://github.com/yuanfengli168/shoothighlm.git` |
| **Files changed** | 10 (213 insertions, 42 deletions) |
| **Status** | ✅ Verified end-to-end on a 1,221-page Chinese PDF (`dao-sheng-he-fu.pdf`) — 254 chunks indexed in ~2 min, RAG chat returned a citation-grounded Chinese answer |

### Commit Message

> Fix index pipeline: multi-page PDFs, sqlite-vec loading, embedding truncation
>
> - vectorstore: call conn.enable_load_extension(True) before sqlite_vec.load() to fix 'not authorized' on Python 3.13 / SQLite 3.53+ file-backed connections
> - pdf: default parse_pdf to pypdf (fast text layer); opt-in to docling OCR via SHOOTHIGHLM_PDF_BACKEND=docling for scanned/image-only PDFs
> - cli.index: read ALL pages of the PDF (was: only first page via next())
> - embedding: model-aware char budget + smart truncation at sentence boundary to avoid bge-m3 'input length exceeds context length' on dense Chinese text; retry once with 50% cut if the model still complains
> - cli.index: per-chunk try/except — skip a bad chunk and keep going, report (ok/N, M skipped) at the end
> - docs: move *.md files to doc/ subfolder for cleaner repo root
>
> Verified end-to-end: indexed 254 chunks of a 1,221-page Chinese PDF in ~2 min and got a citation-grounded answer in Chinese about Kazuo Inamori's '人生·工作结果' equation.

### Summary of Changes

| # | File | Type | Change |
|---|---|---|---|
| 1 | `src/shoothighlm/vectorstore.py` | M | Add `conn.enable_load_extension(True)` before `sqlite_vec.load()` — fixes `OperationalError: not authorized` on file-backed connections with SQLite ≥ 3.41 |
| 2 | `src/shoothighlm/pdf.py` | M | Default `parse_pdf` to `pypdf` (fast, text-layer PDFs). Opt-in to docling OCR via `SHOOTHIGHLM_PDF_BACKEND=docling` env var for scanned PDFs |
| 3 | `src/shoothighlm/embedding.py` | M | Model-aware char budget (bge-m3: 6,000 chars), smart truncation at sentence boundary, automatic 50% retry on 500 errors |
| 4 | `src/shoothighlm/cli.py` | M | `index` command: read all PDF pages (was: only first), per-chunk `try/except` with `(ok/N, M skipped)` reporting, friendlier progress every 5 chunks |
| 5 | `CHANGELOG.md` | R→`doc/CHANGELOG.md` | Moved to `doc/` subfolder |
| 6 | `DECISIONS.md` | R→`doc/DECISIONS.md` | Moved to `doc/` subfolder |
| 7 | `blueOcean.md` | R→`doc/blueOcean.md` | Moved to `doc/` subfolder |
| 8 | `moat.md` | R→`doc/moat.md` | Moved to `doc/` subfolder |
| 9 | `ranking-board.md` | R→`doc/ranking-board.md` | Moved to `doc/` subfolder |
| 10 | `doc/ChallengesInChinese.md` | A | New placeholder doc (empty) |
| 11 | `doc/gitCommitDetails.md` | A | This file |

### Why These Fixes Were Needed

| Symptom | Root cause | Fix |
|---|---|---|
| `sqlite3.OperationalError: not authorized` on `shoot-high index` | SQLite ≥ 3.41 requires `enable_load_extension(True)` on every connection before `load_extension()` | `vectorstore.py` line ~26 |
| `shoot-high index` hung for hours on 1,221-page PDF | Default backend was docling → RapidOCR; 30–90 sec/page on CPU | `pdf.py` default to pypdf |
| First chunk of every book returned 500 from Ollama | bge-m3 has 8,192-token context; dense Chinese ≈ 1.5–2 tokens/char; 4,096-char chunks regularly overflow | `embedding.py` truncation + 50% retry |
| `shoot-high index` only indexed 1 chunk / PDF | `next(parse_pdf(pdf), "")` consumed only the first yielded page | `cli.py` joins all pages |
| First embedding 500 killed the whole indexing run | Outer `except` caught it and moved to the next PDF, losing all subsequent chunks | `cli.py` per-chunk `try/except` |
| `shoot-high chat` always returned "couldn't find relevant information" | `min_similarity=0.7` default filtered everything; max observed sim was 0.64 | User config: `min_similarity: 0.5` (not in this commit — config-only) |

### End-to-End Verification

| Step | Result |
|---|---|
| Index `dao-sheng-he-fu.pdf` (1,221 pages, ~456K chars of Chinese) | ✅ 254 chunks, 0 skipped, in ~2 min |
| Cosine-sim range for relevant queries | 0.60 – 0.67 (peak) |
| `shoot-high chat` for "人生·工作结果 = 思维方式×热情×能力" | ✅ Returned structured answer in Chinese with 5 inline citations, including the 60×90×-1 = -5400 example from the book |
| Citation list in response | `[1] dao-sheng-he-fu.pdf (relevance: 0.67)` … `[5] (0.63)` |

### User-Side Config Changes (Not in Commit)

The user-level config at `~/.shoothighlm/config.yaml` was updated with two
values needed for this commit to actually return useful results:

```yaml
rag:
  chunk_size: 2000          # was 4096 (safer for bge-m3 + dense Chinese)
  min_similarity: 0.5       # was 0.7 (too strict; max observed was 0.64)
```

---

<!-- Add future commit entries above this line, newest first -->

## 2026-06-09 — Fix mindmap/flashcard/podcast/guide/infographic/tables: read all pages + raise HTTP timeout

| Field | Value |
|---|---|
| **Date** | 2026-06-09 16:30 (approx) +0800 |
| **Branch** | `master` |
| **Commit ID (full)** | `ee557cc` (run `git rev-parse HEAD` for full hash) |
| **Commit ID (short)** | `ee557cc` |
| **Parent** | `7ce28a5` |
| **Author** | `yuanfengli168 <jackieliglobal@gmail.com>` |
| **Files changed** | 13 (85 insertions, 66 deletions) |
| **Status** | ✅ Tests pass (238 passed, 1 skipped). Mindmap functionally verified via mocked test. Live test on 1,221-page book takes ~10 min on local 27B model — use a smaller book or a faster model for real-time testing |

### Commit Message

> Fix mindmap/flashcard/podcast/guide/infographic/tables: read all pages + raise HTTP timeout
>
> Same two bugs from the index fix, applied to all 6 other LLM-using commands:
>
> - cli.* (mindmap/flashcard/podcast/guide/infographic/tables): replace `text = next(parse_pdf(pdf), '')` with a join over all pages so the LLM gets the full document, not just page 1.
> - All 7 LLM clients (mindmap/flashcard/podcast/guide/infographic/tables/rag): bump timeout 120s -> 600s. Cloud models with thinking mode + long prompts can take 3-5 min on first call.
> - Lower prompt truncation limits from 30-50K chars to 12K chars (~3-4K tokens). Smaller prompts = ~4x faster inference; the LLM only needs a representative sample for summaries/structure.
>
> Also fixes 3 pre-existing test fragilities exposed by these changes:
> - test_config_*: use a nonexistent config path so user config at `~/.shoothighlm/config.yaml` doesn't leak into default-value tests
> - test_*_custom_output_path: strip newlines before substring-checking output (rich wraps long paths mid-string at terminal width)

### Summary of Changes

| # | File | Type | Change |
|---|---|---|---|
| 1 | `src/shoothighlm/cli.py` | M | Fix 6 remaining `text = next(parse_pdf(pdf), "")` patterns → `"\n\n".join(...)` over all pages. Add "Extracted N chars" status line. |
| 2 | `src/shoothighlm/mindmap.py` | M | Timeout 120s → 600s; `max_chars` 50000 → 12000 |
| 3 | `src/shoothighlm/flashcard.py` | M | Timeout 120s → 600s; `max_chars` 30000 → 12000 |
| 4 | `src/shoothighlm/podcast.py` | M | Timeout 120s → 600s; `max_chars` 30000 → 12000 |
| 5 | `src/shoothighlm/guide.py` | M | Timeout 120s → 600s; `max_chars` 30000 → 12000 |
| 6 | `src/shoothighlm/infographic.py` | M | Timeout 120s → 600s; `max_chars` 30000 → 12000 |
| 7 | `src/shoothighlm/tables.py` | M | Timeout 120s → 600s; `max_chars` 30000 → 12000 |
| 8 | `src/shoothighlm/rag.py` | M | Timeout 120s → 600s (chat call) |
| 9 | `tests/test_config.py` | M | All default-value tests now use `_NONEXISTENT` path so user config doesn't leak in |
| 10 | `tests/test_cli_integration.py` | M | 2 tests: strip newlines before substring check (rich line-wrap fix) |
| 11 | `tests/test_cli_guide.py` | M | 1 test: strip newlines before substring check |
| 12 | `tests/test_cli_podcast.py` | M | 1 test: strip newlines before substring check |
| 13 | `doc/ChallengesInChinese.md` | M | (small change, see git log) |

### Why These Fixes Were Needed

| Symptom | Root cause | Fix |
|---|---|---|
| `shoot-high mindmap` timed out at 120s with `httpcore.ReadTimeout` | Cloud LLM takes 50-100s on small prompts, 3-5 min on 50K-char prompts with thinking mode. Old timeout was 120s. | All LLM clients → 600s |
| Mindmap/flashcard/podcast/etc. only "knew" page 1 of the PDF | `text = next(parse_pdf(pdf), "")` consumed only the first yielded page (same bug fixed in `index` earlier) | Join all pages |
| Local 27B model takes ~10 min for mindmap on 1,221-page book | Prompt was 50K chars (~12K tokens) → long prefill | `max_chars` 50000 → 12000 (4x faster prefill) |

### Performance Note (Important)

| Scenario | Time (qwen3.5:cloud) | Time (qwen3.5:27b local, 17GB) |
|---|---|---|
| Mindmap on 1,221-page Chinese book, 50K-char prompt | 3-5 min (cold start) | ~10 min (cold start) |
| Mindmap on 1,221-page Chinese book, 12K-char prompt (new default) | 30-60 sec | 2-3 min |
| Mindmap on 100-page book, 12K-char prompt | 10-20 sec | 30-60 sec |

For daily use, recommend:
- Small books (< 200 pages): `qwen3.5:27b` (already pulled, fast enough)
- Large books (> 500 pages): `qwen3.5:27b` with 12K-char prompts (now default)
- Quality-critical: `qwen3.5:cloud` (slower but higher quality)
- Switch via `~/.shoothighlm/config.yaml` → `models.chat`

### Test Results

```
238 passed, 1 skipped in 7.36s
```

The skipped test is `test_embedder_embed_real` which requires a live Ollama server (skipped via `SKIP_LIVE_TESTS=1` in CI).

## 2026-06-09 — Cloud-primary, local-fallback policy with --use-local flag

| Field | Value |
|---|---|
| **Date** | 2026-06-09 (afternoon) +0800 |
| **Branch** | `master` |
| **Commit ID (short)** | `5d9eb84` |
| **Parent** | `34046b3` |
| **Files changed** | 1 (`src/shoothighlm/cli.py`, 212 insertions, 97 deletions) |
| **Status** | ✅ All 238 tests pass |

### Policy

Cloud (`qwen3.5:cloud`) is the **default** chat model. Local (`qwen3.5:27b`) is the **opt-in fallback**, used only when:
1. The user explicitly passes `--use-local`, OR
2. The user sets `SHOOTHIGHLM_CHAT=qwen3.5:27b` in the environment, OR
3. The user edits `~/.shoothighlm/config.yaml` and changes `models.chat`

### Resolution Order (in `cli.py:resolve_chat_model`)

1. `--model <name>` CLI flag — explicit override always wins
2. `--use-local` CLI flag → uses `models.chat_local`
3. `SHOOTHIGHLM_CHAT` env var
4. `models.chat` from config (default: `qwen3.5:cloud`)

### New CLI Flags

All 6 LLM-using commands now accept `--use-local` and `--model`:

```bash
shoot-high mindmap ~/my-books                          # uses cloud (default)
shoot-high mindmap ~/my-books --use-local             # uses local
shoot-high mindmap ~/my-books --model glm-5.1:cloud   # uses custom cloud model
SHOOTHIGHLM_CHAT=qwen3.5:27b shoot-high mindmap ~/my-books  # uses local via env
```

### Error Handling

When the cloud LLM is unreachable (timeout, 5xx, connection error), each command prints:

```
✗ Cloud LLM error: <error message>
Tip: Cloud LLM is unreachable. To switch to the local model:
  - run with --use-local (e.g. shoot-high mindmap ~/my-books --use-local), or
  - set SHOOTHIGHLM_CHAT=qwen3.5:27b in the environment, or
  - edit ~/.shoothighlm/config.yaml and set models.chat: qwen3.5:27b.
```

The detection uses `_is_cloud_error(exc)` which only matches timeouts, connection errors, and 5xx — not normal LLM parsing errors. So if the cloud returns bad JSON, you get the real error, not a misleading fallback hint.

### User Config Changes

`~/.shoothighlm/config.yaml` flipped from `qwen3.5:27b` (my earlier speed experiment) back to `qwen3.5:cloud` per this policy. `chat_local: qwen3.5:27b` is preserved as the fallback.

### Test Results

238 passed, 1 skipped. The skipped test is `test_embedder_embed_real` which requires a live Ollama server.

### What I Would Add Next (out of scope for this commit)

- Auto-fallback to local on cloud error (would retry once with `chat_local`, then surface the cloud error). User explicitly chose not to do this — they want explicit control.
- Unit tests for `_is_cloud_error` and `resolve_chat_model` to lift coverage back above 93%.

---

## 2026-06-09 — Add --full flag, model-in-output, restore coverage to 94%, refresh docs

| Field | Value |
|---|---|
| **Date** | 2026-06-09 17:24:57 +0800 |
| **Branch** | `master` |
| **Commit ID (full)** | `fe8c8b287b76337f9462d81567c3b46d3580c7af` |
| **Commit ID (short)** | `fe8c8b2` |
| **Parent** | `2d7dedd` (_"docs: record cloud-primary / local-fallback policy commit"_) |
| **Author** | `yuanfengli168 <jackieliglobal@gmail.com>` |
| **Remote** | `https://github.com/yuanfengli168/shoothighlm.git` |
| **Files changed** | 17 (1,762 insertions, 59 deletions) |
| **Status** | ✅ 302 tests pass, 1 skipped, coverage 94.23% |

### Commit Message

> Add --full flag, model-in-output, restore coverage to 94%, refresh docs
>
> - --full flag on all 6 LLM commands (50K-char prompt vs 12K default)
> - All 6 generators accept use_full=True and switch to 50K-char mode
> - Each command prints '(model: X, prompt: 12K|50K chars)' status line
> - New helpers in cli.py: _is_cloud_error, resolve_chat_model,
>   _config_get (works on both Config objects and plain dicts)
> - Bug fix: infographic and tables commands now catch httpx.HTTPError
>   on the LLM call (was: only ValueError/RuntimeError — would crash
>   on real network outage)

### Why this commit

The user (Yuanfeng) was doing a Chinese-PDF RAG test pass on a 1,221-page
book (《道生合符》 by Kazuo Inamori) on his MacBook Pro M1 Max. After
the previous commit's cloud-fallback policy, the second wave of feedback
was:

1. Mindmap/flashcard/podcast/guide quality on long books was weak
   because the 12K-char prompt only covers the first ~30 pages. Add
   `--full` to opt into 50K.
2. The user wanted to know which model was active. Add `(model: X)`
   to every command's status line.
3. Stale docs across README / CHANGELOG / DECISIONS / ChallengesInChinese.
4. Coverage dropped from 95% → 90% after the helpers in the previous
   commit. Restore it to >93%.
5. While writing the cloud-error tests, I discovered that
   `infographic()` and `tables()` only caught `ValueError` /
   `RuntimeError` from the LLM call — a real `httpx.ConnectError` on
   cloud outage would propagate as a Click exception and crash. Added
   `httpx.HTTPError` to the catch list. Same fix as the other 4 commands.

### New test files (64 new tests)

| File | Tests | What it covers |
|---|---|---|
| `tests/test_cli_helpers.py` | 16 | `resolve_chat_model` priority chain, `_is_cloud_error` |
| `tests/test_use_full_flag.py` | 14 | `--full` flag propagation, 12K→50K switch |
| `tests/test_pdf_embedding_edges.py` | 14 | docling fallback, 50% retry on 500, sentence-boundary truncation |
| `tests/test_cli_cloud_errors.py` | 9 | chat cloud/non-cloud/500 paths |
| `tests/test_cli_generator_errors.py` | 12 | cloud + generic error paths in all 6 generators |

### Test Results

```
302 passed, 1 skipped in 7.17s
Coverage: 94.23% (was 90%)
Per-file:
  embedding.py  100%
  vectorstore.py 100%
  pdf.py         95%
  cli.py         85% (large, mostly command-body glue)
  All generators 96-98%
```

The 1 skipped test is still `test_embedder_embed_real` (requires
live Ollama). Gated by `SKIP_LIVE_TESTS=1` in CI.

### Bug fix detail

**Before:**
```python
# cli.py — infographic
try:
    info = generator.generate(...)
except (ValueError, RuntimeError) as e:
    if _is_cloud_error(e): ...  # never reached on httpx.ConnectError
    else: ...
```

**After:**
```python
try:
    info = generator.generate(...)
except (ValueError, RuntimeError, httpx.HTTPError) as e:
    if _is_cloud_error(e): ...
    else: ...
```

Same fix for `tables()`. The other 4 generator commands (mindmap,
flashcard, podcast, guide) already used `except Exception as e` so
they were already safe.

### Doc refresh

- **CHANGELOG.md**: New "Index pipeline hardening + cloud-fallback policy" section
  under `[Unreleased]`. New "Bug fix: CLI exception handlers" note. Test list
  updated to 302/94.23%.
- **DECISIONS.md**: New "提示采样策略" (12K vs 50K), "PDF 后端策略" (pypdf vs
  docling), "测试覆盖" (95% → 89% → 94.23% trajectory) sections in Chinese.
- **README.md**:
  - Install instructions: `git clone` + `pip install -e ".[pdf,tts,image,dev]"`
  - "Pick a model and run" section with `--use-local`, `--model`, env var, `--full`
  - Troubleshooting table (10 issues, real ones hit during testing)
  - "Cloud vs Local — How to Choose" section
  - Fixed the `synthesize` example: podcast defaults to **markdown** for
    human reading, so users need `--format json` to feed it to `synthesize`
  - Test count: 238 → 302, coverage: ~90% → 94.23%
- **Todo.md**: Created (was missing). Living doc of strategies + status.
  Sections: 1) Smart sampling, 2) Multi-model providers, 3) Shell prompt,
  4) Stale docs, 5) Coverage. Action items at the bottom.
- **ChallengesInChinese.md**: Rewrote from empty placeholder. 7 detailed
  sections on real bugs hit (sqlite-vec "not authorized", docling 10+ hour
  OCR, bge-m3 500 on Chinese, multi-page bug, 120s timeout, "couldn't find
  relevant info", exception handler gaps). "共同模式" section with 4
  patterns for Chinese LLM applications.

---

## 2026-06-09 — Fix chat 'no relevant info' + synthesize accepts .md

| Field | Value |
|---|---|
| **Date** | 2026-06-09 (evening) |
| **Branch** | `master` |
| **Commit ID (short)** | `1a03c34` |
| **Parent** | `0583f95` |
| **Author** | `yuanfengli168 <jackieliglobal@gmail.com>` |
| **Files changed** | 10 (833 insertions, 77 deletions) |
| **Status** | ✅ 318 tests pass, coverage 94.80%; chat verified end-to-end against 1,221-page Chinese book |

### User-reported issues addressed

1. **"I asked '可以总结一下第一章节讲了什么吗?' and got 'couldn't find relevant information'"**
2. **"How do I set FISH_AUDIO_API_KEY?"**
3. **"Can you add `--full` examples to each command in README?"**
4. **"synthesize says Invalid JSON when I pass my .md file"**

### Root cause of #1

With bge-m3 + dense Chinese, observed top-5 chunk similarity is
0.45–0.55, well below the 0.5 threshold the user had configured.
So RAG returned nothing even when the answer was clearly in the
top 5 chunks (chunk #2 actually contained the book's table of
contents — directly relevant to the question).

### Fix: two-stage retrieval

```python
# rag.py — RAGChat.build_context()
above_threshold = [r for r in results if (1 - r.distance) >= self.min_similarity]
chosen = above_threshold if above_threshold else results[: self.fallback_top_n]
```

When the fallback is used, the response is prefixed with a
`[dim]Note: ...[/dim]` line explaining it's best-effort.

### Verified end-to-end

```
$ shoot-high chat ~/my-books "什么是稻盛和夫的经营哲学?" --min-similarity 0.4
1. 经营目的：追求全体员工物质和精神两方面的幸福 [1][2]
2. 核心准则：把作为人应该做的正确的事情以正确的方式贯彻到底
3. 主要体系：人生·工作的结果 = 思维方式 × 努力 × 能力
...
[1] dao-sheng-he-fu.pdf (relevance: 0.71)
[2] dao-sheng-he-fu.pdf (relevance: 0.70)
...
```

A 0.71-relevance Chinese answer with 5 properly cited sources.

### Fix for #4: synthesize accepts .md

New helper `_parse_markdown_script()` in `podcast.py`. Handles
Chinese, multi-line speaker turns, skips metadata lines like
`**Duration:**` and `**Hosts:**`. Round-trip test:
`PodcastScript.to_markdown()` → `_parse_markdown_script()` produces
the same segments.

### Fix for #2: FISH_AUDIO_API_KEY docs

New section in README.md under "Configuration" with 3 methods:
- env var (recommended): `export FISH_AUDIO_API_KEY="..."`
- config file: `tts.api_key: "..."` in `~/.shoothighlm/config.yaml`
- one-off: prefix the command

Also added a "TTS: how to set FISH_AUDIO_API_KEY" section with
step-by-step signup instructions for fish.audio.

### Fix for #3: --full examples in README

Added `--full` to all 6 generator commands in the Quick Start:
- `mindmap --full`
- `flashcard --full`
- `podcast --full`
- `guide --full`
- `infographic --full`
- `tables --full`

Plus a comparison table showing 12K (default) vs 50K (`--full`)
and the ~4× slower trade-off.

### New test files

- `tests/test_chat_flags.py` (4) — `--show-sources`,
  `--min-similarity`, `fallback_top_n` propagation
- `tests/test_podcast_parser.py` (7) — Chinese, multi-line,
  metadata skipping, round-trip
- `tests/test_synthesize_md.py` (3) — synthesize with .json,
  with .md, with malformed JSON
- `tests/test_rag.py` (+2) — fallback_top_n behavior,
  `_used_fallback` flag

### Test results

```
318 passed, 1 skipped in 7.23s
Coverage: 94.80% (was 94.23%)
  embedding.py  100%
  vectorstore.py 100%
  podcast.py     99%
  rag.py         96%
  pdf.py         95%
  cli.py         85%
```

### User's config

Updated `~/.shoothighlm/config.yaml`:
- `min_similarity: 0.4` (was 0.5; observed max sim is ~0.48)
- `fallback_top_n: 3` (new)

Also `config.template.yaml` for new users.
