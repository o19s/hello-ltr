"""Logging configuration for the ltr package.

This module provides a centralized logging setup for the hello-ltr library.
Log levels can be configured via environment variables or programmatically.
"""

import logging
import os
from typing import Optional, Union

# Default log level
_DEFAULT_LOG_LEVEL = os.environ.get("LTR_LOG_LEVEL", "INFO").upper()

# Logger instance for the ltr package
_logger: Optional[logging.Logger] = None


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get or create a logger for the ltr package.

    Args:
        name: Optional logger name. If None, uses 'ltr' as the base logger name.
            Sub-modules can use 'ltr.module_name' for hierarchical logging.

    Returns:
        logging.Logger: Configured logger instance.

    Example:
        >>> from ltr.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing documents")
    """
    global _logger

    if name is None:
        name = "ltr"

    logger = logging.getLogger(name)

    # Only configure if not already configured (avoid duplicate handlers)
    if not logger.handlers and logger.parent.name == "root":
        # Set log level from environment or default
        log_level = getattr(logging, _DEFAULT_LOG_LEVEL, logging.INFO)
        logger.setLevel(log_level)

        # Create console handler with formatting
        handler = logging.StreamHandler()
        handler.setLevel(log_level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

        # Prevent propagation to root logger to avoid duplicate messages
        logger.propagate = False

    return logger


def set_log_level(level: Union[str, int]) -> None:
    """Set the log level for all ltr loggers.

    Args:
        level: Log level as string ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            or logging constant (logging.DEBUG, etc.).

    Example:
        >>> from ltr.logger import set_log_level
        >>> set_log_level('DEBUG')
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Update all existing ltr loggers
    root_logger = logging.getLogger("ltr")
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)

    # Also update child loggers
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("ltr."):
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)


# Initialize default logger
get_logger("ltr")
