# Todo & Strategy Notes

> Living doc. Things we **decided to do** (with status) + things we
> **decided NOT to do yet** (with rationale). Most recent first.

> **🚨 Reference for new chat sessions: read the "Next-up back-log" section below FIRST, then come back here for the in-flight design discussions. Don't re-litigate decisions already made.**

---

## ✅ Latest pass (full repo review + 5 fixes shipped)

> Snapshot of what changed in the "review the whole repo" pass. Keep
> terse — this is a release note, not a design doc.

- **`min_similarity` default fixed**: was `0.7` in `config.py` (didn't
  match CHANGELOG, template, or live config). Now `0.4`, matching the
  template and the documented "0.5 was still too strict" narrative.
- **Multi-PDF processing in `mindmap` / `flashcard` / `podcast`**: was
  `pdf = pdfs[0]`, silently dropping books 2..N. Now loops all PDFs
  and writes one output file per PDF, with per-PDF error resilience
  (one bad book no longer aborts the batch). `--output` is rejected
  when more than 1 PDF is found.
- **Stratified text sampling**: new `shoothighlm/sampling.py` with
  `stratified_sample()` and `head_sample()`. Wired into all 6
  LLM-using modules. Default 12K budget now uses start + middle + end
  windows; `--full` (50K) still uses head sampling. See §1 below.
- **Cleaned up unused `Path` imports** in `mindmap.py`, `flashcard.py`,
  `podcast.py`, `guide.py`.
- **Todo.md annotated**: remaining items from the review are now in
  the **"Next-up back-log"** section below, ready to pick up.

### Repo review findings (full list, with disposition)

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | `min_similarity: 0.7` hardcoded | 🔴 Critical | ✅ Fixed |
| 2 | Only first PDF processed in 3 commands | 🔴 Critical | ✅ Fixed |
| 3 | CosyVoice TTS is a stub | 🟡 High | → Back-log #1 |
| 4 | Page tracking not implemented (citations) | 🟡 High | → Back-log #2 |
| 5 | `_extract_json` duplicated 6× | 🟡 High | → Back-log #3 |
| 6 | Naive `text[:12000]` truncation | 🟡 High | ✅ Fixed (sampling.py) |
| 7 | No config schema validation | 🟡 High | → Back-log #4 |
| 8 | `max_file_size` not enforced | 🟢 Medium | → Back-log #5 |
| 9 | TTS host-voice detection is fragile | 🟢 Medium | → Back-log #7 |
| 10 | No `logging` to disk | 🟢 Medium | → Back-log #6 |
| 11 | Unused imports in 4 modules | 🟢 Medium | ✅ Fixed |
| 12 | Inconsistent error handling | 🟢 Medium | (Use `_is_cloud_error` in new code) |
| 13 | Character-based chunking | ⚪ Low | → Back-log #9 |
| 14 | Incomplete docstrings | ⚪ Low | → Back-log #10 |
| 15 | `resolve_chat_model` polymorphism | ⚪ Low | → Back-log #11 |
| 16 | Chrome fallback order | ⚪ Low | → Back-log #12 |
| 17 | Shell-prompt model display | ⚪ Low | → Back-log #13 |
| 18 | 30-min podcast for long books | ⚪ Low | → Back-log #14 |
| 19 | Multi-PDF test coverage | ⚪ Low | → Back-log #8 |

---
## Yuanfeng:
- I like the mindmap html, works really well, and now I want it in all the commands like flashcards, etc.
- the fish audio is impressive, but why there are more than 2 accent? can we limit it to 2 accent only?
  - and test alibaba api in Chinese meaning, now it only supports the English version.
  - and for the very long book, why is it only 2:35 min long? I want a 30 minute version etc.

---

## Next-up back-log (queued for the next pass — do these before opening new design threads)

> Each item was identified in the "full repo review" chat. They are
> already triaged; just pick one and ship it. Files mentioned are
> verified paths.

