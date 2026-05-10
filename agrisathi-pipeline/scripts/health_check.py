"""
health_check.py — Check pipeline health: Qdrant vectors, DB source states, advisor test.
Run inside Docker: docker exec agrisathi-pipeline-api-1 python scripts/health_check.py
"""
import httpx
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, text
from core.config import settings

QDRANT_HOST = "qdrant"   # Docker service name; use "localhost" if running outside Docker
QDRANT_PORT = 6333
COLLECTION  = "agrisathi_kb"
API_BASE    = "http://localhost:8000"


def check_qdrant() -> int:
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    info = client.get_collection(COLLECTION)
    count = info.points_count or 0
    print(f"\n{'─'*60}")
    print(f"  QDRANT  Collection : {COLLECTION}")
    print(f"          Vectors    : {count}")
    print(f"          Status     : {info.status}")
    print(f"{'─'*60}")
    return count


def check_database():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT name, status, last_fetched_at, last_hash
                FROM data_sources
                ORDER BY name
            """)
        ).fetchall()

    never_fetched = 0
    print(f"\n  {'SOURCE NAME':<38} {'STATUS':<8} {'LAST FETCHED':<22} {'HASH'}")
    print(f"  {'─'*38} {'─'*8} {'─'*22} {'─'*8}")
    for name, status, last_fetched, last_hash in rows:
        fetched_str = str(last_fetched)[:19] if last_fetched else "never"
        hash_str    = (last_hash or "")[:8] or "—"
        if last_fetched is None:
            never_fetched += 1
        print(f"  {name:<38} {status:<8} {fetched_str:<22} {hash_str}")

    print(f"\n  Total sources : {len(rows)}")
    if never_fetched:
        print(f"  WARNING: {never_fetched} source(s) have never been fetched")
        print(f"  → Run: POST /sources/{{name}}/trigger  for each unfetched source")
    else:
        print(f"  All sources have been fetched at least once.")
    return never_fetched


def check_advisor():
    print(f"\n{'─'*60}")
    print("  ADVISOR TEST")
    print(f"{'─'*60}")
    payload = {
        "question": "cotton pest management Maharashtra",
        "farmer_context": {"crop": "cotton", "district": "Nagpur"},
    }
    try:
        r = httpx.post(f"{API_BASE}/ask", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        answer = data.get("answer", "")
        chunks = data.get("chunks_used", 0)
        lang   = data.get("language", "?")
        print(f"  Language    : {lang.upper()}")
        print(f"  Chunks used : {chunks}")
        print(f"  Answer      :\n")
        for line in answer[:500].split("\n"):
            print(f"    {line}")
        if len(answer) > 500:
            print(f"    ... [{len(answer)} chars total]")
        print()
        if len(answer) >= 100:
            print("  ✔  ADVISOR WORKING")
        else:
            print("  ✘  ADVISOR NEEDS ATTENTION — response too short")
    except Exception as e:
        print(f"  ✘  ADVISOR NEEDS ATTENTION — {e}")


def main():
    print("\n" + "="*60)
    print("  AgriSathi Health Check")
    print("="*60)

    try:
        check_qdrant()
    except Exception as e:
        print(f"  Qdrant ERROR: {e}")

    print()
    try:
        check_database()
    except Exception as e:
        print(f"  Database ERROR: {e}")

    check_advisor()
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
