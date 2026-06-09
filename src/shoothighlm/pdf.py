"""PDF parsing and text extraction"""

from pathlib import Path
from dataclasses import dataclass
from typing import Iterator


@dataclass
class Chunk:
    """A chunk of text from a document"""
    text: str
    source: str  # File path
    start_page: int
    end_page: int
    chunk_id: str


def parse_pdf(pdf_path: Path) -> Iterator[str]:
    """
    Parse PDF and extract text.

    Yields text per page.

    Backend selection (env var SHOOTHIGHLM_PDF_BACKEND):
      - "pypdf"  (default): fast pure-Python text extraction. Works for
                 PDFs that have a real text layer (the common case for
                 modern e-books, including most Chinese books).
      - "docling": heavyweight OCR + layout analysis. Use only for
                 scanned PDFs with no text layer. 50-100x slower on CPU.

    Falls back to pypdf automatically if docling fails to import or
    SHOOTHIGHLM_PDF_BACKEND=docling is set but the binary fails to run.
    """
    import os
    backend = os.environ.get("SHOOTHIGHLM_PDF_BACKEND", "pypdf").lower()

    if backend == "docling":
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(str(pdf_path))
            yield result.document.export_to_text()
            return
        except Exception:
            # Fall through to pypdf
            pass

    # Default: pypdf (fast, works for text-layer PDFs)
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            yield text


def chunk_text(
    text: str,
    source: str,
    chunk_size: int = 4096,
    chunk_overlap: int = 200,
) -> Iterator[Chunk]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        source: Source file path
        chunk_size: Target tokens per chunk
        chunk_overlap: Overlap tokens between chunks
    """
    # Simple character-based chunking (token-based would be more accurate)
    # For production, use tiktoken or similar
    start = 0
    chunk_num = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end]
        
        yield Chunk(
            text=chunk_text,
            source=source,
            start_page=0,  # TODO: Track actual pages
            end_page=0,
            chunk_id=f"{Path(source).stem}-{chunk_num}",
        )
        
        start += chunk_size - chunk_overlap
        chunk_num += 1
