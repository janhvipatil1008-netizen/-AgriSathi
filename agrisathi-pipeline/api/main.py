"""
FastAPI management API.

Endpoints allow operators to inspect sources, trigger runs manually,
and pause/resume sources without touching the database directly.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.advisor import router as advisor_router
from api.live_data import router as live_data_router
from api.weather import router as weather_router
from core.config import QDRANT_COLLECTION
from core.logger import get_logger
from core.registry import Base, DataSource, SourceStatus, get_active_sources, get_engine, get_source_by_name
from embedder.embed import QUERY_PREFIX, _get_client, _get_model
from scheduler.runner import run_pipeline_for_source

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    # Create any tables that don't exist yet (idempotent)
    Base.metadata.create_all(get_engine())
    log.info("Database tables verified / created.")
    yield


app = FastAPI(title="AgriSathi Pipeline API", version="0.1.0", lifespan=lifespan)
app.include_router(advisor_router)
app.include_router(live_data_router)
app.include_router(weather_router)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    schedule_cron: str
    status: str
    last_fetched_at: str | None
    last_hash: str | None

    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str
    url: str
    source_type: str
    schedule_cron: str


class QueryRequest(BaseModel):
    text: str
    top_k: int = 5


class QueryResult(BaseModel):
    score: float
    source_name: str
    text: str
    tags: list[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/sources", response_model=list[SourceOut])
def list_sources():
    with Session(get_engine()) as session:
        return get_active_sources(session)


@app.post("/sources", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate):
    with Session(get_engine()) as session:
        if get_source_by_name(session, body.name):
            raise HTTPException(status_code=409, detail="Source name already exists.")
        source = DataSource(**body.model_dump())
        session.add(source)
        session.commit()
        session.refresh(source)
        return source


@app.post("/sources/{name}/trigger")
def trigger_source(name: str):
    """Manually run the pipeline for a named source immediately."""
    with Session(get_engine()) as session:
        source = get_source_by_name(session, name)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found.")

    log.info("Manual trigger for source: %s", name)
    threading.Thread(target=run_pipeline_for_source, args=(source,), daemon=True).start()
    return {"status": "ok", "source": name}


@app.patch("/sources/{name}/pause")
def pause_source(name: str):
    with Session(get_engine()) as session:
        source = get_source_by_name(session, name)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found.")
        source.status = SourceStatus.PAUSED
        session.commit()
    return {"status": "paused", "source": name}


@app.patch("/sources/{name}/resume")
def resume_source(name: str):
    with Session(get_engine()) as session:
        source = get_source_by_name(session, name)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found.")
        source.status = SourceStatus.ACTIVE
        session.commit()
    return {"status": "active", "source": name}


@app.post("/query", response_model=list[QueryResult])
def query_knowledge_base(body: QueryRequest):
    """Semantic search over the AgriSathi knowledge base."""
    vector = _get_model().encode(QUERY_PREFIX + body.text).tolist()
    result = _get_client().query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=body.top_k,
    )
    return [
        QueryResult(
            score=h.score,
            source_name=h.payload.get("source_name", ""),
            text=h.payload.get("text", ""),
            tags=h.payload.get("tags", []),
        )
        for h in result.points
    ]


@app.get("/health")
def health():
    return {"status": "ok"}
