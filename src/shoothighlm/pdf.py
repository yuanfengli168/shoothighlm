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
    
    Uses docling if available, falls back to pypdf.
    Yields text per page.
    """
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        yield result.document.export_to_text()
    except ImportError:
        # Fallback to pypdf
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            yield page.extract_text()


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
