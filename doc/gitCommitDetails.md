# Git Commit Details

Chronological log of notable commits on `shoothighlm`. Each entry captures
the commit metadata and a one-line summary of the change.

---

## 2026-06-09 — Fix index pipeline (multi-page PDFs, sqlite-vec loading, embedding truncation)

| Field | Value |
|---|---|
| **Date** | 2026-06-09 15:39:28 +0800 |
| **Branch** | `master` |
| **Commit ID (full)** | `4dd0532cd71e35c160d34143455059a6bdf18699` |
| **Commit ID (short)** | `4dd0532` |
| **Note** | This file was added via `git commit --amend --no-edit` after the initial commit, so the final hash is `4dd0532` (not the originally-planned `49797a8`). Date, author, branch, and message are identical. |
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
