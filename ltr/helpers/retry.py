"""Retry utilities for handling transient failures with exponential backoff."""

import time
from collections.abc import Callable
from typing import Optional, TypeVar

from ltr.exceptions import QueryError
from ltr.logger import get_logger
from ltr.types import JSONDict

T = TypeVar("T")

logger = get_logger(__name__)


def retry_on_connection_error(
    func: Callable[[], T],
    max_retries: int = 5,
    initial_delay: float = 0.5,
    backoff_multiplier: float = 1.5,
    is_connection_error: Optional[Callable[[Exception], bool]] = None,
) -> T:
    """
    Retry a function call on connection errors with exponential backoff.

    Args:
        func: The function to call (should take no arguments)
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before first retry (default: 0.5)
        backoff_multiplier: Multiplier for exponential backoff (default: 1.5)
        is_connection_error: Optional function to determine if an exception is a connection error.
                            If None, uses default heuristics.

    Returns:
        The return value of func() if successful.

    Raises:
        RuntimeError: If all retries are exhausted, with a helpful error message.
        Any exception raised by func() if it's not a connection error.
    """
    retry_delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exception = e
            error_str = str(e)

            # Determine if this is a connection error
            if is_connection_error is not None:
                should_retry = is_connection_error(e)
            else:
                # Default heuristics for connection errors
                should_retry = (
                    isinstance(e, (ConnectionError, OSError))
                    or "connection" in error_str.lower()
                    or "refused" in error_str.lower()
                    or "timeout" in error_str.lower()
                    or "network" in error_str.lower()
                )

            if should_retry and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= backoff_multiplier
                continue
            # Not a connection error - re-raise the original exception
            if not should_retry:
                raise last_exception
            # Last attempt failed - raise RuntimeError with context
            raise RuntimeError(
                f"Operation failed after {attempt + 1} attempts. "
                f"Last error: {last_exception}"
            ) from last_exception

    # Exhausted all retries - this should never be reached due to raise above,
    # but satisfies type checker requirement that all paths return/raise
    assert last_exception is not None, "Retry loop completed without exception"
    raise RuntimeError(
        f"Operation failed after {max_retries} attempts. Last error: {last_exception}"
    ) from last_exception


def is_opensearch_connection_error(exception: Exception) -> bool:
    """
    Check if an exception is an OpenSearch connection error.

    Args:
        exception: The exception to check

    Returns:
        True if the exception is a connection error, False otherwise
    """
    from opensearchpy.exceptions import (
        ConnectionError as OpenSearchConnectionError,
    )
    from opensearchpy.exceptions import (
        NotFoundError,
        TransportError,
    )

    # NotFoundError is not a connection error - it means the resource doesn't exist
    # and should not be retried
    if isinstance(exception, NotFoundError):
        return False

    error_str = str(exception)
    return (
        isinstance(exception, (OpenSearchConnectionError, TransportError))
        or "connection" in error_str.lower()
        or "refused" in error_str.lower()
        or "timeout" in error_str.lower()
        or "network" in error_str.lower()
        or isinstance(exception, (ConnectionError, OSError))
    )


def is_requests_connection_error(exception: Exception) -> bool:
    """
    Check if an exception is a requests library connection error.

    Args:
        exception: The exception to check

    Returns:
        True if the exception is a connection error, False otherwise
    """
    try:
        import requests.exceptions
    except ImportError:
        # requests not available, use default heuristics
        error_str = str(exception)
        return (
            isinstance(exception, (ConnectionError, OSError))
            or "connection" in error_str.lower()
            or "refused" in error_str.lower()
            or "timeout" in error_str.lower()
            or "network" in error_str.lower()
        )

    error_str = str(exception)
    return (
        isinstance(
            exception,
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ),
        )
        or "connection" in error_str.lower()
        or "refused" in error_str.lower()
        or "timeout" in error_str.lower()
        or "network" in error_str.lower()
        or isinstance(exception, (ConnectionError, OSError))
    )


def is_opensearch_timing_error(exception: Exception) -> bool:
    """
    Check if an exception is an OpenSearch timing error that should be retried.

    These are application-level errors that occur when resources (models, feature sets)
    are not yet ready after creation, typically due to internal indexing delays.

    Args:
        exception: The exception to check

    Returns:
        True if the exception is a timing error that should be retried, False otherwise
    """
    error_str = str(exception)

    # Extract error details from exception attributes
    error_info = getattr(exception, "info", {})
    error_attr = getattr(exception, "error", "")
    error_reason = ""

    # Try to extract error reason from info dict
    if isinstance(error_info, dict):
        error_detail = error_info.get("error", {})
        if isinstance(error_detail, dict):
            error_reason = error_detail.get("reason", "")

    # Also check error attribute directly (might be a string)
    if isinstance(error_attr, str):
        error_reason = error_reason or error_attr

    # Check for timing-related error patterns
    timing_patterns = [
        "Unknown model",
        "IllegalArgumentException",
        "NullPointerException",
        "getAndParse",
        "optimize()",
        "StoredFeatureSet",
    ]

    # Check error string and reason
    error_text = f"{error_str} {error_reason}".lower()
    return any(pattern.lower() in error_text for pattern in timing_patterns)


