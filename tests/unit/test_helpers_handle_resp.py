"""Unit tests for handle_resp helper module."""

from unittest.mock import MagicMock

import pytest

from ltr.exceptions import ClientError
from ltr.helpers.handle_resp import resp_msg


class TestRespMsg:
    """Test HTTP response message handling functionality."""

    def test_success_status_no_exception(self):
        """Test that successful status codes don't raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "OK"

        # Act & Assert - Should not raise
        resp_msg("Test operation", resp, throw=True)

    def test_error_status_logs_error(self):
        """Test that error status codes are handled correctly."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not Found"

        # Act & Assert - Should not raise when throw=False
        resp_msg("Test operation", resp, throw=False)

    def test_error_status_raises_exception(self):
        """Test that error status codes raise exception when throw=True."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"

        # Act & Assert
        with pytest.raises(ClientError, match="HTTP 500"):
            resp_msg("Test operation", resp, throw=True)

    def test_error_status_no_exception_when_throw_false(self):
        """Test that error status codes don't raise exception when throw=False."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"

        # Act & Assert - Should not raise
        resp_msg("Test operation", resp, throw=False)

    def test_ignored_status_codes(self):
        """Test that ignored status codes don't raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "Not Found"

        # Act & Assert - Should not raise even with throw=True
        resp_msg("Test operation", resp, throw=True, ignore=[404])

    def test_ignored_status_codes_list(self):
        """Test that multiple ignored status codes work."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 403
        resp.text = "Forbidden"

        # Act & Assert
        resp_msg("Test operation", resp, throw=True, ignore=[404, 403])

    def test_non_ignored_error_raises(self):
        """Test that non-ignored error codes still raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Internal Server Error"

        # Act & Assert
        with pytest.raises(ClientError):
            resp_msg("Test operation", resp, throw=True, ignore=[404, 403])

    def test_4xx_status_raises(self):
        """Test that 4xx status codes raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 400
        resp.text = "Bad Request"

        # Act & Assert
        with pytest.raises(ClientError, match="HTTP 400"):
            resp_msg("Test operation", resp, throw=True)

    def test_5xx_status_raises(self):
        """Test that 5xx status codes raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 503
        resp.text = "Service Unavailable"

        # Act & Assert
        with pytest.raises(ClientError, match="HTTP 503"):
            resp_msg("Test operation", resp, throw=True)

    def test_2xx_status_no_exception(self):
        """Test that 2xx status codes don't raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 201
        resp.text = "Created"

        # Act & Assert - Should not raise
        resp_msg("Test operation", resp, throw=True)

    def test_3xx_status_no_exception(self):
        """Test that 3xx status codes don't raise exceptions."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 301
        resp.text = "Moved Permanently"

        # Act & Assert - Should not raise
        resp_msg("Test operation", resp, throw=True)

    def test_exception_includes_response_text(self):
        """Test that exception includes response text."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Custom error message"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            resp_msg("Test operation", resp, throw=True)

        assert "Custom error message" in str(exc_info.value)

    def test_exception_includes_operation(self):
        """Test that exception includes operation name."""
        # Arrange
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "Error"

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            resp_msg("My Operation", resp, throw=True)

        assert "My Operation" in str(exc_info.value.operation)
