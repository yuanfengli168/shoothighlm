"""Tests for the batch runner."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from shoothighlm.batch import (
    BatchRunner,
    CommandSpec,
    COMMANDS,
    _is_token_quota_error_str,
    _job_key,
    parse_csv_list,
)
from shoothighlm.cli import main
from shoothighlm.llm import LLMUsage


# ============== helpers / unit tests ===============


def test_parse_csv_list_basic():
    assert parse_csv_list("mindmap,flashcard") == ["mindmap", "flashcard"]
    assert parse_csv_list(" mindmap , flashcard ") == ["mindmap", "flashcard"]
    assert parse_csv_list("") is None
    assert parse_csv_list(None) is None
    assert parse_csv_list("a,,b") == ["a", "b"]


def test_job_key_format():
    assert _job_key("mindmap", "a.pdf") == "mindmap::a.pdf"


def test_is_token_quota_error_str():
    assert _is_token_quota_error_str("input length exceeds the context length")
    assert _is_token_quota_error_str("Out of context window")
    assert _is_token_quota_error_str("Rate limit exceeded")
    assert _is_token_quota_error_str("quota exhausted")
    assert _is_token_quota_error_str("too many tokens for model")
    # Negative cases
    assert not _is_token_quota_error_str("no PDFs found")
    assert not _is_token_quota_error_str("JSON parse error")
    assert not _is_token_quota_error_str("")


def test_commands_registry_has_all_six():
    """Belt-and-suspenders: the registry should have 6 commands and they
    should match the names the batch CLI accepts."""
    expected = {"mindmap", "flashcard", "podcast", "guide", "infographic", "tables"}
    assert {c.name for c in COMMANDS} == expected
    # All have non-empty labels
    assert all(c.label for c in COMMANDS)


# ============== filter / plan ===============


def test_filter_commands_default_returns_all(tmp_path: Path):
    """No include/exclude → all 6 commands."""
    runner = BatchRunner(tmp_path)
    assert [c.name for c in runner.filter_commands()] == [c.name for c in COMMANDS]


def test_filter_commands_include_narrows(tmp_path: Path):
    runner = BatchRunner(tmp_path, include=["mindmap", "tables"])
    assert [c.name for c in runner.filter_commands()] == ["mindmap", "tables"]


def test_filter_commands_exclude_drops(tmp_path: Path):
    runner = BatchRunner(tmp_path, exclude=["mindmap", "flashcard"])
    chosen = {c.name for c in runner.filter_commands()}
    assert "mindmap" not in chosen
    assert "flashcard" not in chosen
    assert "guide" in chosen


def test_filter_commands_include_wins_over_exclude(tmp_path: Path):
    """If both are set, include wins — explicit selection beats blacklist."""
    runner = BatchRunner(
        tmp_path, include=["mindmap"], exclude=["mindmap", "flashcard"]
    )
    chosen = [c.name for c in runner.filter_commands()]
    assert chosen == ["mindmap"]


def test_plan_returns_command_x_pdf_grid(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 fake b")
    runner = BatchRunner(tmp_path, include=["mindmap", "flashcard"])
    plan = runner.plan()
    assert len(plan) == 4  # 2 cmds × 2 pdfs
    # Deterministic order: iterate commands first, then pdfs
    assert plan[0][0].name == "mindmap" and plan[0][1].name == "a.pdf"
    assert plan[1][0].name == "mindmap" and plan[1][1].name == "b.pdf"
    assert plan[2][0].name == "flashcard" and plan[2][1].name == "a.pdf"


def test_plan_empty_notebook(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    assert runner.plan() == []


# ============== dry-run ===============


def test_dry_run_does_not_invoke_llm(tmp_path: Path):
    """--dry-run should plan + print, but never call any generator."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    runner = BatchRunner(tmp_path, dry_run=True)

    # Even if a generator would raise, dry-run should never touch it.
    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.flashcard.FlashcardGenerator") as fg_class, \
         patch("shoothighlm.podcast.PodcastGenerator") as pg_class, \
         patch("shoothighlm.guide.GuideGenerator") as gg_class, \
         patch("shoothighlm.infographic.InfographicGenerator") as ig_class, \
         patch("shoothighlm.tables.TableExtractor") as te_class:
        summary = runner.run()

    mm_class.assert_not_called()
    fg_class.assert_not_called()
    pg_class.assert_not_called()
    gg_class.assert_not_called()
    ig_class.assert_not_called()
    te_class.assert_not_called()

    # All jobs should be marked skipped in dry-run mode
    assert summary.total == 6  # 6 cmds × 1 pdf
    assert summary.skipped == 6
    assert summary.ok == 0
    assert summary.error == 0


