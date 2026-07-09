"""
PDF parsing (PyMuPDF for speed/accuracy) and token-aware chunking with overlap.
Also does lightweight metadata extraction (title/authors/abstract heuristics).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.core.config import get_settings

settings = get_settings()


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    full_text: str
    title: str | None
    abstract: str | None


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None
    token_count: int


def file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def parse_pdf(filepath: str) -> ParsedDocument:
    doc = fitz.open(filepath)
    pages: list[ParsedPage] = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append(ParsedPage(page_number=i + 1, text=text))
    full_text = "\n".join(p.text for p in pages)
    doc.close()

    title = _extract_title(pages)
    abstract = _extract_abstract(full_text)
    return ParsedDocument(pages=pages, full_text=full_text, title=title, abstract=abstract)


def _extract_title(pages: list[ParsedPage]) -> str | None:
    if not pages:
        return None
    first_page_lines = [ln.strip() for ln in pages[0].text.splitlines() if ln.strip()]
    # Heuristic: title is usually the longest of the first few non-empty lines
    # that isn't an email/URL/affiliation line.
    candidates = [
        ln for ln in first_page_lines[:8]
        if len(ln) > 15 and "@" not in ln and not ln.lower().startswith(("abstract", "http"))
    ]
    return max(candidates, key=len) if candidates else (first_page_lines[0] if first_page_lines else None)


def _extract_abstract(full_text: str) -> str | None:
    match = re.search(r"abstract[:\s]*\n?(.*?)(?:\n\s*\n|1\.?\s+introduction)", full_text, re.IGNORECASE | re.DOTALL)
    if match:
        abstract = match.group(1).strip()
        return abstract[:2000] if abstract else None
    return None


def _approx_token_count(text: str) -> int:
    # Fast approximation (~4 chars/token) — avoids loading a tokenizer just for chunk sizing.
    return max(1, len(text) // 4)


def chunk_document(doc: ParsedDocument, chunk_size_tokens: int | None = None, overlap_tokens: int | None = None) -> list[Chunk]:
    """
    Sliding-window chunking over page-tagged text so each chunk retains
    a best-effort page number for citation purposes.
    """
    chunk_size = chunk_size_tokens or settings.CHUNK_SIZE_TOKENS
    overlap = overlap_tokens or settings.CHUNK_OVERLAP_TOKENS
    chunk_chars = chunk_size * 4
    overlap_chars = overlap * 4

    # Flatten with page markers
    tagged_text = ""
    page_boundaries: list[tuple[int, int]] = []  # (char_offset, page_number)
    for page in doc.pages:
        page_boundaries.append((len(tagged_text), page.page_number))
        tagged_text += page.text + "\n"

    chunks: list[Chunk] = []
    start = 0
    idx = 0
    text_len = len(tagged_text)
    if text_len == 0:
        return chunks

    while start < text_len:
        end = min(start + chunk_chars, text_len)
        text = tagged_text[start:end].strip()
        if text:
            page_num = _page_for_offset(page_boundaries, start)
            chunks.append(Chunk(index=idx, text=text, page=page_num, token_count=_approx_token_count(text)))
            idx += 1
        if end >= text_len:
            break
        start = end - overlap_chars if end - overlap_chars > start else end

    return chunks


def _page_for_offset(page_boundaries: list[tuple[int, int]], offset: int) -> int | None:
    page_num = None
    for boundary_offset, pnum in page_boundaries:
        if boundary_offset <= offset:
            page_num = pnum
        else:
            break
    return page_num
