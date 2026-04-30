"""PDF text extraction using PyMuPDF (fitz)."""
from __future__ import annotations
import os
import re

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def _sort_blocks(blocks: list) -> list:
    """Sort text blocks to handle 2-column layouts: top-to-bottom, left-to-right per row."""
    return sorted(blocks, key=lambda b: (round(b[1] / 50), b[0]))


def extract_title_abstract(pdf_path: str) -> dict:
    """Fast mode: read only first 2 pages, return title + abstract."""
    if fitz is None:
        raise ImportError("PyMuPDF is not installed. Run: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    text_parts = []
    for page_num in range(min(2, len(doc))):
        page = doc[page_num]
        blocks = page.get_text("blocks")
        blocks = _sort_blocks(blocks)
        for block in blocks:
            if block[6] == 0:  # text block
                text_parts.append(block[4].strip())
    doc.close()

    full_text = '\n'.join(text_parts)

    title = _extract_title(full_text, os.path.basename(pdf_path))
    abstract = _extract_abstract(full_text)

    return {
        'filename': os.path.basename(pdf_path),
        'path': pdf_path,
        'title': title,
        'abstract': abstract,
    }


def extract_full_text(pdf_path: str) -> str:
    """Extract all text from the PDF, handling 2-column layouts."""
    if fitz is None:
        raise ImportError("PyMuPDF is not installed. Run: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    all_parts = []
    for page in doc:
        blocks = page.get_text("blocks")
        blocks = _sort_blocks(blocks)
        for block in blocks:
            if block[6] == 0:
                text = block[4].strip()
                if text:
                    all_parts.append(text)
    doc.close()
    return '\n'.join(all_parts)


def _extract_title(text: str, filename: str) -> str:
    """Heuristic: title is usually the first substantial non-short line."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:15]:
        if 10 < len(line) < 250 and not line.lower().startswith('abstract'):
            return line
    # fallback: use filename without extension
    return os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ')


def _extract_abstract(text: str) -> str:
    """Extract abstract section."""
    # Look for 'Abstract' keyword
    pattern = re.compile(
        r'abstract\s*[:\-—]?\s*(.*?)(?=\n\s*(?:introduction|keywords|background|1\.|i\s+introduction))',
        re.IGNORECASE | re.DOTALL
    )
    match = pattern.search(text)
    if match:
        abstract = match.group(1).strip()
        # Limit to ~600 chars
        return abstract[:600] + ('...' if len(abstract) > 600 else '')

    # fallback: return first 400 chars after the title
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    # skip first few lines (title area), grab next substantial block
    for i, line in enumerate(lines):
        if line.lower().startswith('abstract'):
            rest = ' '.join(lines[i+1:i+10])
            return rest[:500] + ('...' if len(rest) > 500 else '')

    # Last fallback: second paragraph of text
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 100]
    if len(paragraphs) >= 2:
        return paragraphs[1][:500]
    elif paragraphs:
        return paragraphs[0][:500]
    return ''
