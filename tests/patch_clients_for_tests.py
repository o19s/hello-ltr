"""
Test Port Patching for hello-ltr

This module provides utilities for test environments:
1. Patches requests library to rewrite URLs with hardcoded ports
2. Adds timing adjustments for test environments (reset_ltr delays)

Port Configuration:
- Clients now use dependency injection via port parameters
- Ports are passed via environment variables or explicit parameters
- No monkey patching of client __init__ methods needed

Retry Logic:
- Automatically retries network requests on connection errors, timeouts, and 5xx errors
- Uses exponential backoff: 0.1s, 0.2s, 0.4s delays
- Maximum 3 retry attempts per request
- Note: Client methods already have comprehensive retry logic, so this only handles
  direct requests library calls that bypass client methods

Configuration:
- TEST_RESET_LTR_DELAY: Extra delay after reset_ltr() in test environments (default: 0.3s)

Usage:
    from tests.patch_clients_for_tests import patch_requests_for_test_ports
    patch_requests_for_test_ports()

Note: Client port configuration is now handled via dependency injection.
The test runner (tests/notebooks/runner.py) sets environment variables
and uses client factory functions for dependency injection.
"""

import os
import time

from ltr.logger import get_logger
from tests.port_management import get_port

logger = get_logger(__name__)

# Retry configuration constants
REQUESTS_MAX_RETRIES = 3


def patch_requests_for_test_ports():
    """Patch requests library to rewrite URLs with hardcoded ports."""
    solr_port = get_port("SOLR_PORT")
    elasticsearch_port = get_port("ELASTICSEARCH_PORT")
    opensearch_port = get_port("OPENSEARCH_PORT")

    if not any([solr_port, elasticsearch_port, opensearch_port]):
        return

    try:
        import requests
    except ImportError:
        return

    # Store original request method
    if not hasattr(requests.Session, "_original_request"):
        requests.Session._original_request = requests.Session.request  # type: ignore[attr-defined]

    def rewrite_url(url):
        """Rewrite URL to use test ports if they match standard ports."""
        if solr_port and ":8983" in url:
            url = url.replace(":8983", f":{solr_port}")
        if elasticsearch_port and ":9200" in url:
            url = url.replace(":9200", f":{elasticsearch_port}")
        if opensearch_port and ":9201" in url:
            url = url.replace(":9201", f":{opensearch_port}")
        return url

    def _should_retry_error(exception):
        """Check if an exception should trigger a retry."""
        if exception is None:
            return False

        # Check for connection errors, timeouts, and 5xx server errors
        exception_str = str(exception).lower()
        error_types = (
            "connection",
            "timeout",
            "timed out",
            "network",
            "errno",
            "econnrefused",
            "econnreset",
        )

        # Check if it's a requests exception with retryable status
        if hasattr(exception, "response") and exception.response is not None:
            status_code = getattr(exception.response, "status_code", None)
            if status_code and 500 <= status_code < 600:
                return True

        return any(err_type in exception_str for err_type in error_types)

    def _retry_request(request_func, *args, max_retries=REQUESTS_MAX_RETRIES, **kwargs):
        """
        Execute a request with automatic retry logic for transient failures.

        Uses exponential backoff: 0.1s, 0.2s, 0.4s delays between retries.
        Retries on connection errors, timeouts, and 5xx server errors.

        Args:
            request_func: The request function to call (can be bound method or function)
            *args: Positional arguments to pass to request_func
            max_retries: Maximum number of retry attempts (default: 3)
            **kwargs: Keyword arguments to pass to request_func
        """
        base_delay = 0.1  # Start with 100ms

        for attempt in range(max_retries):
            try:
                return request_func(*args, **kwargs)
            except Exception as e:
                # Check if we should retry this error
                if attempt < max_retries - 1 and _should_retry_error(e):
                    delay = base_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                # Either not retryable or last attempt - raise the exception
                raise

    def patched_request(self, method, url, **kwargs):
        """Patched request method that rewrites URLs and adds retry logic."""
        url = rewrite_url(url)
        return _retry_request(
            self._original_request,
            method,
            url,
            max_retries=REQUESTS_MAX_RETRIES,
            **kwargs,
        )

    requests.Session.request = patched_request  # type: ignore[assignment]

    # Also patch the module-level functions
    if not hasattr(requests, "_original_get"):
        requests._original_get = requests.get  # type: ignore[attr-defined]
        requests._original_post = requests.post  # type: ignore[attr-defined]
        requests._original_put = requests.put  # type: ignore[attr-defined]
        requests._original_delete = requests.delete  # type: ignore[attr-defined]

    def patched_get(url, **kwargs):
        """Patched GET request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_get,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=REQUESTS_MAX_RETRIES,
            **kwargs,
        )

    def patched_post(url, **kwargs):
        """Patched POST request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_post,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=REQUESTS_MAX_RETRIES,
            **kwargs,
        )

    def patched_put(url, **kwargs):
        """Patched PUT request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_put,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=REQUESTS_MAX_RETRIES,
            **kwargs,
        )

    def patched_delete(url, **kwargs):
        """Patched DELETE request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_delete,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=REQUESTS_MAX_RETRIES,
            **kwargs,
        )

    requests.get = patched_get
    requests.post = patched_post
    requests.put = patched_put
    requests.delete = patched_delete


