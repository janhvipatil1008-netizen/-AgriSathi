"""
Embed text chunks and upsert them into Qdrant.

Each point stored in Qdrant:
  id      → deterministic UUID derived from (source_name, chunk_index)
  vector  → sentence-transformer embedding
  payload → ChunkMetadata fields + raw text
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from core.config import (
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from core.logger import get_logger
from processor.chunker import Chunk
from processor.tagger import ChunkMetadata

log = get_logger(__name__)

# intfloat/multilingual-e5 models require these prefixes for optimal retrieval.
# PASSAGE_PREFIX goes on every document chunk before encoding into Qdrant.
# QUERY_PREFIX goes on every search query at retrieval time.
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX   = "query: "

_model: SentenceTransformer | None = None
_client: QdrantClient | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading embedding model: %s", EMBEDDING_MODEL)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION not in existing:
        dim = _get_model().get_sentence_embedding_dimension()
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        log.info("Created Qdrant collection '%s' (dim=%d)", QDRANT_COLLECTION, dim)


def _chunk_id(source_name: str, chunk_index: int) -> str:
    """Deterministic UUID so re-runs overwrite rather than duplicate."""
    namespace = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    return str(uuid.uuid5(namespace, f"{source_name}::{chunk_index}"))


def embed_and_upsert(
    chunks: list[Chunk],
    metadatas: list[ChunkMetadata],
) -> None:
    if not chunks:
        log.info("No chunks to embed.")
        return

    model = _get_model()
    client = _get_client()

    texts = [PASSAGE_PREFIX + c.text for c in chunks]

    log.info("Embedding %d chunks in batches of %d", len(texts), EMBEDDING_BATCH_SIZE)
    vectors = model.encode(texts, batch_size=EMBEDDING_BATCH_SIZE, show_progress_bar=False)

    points = [
        PointStruct(
            id=_chunk_id(meta.source_name, chunk.index),
            vector=vec.tolist(),
            payload={**asdict(meta), "text": chunk.text},
        )
        for chunk, meta, vec in zip(chunks, metadatas, vectors)
    ]

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    log.info("Upserted %d points to Qdrant collection '%s'", len(points), QDRANT_COLLECTION)
