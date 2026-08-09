"""Unit tests for retry logic helpers."""

from unittest.mock import Mock, patch

import pytest

from ltr.exceptions import QueryError
from ltr.helpers.retry import (
    check_feature_set_error_in_response,
    is_feature_set_timing_error,
    is_model_timing_error,
    is_opensearch_connection_error,
    is_opensearch_timing_error,
    is_requests_connection_error,
    retry_feature_set_query,
    retry_model_query,
    retry_on_connection_error,
    retry_until_true,
)


class TestRetryOnConnectionError:
    """Test retry_on_connection_error function."""

    def test_success_on_first_attempt(self):
        """Test that function succeeds on first attempt."""
        # Arrange
        func = Mock(return_value="success")
        # Act
        result = retry_on_connection_error(func, max_retries=3)
        # Assert
        assert result == "success"
        assert func.call_count == 1

    def test_retry_on_connection_error(self):
        """Test that function retries on connection errors."""
        # Arrange
        func = Mock(side_effect=[ConnectionError("Connection refused"), "success"])
        # Act
        result = retry_on_connection_error(func, max_retries=3, initial_delay=0.01)
        # Assert
        assert result == "success"
        assert func.call_count == 2

    def test_retry_exhausted(self):
        """Test that function raises RuntimeError when retries exhausted."""
        # Arrange
        func = Mock(side_effect=ConnectionError("Connection refused"))
        # Act & Assert
        with pytest.raises(RuntimeError, match="Operation failed after"):
            retry_on_connection_error(func, max_retries=3, initial_delay=0.01)

    def test_non_retryable_error(self):
        """Test that a non-connection error is re-raised unchanged, not wrapped."""
        # Arrange
        func = Mock(side_effect=ValueError("Invalid input"))
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid input"):
            retry_on_connection_error(func, max_retries=3, initial_delay=0.01)

    def test_non_retryable_error_is_not_retried(self):
        """Test that function does not retry on non-retryable errors."""
        # Arrange
        func = Mock(side_effect=ValueError("Invalid input"))
        # Act
        with pytest.raises(ValueError):
            retry_on_connection_error(func, max_retries=3, initial_delay=0.01)
        # Assert
        assert func.call_count == 1

    def test_custom_connection_error_checker(self):
        """Test that custom connection error checker is used."""

        # Arrange
        def is_custom_error(e: Exception) -> bool:
            return isinstance(e, ValueError)

        func = Mock(side_effect=[ValueError("Custom error"), "success"])
        # Act
        result = retry_on_connection_error(
            func, max_retries=3, initial_delay=0.01, is_connection_error=is_custom_error
        )
        # Assert
        assert result == "success"
        assert func.call_count == 2

    def test_exponential_backoff(self):
        """Test that exponential backoff is applied."""
        # Arrange
        func = Mock(side_effect=[ConnectionError("Connection refused"), "success"])
        initial_delay = 0.01
        backoff_multiplier = 2.0
        # Act
        with patch("time.sleep") as mock_sleep:
            retry_on_connection_error(
                func,
                max_retries=3,
                initial_delay=initial_delay,
                backoff_multiplier=backoff_multiplier,
            )
        # Assert
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] == initial_delay


class TestIsOpenSearchConnectionError:
    """Test is_opensearch_connection_error function."""

    def test_opensearch_connection_error(self):
        """Test that OpenSearch connection errors are detected."""
        # Arrange
        try:
            from opensearchpy.exceptions import (
                ConnectionError as OpenSearchConnectionError,
            )

            # OpenSearchConnectionError inherits from TransportError which needs error, info, status
            error = OpenSearchConnectionError("Connection failed", {}, {})
            # Act & Assert
            assert is_opensearch_connection_error(error) is True
        except (ImportError, TypeError):
            # If opensearchpy not available or exception structure differs, test string matching
            error = Exception("Connection failed")
            assert is_opensearch_connection_error(error) is True

    def test_transport_error(self):
        """Test that transport errors are detected."""
        # Arrange
        try:
            from opensearchpy.exceptions import TransportError

            # TransportError needs error, info, status parameters
            error = TransportError("Transport failed", {}, {})
            # Act & Assert
            assert is_opensearch_connection_error(error) is True
        except (ImportError, TypeError):
            # If opensearchpy not available or exception structure differs, test string matching
            error = Exception("Transport failed")
            assert is_opensearch_connection_error(error) is True

    def test_standard_connection_error(self):
        """Test that standard ConnectionError is detected."""
        # Arrange
        error = ConnectionError("Connection refused")
        # Act & Assert
        assert is_opensearch_connection_error(error) is True

    def test_error_string_matching(self):
        """Test that error strings are matched."""
        # Arrange
        error = ValueError("Connection timeout occurred")
        # Act & Assert
        assert is_opensearch_connection_error(error) is True

    def test_non_connection_error(self):
        """Test that non-connection errors are not detected."""
        # Arrange
        error = ValueError("Invalid input")
        # Act & Assert
        assert is_opensearch_connection_error(error) is False


