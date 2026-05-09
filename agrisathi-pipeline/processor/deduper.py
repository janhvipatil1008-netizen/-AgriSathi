"""
Near-duplicate detection using MinHash + Locality-Sensitive Hashing (LSH).

Chunks that are ≥ SIMILARITY_THRESHOLD similar to an already-seen chunk
are dropped before embedding to avoid polluting the vector store.
"""

from __future__ import annotations

from datasketch import MinHash, MinHashLSH

from core.logger import get_logger
from processor.chunker import Chunk

log = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.85
NUM_PERM = 128          # MinHash permutations — higher = more accurate, slower


class Deduper:
    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self._lsh = MinHashLSH(threshold=threshold, num_perm=NUM_PERM)
        self._seen: set[str] = set()

    def _minhash(self, text: str) -> MinHash:
        m = MinHash(num_perm=NUM_PERM)
        for word in text.lower().split():
            m.update(word.encode())
        return m

    def is_duplicate(self, chunk: Chunk) -> bool:
        key = f"chunk_{chunk.index}"
        m = self._minhash(chunk.text)
        result = self._lsh.query(m)
        if result:
            return True
        self._lsh.insert(key, m)
        return False

    def filter(self, chunks: list[Chunk]) -> list[Chunk]:
        unique: list[Chunk] = []
        for chunk in chunks:
            if self.is_duplicate(chunk):
                log.debug("Dropping near-duplicate chunk %d", chunk.index)
            else:
                unique.append(chunk)
        log.info("Dedup: %d → %d chunks", len(chunks), len(unique))
        return unique
