"""
Centralised logging setup.
Call get_logger(__name__) in every module instead of using print().
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _build_handler(handler: logging.Handler, level: int = logging.DEBUG) -> logging.Handler:
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    # Console — INFO and above
    logger.addHandler(_build_handler(logging.StreamHandler(sys.stdout), logging.INFO))

    # Rotating file — DEBUG and above (10 MB × 5 files)
    file_handler = RotatingFileHandler(
        LOG_DIR / "agrisathi-pipeline.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logger.addHandler(_build_handler(file_handler, logging.DEBUG))

    return logger
