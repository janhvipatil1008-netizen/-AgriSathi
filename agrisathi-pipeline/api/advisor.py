"""
AgriSathi LLM answer layer.

POST /ask  — takes a farmer's question, retrieves relevant chunks from
Qdrant, builds a grounded prompt, calls Claude, and returns the answer.
"""

from __future__ import annotations

import re

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchAny

from api.live_data import get_db_latest_price
from api.weather import fetch_weather_data
from core.config import ANTHROPIC_API_KEY, QDRANT_COLLECTION
from core.logger import get_logger
from embedder.embed import QUERY_PREFIX, _get_client, _get_model

log = get_logger(__name__)
router = APIRouter()

# Keywords that trigger live data injection
_PRICE_KW  = {"price", "rate", "bhav", "भाव", "किंमत", "mandi", "मंडी",
               "market", "quintal", "cost", "दर"}
_WEATHER_KW = {"weather", "rain", "rainfall", "temperature", "temp",
               "humidity", "हवामान", "पाऊस", "तापमान", "forecast", "climate"}

_CLAUDE_MODEL = "claude-sonnet-4-6"
_NO_CONTEXT_REPLY = (
    "I don't have enough information about this topic yet. "
    "Please contact your local KVK (Krishi Vigyan Kendra) for guidance."
)
_SYSTEM_PROMPT = (
    "You are AgriSathi, an expert agricultural advisor for Maharashtra farmers. "
    "Answer only based on the provided context. "
    "If the answer is not in the context, say so clearly. "
    "Respond in the same language the farmer used."
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class FarmerContext(BaseModel):
    crop: str | None = None        # e.g. "cotton", "soybean"
    district: str | None = None    # e.g. "Nagpur", "Pune"
    language: str | None = None    # hint: "en" or "mr" (auto-detected if omitted)


class AskRequest(BaseModel):
    question: str
    farmer_context: FarmerContext | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    language: str       # "en" or "mr"
    chunks_used: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _words(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


def _get_live_context(question: str, ctx: FarmerContext | None) -> str:
    """
    Fetch live price and/or weather data when the question seems to need it.
    Returns a formatted string to prepend to the RAG context, or "".
    Never raises — all errors are logged and silently ignored.
    """
    q_words = _words(question)
    parts: list[str] = []

    # ── Price ──────────────────────────────────────────────────────────────
    if q_words & _PRICE_KW and ctx and ctx.crop:
        try:
            row = get_db_latest_price(
                commodity=ctx.crop,
                market=ctx.district,   # None is fine — returns best match
            )
            if row:
                loc = f"{row.market}, {row.district}"
                parts.append(
                    f"{row.commodity} price at {loc}: "
                    f"₹{row.modal_price:.0f}/quintal "
                    f"(min ₹{row.min_price:.0f}, max ₹{row.max_price:.0f}) "
                    f"as of {row.arrival_date}."
                )
        except Exception as exc:
            log.warning("Live price lookup failed: %s", exc)

    # ── Weather ────────────────────────────────────────────────────────────
    if q_words & _WEATHER_KW and ctx and ctx.district:
        try:
            w = fetch_weather_data(ctx.district)
            if w:
                rain_note = (f", rainfall {w.rainfall_mm} mm"
                             if w.rainfall_mm else ", no rainfall")
                parts.append(
                    f"Weather in {w.district}: {w.temp_c:.1f}°C, "
                    f"humidity {w.humidity}%, {w.description}{rain_note}."
                )
        except Exception as exc:
            log.warning("Live weather lookup failed: %s", exc)

    if not parts:
        return ""
    return "Live data as of today:\n" + "\n".join(f"- {p}" for p in parts)


def _detect_language(text: str) -> str:
    """Return 'mr' if text contains Devanagari characters, else 'en'."""
    return "mr" if any("\u0900" <= ch <= "\u097f" for ch in text) else "en"


def _build_qdrant_filter(ctx: FarmerContext | None) -> Filter | None:
    """
    Build a Qdrant metadata filter from farmer context.
    Crop filter: matches chunks whose 'crops' list contains the requested crop.
    District filter: not yet stored as a tag — skipped until tagger is extended.
    """
    if not ctx:
        return None

    must: list[FieldCondition] = []

    if ctx.crop:
        must.append(
            FieldCondition(
                key="crops",
                match=MatchAny(any=[ctx.crop.lower()]),
            )
        )

    # District tags are not currently stored in Qdrant payload.
    # To enable: extend processor/tagger.py to extract district names
    # and store them as a 'districts' list, then add a FieldCondition here.

    return Filter(must=must) if must else None


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """
    Retrieve context from Qdrant, then generate a grounded answer with Claude.
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set. Add it to .env and restart.",
        )

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty.")

    # ── 1. Detect language ────────────────────────────────────────────────────
    language = _detect_language(question)
    log.info("/ask language=%s question=%r", language, question[:80])

    # ── 2. Embed question ─────────────────────────────────────────────────────
    vector = _get_model().encode(QUERY_PREFIX + question).tolist()

    # ── 3. Search Qdrant ──────────────────────────────────────────────────────
    q_filter = _build_qdrant_filter(body.farmer_context)
    result = _get_client().query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        query_filter=q_filter,
        limit=5,
    )
    hits = result.points

    # If crop filter returned nothing, retry without the filter so the farmer
    # still gets a useful answer even when crop isn't tagged yet.
    if not hits and q_filter:
        log.info("No results with crop filter — retrying without filter.")
        result = _get_client().query_points(
            collection_name=QDRANT_COLLECTION,
            query=vector,
            limit=5,
        )
        hits = result.points

    # ── 4. No context → safe fallback ─────────────────────────────────────────
    if not hits:
        log.info("No chunks found for question — returning fallback reply.")
        return AskResponse(
            answer=_NO_CONTEXT_REPLY,
            sources=[],
            language=language,
            chunks_used=0,
        )

    # ── 5. Build prompt ───────────────────────────────────────────────────────
    context_blocks = "\n\n".join(
        f"[{h.payload.get('source_name', 'unknown')}]\n{h.payload.get('text', '')}"
        for h in hits
    )

    live_ctx = _get_live_context(question, body.farmer_context)
    if live_ctx:
        log.info("Injecting live context into prompt.")
        context_blocks = live_ctx + "\n\n" + context_blocks

    user_message = f"Context:\n{context_blocks}\n\nFarmer question: {question}"

    # ── 6. Call Claude ────────────────────────────────────────────────────────
    log.info("Calling Claude with %d context chunks.", len(hits))
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    answer = msg.content[0].text

    # Deduplicate sources while preserving order
    seen: set[str] = set()
    sources: list[str] = []
    for h in hits:
        name = h.payload.get("source_name", "")
        if name and name not in seen:
            sources.append(name)
            seen.add(name)

    log.info("/ask done  chunks=%d  sources=%s", len(hits), sources)
    return AskResponse(
        answer=answer,
        sources=sources,
        language=language,
        chunks_used=len(hits),
    )
