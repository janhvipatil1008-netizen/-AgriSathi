"""
End-to-end pipeline smoke test for mahadbt_scheme_page.

Runs every pipeline step manually and verifies Qdrant gets populated.

Usage (inside Docker or with venv active):
    python -m scripts.test_pipeline
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session

from core.config import QDRANT_COLLECTION
from core.registry import get_engine, get_source_by_name
from downloader.fetcher import download_file
from downloader.hash_check import sha256_file
from downloader.storage import store
from embedder.embed import QUERY_PREFIX, _get_client, _get_model, embed_and_upsert
from processor.chunker import chunk_pages
from processor.deduper import Deduper
from processor.extractor import extract
from processor.tagger import tag

SOURCE_NAME = "mahadbt_scheme_page"
QUERY = "farmer scheme eligibility Maharashtra"


def main() -> None:
    # ── 1. Load source from DB ────────────────────────────────────────────────
    print(f"[1] Loading source '{SOURCE_NAME}' from Postgres...")
    with Session(get_engine()) as session:
        source = get_source_by_name(session, SOURCE_NAME)
        if not source:
            print(f"FAIL: source '{SOURCE_NAME}' not found in data_sources table.")
            sys.exit(1)
        # Copy attributes before session closes
        src_name  = source.name
        src_url   = source.url
        src_type  = source.source_type
        src_id    = source.id
    print(f"     OK  url={src_url[:60]}...")

    # ── 2. Download ───────────────────────────────────────────────────────────
    print("[2] Downloading...")
    _type_to_ext = {"pdf": ".pdf", "csv": ".csv", "html": ".html", "api": ".json"}
    suffix = Path(src_url).suffix or _type_to_ext.get(src_type, ".bin")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"download{suffix}"
        download_file(src_url, tmp_path)
        new_hash = sha256_file(tmp_path)
        print(f"     OK  hash={new_hash[:16]}...  size={tmp_path.stat().st_size} bytes")

        # ── 3. Store ──────────────────────────────────────────────────────────
        print("[3] Storing versioned copy...")
        stored = store(src_name, tmp_path, new_hash)
        print(f"     OK  {stored}")

        # ── 4. Extract ────────────────────────────────────────────────────────
        print("[4] Extracting text...")
        pages = extract(tmp_path)
        print(f"     OK  {len(pages)} pages/rows")
        if not pages:
            print("FAIL: extractor returned 0 pages.")
            sys.exit(1)

        # ── 5. Chunk ──────────────────────────────────────────────────────────
        print("[5] Chunking...")
        chunks = chunk_pages(pages, source_type=src_type)
        print(f"     OK  {len(chunks)} chunks before dedup")

        # ── 6. Dedup ──────────────────────────────────────────────────────────
        print("[6] Deduplicating...")
        chunks = Deduper().filter(chunks)
        print(f"     OK  {len(chunks)} chunks after dedup")
        if not chunks:
            print("FAIL: all chunks were duplicates.")
            sys.exit(1)

        # ── 7. Tag ────────────────────────────────────────────────────────────
        print("[7] Tagging...")
        metadatas = [tag(c, src_name, src_type, src_url) for c in chunks]
        print(f"     OK  tagged {len(metadatas)} chunks")

        # ── 8. Embed + upsert ─────────────────────────────────────────────────
        print("[8] Embedding and upserting to Qdrant (first run downloads model ~1 GB)...")
        embed_and_upsert(chunks, metadatas)
        print(f"     OK  upserted {len(chunks)} vectors")

    # ── 9. Query Qdrant ───────────────────────────────────────────────────────
    print(f"[9] Querying Qdrant: '{QUERY}'")
    vector = _get_model().encode(QUERY_PREFIX + QUERY).tolist()
    result = _get_client().query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=3,
    )
    hits = result.points

    print()
    if hits:
        print(f"PASS — {len(chunks)} chunks embedded, top {len(hits)} results:")
        for h in hits:
            snippet = h.payload.get("text", "")[:120].replace("\n", " ")
            print(f"  score={h.score:.4f} | {snippet}...")
    else:
        print("FAIL — Qdrant returned 0 results after embedding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
