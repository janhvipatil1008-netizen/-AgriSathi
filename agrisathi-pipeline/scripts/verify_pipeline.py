"""
End-to-end pipeline verification for mahadbt_scheme_page.

Runs the full pipeline synchronously, then queries Qdrant to confirm
embeddings landed correctly.

Usage (inside Docker):
    docker exec agrisathi-pipeline-api-1 python scripts/verify_pipeline.py
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
VERIFY_QUERY = "farmer scheme Maharashtra eligibility"
_TYPE_TO_EXT = {"pdf": ".pdf", "csv": ".csv", "html": ".html", "api": ".json"}


def _step(n: int, label: str) -> None:
    print(f"[{n}] {label}")


def main() -> None:
    # ── Load source ───────────────────────────────────────────────────────────
    _step(1, f"Loading '{SOURCE_NAME}' from Postgres …")
    with Session(get_engine()) as session:
        source = get_source_by_name(session, SOURCE_NAME)
        if not source:
            print(f"\nPIPELINE FAILED — source '{SOURCE_NAME}' not found in data_sources table.")
            sys.exit(1)
        src_name  = source.name
        src_url   = source.url
        src_type  = source.source_type
    print(f"     OK  type={src_type}  url={src_url[:70]} …")

    # ── Download ──────────────────────────────────────────────────────────────
    _step(2, "Downloading …")
    suffix = Path(src_url).suffix or _TYPE_TO_EXT.get(src_type, ".bin")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"download{suffix}"
        try:
            download_file(src_url, tmp_path)
        except Exception as exc:
            print(f"\nPIPELINE FAILED — download error: {exc}")
            sys.exit(1)

        new_hash = sha256_file(tmp_path)
        size_kb = tmp_path.stat().st_size // 1024
        print(f"     OK  {size_kb} KB  hash={new_hash[:16]} …")

        # ── Store ─────────────────────────────────────────────────────────────
        _step(3, "Storing versioned copy …")
        stored = store(src_name, tmp_path, new_hash)
        print(f"     OK  {stored}")

        # ── Extract ───────────────────────────────────────────────────────────
        _step(4, "Extracting text …")
        try:
            pages = extract(tmp_path)
        except Exception as exc:
            print(f"\nPIPELINE FAILED — extractor error: {exc}")
            sys.exit(1)
        print(f"     OK  {len(pages)} pages/rows extracted")
        if not pages:
            print("\nPIPELINE FAILED — extractor returned 0 pages.")
            sys.exit(1)

        # ── Chunk ─────────────────────────────────────────────────────────────
        _step(5, "Chunking …")
        chunks = chunk_pages(pages, source_type=src_type)
        print(f"     OK  {len(chunks)} chunks before dedup")

        # ── Dedup ─────────────────────────────────────────────────────────────
        _step(6, "Deduplicating …")
        chunks = Deduper().filter(chunks)
        print(f"     OK  {len(chunks)} chunks after dedup")
        if not chunks:
            print("\nPIPELINE FAILED — all chunks were duplicates.")
            sys.exit(1)

        # ── Tag ───────────────────────────────────────────────────────────────
        _step(7, "Tagging …")
        metadatas = [tag(c, src_name, src_type, src_url) for c in chunks]
        print(f"     OK")

        # ── Embed + upsert ────────────────────────────────────────────────────
        _step(8, "Embedding and upserting to Qdrant (may take 1-5 min on first run) …")
        try:
            embed_and_upsert(chunks, metadatas)
        except Exception as exc:
            print(f"\nPIPELINE FAILED — embed/upsert error: {exc}")
            sys.exit(1)
        print(f"     OK  {len(chunks)} vectors upserted")

    # ── Query Qdrant ──────────────────────────────────────────────────────────
    _step(9, f"Querying Qdrant: '{VERIFY_QUERY}' …")
    try:
        vector = _get_model().encode(QUERY_PREFIX + VERIFY_QUERY).tolist()
        result = _get_client().query_points(
            collection_name=QDRANT_COLLECTION,
            query=vector,
            limit=3,
        )
        hits = result.points
    except Exception as exc:
        print(f"\nPIPELINE FAILED — Qdrant query error: {exc}")
        sys.exit(1)

    print()
    if hits:
        for h in hits:
            snippet = h.payload.get("text", "")[:100].replace("\n", " ")
            print(f"  score={h.score:.4f}  source={h.payload.get('source_name','?')}")
            print(f"  text : {snippet} …")
            print()
        print(f"PIPELINE VERIFIED — {len(chunks)} chunks embedded, {len(hits)} results returned.")
    else:
        print("PIPELINE FAILED — Qdrant returned 0 results after embedding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
