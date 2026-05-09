"""
APScheduler-based pipeline runner.

Each active DataSource row has a cron expression that controls when its
fetch → process → embed cycle executes. On startup, all active sources
are scheduled; the loop then runs indefinitely.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from api.live_data import fetch_and_store_mandi_prices
from core.config import SCHEDULER_TIMEZONE
from core.logger import get_logger
from core.registry import DataSource, get_active_sources, get_engine, update_fetch_metadata
from downloader.fetcher import download_file
from downloader.hash_check import has_changed, sha256_file
from downloader.storage import store
from embedder.embed import embed_and_upsert
from processor.chunker import chunk_pages
from processor.deduper import Deduper
from processor.extractor import extract
from processor.tagger import tag

log = get_logger(__name__)


def run_pipeline_for_source(source: DataSource) -> None:
    """Full fetch → extract → chunk → dedup → embed cycle for one source."""
    log.info("=== Pipeline start: %s ===", source.name)

    with tempfile.TemporaryDirectory() as tmp_dir:
        _type_to_ext = {"pdf": ".pdf", "csv": ".csv", "html": ".html", "api": ".json"}
        suffix = Path(source.url).suffix or _type_to_ext.get(source.source_type, ".bin")
        tmp_path = Path(tmp_dir) / f"download{suffix}"

        # 1. Download
        download_file(source.url, tmp_path)

        # 2. Change detection
        new_hash = sha256_file(tmp_path)
        if not has_changed(new_hash, source.last_hash):
            log.info("No change detected for %s — skipping.", source.name)
            return

        # 3. Versioned storage
        store(source.name, tmp_path, new_hash)

        # 4. Extract text
        pages = extract(tmp_path)

        # 5. Chunk
        chunks = chunk_pages(pages, source_type=source.source_type)

        # 6. Dedup
        deduper = Deduper()
        chunks = deduper.filter(chunks)

        # 7. Tag
        metadatas = [
            tag(chunk, source.name, source.source_type, source.url)
            for chunk in chunks
        ]

        # 8. Embed + upsert
        embed_and_upsert(chunks, metadatas)

    # 9. Update registry
    with Session(get_engine()) as session:
        db_source = session.get(DataSource, source.id)
        update_fetch_metadata(session, db_source, new_hash)

    log.info("=== Pipeline done: %s ===", source.name)


def schedule_all() -> None:
    scheduler = BlockingScheduler(timezone=SCHEDULER_TIMEZONE)

    with Session(get_engine()) as session:
        sources = get_active_sources(session)

    if not sources:
        log.warning("No active sources found in registry. Add rows to data_sources table.")
        return

    for source in sources:
        scheduler.add_job(
            run_pipeline_for_source,
            trigger=CronTrigger.from_crontab(source.schedule_cron, timezone=SCHEDULER_TIMEZONE),
            args=[source],
            id=f"source_{source.id}",
            name=source.name,
            replace_existing=True,
            misfire_grace_time=300,
        )
        log.info("Scheduled '%s' → cron: %s", source.name, source.schedule_cron)

    # Live mandi price fetch — daily at 08:00 IST (after markets open)
    scheduler.add_job(
        fetch_and_store_mandi_prices,
        trigger=CronTrigger(hour=8, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="live_mandi_prices",
        name="Daily mandi price fetch",
        replace_existing=True,
        misfire_grace_time=600,
    )
    log.info("Scheduled 'live_mandi_prices' → daily 08:00 IST")

    log.info("Scheduler starting with %d source jobs + 1 live data job.", len(sources))
    scheduler.start()


if __name__ == "__main__":
    schedule_all()
