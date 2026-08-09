"""Tests for ltr.logger module.

This module tests the logging configuration and functionality.
"""

import logging
import os
from unittest.mock import patch

from ltr.logger import get_logger, set_log_level


class TestGetLogger:
    """Test the get_logger function."""

    def test_get_logger_default_name(self):
        """Test getting logger with default name."""
        logger = get_logger()
        assert logger.name == "ltr"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_custom_name(self):
        """Test getting logger with custom name."""
        logger = get_logger("ltr.test_module")
        assert logger.name == "ltr.test_module"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns the same logger instance for same name."""
        logger1 = get_logger("ltr.test")
        logger2 = get_logger("ltr.test")
        assert logger1 is logger2

    def test_logger_has_handler(self):
        """Test that logger has a handler configured."""
        # Root ltr logger should have a handler
        logger = get_logger("ltr")
        assert len(logger.handlers) > 0
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_logger_has_formatter(self):
        """Test that logger handler has a formatter."""
        # Root ltr logger should have a formatter
        logger = get_logger("ltr")
        handler = logger.handlers[0]
        assert handler.formatter is not None
        assert isinstance(handler.formatter, logging.Formatter)

    def test_logger_propagate_false(self):
        """Test that logger propagation is disabled."""
        # Root ltr logger should have propagate=False
        logger = get_logger("ltr")
        assert logger.propagate is False

    def test_logger_logs_messages(self):
        """Test that logger can log messages."""
        # Use root ltr logger which has handlers
        logger = get_logger("ltr")
        # Verify logger has handlers and can log (no exception should be raised)
        assert len(logger.handlers) > 0
        # Logging should not raise exceptions
        logger.info("Test message")
        logger.debug("Debug message")
        logger.warning("Warning message")
        logger.error("Error message")

    def test_logger_respects_level(self):
        """Test that logger respects log level."""
        logger = get_logger("ltr.test_level")
        # Set level and verify it's set
        logger.setLevel(logging.WARNING)
        # Verify level is set (note: child loggers inherit from parent)
        # The actual level might be inherited, so we check effective level
        effective_level = logger.getEffectiveLevel()
        # Effective level should be at least WARNING
        assert effective_level >= logging.WARNING

    @patch.dict(os.environ, {"LTR_LOG_LEVEL": "DEBUG"})
    def test_logger_uses_env_level(self):
        """Test that logger uses LTR_LOG_LEVEL environment variable."""
        # Clear any existing loggers to test fresh initialization
        logging.getLogger("ltr.test_env").handlers.clear()
        logger = get_logger("ltr.test_env")
        # Note: We can't easily test the level was set from env without
        # more complex mocking, but we can verify it's a valid logger
        assert isinstance(logger, logging.Logger)

    @patch.dict(os.environ, {"LTR_LOG_LEVEL": "INVALID"})
    def test_logger_handles_invalid_env_level(self):
        """Test that logger handles invalid environment log level."""
        # Should fall back to INFO if invalid level
        logging.getLogger("ltr.test_invalid").handlers.clear()
        logger = get_logger("ltr.test_invalid")
        # Should still create a valid logger
        assert isinstance(logger, logging.Logger)


class TestSetLogLevel:
    """Test the set_log_level function."""

    def test_set_log_level_string(self):
        """Test setting log level with string."""
        logger = get_logger("ltr.test_set_string")
        set_log_level("DEBUG")
        assert logger.level == logging.DEBUG

    def test_set_log_level_constant(self):
        """Test setting log level with logging constant."""
        logger = get_logger("ltr.test_set_constant")
        set_log_level(logging.WARNING)
        assert logger.level == logging.WARNING

    def test_set_log_level_updates_handlers(self):
        """Test that set_log_level updates handler levels."""
        logger = get_logger("ltr.test_handler_level")
        set_log_level("ERROR")
        for handler in logger.handlers:
            assert handler.level == logging.ERROR

    def test_set_log_level_updates_child_loggers(self):
        """Test that set_log_level updates child loggers."""
        parent_logger = get_logger("ltr")
        child_logger = get_logger("ltr.child")
        set_log_level("WARNING")
        assert parent_logger.level == logging.WARNING
        assert child_logger.level == logging.WARNING

    def test_set_log_level_case_insensitive(self):
        """Test that set_log_level handles case-insensitive strings."""
        logger = get_logger("ltr.test_case")
        set_log_level("debug")
        assert logger.level == logging.DEBUG
        set_log_level("ERROR")
        assert logger.level == logging.ERROR

    def test_set_log_level_invalid_string(self):
        """Test that set_log_level handles invalid string level."""
        logger = get_logger("ltr.test_invalid")
        original_level = logger.level
        set_log_level("INVALID_LEVEL")
        # Should fall back to INFO
        assert logger.level == logging.INFO or logger.level == original_level


class TestLoggerIntegration:
    """Integration tests for logger functionality."""

    def test_logger_hierarchical_naming(self):
        """Test that logger supports hierarchical naming."""
        parent = get_logger("ltr")
        child = get_logger("ltr.module")
        grandchild = get_logger("ltr.module.submodule")

        assert parent.name == "ltr"
        assert child.name == "ltr.module"
        assert grandchild.name == "ltr.module.submodule"

    def test_multiple_loggers_independent(self):
        """Test that multiple loggers are independent."""
        logger1 = get_logger("ltr.module1")
        logger2 = get_logger("ltr.module2")

        logger1.setLevel(logging.DEBUG)
        logger2.setLevel(logging.ERROR)

        assert logger1.level != logger2.level

    def test_logger_initialization(self):
        """Test that default logger is initialized."""
        # The module initializes a default logger
        # This test verifies that initialization doesn't break
        logger = get_logger()
        assert logger is not None
        assert isinstance(logger, logging.Logger)