def is_feature_set_timing_error(exception: Exception) -> bool:
    """
    Check if an exception indicates a feature set timing issue that should be retried.

    Feature sets may exist but not be immediately usable due to internal indexing delays
    in the LTR plugin. These errors are transient and should be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the exception indicates a feature set timing error, False otherwise
    """
    error_str = str(exception)

    # Extract error details from exception attributes
    error_info = getattr(exception, "info", {})
    error_attr = getattr(exception, "error", "")
    error_reason = ""

    # Try to extract error reason from info dict
    if isinstance(error_info, dict):
        error_detail = error_info.get("error", {})
        if isinstance(error_detail, dict):
            error_reason = error_detail.get("reason", "")

    # Also check error attribute directly (might be a string)
    if isinstance(error_attr, str):
        error_reason = error_reason or error_attr

    # Check for feature set timing error patterns
    timing_patterns = [
        "NullPointerException",
        "getAndParse",
        "optimize()",
        "StoredFeatureSet",
    ]

    # Check error string and reason
    error_text = f"{error_str} {error_reason}".lower()
    return any(pattern.lower() in error_text for pattern in timing_patterns)


def is_model_timing_error(exception: Exception) -> bool:
    """
    Check if an exception indicates a model timing issue that should be retried.

    Models may not be immediately available after creation due to internal indexing delays
    in the LTR plugin. These errors are transient and should be retried.

    Args:
        exception: The exception to check

    Returns:
        True if the exception indicates a model timing error, False otherwise
    """
    error_str = str(exception)

    # Extract error details from exception attributes
    error_info = getattr(exception, "info", {})
    error_attr = getattr(exception, "error", "")
    error_reason = ""

    # Try to extract error reason from info dict
    if isinstance(error_info, dict):
        error_detail = error_info.get("error", {})
        if isinstance(error_detail, dict):
            error_reason = error_detail.get("reason", "")

    # Also check error attribute directly (might be a string)
    if isinstance(error_attr, str):
        error_reason = error_reason or error_attr

    # Check for model timing error patterns
    timing_patterns = [
        "Unknown model",
        "IllegalArgumentException",
    ]

    # Check error string and reason
    error_text = f"{error_str} {error_reason}".lower()
    return any(pattern.lower() in error_text for pattern in timing_patterns)


def check_feature_set_error_in_response(
    resp: JSONDict, error_reason: Optional[str] = None
) -> bool:
    """
    Check if a response contains a feature set timing error.

    Args:
        resp: API response dictionary.
        error_reason: Optional error reason string to check.

    Returns:
        True if the response indicates a feature set timing error, False otherwise.
    """
    if error_reason:
        timing_patterns = [
            "NullPointerException",
            "getAndParse",
            "optimize()",
            "StoredFeatureSet",
        ]
        return any(pattern in error_reason for pattern in timing_patterns)

    if "error" in resp:
        error_detail = resp.get("error", {})
        if isinstance(error_detail, dict):
            reason = error_detail.get("reason", "")
            timing_patterns = [
                "NullPointerException",
                "getAndParse",
                "optimize()",
                "StoredFeatureSet",
            ]
            return any(pattern in reason for pattern in timing_patterns)

    return False


def retry_feature_set_query(
    query_func: Callable[[], JSONDict],
    featureset: str,
    index: str,
    client_name: str,
    max_retries: int = 5,
    initial_delay: float = 0.2,
    backoff_multiplier: float = 1.5,
) -> JSONDict:
    """
    Retry a feature set query with exponential backoff on timing errors.

    Handles retries for feature set queries that may fail due to timing issues
    (feature set not yet indexed/ready). Checks both response errors and exceptions.
    The query_func should handle validation internally and may raise ValueError
    for invalid responses.

    Args:
        query_func: Function that executes the query, validates the response,
            and returns a response dict. May raise ValueError for invalid responses.
        featureset: Name of the feature set being queried (for error messages).
        index: Index name (for error messages).
        client_name: Client name (for error messages).
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        backoff_multiplier: Multiplier for exponential backoff.

    Returns:
        JSONDict: Successful query response.

    Raises:
        QueryError: If the query fails after all retries or encounters a non-retryable error.
    """
    retry_delay = initial_delay
    resp: Optional[JSONDict] = None

    for attempt in range(max_retries):
        try:
            resp = query_func()

            # Check for feature set timing errors in response (before validation)
            if "error" in resp:
                error_detail = resp.get("error", {})
                if isinstance(error_detail, dict):
                    error_reason = error_detail.get("reason", "")
                    if check_feature_set_error_in_response(resp, error_reason):
                        if attempt < max_retries - 1:
                            logger.debug(
                                f"Feature set '{featureset}' not yet usable in query "
                                f"(attempt {attempt + 1}/{max_retries}), retrying..."
                            )
                            time.sleep(retry_delay)
                            retry_delay *= backoff_multiplier
                            continue
                        else:
                            raise QueryError(
                                f"Feature set '{featureset}' is not usable in queries after {max_retries} attempts. "
                                f"Error: {error_reason}. The feature set may need more time to be fully indexed. "
                                f"Try waiting a moment and using the feature set again.",
                                index=index,
                                client_name=client_name,
                            )

            # Success - return response
            return resp

        except ValueError as e:
            # Check if it's a feature set timing error
            if is_feature_set_timing_error(e):
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Feature set '{featureset}' not yet usable "
                        f"(attempt {attempt + 1}/{max_retries}), retrying..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= backoff_multiplier
                    continue
                else:
                    raise QueryError(
                        f"Feature set '{featureset}' is not usable in queries after {max_retries} attempts. "
                        f"Error: {str(e)}",
                        index=index,
                        client_name=client_name,
                    ) from e
            # Re-raise other ValueError exceptions
            raise

    # Should not reach here, but handle case where resp is None
    if resp is None:
        raise QueryError(
            f"Feature set '{featureset}' query failed: no response received after {max_retries} attempts",
            index=index,
            client_name=client_name,
        )

    return resp


