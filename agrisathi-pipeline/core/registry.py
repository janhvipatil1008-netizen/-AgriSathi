"""
Source registry — SQLAlchemy model + helper queries.

Each row represents one data source the pipeline tracks.
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session

from core.config import DATABASE_URL


class SourceStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    url = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)          # pdf | csv | html | api
    schedule_cron = Column(String(100), nullable=False)        # e.g. "0 2 * * *"
    status = Column(Enum(SourceStatus), default=SourceStatus.ACTIVE)
    last_fetched_at = Column(DateTime, nullable=True)
    last_hash = Column(String(64), nullable=True)              # SHA-256 of last download
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<DataSource id={self.id} name={self.name!r} status={self.status}>"


class LiveMandiPrice(Base):
    """Daily mandi price snapshot fetched from data.gov.in Agmarknet API."""

    __tablename__ = "live_mandi_prices"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    commodity    = Column(String(100), nullable=False)
    market       = Column(String(100), nullable=False)
    district     = Column(String(100), nullable=False)
    state        = Column(String(100), nullable=False, default="Maharashtra")
    min_price    = Column(Float, nullable=True)
    max_price    = Column(Float, nullable=True)
    modal_price  = Column(Float, nullable=True)
    arrival_date = Column(Date, nullable=False)
    fetched_at   = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("commodity", "market", "arrival_date",
                         name="uq_mandi_commodity_market_date"),
    )

    def __repr__(self) -> str:
        return (f"<LiveMandiPrice {self.commodity!r} @ {self.market!r} "
                f"on {self.arrival_date} modal=₹{self.modal_price}>")


# ── Engine (module-level singleton) ───────────────────────────────────────────
_engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_engine():
    return _engine


def get_active_sources(session: Session) -> list[DataSource]:
    return list(session.scalars(select(DataSource).where(DataSource.status == SourceStatus.ACTIVE)))


def get_source_by_name(session: Session, name: str) -> DataSource | None:
    return session.scalars(select(DataSource).where(DataSource.name == name)).first()


def update_fetch_metadata(session: Session, source: DataSource, new_hash: str) -> None:
    source.last_fetched_at = datetime.utcnow()
    source.last_hash = new_hash
    session.commit()
