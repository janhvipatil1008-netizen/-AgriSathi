"""
Seed script — inserts the first 5 AgriSathi data sources.

Run AFTER `alembic upgrade head`:
    python -m scripts.seed

Safe to re-run — existing rows are skipped by name.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session

from core.registry import DataSource, SourceStatus, get_engine

SOURCES = [
    # ── 1. ICAR Annual Report PDF ─────────────────────────────────────────────
    # ICAR publishes crop advisory content in their annual report PDF.
    DataSource(
        name="icar_crop_advisory_pdf",
        url="https://icar.org.in/sites/default/files/ICAR-AR-2023-24-Eng.pdf",
        source_type="pdf",
        schedule_cron="0 2 * * 1",   # Every Monday at 02:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 2. Agmarknet daily market-price JSON ──────────────────────────────────
    # data.gov.in open API — JSON endpoint, limit=5000 for full Maharashtra data.
    # Extractor converts each record to a natural-language price sentence.
    DataSource(
        name="agmarknet_market_prices_csv",
        url="https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070?api-key=579b464db66ec23bdd0000013d3af08646a4453c703b53d8fea878b7&format=json&limit=5000&filters[state]=Maharashtra",
        source_type="api",
        schedule_cron="0 6 * * *",   # Every day at 06:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 3. MahaDBT scheme webpage ─────────────────────────────────────────────
    # Maharashtra Direct Benefit Transfer — lists active farmer schemes.
    DataSource(
        name="mahadbt_scheme_page",
        url="https://mahadbt.maharashtra.gov.in/SchemeData/schemeData",
        source_type="html",
        schedule_cron="0 3 * * 1",   # Every Monday at 03:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 4. NCIPM pest surveillance page ───────────────────────────────────────
    # ICAR-NCIPM pest early-warning and surveillance reports.
    DataSource(
        name="ncipm_pest_alerts",
        url="https://ncipm.icar.gov.in/index.php/pest-surveillance",
        source_type="html",
        schedule_cron="0 7 * * *",   # Every day at 07:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 5. Manual upload slot ─────────────────────────────────────────────────
    # Operator places a file at data/raw/manual_upload/latest.pdf and
    # triggers via:  POST /sources/manual_upload_slot/trigger
    # Kept PAUSED so the scheduler never auto-runs it.
    DataSource(
        name="manual_upload_slot",
        url="file:///data/raw/manual_upload/latest.pdf",
        source_type="pdf",
        schedule_cron="0 0 1 1 *",   # Yearly — effectively disabled
        status=SourceStatus.PAUSED,
    ),

    # ── 6. MPKV Cotton Package of Practices PDF ───────────────────────────────
    # Mahatma Phule Krishi Vidyapeeth — Cotton PoP PDF.
    # tagger.py auto-tags: crops=[cotton], topics=[advisory, pest, disease, weather]
    DataSource(
        name="mpkv_cotton_package_of_practices",
        url="https://mpkv.ac.in/wp-content/uploads/2023/07/Cotton-PoP.pdf",
        source_type="pdf",
        schedule_cron="0 2 1 * *",   # 1st of every month at 02:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 7. MPKV Soybean Package of Practices PDF ─────────────────────────────
    # Mahatma Phule Krishi Vidyapeeth — Soybean PoP PDF.
    # tagger.py auto-tags: crops=[soybean], topics=[advisory, pest, disease]
    DataSource(
        name="mpkv_soybean_package_of_practices",
        url="https://mpkv.ac.in/wp-content/uploads/2023/07/Soybean-PoP.pdf",
        source_type="pdf",
        schedule_cron="0 2 1 * *",   # 1st of every month at 02:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 8. Maharashtra Agriculture Dept — Crop Advisory HTML ─────────────────
    # krishi.maharashtra.gov.in weekly crop advisories for Maharashtra farmers.
    # tagger.py auto-tags: crops=[wheat, rice, cotton, soybean, onion, ...], topics=[advisory]
    DataSource(
        name="mahaagri_crop_advisory",
        url="https://krishi.maharashtra.gov.in/1076/Crop-Advisory",
        source_type="html",
        schedule_cron="0 4 * * 1",   # Every Monday at 04:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 9. PMFBY Operational Guidelines PDF ──────────────────────────────────
    # Pradhan Mantri Fasal Bima Yojana crop insurance guidelines.
    # tagger.py auto-tags: crops=[all], topics=[advisory] (insurance/scheme content)
    DataSource(
        name="pmfby_insurance_guidelines",
        url="https://pmfby.gov.in/pdf/operational_guidelines.pdf",
        source_type="pdf",
        schedule_cron="0 3 1 1,7 *",  # Jan 1 and Jul 1 at 03:00 IST (twice yearly)
        status=SourceStatus.ACTIVE,
    ),

    # ── 10. NHRDF Onion & Garlic Advisory HTML ────────────────────────────────
    # National Horticultural Research & Development Foundation circulars.
    # tagger.py auto-tags: crops=[onion, garlic], topics=[advisory, pest, disease]
    DataSource(
        name="nhrdf_onion_advisory",
        url="https://nhrdf.com/en-us/CircularsAndAdvisories",
        source_type="html",
        schedule_cron="0 5 * * 1",   # Every Monday at 05:00 IST
        status=SourceStatus.ACTIVE,
    ),

    # ── 11. IMD Agromet Advisory HTML ─────────────────────────────────────────
    # India Meteorological Department — district-level agro-meteorological advisories.
    # tagger.py auto-tags: crops=[all], topics=[weather, advisory]
    DataSource(
        name="imd_agromet_advisory",
        url="https://internal.imd.gov.in/pages/agromet_main.php",
        source_type="html",
        schedule_cron="0 6 * * *",   # Every day at 06:00 IST
        status=SourceStatus.ACTIVE,
    ),
]


def seed() -> None:
    engine = get_engine()
    inserted = 0
    skipped = 0

    with Session(engine) as session:
        for src in SOURCES:
            exists = session.query(DataSource).filter_by(name=src.name).first()
            if exists:
                print(f"  SKIP  (already exists): {src.name}")
                skipped += 1
            else:
                session.add(src)
                print(f"  INSERT: {src.name}")
                inserted += 1
        session.commit()

    print(f"\nDone — {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    seed()
