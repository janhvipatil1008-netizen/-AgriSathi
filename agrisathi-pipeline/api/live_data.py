"""
Live mandi price layer.

fetch_and_store_mandi_prices() — called by scheduler daily at 08:00 IST.
GET /prices                    — returns latest price for a commodity/market.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.config import DATAGOV_API_KEY
from core.logger import get_logger
from core.registry import LiveMandiPrice, get_engine

log = get_logger(__name__)
router = APIRouter()

_AGMARKNET_URL = (
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    "?api-key={key}&format=json&filters[State.Name]=Maharashtra&limit=5000"
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class MandiPriceOut(BaseModel):
    commodity: str
    market: str
    district: str
    state: str
    min_price: float | None
    max_price: float | None
    modal_price: float | None
    arrival_date: str
    fetched_at: str


# ── Core fetch + store ────────────────────────────────────────────────────────

def fetch_and_store_mandi_prices() -> int:
    """
    Download Maharashtra mandi prices from data.gov.in and upsert into
    live_mandi_prices table.  Returns the number of rows upserted.
    Idempotent — safe to call multiple times per day.
    """
    if not DATAGOV_API_KEY:
        log.warning("DATAGOV_API_KEY not set — skipping mandi price fetch.")
        return 0

    url = _AGMARKNET_URL.format(key=DATAGOV_API_KEY)
    log.info("Fetching mandi prices from data.gov.in …")

    try:
        resp = httpx.get(url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("Mandi price fetch failed: %s", exc)
        return 0

    records = resp.json().get("records", [])
    if not records:
        log.warning("data.gov.in returned 0 price records.")
        return 0

    rows: list[dict] = []
    now = datetime.utcnow()
    for rec in records:
        date_str = rec.get("Price Date", "")
        try:
            arrival = datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            continue

        def _f(val: str) -> float | None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        rows.append({
            "commodity":    rec.get("Commodity", "").strip(),
            "market":       rec.get("Market.Name", "").strip(),
            "district":     rec.get("District.Name", "").strip(),
            "state":        rec.get("State.Name", "Maharashtra").strip(),
            "min_price":    _f(rec.get("Min Price")),
            "max_price":    _f(rec.get("Max Price")),
            "modal_price":  _f(rec.get("Modal Price")),
            "arrival_date": arrival,
            "fetched_at":   now,
        })

    if not rows:
        log.warning("No valid price rows parsed.")
        return 0

    # Batch upsert — insert, update on conflict
    with Session(get_engine()) as session:
        stmt = pg_insert(LiveMandiPrice).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_mandi_commodity_market_date",
            set_={
                "min_price":   stmt.excluded.min_price,
                "max_price":   stmt.excluded.max_price,
                "modal_price": stmt.excluded.modal_price,
                "fetched_at":  stmt.excluded.fetched_at,
            },
        )
        session.execute(stmt)
        session.commit()

    log.info("Upserted %d mandi price rows.", len(rows))
    return len(rows)


# ── DB lookup (used by advisor.py without HTTP round-trip) ────────────────────

def get_db_latest_price(
    commodity: str,
    market: str | None = None,
    on_date: date | None = None,
) -> LiveMandiPrice | None:
    """
    Return the most recent LiveMandiPrice row matching the filters.
    Case-insensitive commodity match; optional market and date filters.
    """
    from sqlalchemy import func, select

    with Session(get_engine()) as session:
        q = select(LiveMandiPrice).where(
            func.lower(LiveMandiPrice.commodity) == commodity.lower()
        )
        if market:
            q = q.where(func.lower(LiveMandiPrice.market) == market.lower())
        if on_date:
            q = q.where(LiveMandiPrice.arrival_date == on_date)
        q = q.order_by(LiveMandiPrice.arrival_date.desc()).limit(1)
        return session.scalars(q).first()


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/prices", response_model=MandiPriceOut)
def get_price(
    commodity: str = Query(..., description="Commodity name, e.g. 'Onion'"),
    market: str | None = Query(None, description="Market/mandi name, e.g. 'Lasalgaon'"),
    date: str | None = Query(None, description="Date as YYYY-MM-DD, defaults to today"),
):
    """Return the latest stored mandi price for a commodity and optional market."""
    on_date: date | None = None
    if date:
        try:
            from datetime import date as date_cls
            on_date = date_cls.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD.")

    row = get_db_latest_price(commodity, market, on_date)
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for '{commodity}'"
                   + (f" at '{market}'" if market else "")
                   + ". Trigger a price fetch first.",
        )

    return MandiPriceOut(
        commodity=row.commodity,
        market=row.market,
        district=row.district,
        state=row.state,
        min_price=row.min_price,
        max_price=row.max_price,
        modal_price=row.modal_price,
        arrival_date=str(row.arrival_date),
        fetched_at=str(row.fetched_at),
    )
