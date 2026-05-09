"""
Versioned raw-file storage.

Directory layout:
    RAW_STORAGE_PATH/
        <source_name>/
            <YYYY-MM-DDTHH-MM-SS>_<hash[:8]>.<ext>   ← versioned copy
            latest.<ext>                              ← symlink / copy to newest
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core.config import RAW_STORAGE_PATH
from core.logger import get_logger

log = get_logger(__name__)

_ROOT = Path(RAW_STORAGE_PATH)


def _source_dir(source_name: str) -> Path:
    d = _ROOT / source_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def store(source_name: str, tmp_path: Path, file_hash: str) -> Path:
    """
    Copy *tmp_path* into the versioned store for *source_name*.
    Returns the final storage path.
    """
    ext = tmp_path.suffix
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    versioned_name = f"{ts}_{file_hash[:8]}{ext}"

    dest_dir = _source_dir(source_name)
    dest_path = dest_dir / versioned_name

    shutil.copy2(tmp_path, dest_path)
    log.info("Stored %s → %s", source_name, dest_path)

    # Update the "latest" pointer
    latest = dest_dir / f"latest{ext}"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    try:
        latest.symlink_to(dest_path.name)
    except (OSError, NotImplementedError):
        # Symlinks may not be available on all platforms; fall back to a copy
        shutil.copy2(dest_path, latest)

    return dest_path


def get_latest(source_name: str, ext: str) -> Path | None:
    """Return the latest stored file for *source_name*, or None if absent."""
    latest = _source_dir(source_name) / f"latest{ext}"
    return latest if latest.exists() else None