# ============== state file (resume) ===============


def test_state_file_persists_on_run(tmp_path: Path):
    """A successful job should be recorded in .batch-state.json."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "output").mkdir()

    runner = BatchRunner(tmp_path, include=["mindmap"], workers=1)

    # Mock MindMapExtractor so we don't hit the LLM
    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (MagicMock(name="tree"), LLMUsage(input_tokens=10, output_tokens=5))
        mock_ext.close = MagicMock()
        mm_class.return_value = mock_ext

        # Avoid the real PDF parser (patched at import site)
        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text content"])):
            summary = runner.run()

    state_path = tmp_path / ".batch-state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mindmap::a.pdf"]["status"] == "ok"
    assert summary.ok == 1


def test_resume_skips_already_completed_jobs(tmp_path: Path):
    """Pre-existing state file with an 'ok' job should be skipped on resume."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")

    # Pre-populate state: mindmap on a.pdf already done
    state_path = tmp_path / ".batch-state.json"
    state_path.write_text(json.dumps({
        "mindmap::a.pdf": {"status": "ok", "error": "", "duration_s": "1.000"}
    }))

    runner = BatchRunner(tmp_path, include=["mindmap"], workers=1, resume=True)

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class:
        mock_ext = MagicMock()
        mm_class.return_value = mock_ext
        mock_ext.extract.return_value = (MagicMock(), LLMUsage())
        mock_ext.close = MagicMock()

        with patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
            summary = runner.run()

    # The LLM should NOT have been called
    mock_ext.extract.assert_not_called()
    assert summary.skipped == 1
    assert summary.ok == 0


