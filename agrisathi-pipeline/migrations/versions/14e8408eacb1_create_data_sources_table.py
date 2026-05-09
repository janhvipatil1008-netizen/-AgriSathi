"""create_data_sources_table

Revision ID: 14e8408eacb1
Revises: 
Create Date: 2026-05-09 13:56:15.905867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14e8408eacb1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Raw SQL — bypasses SQLAlchemy's automatic type management entirely,
    # so no risk of duplicate CREATE TYPE errors on re-runs.
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sourcestatus AS ENUM ('ACTIVE', 'PAUSED', 'FAILED');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS data_sources (
            id          SERIAL PRIMARY KEY,
            name        VARCHAR(255) NOT NULL UNIQUE,
            url         TEXT NOT NULL,
            source_type VARCHAR(50)  NOT NULL,
            schedule_cron VARCHAR(100) NOT NULL,
            status      sourcestatus DEFAULT 'ACTIVE',
            last_fetched_at TIMESTAMP,
            last_hash   VARCHAR(64),
            created_at  TIMESTAMP DEFAULT NOW(),
            updated_at  TIMESTAMP DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS data_sources")
    op.execute("DROP TYPE IF EXISTS sourcestatus")