### High priority (small, high impact)

1. **CosyVoice TTS** — `[tts.py:135-140](src/shoothighlm/tts.py#L135-L140)` raises
   `NotImplementedError` even though `config.template.yaml` advertises
   it. Either implement the Aliyun NLS API integration, or remove
   `cosyvoice` from the template so we don't lie to users.
   Yuanfeng's note above specifically asks for the Alibaba TTS in
   Chinese.

2. **Page tracking in citations** — `[pdf.py:84](src/shoothighlm/pdf.py#L84)`
   hardcodes `start_page=0, end_page=0`. `chat --show-sources` and any
   future citation feature would benefit massively from real page
   numbers. The pypdf backend already iterates per-page, so the fix is
   to make `chunk_text` page-aware and propagate `start_page` /
   `end_page` through the `Chunk` dataclass.

3. **Extract `_extract_json` to a shared utility** — duplicated across
   `infographic.py`, `tables.py`, `podcast.py`, `mindmap.py`,
   `flashcard.py`, `guide.py` (and partially in `synthesize_md`).
   Move to a `utils.py` (or extend `sampling.py` with shared helpers)
   so JSON parsing logic lives in one place. Same story for the
   sentence-boundary truncation already factored into `sampling.py`.

4. **Pydantic schema for config** — typos in YAML
   (e.g. `min_similairty`) silently fall back to defaults. Add a
   pydantic `BaseModel` for each config section and validate at load
   time, so the user gets a clear "this key doesn't exist" error.

5. **Enforce `max_file_size` before indexing** — config defines a
   `50MB` cap, but `[cli.py:115](src/shoothighlm/cli.py#L115)` never
   checks it. A 500MB PDF will silently OOM or time out the
   embedder. Add a pre-flight check in the `index` command.

### Medium priority

6. **Disk-based logging** — everything currently goes to stderr via
   `print()` / `rich.print()`. Add a `logging` setup that writes to
   `~/.shoothighlm/shoothighlm.log` so failures are debuggable after
   the fact. Include model names, prompt sizes, timings.

7. **TTS host-voice detection** — `[tts.py:284](src/shoothighlm/tts.py#L284)`
   uses name matching (`alex` / `host a`). If the user picks
   "Alice" and "Bob", both segments can map to `host_a`. Switch to
   positional assignment (1st segment = host_a, 2nd = host_b).

8. **Multi-PDF integration test fixture** — add a `temp_notebook_with_3_pdfs`
   fixture and test that `mindmap`, `flashcard`, `podcast` produce one
   output file per PDF (and skip failed PDFs without aborting).
   This is the regression test for the multi-PDF fix that just shipped.

9. **Token-based chunking** — `[pdf.py:85](src/shoothighlm/pdf.py#L85)`
   does character-based chunking and even has a TODO about tiktoken.
   Switch once we settle on the default embedding model.

10. **Docstring / type-hint pass** — most modules are good, but a few
    internal helpers (`_dict_to_node`, `chunk_text`, etc.) lack
    docstrings. Linters (`ruff` + `pydocstyle`) can surface them.

11. **Resolve `resolve_chat_model()` polymorphism** —
    `[cli.py:48-72](src/shoothighlm/cli.py#L48-L72)` accepts both a
    `Config` object and a plain `dict` (for tests). Split into two
    functions for clarity, or normalize on `Config` everywhere.

### Low priority / nice-to-have

12. **`render_html_to_png` Chrome fallback** —
    `[infographic.py:520-525](src/shoothighlm/infographic.py#L520-L525)`
    only falls back to system Chrome when bundled chromium fails.
    Make the fallback order robust in all cases.

13. **"model in shell prompt" Option A** — Todo §3 Option A (zsh
    function in `~/.zshrc`) is still un-implemented. Low value
    once Option C (print in command output) is already shipping.

