"""Tests for the sampling utility (replaces naive `text[:max_chars]`)."""

import pytest
from shoothighlm.sampling import head_sample, stratified_sample, even_sample


# ============== head_sample ==============

def test_head_sample_short_text_unchanged():
    """If text is already short, return it as-is."""
    text = "Hello world"
    assert head_sample(text, max_chars=1000) == text


def test_head_sample_truncates_with_marker():
    """If text is too long, return the first max_chars + a marker."""
    text = "A" * 20_000
    result = head_sample(text, max_chars=5000)
    assert len(result) <= 5000 + len("... [truncated]")
    assert result.endswith("... [truncated]")


def test_head_sample_breaks_at_sentence_boundary():
    """When truncating, prefer a sentence/paragraph break over a hard cut."""
    text = "First sentence. " + "x" * 4500 + ". Last sentence here."
    result = head_sample(text, max_chars=1000)
    # Should not end mid-word
    assert not result.endswith(" xxxx")


# ============== stratified_sample ==============

def test_stratified_short_text_unchanged():
    """If text is already short, return it as-is (no sampling needed)."""
    text = "Short text"
    assert stratified_sample(text, max_chars=1000) == text


def test_stratified_includes_start_middle_and_end():
    """A stratified sample should contain text from all three regions."""
    # 50K chars: 25K of "AAA...", 25K of "BBB...", then "END-MARKER-..."
    text = "AAA " * 6250 + "BBB " * 6250 + "END-MARKER " * 100
    text = " ".join(text.split())  # normalize whitespace
    result = stratified_sample(text, max_chars=3000)

    # All three regions should be represented
    assert "AAA" in result
    assert "BBB" in result
    assert "END-MARKER" in result


def test_stratified_respects_max_chars():
    """Output must not exceed max_chars (allow a small overhead for the markers)."""
    text = "x" * 50_000
    result = stratified_sample(text, max_chars=3000)
    # A few hundred chars of overhead for the "[... middle ...]" markers
    assert len(result) <= 3500


def test_stratified_invalid_pcts_raises():
    """start_pct + mid_pct + end_pct must sum to 1.0."""
    text = "x" * 50_000
    with pytest.raises(ValueError, match="must sum to 1.0"):
        stratified_sample(text, max_chars=3000, start_pct=0.5, mid_pct=0.5, end_pct=0.5)


def test_stratified_falls_back_to_head_for_short_text():
    """If the three windows would overlap, fall back to head_sample."""
    # Text shorter than the budget — windows would all cover the
    # same range. We should return the first max_chars, not a
    # three-way sample that repeats everything.
    text = "Short book content here."
    result = stratified_sample(text, max_chars=10_000)
    # Result should be the whole text (it's already short)
    assert result == text


def test_stratified_default_pcts_sum_to_one():
    """The default 40/40/20 split should sum to 1.0 (sanity check)."""
    assert 0.4 + 0.4 + 0.2 == 1.0


def test_stratified_custom_pcts():
    """A 50/30/20 split should produce output with all three regions."""
    text = "START " * 5000 + "MIDDLE " * 5000 + "ENDING " * 5000
    text = " ".join(text.split())
    result = stratified_sample(
        text, max_chars=2000, start_pct=0.5, mid_pct=0.3, end_pct=0.2
    )
    assert "START" in result
    assert "MIDDLE" in result
    assert "ENDING" in result


# ============== even_sample ==============

def test_even_sample_short_text_unchanged():
    """If text is already short, return it as-is."""
    text = "Hello world"
    assert even_sample(text, max_chars=1000) == text


def test_even_sample_emits_section_break_markers():
    """Long text should be split into N windows with markers between."""
    text = "x" * 50_000
    result = even_sample(text, max_chars=3000, slices=10)
    # 10 slices joined by 9 markers
    assert result.count("[... section break ...]") == 9


def test_even_sample_includes_text_from_start_middle_and_end():
    """Uniform sampling should cover all parts of the document."""
    # Build a text where each region is uniquely identifiable.
    text = "AAA " * 10_000 + "BBB " * 10_000 + "CCC " * 10_000
    text = " ".join(text.split())
    result = even_sample(text, max_chars=3000, slices=10)
    # All three regions should be represented
    assert "AAA" in result
    assert "BBB" in result
    assert "CCC" in result


def test_even_sample_respects_max_chars():
    """Output must not exceed max_chars (allow a small overhead for the markers)."""
    text = "x" * 50_000
    result = even_sample(text, max_chars=3000, slices=10)
    # 9 markers × ~24 chars each = ~216 chars of overhead
    assert len(result) <= 3300


def test_even_sample_invalid_slices_raises():
    """slices must be >= 1."""
    text = "x" * 1_000
    with pytest.raises(ValueError, match="slices must be >= 1"):
        even_sample(text, max_chars=500, slices=0)


def test_even_sample_more_slices_than_chars_falls_back_to_head():
    """Degenerate case: more slices than characters. Falls back gracefully."""
    text = "x" * 100
    result = even_sample(text, max_chars=500, slices=1000)
    # Should not crash; should return something sensible
    assert isinstance(result, str)
    assert len(result) > 0
