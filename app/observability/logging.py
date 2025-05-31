"""Standard Python logging configuration."""
from __future__ import annotations

import logging
import sys

LEVEL = logging.INFO

def setup_logging() -> None:
    """Configure standard Python logging.

    Call **exactly once** at app startup.
    """
    if getattr(setup_logging, "_configured", False):  # type: ignore[attr-defined]
        return

    # Create a standard formatter with gunicorn-like brackets
    formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(process)d] [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %z'
    )

    # Configure stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(LEVEL)

    # Configure uvicorn loggers to propagate to root logger
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()  # Remove any existing handlers
        logger.propagate = True  # Propagate logs to root logger
        logger.setLevel(LEVEL)

    setup_logging._configured = True  # type: ignore[attr-defined]