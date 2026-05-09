"""
HTTP + file download logic with retry, timeout, and streaming support.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from core.config import HTTP_RETRIES, HTTP_TIMEOUT_SECONDS
from core.logger import get_logger

log = get_logger(__name__)


def download_file(url: str, dest_path: Path, retries: int = HTTP_RETRIES) -> Path:
    """
    Stream-download *url* to *dest_path*.
    Retries up to *retries* times with exponential back-off.
    Returns *dest_path* on success, raises on final failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            log.info("Fetching %s (attempt %d/%d)", url, attempt, retries)
            with httpx.stream("GET", url, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True) as resp:
                resp.raise_for_status()
                with dest_path.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=65_536):
                        fh.write(chunk)
            log.info("Saved to %s", dest_path)
            return dest_path
        except httpx.HTTPError as exc:
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)  # 2 s, 4 s, 8 s …
            else:
                raise


def fetch_text(url: str) -> str:
    """Fetch a URL and return its text content (for lightweight HTML/API responses)."""
    log.info("Fetching text from %s", url)
    resp = httpx.get(url, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
