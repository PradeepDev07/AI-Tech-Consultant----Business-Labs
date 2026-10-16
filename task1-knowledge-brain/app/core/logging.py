"""Structured logging configuration for Knowledge Brain."""

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Set up and return the application logger."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("knowledge_brain")
    logger.setLevel(numeric_level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
