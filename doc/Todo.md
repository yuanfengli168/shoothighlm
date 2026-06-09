# Todo & Strategy Notes

> Living doc. Things we **decided to do** (with status) + things we
> **decided NOT to do yet** (with rationale). Most recent first.

---
## Yuanfeng: 
- I like the mindmap html, works really well, and now I want it in all the commands like flashcards, etc. 
- 

## 1) Smarter LLM prompt sampling (replaces dumb `text[:12000]` truncation)

**Status:** 🟡 Not implemented — logged for next pass

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
