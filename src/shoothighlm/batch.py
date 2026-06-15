"""Batch runner for shootHighLM.

Coordinates running multiple generation commands (mindmap, flashcard,
podcast, guide, infographic, tables) across every PDF in a notebook,
with support for:

- include/exclude filter (``--include mindmap,flashcard``)
- parallel workers (``--workers N``)
- resume on failure (``.batch-state.json``)
- dry-run mode (no LLM calls)
- token-quota error detection (stop the batch cleanly)
- aggregated token accounting (delegated to ``token_log.TokenLogger``)

The runner is intentionally a thin orchestrator: it imports the same
generator classes the CLI uses (``MindMapExtractor``, ``FlashcardGenerator``,
``PodcastGenerator``, ``GuideGenerator``, ``InfographicGenerator``,
``TableExtractor``) so behavior is identical to running the commands
individually.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from rich import print as rprint

from .llm import LLMUsage
from .token_log import TokenLogger


# ---------------------------------------------------------------------------
# Command registry: maps a command name to a per-PDF runner.
# Each runner receives the parsed PDF text plus command-line options and
# returns ``(LLMUsage, str)`` where the second value is an optional
# side-effect summary (e.g., "saved to /path/mindmap.md").
# ---------------------------------------------------------------------------


@dataclass
class CommandSpec:
    """One generation command supported by the batch runner."""

    name: str
    label: str  # human-friendly name for logs / dry-run
    needs_full_text: bool = True  # all current commands need text


# Order matches the order they'll run in. Kept as a module-level constant
# so ``--include`` / ``--exclude`` can preserve it.
COMMANDS: List[CommandSpec] = [
    CommandSpec("mindmap", "Mind map"),
    CommandSpec("flashcard", "Flashcards"),
    CommandSpec("podcast", "Podcast script"),
    CommandSpec("guide", "Notebook guide"),
    CommandSpec("infographic", "Infographic"),
    CommandSpec("tables", "Data tables"),
]


# ---------------------------------------------------------------------------
# Per-(command, pdf) job record — what gets serialized to the state file
# and what shows up in the summary table at the end.
# ---------------------------------------------------------------------------


@dataclass
class BatchJobResult:
    command: str
    pdf: str
    status: str  # "ok" | "error" | "skipped" | "pending"
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""
    message: str = ""  # human-friendly success line, e.g. "saved to /path/x.md"


@dataclass
class BatchSummary:
    notebook: str
    started_at: str
    finished_at: str
    total: int
    ok: int = 0
    error: int = 0
    skipped: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_s: float = 0.0
    results: List[BatchJobResult] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "",
            "[bold]Batch summary[/bold]",
            f"  Notebook:  {self.notebook}",
            f"  Total:     {self.total} (ok={self.ok}, error={self.error}, skipped={self.skipped})",
            f"  Tokens:    input={self.total_input_tokens:,}  output={self.total_output_tokens:,}  "
            f"total={self.total_input_tokens + self.total_output_tokens:,}",
            f"  Duration:  {self.total_duration_s:.1f}s",
        ]
        if self.error:
            lines.append("")
            lines.append("  [red]Failed jobs:[/red]")
            for r in self.results:
                if r.status == "error":
                    lines.append(f"    - {r.command} / {r.pdf}: {r.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class BatchRunner:
    """Coordinate running multiple commands across a notebook's PDFs.

    Parameters
    ----------
    notebook_path:
        Root of the notebook (the folder containing the PDFs).
    include:
        If set, only run these command names. Takes precedence over
        ``exclude`` when both are set.
    exclude:
        If set, skip these command names.
    use_full:
        Forwarded to every command — use the 50K-char prompt variant.
    model, use_local:
        Forwarded to ``resolve_chat_model`` for every command.
    workers:
        Number of parallel workers. 1 = serial. Each worker runs one
        ``(command, pdf)`` job at a time. Most commands are
        I/O-bound (HTTP to Ollama) so 2-4 workers usually saturate
        a cloud model.
    resume:
        If True, load ``.batch-state.json`` and skip jobs that
        already finished in a previous run.
    dry_run:
        If True, plan the jobs and print what would run, but don't
        invoke any LLM.
    state_path:
        Override the location of the state file. Defaults to
        ``<notebook>/.batch-state.json``.
    """

    STATE_FILENAME = ".batch-state.json"

    def __init__(
        self,
        notebook_path: Path,
        *,
        include: Optional[Sequence[str]] = None,
        exclude: Optional[Sequence[str]] = None,
        use_full: bool = False,
        model: Optional[str] = None,
        use_local: bool = False,
        workers: int = 1,
        resume: bool = False,
        dry_run: bool = False,
        state_path: Optional[Path] = None,
    ) -> None:
        self.notebook_path = Path(notebook_path)
        self.include = list(include) if include else None
        self.exclude = set(exclude) if exclude else set()
        self.use_full = use_full
        self.model = model
        self.use_local = use_local
        self.workers = max(1, int(workers))
        self.resume = resume
        self.dry_run = dry_run
        self.state_path = Path(state_path) if state_path else (
            self.notebook_path / self.STATE_FILENAME
        )

    # ------------------------------------------------------------------ public

    def filter_commands(self) -> List[CommandSpec]:
        """Return the command list after applying --include / --exclude.

        If ``include`` is set, only those commands run. ``exclude`` is
        only consulted for commands that aren't already whitelisted by
        ``include`` — so ``--include mindmap --exclude mindmap`` still
        runs mindmap (explicit selection beats blacklist)."""
        chosen: List[CommandSpec] = []
        for spec in COMMANDS:
            if self.include is not None:
                # include wins — if you said --include mindmap, we run mindmap
                # even if you also said --exclude mindmap.
                if spec.name not in self.include:
                    continue
                chosen.append(spec)
                continue
            if spec.name in self.exclude:
                continue
            chosen.append(spec)
        return chosen

    def plan(self) -> List[Tuple[CommandSpec, Path]]:
        """Return the (command, pdf) job list, in run order."""
        cmds = self.filter_commands()
        pdfs = sorted(self.notebook_path.glob("*.pdf"))
        if not pdfs:
            return []
        return [(spec, pdf) for spec in cmds for pdf in pdfs]

    def run(self) -> BatchSummary:
        """Execute the planned jobs and return a summary."""
        import datetime as _dt

        from .config import Config
        from .pdf import parse_pdf

        # Resolve model once — used for all jobs in this batch.
        config = Config()
        chat_model = self._resolve_model(config)

        jobs = self.plan()
        summary = BatchSummary(
            notebook=self.notebook_path.name,
            started_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
            finished_at="",
            total=len(jobs),
        )

        if not jobs:
            rprint("[yellow]No PDFs found in notebook[/yellow]")
            summary.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            return summary

        if self.dry_run:
            return self._dry_run(jobs, summary)

        # Load resume state (per-job: command+pdf -> status)
        prior: Dict[str, Dict[str, str]] = {}
        if self.resume and self.state_path.exists():
            prior = json.loads(self.state_path.read_text(encoding="utf-8"))
            skipped = sum(
                1 for spec, pdf in jobs
                if prior.get(_job_key(spec.name, pdf.name), {}).get("status") == "ok"
            )
            if skipped:
                rprint(
                    f"[dim]Resuming: {skipped} job(s) already completed, "
                    f"will skip them.[/dim]"
                )

        # Read all PDFs once into memory (small notebooks) or per-job for huge ones.
        # Each PDF's text gets cached so the same PDF isn't re-parsed for
        # every command.
        text_cache: Dict[str, str] = {}

        def get_text(pdf: Path) -> str:
            if pdf.name not in text_cache:
                text_cache[pdf.name] = "\n\n".join(
                    t for t in parse_pdf(pdf) if t
                )
            return text_cache[pdf.name]

        # Pre-build TokenLogger once; it'll append to tokens.log + tokens.csv.
        output_dir = self.notebook_path / "output"
        token_logger = TokenLogger(output_dir)

        # Honor resume: filter out already-ok jobs.
        todo: List[Tuple[CommandSpec, Path]] = []
        for spec, pdf in jobs:
            key = _job_key(spec.name, pdf.name)
            if self.resume and prior.get(key, {}).get("status") == "ok":
                summary.skipped += 1
                summary.results.append(BatchJobResult(
                    command=spec.name, pdf=pdf.name, status="skipped",
                ))
                continue
            todo.append((spec, pdf))

        if not todo:
            summary.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            return summary

        def run_one(spec: CommandSpec, pdf: Path) -> BatchJobResult:
            text = get_text(pdf)
            if not text.strip():
                return BatchJobResult(
                    command=spec.name, pdf=pdf.name, status="error",
                    error="No text extracted from PDF",
                )
            started = time.monotonic()
            try:
                usage, message = self._invoke(spec, text, pdf, chat_model, config)
                duration = time.monotonic() - started
                token_logger.log(
                    notebook=self.notebook_path.name,
                    command=spec.name,
                    source=pdf.name,
                    model=chat_model,
                    usage=usage,
                    duration_s=duration,
                    status="ok",
                )
                return BatchJobResult(
                    command=spec.name, pdf=pdf.name, status="ok",
                    duration_s=duration,
                    input_tokens=int(usage.input_tokens),
                    output_tokens=int(usage.output_tokens),
                    message=message,
                )
            except Exception as e:
                duration = time.monotonic() - started
                token_logger.log(
                    notebook=self.notebook_path.name,
                    command=spec.name,
                    source=pdf.name,
                    model=chat_model,
                    usage=LLMUsage(),
                    duration_s=duration,
                    status="error",
                    error=str(e),
                )
                return BatchJobResult(
                    command=spec.name, pdf=pdf.name, status="error",
                    duration_s=duration, error=str(e),
                )

        # Execute jobs, in parallel if --workers > 1.
        completed: List[BatchJobResult] = []
        quota_exceeded = False

        if self.workers == 1:
            for spec, pdf in todo:
                if quota_exceeded:
                    break
                rprint(f"[blue]▶ {spec.label}:[/blue] {pdf.name}")
                result = run_one(spec, pdf)
                completed.append(result)
                if result.status == "ok":
                    rprint(f"  [green]✓ {result.message}[/green] "
                           f"({result.input_tokens + result.output_tokens:,} tokens, "
                           f"{result.duration_s:.1f}s)")
                else:
                    rprint(f"  [red]✗ {result.error}[/red]")
                if _is_token_quota_error_str(result.error):
                    quota_exceeded = True
                    rprint(
                        "[red]Token quota / context-length error detected — "
                        "stopping batch.[/red]"
                    )
        else:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                future_to_job = {
                    pool.submit(run_one, spec, pdf): (spec, pdf)
                    for spec, pdf in todo
                }
                for fut in as_completed(future_to_job):
                    spec, pdf = future_to_job[fut]
                    try:
                        result = fut.result()
                    except Exception as e:  # pragma: no cover (defensive)
                        result = BatchJobResult(
                            command=spec.name, pdf=pdf.name, status="error",
                            error=f"worker crashed: {e}",
                        )
                    completed.append(result)
                    tag = "✓" if result.status == "ok" else "✗"
                    color = "green" if result.status == "ok" else "red"
                    rprint(
                        f"  [{color}]{tag} {spec.label}: {pdf.name}[/{color}]"
                    )
                    if _is_token_quota_error_str(result.error):
                        quota_exceeded = True
                        # Drain remaining in-flight futures; don't start new ones.
                        # (as_completed will still yield them, but we'll skip
                        # recording the new ones below.)
                        rprint(
                            "[red]Token quota / context-length error detected — "
                            "stopping batch.[/red]"
                        )
                        # Cancel pending (Python 3.9+; safe no-op if not cancellable)
                        for f, j in future_to_job.items():
                            if not f.done():
                                f.cancel()
                        break

        # Roll completed results into summary
        for r in completed:
            summary.results.append(r)
            if r.status == "ok":
                summary.ok += 1
                summary.total_input_tokens += r.input_tokens
                summary.total_output_tokens += r.output_tokens
            elif r.status == "error":
                summary.error += 1
            else:
                summary.skipped += 1
            summary.total_duration_s += r.duration_s

        # Persist state file (so `--resume` works on the next invocation).
        self._write_state(completed)

        summary.finished_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
        return summary

    # ------------------------------------------------------------------ helpers

    def _dry_run(
        self, jobs: List[Tuple[CommandSpec, Path]], summary: BatchSummary
    ) -> BatchSummary:
        rprint("[bold]Dry run — no LLM calls will be made.[/bold]")
        if not jobs:
            rprint("[yellow]No PDFs found in notebook[/yellow]")
            return summary
        for spec, pdf in jobs:
            rprint(f"  [dim]would run:[/dim] {spec.label} [dim]on[/dim] {pdf.name}")
            summary.results.append(BatchJobResult(
                command=spec.name, pdf=pdf.name, status="skipped",
            ))
            summary.skipped += 1
        return summary

    def _resolve_model(self, config) -> str:
        # Re-use the CLI helper if available; fall back to default otherwise.
        try:
            from .cli import resolve_chat_model
            return resolve_chat_model(config, self.use_local, self.model)
        except Exception:
            return self.model or "qwen3.5:cloud"

    def _invoke(
        self,
        spec: CommandSpec,
        text: str,
        pdf: Path,
        chat_model: str,
        config,
    ) -> Tuple[LLMUsage, str]:
        """Call the right generator for ``spec`` and return (usage, message)."""
        from .mindmap import MindMapExtractor
        from .flashcard import FlashcardGenerator
        from .podcast import PodcastGenerator
        from .guide import GuideGenerator
        from .infographic import InfographicGenerator
        from .tables import TableExtractor

        if spec.name == "mindmap":
            gen = MindMapExtractor(chat_model=chat_model)
            try:
                tree, usage = gen.extract(text, title=pdf.stem, use_full=self.use_full)
            finally:
                gen.close()
            return usage, f"extracted mind map for {pdf.stem}"

        if spec.name == "flashcard":
            gen = FlashcardGenerator(chat_model=chat_model)
            try:
                cards, usage = gen.generate(
                    text, num_cards=10, source=pdf.name, use_full=self.use_full
                )
            finally:
                gen.close()
            return usage, f"generated {len(cards)} flashcards for {pdf.stem}"

        if spec.name == "podcast":
            gen = PodcastGenerator(chat_model=chat_model)
            try:
                script, usage = gen.generate(
                    text, title=pdf.stem, duration_minutes=8,
                    use_full=self.use_full,
                )
            finally:
                gen.close()
            return usage, f"generated podcast script for {pdf.stem}"

        if spec.name == "guide":
            gen = GuideGenerator(chat_model=chat_model)
            try:
                # The CLI collects a sources list and passes it through;
                # batch just uses the single PDF name.
                nb_guide, usage = gen.generate(
                    text,
                    title=self.notebook_path.name,
                    sources=[pdf.name],
                    num_questions=5,
                    use_full=self.use_full,
                )
            finally:
                gen.close()
            return usage, f"generated guide for {pdf.stem}"

        if spec.name == "infographic":
            gen = InfographicGenerator(chat_model=chat_model)
            try:
                info, usage = gen.generate(
                    text,
                    template="summary_card",
                    title=pdf.stem,
                    sources=[pdf.name],
                    use_full=self.use_full,
                )
            finally:
                gen.close()
            return usage, f"generated infographic for {pdf.stem}"

        if spec.name == "tables":
            gen = TableExtractor(chat_model=chat_model)
            try:
                tables_found, usage = gen.extract(
                    text, max_tables=3, use_full=self.use_full,
                )
            finally:
                gen.close()
            return usage, f"extracted {len(tables_found)} table(s) for {pdf.stem}"

        raise ValueError(f"Unknown command: {spec.name!r}")

    def _write_state(self, completed: List[BatchJobResult]) -> None:
        # Merge with prior state so resume accumulates, not overwrites.
        prior: Dict[str, Dict[str, str]] = {}
        if self.state_path.exists():
            try:
                prior = json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prior = {}
        for r in completed:
            if r.status in ("ok", "error"):
                prior[_job_key(r.command, r.pdf)] = {
                    "status": r.status,
                    "error": r.error,
                    "duration_s": f"{r.duration_s:.3f}",
                }
        self.state_path.write_text(
            json.dumps(prior, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _job_key(command: str, pdf: str) -> str:
    return f"{command}::{pdf}"


def _is_token_quota_error_str(error_text: str) -> bool:
    """Heuristic for token-quota / context-length exhaustion errors."""
    if not error_text:
        return False
    lowered = error_text.lower()
    triggers = (
        "context length",
        "exceeds the context",
        "input length exceeds",
        "out of context",
        "rate limit",
        "quota",
        "too many tokens",
    )
    return any(t in lowered for t in triggers)


def parse_csv_list(value: Optional[str]) -> Optional[List[str]]:
    """Parse ``--include mindmap,flashcard`` into ``['mindmap', 'flashcard']``."""
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]
