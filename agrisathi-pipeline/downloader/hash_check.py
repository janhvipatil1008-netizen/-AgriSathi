"""
Change detection via SHA-256 hashing.
Used to skip re-processing when a source has not changed since last fetch.
"""

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    """Return the hex SHA-256 digest of a string (UTF-8 encoded)."""
    return hashlib.sha256(text.encode()).hexdigest()


def has_changed(new_hash: str, previous_hash: str | None) -> bool:
    """True when the content differs from the last recorded hash."""
    return new_hash != previous_hash
