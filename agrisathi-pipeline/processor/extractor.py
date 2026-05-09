"""
Text extraction from PDF, CSV, and HTML files.
Returns a list of (page/row index, raw text) tuples for downstream chunking.
"""

from __future__ import annotations

from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

PageText = tuple[int, str]   # (index, text)


def extract(path: Path) -> list[PageText]:
    """Dispatch to the right extractor based on file extension."""
    suffix = path.suffix.lower()
    extractors = {
        ".pdf": _extract_pdf,
        ".csv": _extract_csv,
        ".json": _extract_json_api,
        ".html": _extract_html,
        ".htm": _extract_html,
        ".aspx": _extract_html,
        ".txt": _extract_txt,
    }
    fn = extractors.get(suffix)
    if fn is None:
        raise ValueError(f"Unsupported file type: {suffix}")
    log.info("Extracting text from %s", path.name)
    return fn(path)


# ── Per-format extractors ─────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> list[PageText]:
    import pdfplumber
    results: list[PageText] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                results.append((i, text))
    return results


def _extract_csv(path: Path) -> list[PageText]:
    import csv
    results: list[PageText] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            results.append((i, text))
    return results


def _extract_html(path: Path) -> list[PageText]:
    from bs4 import BeautifulSoup
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    # Remove boilerplate tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all(["p", "li", "h1", "h2", "h3"])]
    return [(i, text) for i, text in enumerate(paragraphs) if text]


def _extract_json_api(path: Path) -> list[PageText]:
    """
    Handle data.gov.in API JSON responses.
    Converts mandi price records to natural-language sentences.
    Falls back to key=value text for unrecognised JSON shapes.
    """
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") if isinstance(data, dict) else None

    if not records:
        # Generic JSON — stringify top-level values
        items = records if isinstance(data, list) else [data]
        return [(i, " | ".join(f"{k}: {v}" for k, v in item.items() if v))
                for i, item in enumerate(items)]

    results: list[PageText] = []
    for i, rec in enumerate(records):
        date      = rec.get("Price Date", "")
        commodity = rec.get("Commodity", "")
        market    = rec.get("Market.Name", "")
        district  = rec.get("District.Name", "")
        modal     = rec.get("Modal Price", "")
        lo        = rec.get("Min Price", "")
        hi        = rec.get("Max Price", "")
        text = (
            f"On {date}, {commodity} at {market}, {district} was priced at "
            f"\u20b9{modal} per quintal (min: \u20b9{lo}, max: \u20b9{hi})"
        )
        results.append((i, text))
    return results


def _extract_txt(path: Path) -> list[PageText]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [(i, line) for i, line in enumerate(lines) if line.strip()]
