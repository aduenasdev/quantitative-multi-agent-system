"""Logging configuration: one ``qmas`` logger, configured once per process."""

from __future__ import annotations

import logging

LOGGER_NAME = "qmas"
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
HANDLER_NAME = "qmas-stream"


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure the ``qmas`` logger with a single stream handler and return it.

    Calling it again only updates the level; it never adds a second handler.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if not any(handler.get_name() == HANDLER_NAME for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.set_name(HANDLER_NAME)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(level)
    return logger
