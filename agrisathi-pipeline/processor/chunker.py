"""
Domain-specific chunking strategies.

Agriculture text benefits from semantic chunking that respects:
- Crop / pest / disease boundaries
- Advisory sections (sowing, irrigation, harvest)
- Table rows (fertiliser doses, weather thresholds)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.logger import get_logger

log = get_logger(__name__)

CHUNK_SIZE = 400        # target tokens (approx characters / 4)
CHUNK_OVERLAP = 80      # overlap to preserve context across boundaries


@dataclass
class Chunk:
    index: int
    text: str
    source_page: int    # original page / row index from extractor


def chunk_pages(pages: list[tuple[int, str]], source_type: str = "generic") -> list[Chunk]:
    """
    Convert extractor output (list of (page_idx, text)) into overlapping chunks.
    *source_type* selects the splitting strategy.
    """
    if source_type == "csv":
        return _chunk_tabular(pages)
    return _chunk_prose(pages)


# ── Prose chunking (sliding window on sentences) ──────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[.!?।])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _chunk_prose(pages: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0
    current_page = 0
    chunk_idx = 0

    def flush():
        nonlocal chunk_idx
        if buffer:
            chunks.append(Chunk(index=chunk_idx, text=" ".join(buffer), source_page=current_page))
            chunk_idx += 1

    for page_idx, text in pages:
        current_page = page_idx
        for sentence in _sentences(text):
            s_len = len(sentence)
            if buffer_len + s_len > CHUNK_SIZE * 4 and buffer:
                flush()
                # keep last overlap characters
                overlap_text = " ".join(buffer)[-CHUNK_OVERLAP * 4:]
                buffer = [overlap_text]
                buffer_len = len(overlap_text)
            buffer.append(sentence)
            buffer_len += s_len

    flush()
    log.debug("Produced %d prose chunks", len(chunks))
    return chunks


# ── Tabular chunking (one chunk per row or small batch) ───────────────────────

_ROWS_PER_CHUNK = 5


def _chunk_tabular(pages: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    batch: list[str] = []

    for i, (row_idx, text) in enumerate(pages):
        batch.append(text)
        if len(batch) >= _ROWS_PER_CHUNK:
            chunks.append(Chunk(index=len(chunks), text="\n".join(batch), source_page=row_idx))
            batch = []

    if batch:
        chunks.append(Chunk(index=len(chunks), text="\n".join(batch), source_page=pages[-1][0]))

    log.debug("Produced %d tabular chunks", len(chunks))
    return chunks