14. **Long-book podcast duration** — Yuanfeng's note above wants
    30-minute versions, not 2:35. Investigate whether the
    `num_dialogues` heuristic in `podcast.py` is the right
    scaling factor, or whether we need a `--long-form` mode.

---

## 1) Smarter LLM prompt sampling (replaces dumb `text[:12000]` truncation)

**Status:** 🟢 **Shipped** (commits pending). New `sampling.py` module
exposes `stratified_sample(text, max_chars)` (40% start / 40% middle /
20% end, breaking at sentence boundaries) and `head_sample(...)` for
the `--full` fast path. Wired into all 6 LLM-using commands:
mindmap, flashcard, podcast, guide, infographic, tables. Default 12K
char limit now uses stratified sampling; `--full` (50K chars) uses
head sampling.

### Problem

Current `mindmap.py:extract` (and friends) does `text[: max_chars]` —
takes the **first** 12K characters of a 1,200-page book. That means:

- We over-sample the intro / TOC / copyright page
- We miss the conclusion and synthesis
- For a 6-book collection (like the Inamori series), we usually only
  see the first book

### Options considered

| Strategy | Quality | Speed | Complexity | Status |
|---|---|---|---|---|
| Current: `text[:12K]` | 🟡 Mediocre | Fast | ✅ Done | shipped |
| **Stratified sampling**: 4K start + 4K middle + 4K end | 🟢 Good | Fast | 🟡 Medium | **proposed** |
| **Diversity-based sampling**: pick top-N chunks by embedding distance from the book's centroid | 🟢 Best | Slow (needs index) | 🔴 High | later |
| **Hierarchical summarization**: chunk → summarize each → summarize summaries | 🟢 Best | Very slow | 🔴 High | research only |
| **`--full` flag** to opt into 50K-char mode | 🟡 Mediocre (but better than 12K) | Slow | ✅ Easy | **proposed** |

### Plan

1. Add `--full` flag to all 6 LLM commands → uses 50K chars instead of 12K.
2. Replace current first-12K truncation with **stratified sampling** (start + middle + end blocks). Default.
3. Keep the "smart truncation at sentence boundary" code so we don't
   chop mid-word at block boundaries.

### Bump HTTP timeouts to 600s

**Status:** ✅ Done (commit `ee557cc`)

All 7 LLM client classes (mindmap / flashcard / podcast / guide /
infographic / tables / rag) now use `httpx.Client(timeout=600.0)` so
cloud models with thinking mode + long prompts don't time out at 120s.

---

## 2) Multi-model + multi-provider support (Ollama / OpenRouter / OpenAI / Anthropic)

**Status:** 🟡 Not implemented — logged

### Goal

Easy switching between:

- `ollama:qwen3.5:cloud`
- `ollama:minimax-m3:cloud`
- `ollama:glm-5.1:cloud`
- `openrouter:qwen/qwen-2.5-72b-instruct` (free)
- `openrouter:anthropic/claude-4.5-sonnet`
- `openai:gpt-5`
- `anthropic:claude-4.5-opus`
- (any future provider with OpenAI-compatible API)

### Three layers of UX (combine all three)

**Option A — `--provider` flag (decouples protocol from model name):**

```bash
shoot-high mindmap ~/my-books --provider ollama --model minimax-m3:cloud
shoot-high mindmap ~/my-books --provider openrouter --model anthropic/claude-4.5-sonnet
shoot-high mindmap ~/my-books --provider openai --model gpt-5
```

The provider knows the `base_url`, auth header, and any request
formatting quirks. The model name is whatever the provider expects.

**Option B — `shoot-high models` subcommand (interactive discovery):**