class TestIsRequestsConnectionError:
    """Test is_requests_connection_error function."""

    def test_requests_connection_error(self):
        """Test that requests connection errors are detected."""
        # Arrange
        try:
            import requests.exceptions

            error = requests.exceptions.ConnectionError("Connection failed")
            # Act & Assert
            assert is_requests_connection_error(error) is True
        except ImportError:
            pytest.skip("requests library not available")

    def test_requests_timeout(self):
        """Test that requests timeout errors are detected."""
        # Arrange
        try:
            import requests.exceptions

            error = requests.exceptions.Timeout("Request timeout")
            # Act & Assert
            assert is_requests_connection_error(error) is True
        except ImportError:
            pytest.skip("requests library not available")

    def test_error_string_matching(self):
        """Test that error strings are matched."""
        # Arrange
        error = ValueError("Connection refused")
        # Act & Assert
        assert is_requests_connection_error(error) is True


class TestIsTimingErrors:
    """Test timing error detection functions."""

    def test_is_model_timing_error_unknown_model(self):
        """Test that Unknown model errors are detected."""
        # Arrange
        error = ValueError("Unknown model test_model")
        # Act & Assert
        assert is_model_timing_error(error) is True

    def test_is_model_timing_error_illegal_argument(self):
        """Test that IllegalArgumentException errors are detected."""
        # Arrange
        error = ValueError("IllegalArgumentException: invalid model")
        # Act & Assert
        assert is_model_timing_error(error) is True

    def test_is_feature_set_timing_error(self):
        """Test that feature set timing errors are detected."""
        # Arrange
        error = ValueError("NullPointerException in feature set")
        # Act & Assert
        assert is_feature_set_timing_error(error) is True

    def test_is_opensearch_timing_error(self):
        """Test that OpenSearch timing errors are detected."""
        # Arrange
        error = ValueError("StoredFeatureSet not found")
        # Act & Assert
        assert is_opensearch_timing_error(error) is True

    def test_non_timing_error(self):
        """Test that non-timing errors are not detected."""
        # Arrange
        error = ValueError("Invalid input")
        # Act & Assert
        assert is_model_timing_error(error) is False
        assert is_feature_set_timing_error(error) is False
        assert is_opensearch_timing_error(error) is False


class TestCheckFeatureSetErrorInResponse:
    """Test check_feature_set_error_in_response function."""

    def test_feature_set_error_in_response(self):
        """Test that feature set errors in response are detected."""
        # Arrange
        resp = {"error": {"reason": "NullPointerException in feature set"}}
        # Act & Assert
        assert check_feature_set_error_in_response(resp) is True

    def test_no_error_in_response(self):
        """Test that responses without errors return False."""
        # Arrange
        resp = {"hits": {"total": 10}}
        # Act & Assert
        assert check_feature_set_error_in_response(resp) is False

    def test_error_reason_parameter(self):
        """Test that error_reason parameter is checked."""
        # Arrange
        resp = {}
        error_reason = "NullPointerException"
        # Act & Assert
        assert check_feature_set_error_in_response(resp, error_reason) is True


