"""
Logging utility for the Avature scraper project.

Provides a simple logging setup with console output and timestamps.
"""

import logging
import sys
from typing import Optional


# Default log format with timestamp
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Default log level
DEFAULT_LEVEL = logging.INFO

# Global flag to track if logging is configured
_logging_configured = False


def _configure_logging(level: int = DEFAULT_LEVEL):
    """
    Configure root logger with console handler.

    Args:
        level: Logging level (default: INFO)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter with timestamp
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    _logging_configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__). If None, returns root logger.

    Returns:
        Logger instance configured with console output and timestamps.
    """
    _configure_logging()
    return logging.getLogger(name)


def set_level(level: int):
    """
    Set the logging level for all loggers.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO, logging.WARNING)
    """
    _configure_logging(level)
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)