def retry_model_query(
    query_func: Callable[[], JSONDict],
    model_name: str,
    index: str,
    client_name: str,
    max_retries: int = 5,
    initial_delay: float = 0.5,
    backoff_multiplier: float = 1.5,
) -> JSONDict:
    """
    Retry a model query with exponential backoff on timing errors.

    Handles retries for model queries that may fail due to timing issues
    (model not yet available after creation). Checks both response errors and exceptions.

    Args:
        query_func: Function that executes the query, validates the response,
            and returns a response dict. May raise ValueError for invalid responses.
        model_name: Name of the model being queried (for error messages).
        index: Index name (for error messages).
        client_name: Client name (for error messages).
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        backoff_multiplier: Multiplier for exponential backoff.

    Returns:
        JSONDict: Successful query response.

    Raises:
        ModelError: If the query fails after all retries or encounters a non-retryable error.
    """
    from ltr.exceptions import ModelError

    retry_delay = initial_delay
    resp: Optional[JSONDict] = None

    for attempt in range(max_retries):
        try:
            resp = query_func()

            # Check for model timing errors in response (before validation)
            if "error" in resp:
                error_str = str(resp.get("error", ""))
                if (
                    "Unknown model" in error_str
                    or "IllegalArgumentException" in error_str
                ):
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"Model '{model_name}' not yet available "
                            f"(attempt {attempt + 1}/{max_retries}), retrying..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= backoff_multiplier
                        continue
                    else:
                        raise ModelError(
                            f"Model '{model_name}' is not available after {max_retries} attempts. "
                            f"Error: {error_str}. This may indicate a timing issue with the LTR plugin "
                            f"or the model was not successfully created.",
                            model_name=model_name,
                            operation="query",
                            context={"index": index},
                        )

            # Success - return response
            return resp

        except ValueError as e:
            # Check if it's a model timing error
            if is_model_timing_error(e):
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Model '{model_name}' not yet available "
                        f"(attempt {attempt + 1}/{max_retries}), retrying..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= backoff_multiplier
                    continue
                else:
                    raise ModelError(
                        f"Model '{model_name}' is not available after {max_retries} attempts. "
                        f"Error: {str(e)}. This may indicate a timing issue with the LTR plugin "
                        f"or the model was not successfully created.",
                        model_name=model_name,
                        operation="query",
                        context={"index": index},
                    ) from e
            # Re-raise other ValueError exceptions
            raise

    # Should not reach here, but handle case where resp is None
    if resp is None:
        raise ModelError(
            f"Model '{model_name}' query failed: no response received after {max_retries} attempts",
            model_name=model_name,
            operation="query",
            context={"index": index},
        )

    return resp


def retry_until_true(
    check_func: Callable[[], bool],
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_multiplier: float = 2.0,
    error_message: str = "Verification failed",
) -> None:
    """
    Retry a check function until it returns True, with exponential backoff.

    Useful for verification loops that check if a resource exists or is ready.

    Args:
        check_func: Function that returns True when verification succeeds, False otherwise.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        backoff_multiplier: Multiplier for exponential backoff.
        error_message: Error message to include if all retries are exhausted.

    Raises:
        RuntimeError: If check_func never returns True after all retries.
    """
    retry_delay = initial_delay

    for attempt in range(max_retries):
        if check_func():
            return  # Success
        # Check failed, retry if we have attempts left
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
            retry_delay *= backoff_multiplier
            continue
        # All retries exhausted
        raise RuntimeError(f"{error_message} after {max_retries} attempts.")