def patch_reset_ltr_timing():
    """
    Patch reset_ltr methods to add extra delays for test environments.

    Test environments may be slower, so this adds extra delay after reset_ltr()
    operations. This can be configured via TEST_RESET_LTR_DELAY env var (default: 0.3s).

    Note: This is a minimal patch that only affects timing, not port configuration.
    Port configuration is now handled via dependency injection.
    """
    import importlib

    # Check if we should apply timing patches
    extra_delay = float(os.environ.get("TEST_RESET_LTR_DELAY", "0.3"))
    if extra_delay <= 0:
        return

    # Only patch if test ports are set (indicating we're running tests)
    solr_port = get_port("SOLR_PORT")
    elasticsearch_port = get_port("ELASTICSEARCH_PORT")
    opensearch_port = get_port("OPENSEARCH_PORT")

    if not any([solr_port, elasticsearch_port, opensearch_port]):
        # Not running tests, don't patch
        return

    # Patch ElasticClient reset_ltr timing
    if elasticsearch_port:
        try:
            elastic_client_module = importlib.import_module("ltr.client.elastic_client")
            original_reset_ltr = elastic_client_module.ElasticClient.reset_ltr

            def patched_reset_ltr(self, index: str) -> None:
                """Patched reset_ltr with longer delay for test environments."""
                original_reset_ltr(self, index)
                if extra_delay > 0:
                    time.sleep(extra_delay)

            elastic_client_module.ElasticClient.reset_ltr = patched_reset_ltr
        except Exception:
            # If patching fails, continue without it
            pass

    # Patch OpenSearchClient reset_ltr timing
    if opensearch_port:
        try:
            opensearch_client_module = importlib.import_module(
                "ltr.client.opensearch_client"
            )
            original_reset_ltr = opensearch_client_module.OpenSearchClient.reset_ltr

            def patched_reset_ltr(self, index: str) -> None:
                """Patched reset_ltr with longer delay for test environments."""
                original_reset_ltr(self, index)
                if extra_delay > 0:
                    time.sleep(extra_delay)

            opensearch_client_module.OpenSearchClient.reset_ltr = patched_reset_ltr
        except Exception:
            # If patching fails, continue without it
            pass


# Backward compatibility: patch_clients_for_test_ports now only patches requests
# Client port configuration is handled via dependency injection
def patch_clients_for_test_ports():
    """
    Legacy function name for backward compatibility.

    This function now only patches the requests library for hardcoded URLs.
    Client port configuration is handled via dependency injection (port parameters).

    Note: This function is kept for backward compatibility but is no longer needed
    for client port configuration. Use dependency injection instead.
    """
    patch_requests_for_test_ports()
    patch_reset_ltr_timing()
