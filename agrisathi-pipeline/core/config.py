"""
Centralised configuration — reads from .env via python-dotenv.
All other modules import from here; never read os.environ directly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.environ["DATABASE_URL"]

# ── Object / raw-file storage ─────────────────────────────────────────────────
RAW_STORAGE_PATH: str = os.getenv("RAW_STORAGE_PATH", "./data/raw")

# ── Qdrant vector store ───────────────────────────────────────────────────────
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "agrisathi_kb")

# ── Embedding model ───────────────────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))

# ── HTTP fetcher ──────────────────────────────────────────────────────────────
HTTP_TIMEOUT_SECONDS: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
HTTP_RETRIES: int = int(os.getenv("HTTP_RETRIES", "3"))

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "Asia/Kolkata")

# ── LLM ───────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Live data APIs ────────────────────────────────────────────────────────────
DATAGOV_API_KEY: str = os.getenv("DATAGOV_API_KEY", "")
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