# ============== CLI ===============


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_cli_batch_dry_run_prints_plan(cli_runner, tmp_path: Path, capsys):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    result = cli_runner.invoke(main, ["batch", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Batch plan: 6 command(s) × 1 PDF(s) = 6 job(s)" in out
    assert "would run: Mind map on a.pdf" in out
    assert "Dry-run:  on" in out


def test_cli_batch_include_filter(cli_runner, tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    result = cli_runner.invoke(
        main, ["batch", str(tmp_path), "--dry-run", "--include", "mindmap,flashcard"]
    )
    assert result.exit_code == 0, result.output
    assert "Batch plan: 2 command(s)" in result.output
    assert "Mind map" in result.output
    assert "Flashcards" in result.output
    # Excluded commands should not appear
    assert "Podcast script" not in result.output
    assert "Data tables" not in result.output


def test_cli_batch_exclude_filter(cli_runner, tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    result = cli_runner.invoke(
        main,
        ["batch", str(tmp_path), "--dry-run", "--exclude", "mindmap,flashcard,podcast"],
    )
    assert result.exit_code == 0, result.output
    assert "3 command(s)" in result.output  # guide, infographic, tables


def test_cli_batch_no_pdfs(cli_runner, tmp_path: Path):
    result = cli_runner.invoke(main, ["batch", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "No PDFs found" in result.output


def test_cli_batch_workers_flag_passes_through(cli_runner, tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    result = cli_runner.invoke(
        main, ["batch", str(tmp_path), "--dry-run", "-w", "4"]
    )
    assert result.exit_code == 0
    # Just check the flag didn't crash and the plan was printed
    assert "Batch plan:" in result.output
    # (The "Workers: 4" line is conditional on workers > 1, but the run
    # itself should still succeed.)


def test_cli_batch_resume_flag_accepted(cli_runner, tmp_path: Path):
    """The --resume flag should be accepted even with no prior state."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    result = cli_runner.invoke(
        main, ["batch", str(tmp_path), "--dry-run", "--resume"]
    )
    # Dry-run with --resume should not crash, even though dry-run short-
    # circuits before reading state.
    assert result.exit_code == 0


# ============== _invoke (per-command dispatch) ==============
# These tests exercise each branch of BatchRunner._invoke() so the
# command dispatch is covered even when not exercised by a real batch.


def test_invoke_mindmap_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class:
        mock_ext = MagicMock()
        mock_ext.extract.return_value = (MagicMock(name="tree"), LLMUsage(input_tokens=100, output_tokens=50))
        mock_ext.close = MagicMock()
        mm_class.return_value = mock_ext
        usage, message = runner._invoke(
            CommandSpec("mindmap", "Mind map"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 100
    assert "mind map" in message
    mock_ext.close.assert_called_once()


def test_invoke_flashcard_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.flashcard.FlashcardGenerator") as fg_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = ([MagicMock()] * 5, LLMUsage(input_tokens=200, output_tokens=80))
        mock_gen.close = MagicMock()
        fg_class.return_value = mock_gen
        usage, message = runner._invoke(
            CommandSpec("flashcard", "Flashcards"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 200
    assert "5 flashcards" in message
    mock_gen.close.assert_called_once()


def test_invoke_podcast_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.podcast.PodcastGenerator") as pg_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (MagicMock(), LLMUsage(input_tokens=300, output_tokens=120))
        mock_gen.close = MagicMock()
        pg_class.return_value = mock_gen
        usage, message = runner._invoke(
            CommandSpec("podcast", "Podcast"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 300
    assert "podcast script" in message
    mock_gen.close.assert_called_once()


def test_invoke_guide_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.guide.GuideGenerator") as gg_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (MagicMock(), LLMUsage(input_tokens=400, output_tokens=160))
        mock_gen.close = MagicMock()
        gg_class.return_value = mock_gen
        usage, message = runner._invoke(
            CommandSpec("guide", "Notebook guide"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 400
    assert "guide" in message
    mock_gen.close.assert_called_once()


def test_invoke_infographic_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.infographic.InfographicGenerator") as ig_class:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = (MagicMock(), LLMUsage(input_tokens=500, output_tokens=200))
        mock_gen.close = MagicMock()
        ig_class.return_value = mock_gen
        usage, message = runner._invoke(
            CommandSpec("infographic", "Infographic"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 500
    assert "infographic" in message
    mock_gen.close.assert_called_once()


def test_invoke_tables_branch(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.tables.TableExtractor") as te_class:
        mock_gen = MagicMock()
        mock_gen.extract.return_value = ([MagicMock()] * 3, LLMUsage(input_tokens=600, output_tokens=240))
        mock_gen.close = MagicMock()
        te_class.return_value = mock_gen
        usage, message = runner._invoke(
            CommandSpec("tables", "Data tables"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )
    assert usage.input_tokens == 600
    assert "3 table" in message
    mock_gen.close.assert_called_once()


def test_invoke_unknown_command_raises(tmp_path: Path):
    runner = BatchRunner(tmp_path)
    with pytest.raises(ValueError, match="Unknown command"):
        runner._invoke(
            CommandSpec("nonsense", "Bogus"), "text", tmp_path / "a.pdf",
            "qwen3.5:cloud", MagicMock(),
        )


def test_invoke_closes_generator_on_exception(tmp_path: Path):
    """If the LLM call raises, the generator's close() should still run."""
    runner = BatchRunner(tmp_path)
    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class:
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = RuntimeError("LLM down")
        mock_ext.close = MagicMock()
        mm_class.return_value = mock_ext
        with pytest.raises(RuntimeError, match="LLM down"):
            runner._invoke(
                CommandSpec("mindmap", "Mind map"), "text", tmp_path / "a.pdf",
                "qwen3.5:cloud", MagicMock(),
            )
    mock_ext.close.assert_called_once()


# ============== full run() with mocked generators ===============


def test_full_run_serial_writes_state_and_tokens_log(tmp_path: Path):
    """Run a 1-PDF, 2-cmd batch end-to-end with everything mocked."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    runner = BatchRunner(tmp_path, include=["mindmap", "flashcard"], workers=1)

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.flashcard.FlashcardGenerator") as fg_class, \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        mm = MagicMock()
        mm.extract.return_value = (MagicMock(), LLMUsage(input_tokens=10, output_tokens=5))
        mm.close = MagicMock()
        mm_class.return_value = mm

        fg = MagicMock()
        fg.generate.return_value = ([MagicMock()] * 7, LLMUsage(input_tokens=20, output_tokens=8))
        fg.close = MagicMock()
        fg_class.return_value = fg

        summary = runner.run()

    assert summary.ok == 2
    assert summary.error == 0
    assert summary.total_input_tokens == 30
    assert summary.total_output_tokens == 13

    # State file should have both jobs
    state = json.loads((tmp_path / ".batch-state.json").read_text(encoding="utf-8"))
    assert "mindmap::a.pdf" in state
    assert "flashcard::a.pdf" in state

    # Token log should have 2 rows
    log_text = (output_dir / "tokens.log").read_text(encoding="utf-8")
    log_lines = [l for l in log_text.splitlines() if l.strip()]
    assert len(log_lines) == 2


def test_full_run_records_error_in_state(tmp_path: Path):
    """A failed LLM call should still record an 'error' entry in state."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "output").mkdir()

    runner = BatchRunner(tmp_path, include=["mindmap"], workers=1)

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = RuntimeError("LLM is down")
        mock_ext.close = MagicMock()
        mm_class.return_value = mock_ext
        summary = runner.run()

    assert summary.ok == 0
    assert summary.error == 1

    state = json.loads((tmp_path / ".batch-state.json").read_text(encoding="utf-8"))
    assert state["mindmap::a.pdf"]["status"] == "error"
    assert "LLM is down" in state["mindmap::a.pdf"]["error"]


def test_full_run_empty_text_yields_error(tmp_path: Path):
    """A PDF that produces no text should be reported as error, not crash."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "output").mkdir()

    runner = BatchRunner(tmp_path, include=["mindmap"], workers=1)

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["", "  "])):
        mock_ext = MagicMock()
        mm_class.return_value = mock_ext
        summary = runner.run()

    # The extractor should never have been called — empty text is detected upstream
    mock_ext.extract.assert_not_called()
    assert summary.error == 1
    assert any("No text extracted" in r.error for r in summary.results)


def test_full_run_with_workers(tmp_path: Path):
    """Parallel execution path: --workers 2 should work with multiple jobs."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 fake b")
    (tmp_path / "output").mkdir()

    runner = BatchRunner(
        tmp_path, include=["mindmap", "flashcard"], workers=2,
    )

    # side_effect must return a fresh iter on every call (parse_pdf is a
    # generator, gets exhausted after one .next()).
    def fresh_text(*args, **kwargs):
        return iter(["text"])

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.flashcard.FlashcardGenerator") as fg_class, \
         patch("shoothighlm.pdf.parse_pdf", side_effect=fresh_text):
        mm = MagicMock()
        mm.extract.return_value = (MagicMock(), LLMUsage())
        mm.close = MagicMock()
        mm_class.return_value = mm
        fg = MagicMock()
        fg.generate.return_value = ([MagicMock()], LLMUsage())
        fg.close = MagicMock()
        fg_class.return_value = fg

        summary = runner.run()

    assert summary.ok == 4  # 2 cmds × 2 pdfs
    assert summary.error == 0


def test_full_run_quota_error_stops_batch(tmp_path: Path):
    """A token-quota / context-length error should stop the batch cleanly."""
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4 fake a")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4 fake b")
    (tmp_path / "output").mkdir()

    runner = BatchRunner(
        tmp_path, include=["mindmap", "flashcard"], workers=1,
    )

    with patch("shoothighlm.mindmap.MindMapExtractor") as mm_class, \
         patch("shoothighlm.flashcard.FlashcardGenerator") as fg_class, \
         patch("shoothighlm.pdf.parse_pdf", return_value=iter(["text"])):
        # First mindmap call fails with quota error; second should not run.
        mock_ext = MagicMock()
        mock_ext.extract.side_effect = RuntimeError(
            "input length exceeds the context length"
        )
        mock_ext.close = MagicMock()
        mm_class.return_value = mock_ext

        fg = MagicMock()
        fg.generate.return_value = ([MagicMock()], LLMUsage())
        fg.close = MagicMock()
        fg_class.return_value = fg

        summary = runner.run()

    # Only 2 jobs (mindmap on a, mindmap on b) should have actually executed.
    # flashcard jobs should be skipped because quota was hit.
    assert summary.error >= 1
    # State file should mark the mindmap jobs as errors
    state = json.loads((tmp_path / ".batch-state.json").read_text(encoding="utf-8"))
    assert all(v.get("status") == "error" for v in state.values())