```bash
shoot-high models list
# ollama:        qwen3.5:cloud, minimax-m3:cloud, glm-5.1:cloud  (current: qwen3.5:cloud)
# openrouter:    qwen/qwen-2.5-72b-instruct, anthropic/claude-4.5-sonnet
# openai:        gpt-5, gpt-4o
# anthropic:     claude-4.5-opus, claude-4.5-sonnet
# cohere:        command-r-plus

shoot-high models use openai/gpt-5         # sets default in config
shoot-high models use ollama:glm-5.1:cloud
shoot-high models alias smart anthropic/claude-4.5-opus   # adds an alias
```

Persists to `~/.shoothighlm/config.yaml` so it sticks across sessions.

**Option C — Quick-switch aliases in config (manual but fastest):**

```yaml
# ~/.shoothighlm/config.yaml
models:
  chat: "qwen3.5:cloud"        # default
  aliases:
    fast: "openrouter:qwen/qwen-2.5-72b-instruct"
    smart: "anthropic:claude-4.5-sonnet"
    chinese: "ollama:glm-5.1:cloud"
    vision: "ollama:minimax-m3:cloud"
```

```bash
shoot-high mindmap ~/my-books --model @smart
shoot-high mindmap ~/my-books --model @chinese
```

### Provider abstraction design

```python
# src/shoothighlm/providers.py (new file, ~150 lines)

@dataclass
class Provider:
    name: str
    base_url: str
    api_key: Optional[str]  # from env var or config
    default_model: str
    headers: dict = field(default_factory=dict)

PROVIDERS = {
    "ollama":     Provider("ollama",     "http://127.0.0.1:11434", None, "qwen3.5:cloud"),
    "openrouter": Provider("openrouter", "https://openrouter.ai/api/v1", "${OPENROUTER_API_KEY}", None),
    "openai":     Provider("openai",     "https://api.openai.com/v1",  "${OPENAI_API_KEY}",     "gpt-5"),
    "anthropic":  Provider("anthropic",  "https://api.anthropic.com", "${ANTHROPIC_API_KEY}",  "claude-4.5-sonnet"),
}

def resolve_provider_and_model(spec: str) -> tuple[Provider, str]:
    """Parse 'provider:model' or just 'model' (uses default provider)."""
```

### Plan

1. ✅ **Already done**: `--model TEXT` free-form flag (current state).
2. 🟡 **Next**: implement Option A (`--provider` flag) — most impactful,
   most code (~100 lines in `providers.py`).
3. 🟡 **Next**: implement Option C (aliases in config) — small (~30
   lines), high value.
4. ⏳ **Later**: implement Option B (`shoot-high models` subcommand) —
   more code, nice-to-have.

---

## 3) Show current model in shell prompt

**Status:** 🟢 Option C done, Option A queued as follow-up

### Option C — Print in command output (DONE)

Every LLM-using command now prints the active model on the "Extracting..."
status line:

```
$ shoot-high mindmap ~/my-books
Found 1 PDF(s)
Processing: dao-sheng-he-fu.pdf
  Extracted 456,269 chars
Extracting mind map with model qwen3.5:cloud...    ← here
✓ Mind map saved to: /Users/jackyli/my-books/output/dao-sheng-he-fu-mindmap.md
```

Zero shell config needed. Works in any terminal, any shell, any OS.

### Option A — Shell function in `~/.zshrc` (NOT done, queued)

Add to your `~/.zshrc`:

```bash
# Show the current shoot-high chat model in the prompt
shoot-high-model() {
    local model
    if [[ -n "$SHOOTHIGHLM_CHAT" ]]; then
        model="$SHOOTHIGHLM_CHAT"
    elif command -v yq >/dev/null 2>&1; then
        model=$(yq -r '.models.chat // "qwen3.5:cloud"' ~/.shoothighlm/config.yaml 2>/dev/null)
    else
        model="qwen3.5:cloud"
    fi
    # Sanitize: colons and dots break some shell prompts
    echo "($(echo "$model" | tr ':' '-' | tr '.' '-'))"
}
setopt PROMPT_SUBST
PROMPT='%F{cyan}(.venv)%f %F{green}%n@%m%f %F{blue}%~%f %F{yellow}$(shoot-high-model)%f %# '
```