class TestRetryFeatureSetQuery:
    """Test retry_feature_set_query function."""

    def test_success_on_first_attempt(self):
        """Test that query succeeds on first attempt."""
        # Arrange
        query_func = Mock(return_value={"hits": {"total": 10}})
        # Act
        result = retry_feature_set_query(
            query_func, "test_featureset", "test_index", "solr", max_retries=3
        )
        # Assert
        assert result == {"hits": {"total": 10}}
        assert query_func.call_count == 1

    def test_retry_on_timing_error(self):
        """Test that query retries on timing errors."""
        # Arrange
        query_func = Mock(
            side_effect=[
                ValueError("NullPointerException"),
                {"hits": {"total": 10}},
            ]
        )
        # Act
        result = retry_feature_set_query(
            query_func,
            "test_featureset",
            "test_index",
            "solr",
            max_retries=3,
            initial_delay=0.01,
        )
        # Assert
        assert result == {"hits": {"total": 10}}
        assert query_func.call_count == 2

    def test_retry_exhausted(self):
        """Test that QueryError is raised when retries exhausted."""
        # Arrange
        query_func = Mock(side_effect=ValueError("NullPointerException"))
        # Act & Assert
        with pytest.raises(QueryError, match="is not usable in queries after"):
            retry_feature_set_query(
                query_func,
                "test_featureset",
                "test_index",
                "solr",
                max_retries=3,
                initial_delay=0.01,
            )

    def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        # Arrange
        query_func = Mock(side_effect=ValueError("Invalid input"))
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid input"):
            retry_feature_set_query(
                query_func,
                "test_featureset",
                "test_index",
                "solr",
                max_retries=3,
                initial_delay=0.01,
            )


class TestRetryModelQuery:
    """Test retry_model_query function."""

    def test_success_on_first_attempt(self):
        """Test that query succeeds on first attempt."""
        # Arrange
        query_func = Mock(return_value={"hits": {"total": 10}})
        # Act
        result = retry_model_query(
            query_func, "test_model", "test_index", "solr", max_retries=3
        )
        # Assert
        assert result == {"hits": {"total": 10}}
        assert query_func.call_count == 1

    def test_retry_on_timing_error(self):
        """Test that query retries on timing errors."""
        # Arrange
        query_func = Mock(
            side_effect=[
                {"error": "Unknown model test_model"},
                {"hits": {"total": 10}},
            ]
        )
        # Act
        result = retry_model_query(
            query_func,
            "test_model",
            "test_index",
            "solr",
            max_retries=3,
            initial_delay=0.01,
        )
        # Assert
        assert result == {"hits": {"total": 10}}
        assert query_func.call_count == 2

    def test_retry_exhausted(self):
        """Test that ModelError is raised when retries exhausted."""
        # Arrange
        query_func = Mock(return_value={"error": "Unknown model test_model"})
        # Act & Assert
        from ltr.exceptions import ModelError

        with pytest.raises(ModelError, match="is not available after"):
            retry_model_query(
                query_func,
                "test_model",
                "test_index",
                "solr",
                max_retries=3,
                initial_delay=0.01,
            )


class TestRetryUntilTrue:
    """Test retry_until_true function."""

    def test_success_on_first_attempt(self):
        """Test that check succeeds on first attempt."""
        # Arrange
        check_func = Mock(return_value=True)
        # Act
        retry_until_true(check_func, max_retries=3, initial_delay=0.01)
        # Assert
        assert check_func.call_count == 1

    def test_retry_until_success(self):
        """Test that function retries until check succeeds."""
        # Arrange
        check_func = Mock(side_effect=[False, False, True])
        # Act
        retry_until_true(check_func, max_retries=3, initial_delay=0.01)
        # Assert
        assert check_func.call_count == 3

    def test_retry_exhausted(self):
        """Test that RuntimeError is raised when retries exhausted."""
        # Arrange
        check_func = Mock(return_value=False)
        # Act & Assert
        with pytest.raises(RuntimeError, match="Verification failed after"):
            retry_until_true(
                check_func,
                max_retries=3,
                initial_delay=0.01,
                error_message="Verification failed",
            )

    def test_custom_error_message(self):
        """Test that custom error message is used."""
        # Arrange
        check_func = Mock(return_value=False)
        # Act & Assert
        with pytest.raises(RuntimeError, match="Custom error message"):
            retry_until_true(
                check_func,
                max_retries=3,
                initial_delay=0.01,
                error_message="Custom error message",
            )
