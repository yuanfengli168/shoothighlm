"""Tests for PDF backend selection and embedding retry/fallback behavior."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from shoothighlm.embedding import Embedder, _char_limit_for
from shoothighlm.pdf import parse_pdf


# ============== PDF backend selection ==============

def test_parse_pdf_default_uses_pypdf(tmp_path, monkeypatch):
    """Default backend is pypdf (env var unset)."""
    monkeypatch.delenv("SHOOTHIGHLM_PDF_BACKEND", raising=False)

    fake_pdf = tmp_path / "book.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    # Mock PdfReader so we don't need a real PDF
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Hello world"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page, mock_page]

    with patch("pypdf.PdfReader", return_value=mock_reader) as mock_pdf_reader:
        pages = list(parse_pdf(fake_pdf))

    assert pages == ["Hello world", "Hello world"]
    mock_pdf_reader.assert_called_once()


def test_parse_pdf_docling_fallback_on_import_error(tmp_path, monkeypatch):
    """If docling is requested but not importable, fall back to pypdf."""
    monkeypatch.setenv("SHOOTHIGHLM_PDF_BACKEND", "docling")
    fake_pdf = tmp_path / "book.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "docling-fallback text"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    # Make the docling import raise (simulating "not installed")
    with patch.dict("sys.modules", {"docling": None, "docling.document_converter": None}):
        with patch("pypdf.PdfReader", return_value=mock_reader) as mock_pdf:
            pages = list(parse_pdf(fake_pdf))

    assert pages == ["docling-fallback text"]
    mock_pdf.assert_called_once()


def test_parse_pdf_docling_fallback_on_converter_failure(tmp_path, monkeypatch):
    """If docling is requested but converter.convert() raises, fall back to pypdf."""
    monkeypatch.setenv("SHOOTHIGHLM_PDF_BACKEND", "docling")
    fake_pdf = tmp_path / "book.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "fallback"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    # Mock the docling import path so it appears to be importable
    fake_converter_cls = MagicMock()
    fake_converter = fake_converter_cls.return_value
    fake_converter.convert.side_effect = RuntimeError("docling crashed")

    fake_module = MagicMock()
    fake_module.DocumentConverter = fake_converter_cls

    with patch.dict("sys.modules", {
        "docling": MagicMock(),
        "docling.document_converter": fake_module,
    }):
        with patch("pypdf.PdfReader", return_value=mock_reader) as mock_pdf:
            pages = list(parse_pdf(fake_pdf))

    assert pages == ["fallback"]


def test_parse_pdf_skips_empty_pages(tmp_path, monkeypatch):
    """Pages with no text should be skipped (not yielded)."""
    monkeypatch.delenv("SHOOTHIGHLM_PDF_BACKEND", raising=False)
    fake_pdf = tmp_path / "book.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")

    empty_page = MagicMock()
    empty_page.extract_text.return_value = ""  # empty
    none_page = MagicMock()
    none_page.extract_text.return_value = None  # also skipped
    good_page = MagicMock()
    good_page.extract_text.return_value = "content"

    mock_reader = MagicMock()
    mock_reader.pages = [empty_page, none_page, good_page]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        pages = list(parse_pdf(fake_pdf))

    assert pages == ["content"]


# ============== Embedder retry / truncation ==============

def test_char_limit_for_known_models():
    assert _char_limit_for("bge-m3") == 6_000
    assert _char_limit_for("bge-m3:latest") == 6_000
    assert _char_limit_for("qwen3-embedding") == 28_000
    assert _char_limit_for("nomic-embed-text") == 28_000
    assert _char_limit_for("mxbai-embed-large") == 12_000


def test_char_limit_for_unknown_model_uses_default():
    assert _char_limit_for("unknown-model-xyz") == 16_000


def test_embedder_truncate_short_text():
    """Text under the limit should not be truncated."""
    e = Embedder(model="bge-m3")
    out = e._truncate("short text")
    assert out == "short text"


def test_embedder_truncate_at_sentence_boundary():
    """Long text should be cut at the nearest sentence/paragraph boundary."""
    e = Embedder(model="bge-m3")
    # bge-m3 limit is 6000 chars. Build a 7K char text with a paragraph
    # boundary in the right place.
    para1 = "A" * 5000 + "\n\n"
    para2 = "B" * 2500  # pushes total over 6K
    text = para1 + para2
    out = e._truncate(text)
    # The cut should preserve paragraph 1 (incl. the "\n\n") and not include para2
    assert out.endswith("\n\n")
    assert "B" * 100 not in out


def test_embedder_truncate_falls_back_to_hard_cut():
    """If no good boundary in the last 30%, cut hard at max_chars."""
    e = Embedder(model="bge-m3")
    # No sentence/paragraph boundaries anywhere
    text = "X" * 8000
    out = e._truncate(text)
    assert len(out) == 6000


def test_embedder_retry_on_500():
    """If Ollama returns 500 and text is long enough, retry with 50% cut."""
    e = Embedder(model="bge-m3")

    # First call returns 500, second call succeeds
    bad = MagicMock()
    bad.status_code = 500
    bad.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=bad,
    ))
    good = MagicMock()
    good.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
    good.raise_for_status = MagicMock()

    with patch.object(e.client, "post", side_effect=[bad, good]) as mock_post:
        result = e.embed("A" * 5000)

    assert result == [0.1, 0.2, 0.3]
    # First call: full text. Second call: hard-cut to ~50%
    first_call = mock_post.call_args_list[0]
    second_call = mock_post.call_args_list[1]
    first_prompt = first_call[1]["json"]["prompt"]
    second_prompt = second_call[1]["json"]["prompt"]
    assert len(first_prompt) == 5000
    assert len(second_prompt) == 2500


def test_embedder_no_retry_when_text_too_short():
    """If text is shorter than 500 chars, do not retry on 500."""
    e = Embedder(model="bge-m3")
    bad = MagicMock()
    bad.status_code = 500
    bad.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=bad,
    ))
    with patch.object(e.client, "post", return_value=bad) as mock_post:
        with pytest.raises(httpx.HTTPStatusError):
            e.embed("tiny text")  # only 9 chars
    # Should NOT have made a second call
    assert mock_post.call_count == 1


def test_embedder_non_500_error_not_retried():
    """4xx errors should not trigger the 50%-cut retry."""
    e = Embedder(model="bge-m3")
    err = MagicMock()
    err.status_code = 404
    err.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "not found", request=MagicMock(), response=err,
    ))
    with patch.object(e.client, "post", return_value=err) as mock_post:
        with pytest.raises(httpx.HTTPStatusError):
            e.embed("A" * 1000)
    assert mock_post.call_count == 1


def test_embedder_batch_returns_list_of_lists():
    """embed_batch should return one embedding per input text."""
    e = Embedder(model="bge-m3")
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": [0.5]}
    mock_response.raise_for_status = MagicMock()
    with patch.object(e.client, "post", return_value=mock_response):
        result = e.embed_batch(["text1", "text2", "text3"])
    assert len(result) == 3
    assert result == [[0.5], [0.5], [0.5]]


def test_get_embedder_ignores_use_cloud():
    """Ollama Cloud doesn't support embeddings, so use_cloud is ignored."""
    e_local = __import__("shoothighlm.embedding", fromlist=["get_embedder"]).get_embedder(
        model="bge-m3", use_cloud=True,
    )
    # Just verify we still get an Embedder pointing to localhost
    assert e_local.base_url == "http://127.0.0.1:11434"