This gives you:

```
(.venv) jackyli@Jackys-MacBook-Pro ~/shoothighlm (qwen3-5-cloud) %
(.venv) jackyli@Jackys-MacBook-Pro ~/shoothighlm (qwen3-5-27b)  %
```

The follow-up task: ship a `shoot-high-current-model` (or
`shoot-high model --current`) subcommand so the shell helper doesn't
need `yq`.

### Plan

1. ✅ Done: Option C in command output.
2. 🟡 Follow-up: add `shoot-high current-model` (or
   `shoot-high model --current`) subcommand for shell-prompt use.
3. 🟡 Follow-up: ship a one-liner `shoot-high` shell-init snippet that
   adds the helper to `~/.zshrc` / `~/.bashrc` automatically.

---

## 4) Stale docs

**Status:** ✅ All stale items updated (CHANGELOG, DECISIONS, README, ChallengesInChinese)

### What's stale

| Doc | Stale content | Fix |
|---|---|---|
| `doc/CHANGELOG.md` | Doesn't mention the last 3 commits (sqlite-vec, multi-page, cloud-fallback) | Add entries |
| `doc/DECISIONS.md` | Says pdf default is docling; doesn't mention the cloud-primary policy | Update pdf default entry; add "Cloud-primary / local-fallback" decision |
| `doc/ChallengesInChinese.md` | Empty placeholder | Write up today's lessons: SQLite version, bge-m3 token limit, docling slowness, cloud timeout |
| `README.md` | `pip install shoothighlm` (won't work — not on PyPI); no mention of `--use-local` flag | Update install instructions; add Troubleshooting section |
| `doc/blueOcean.md` | Mostly fine; could mention LLM Ranking Board we already have | Minor |
| `doc/moat.md` | Could highlight multi-LLM portability | Minor |

---

## 5) Coverage back above 90%

**Status:** ✅ Done — 94.23% (302 tests, above 93% threshold)

### Why it dropped

Went from 93% → 89% after adding two new helpers to `cli.py`:

- `_is_cloud_error(exc)` — no direct test
- `resolve_chat_model(config, use_local, model)` — no direct test

Functional paths through them are tested (6 commands × multiple tests
each), but the helper functions themselves show as uncovered.

### Plan

Add a `tests/test_cli_helpers.py` (~30 lines, 5 tests):

```python
def test_is_cloud_error_timeout()
def test_is_cloud_error_5xx()
def test_is_cloud_error_normal_error_passes_through()
def test_resolve_chat_model_model_override_wins()
def test_resolve_chat_model_use_local()
def test_resolve_chat_model_config_default()
def test_resolve_chat_model_env_var()
```

Plus add 1-2 tests per command for the new `--use-local` and `--model`
flags. Total ~12 small tests, brings coverage back to ~95%.

---

## Order of operations (next)

| # | Task | Status |
|---|---|---|
| 1 | Write this Todo.md (DONE) | ✅ |
| 2 | Implement Option C: `--full` flag + print model in command output (already done) + verify 600s timeouts (already done) | ✅ |
| 3 | Update stale docs (CHANGELOG, DECISIONS, README, ChallengesInChinese) | ✅ |
| 4 | Add helper tests for coverage | ✅ (94.23%, **302 tests**) |
| 5 | Commit and push | 🟡 in progress |
| 6 | (Follow-up) Implement Option A (multi-provider with `--provider` flag) | ⏳ |
| 7 | (Follow-up) Implement Option C aliases in config | ⏳ |
| 8 | (Follow-up) Implement Option B (`shoot-high models` subcommand) | ⏳ |
| 9 | (Follow-up) Implement Option A shell-prompt helper (ship `shoot-high current-model` + shell init) | ⏳ |
| 10 | (Follow-up) Replace `text[:12K]` with stratified sampling in prompt builders | ⏳ |
