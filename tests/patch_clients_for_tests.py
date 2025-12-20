"""
Test Port Patching for hello-ltr

This module patches client classes and the requests library to use test ports
instead of default ports, enabling integration tests to run without conflicts
with production services. It also adds automatic retry logic for network operations
to handle transient failures.

Port Mapping:
- Solr: 8983 → 18983 (if SOLR_PORT env var set)
- Elasticsearch: 9200 → 19200 (if ELASTICSEARCH_PORT env var set)
- OpenSearch: 9201 → 19201 (if OPENSEARCH_PORT env var set)

Retry Logic:
- Automatically retries network requests on connection errors, timeouts, and 5xx errors
- Uses exponential backoff: 0.1s, 0.2s, 0.4s delays
- Maximum 3 retry attempts per request

Usage:
    from tests.patch_clients_for_test_ports import patch_clients_for_test_ports, patch_requests_for_test_ports
    patch_clients_for_test_ports()
    patch_requests_for_test_ports()

Note: This module does NOT auto-patch on import. Functions must be called explicitly.
The test runner (tests/runner.py) automatically injects these calls as the first
cell in notebooks during test execution.

Implementation:
- Uses monkey patching to modify __init__ methods of client classes
- Patches are applied via importlib.reload to ensure changes take effect
- Only patches clients when corresponding environment variables are set
- Adds retry logic with exponential backoff for network operations
"""

import os
import sys
import time


def patch_requests_for_test_ports():
    """Patch requests library to rewrite URLs with hardcoded ports."""
    solr_port = os.environ.get("SOLR_PORT")
    elasticsearch_port = os.environ.get("ELASTICSEARCH_PORT")
    opensearch_port = os.environ.get("OPENSEARCH_PORT")

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

    def _retry_request(request_func, *args, max_retries=3, **kwargs):
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
            self._original_request, method, url, max_retries=3, **kwargs
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
            max_retries=3,
            **kwargs,
        )

    def patched_post(url, **kwargs):
        """Patched POST request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_post,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=3,
            **kwargs,
        )

    def patched_put(url, **kwargs):
        """Patched PUT request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_put,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=3,
            **kwargs,
        )

    def patched_delete(url, **kwargs):
        """Patched DELETE request that rewrites URLs and adds retry logic."""
        rewritten_url = rewrite_url(url)
        return _retry_request(
            requests._original_delete,  # type: ignore[attr-defined]
            rewritten_url,
            max_retries=3,
            **kwargs,
        )

    requests.get = patched_get
    requests.post = patched_post
    requests.put = patched_put
    requests.delete = patched_delete


def _reload_or_import_module(module_path):
    """
    Reload a module if it's already imported, otherwise import it.

    This helper function ensures we're working with the latest version of a module,
    which is important when patching classes that may have been imported before
    the patch is applied.

    Args:
        module_path: Full module path as string (e.g., 'ltr.client.solr_client')

    Returns:
        The module object (reloaded or newly imported)

    Example:
        >>> solr_module = _reload_or_import_module('ltr.client.solr_client')
        >>> # Module is reloaded if already imported, or imported if not
    """
    import importlib

    if module_path in sys.modules:
        module = sys.modules[module_path]
        importlib.reload(module)
        return module
    else:
        # Import the module dynamically using importlib
        return importlib.import_module(module_path)


# Track patching state to avoid redundant patching
_patching_state = {"done": False, "ports": None}


def patch_clients_for_test_ports():
    """
    Patch client classes to use test ports from environment variables.

    This function is idempotent - calling it multiple times with the same ports
    is safe but inefficient. A guard prevents redundant patching if ports haven't changed.
    """
    # Only patch if test ports are set (indicating we're running tests)
    solr_port = os.environ.get("SOLR_PORT")
    elasticsearch_port = os.environ.get("ELASTICSEARCH_PORT")
    opensearch_port = os.environ.get("OPENSEARCH_PORT")

    if not any([solr_port, elasticsearch_port, opensearch_port]):
        # Not running tests, don't patch
        return

    # Check if we've already patched with these exact ports
    current_ports = (solr_port, elasticsearch_port, opensearch_port)
    if _patching_state["done"] and _patching_state["ports"] == current_ports:
        # Already patched with these ports, skip redundant patching
        return

    # Patch requests library first to handle hardcoded URLs
    patch_requests_for_test_ports()

    # Import here to avoid circular imports and ensure clients are loaded
    # Force reload to ensure we're patching the right modules
    # Use helper function to eliminate code duplication
    solr_client_module = _reload_or_import_module("ltr.client.solr_client")
    elastic_client_module = _reload_or_import_module("ltr.client.elastic_client")
    opensearch_client_module = _reload_or_import_module("ltr.client.opensearch_client")

    # Patch SolrClient
    if solr_port:
        original_init = solr_client_module.SolrClient.__init__

        def patched_solr_init(self):
            """Patched SolrClient.__init__ that uses test port instead of default.

            Calls the original __init__ then modifies the connection endpoint
            to use the test port (from SOLR_PORT env var) for non-docker connections.
            """
            original_init(self)
            if not self.docker:  # Only patch non-docker connections
                self.solr_base_ep = f"http://localhost:{solr_port}/solr"

        solr_client_module.SolrClient.__init__ = patched_solr_init

    # Patch ElasticClient
    if elasticsearch_port:
        original_init = elastic_client_module.ElasticClient.__init__

        def patched_elastic_init(self, configs_dir="."):
            """Patched ElasticClient.__init__ that uses test port instead of default.

            Calls the original __init__ then modifies the connection endpoint
            and Elasticsearch client to use the test port (from ELASTICSEARCH_PORT env var)
            for non-docker connections.

            Args:
                configs_dir: Configuration directory (passed to original __init__)
            """
            original_init(self, configs_dir)
            if not self.docker:  # Only patch non-docker connections
                self.elastic_ep = f"http://{self.host}:{elasticsearch_port}/_ltr"
                from elasticsearch import Elasticsearch

                self.es = Elasticsearch(f"http://{self.host}:{elasticsearch_port}")

        elastic_client_module.ElasticClient.__init__ = patched_elastic_init

        # Patch ElasticClient timing methods for test environments
        # Test environments may be slower, so increase delays and retries
        original_reset_ltr = elastic_client_module.ElasticClient.reset_ltr
        original_create_featureset = (
            elastic_client_module.ElasticClient.create_featureset
        )

        def patched_reset_ltr(self, index: str) -> None:
            """Patched reset_ltr with longer delay for test environments."""
            original_reset_ltr(self, index)
            # Add extra delay in test environments (original has 200ms, we add 300ms more)
            time.sleep(0.3)

        def patched_create_featureset(self, index: str, name: str, ftr_config):
            """Patched create_featureset with additional retries for test environments."""
            try:
                # Call original method (which has 5 retries)
                original_create_featureset(self, index, name, ftr_config)
            except RuntimeError as e:
                # If original failed due to timing, add extra retries
                error_str = str(e)
                if (
                    "not usable in queries" in error_str
                    or "Unknown featureset" in error_str
                ):
                    # Feature set exists but not ready - add extra retries
                    max_additional_retries = 5
                    for attempt in range(max_additional_retries):
                        try:
                            test_params = {
                                "query": {
                                    "bool": {
                                        "filter": [
                                            {
                                                "sltr": {
                                                    "_name": "test_features",
                                                    "featureset": name,
                                                    "params": {},
                                                }
                                            }
                                        ]
                                    }
                                },
                                "size": 0,
                            }
                            test_resp = self.es.search(index=index, body=test_params)
                            if "error" not in test_resp:
                                return  # Feature set is ready
                        except Exception:
                            pass
                        if attempt < max_additional_retries - 1:
                            time.sleep(0.5)  # 500ms delay between retries
                    # Still not ready after extra retries, re-raise original error
                raise

        elastic_client_module.ElasticClient.reset_ltr = patched_reset_ltr
        elastic_client_module.ElasticClient.create_featureset = (
            patched_create_featureset
        )

    # Patch OpenSearchClient
    if opensearch_port:
        original_init = opensearch_client_module.OpenSearchClient.__init__

        def patched_opensearch_init(self, configs_dir="."):
            """Patched OpenSearchClient.__init__ that uses test port instead of default.

            Calls the original __init__ then modifies the connection endpoint
            and OpenSearch client to use the test port (from OPENSEARCH_PORT env var)
            for non-docker connections.

            Args:
                configs_dir: Configuration directory (passed to original __init__)
            """
            original_init(self, configs_dir)
            if not self.docker:  # Only patch non-docker connections
                self.opensearch_ep = f"http://{self.host}:{opensearch_port}/_ltr"
                from opensearchpy import OpenSearch

                self.opensearch = OpenSearch(f"http://{self.host}:{opensearch_port}")

        opensearch_client_module.OpenSearchClient.__init__ = patched_opensearch_init

        # Patch OpenSearchClient timing methods for test environments
        # Test environments may be slower, so increase delays and retries
        original_reset_ltr_opensearch = (
            opensearch_client_module.OpenSearchClient.reset_ltr
        )
        original_create_featureset_opensearch = (
            opensearch_client_module.OpenSearchClient.create_featureset
        )

        def patched_reset_ltr_opensearch(self, index: str) -> None:
            """Patched reset_ltr with longer delay for test environments."""
            original_reset_ltr_opensearch(self, index)
            # Add extra delay in test environments (original has 200ms, we add 300ms more)
            time.sleep(0.3)

        def patched_create_featureset_opensearch(
            self, index: str, name: str, ftr_config
        ):
            """Patched create_featureset with additional retries for test environments."""
            try:
                # Call original method (which has 5 retries)
                original_create_featureset_opensearch(self, index, name, ftr_config)
            except RuntimeError as e:
                # If original failed due to timing, add extra retries
                error_str = str(e)
                if (
                    "not usable in queries" in error_str
                    or "Unknown featureset" in error_str
                ):
                    # Feature set exists but not ready - add extra retries
                    max_additional_retries = 5
                    for attempt in range(max_additional_retries):
                        try:
                            test_params = {
                                "query": {
                                    "bool": {
                                        "filter": [
                                            {
                                                "sltr": {
                                                    "_name": "test_features",
                                                    "featureset": name,
                                                    "params": {},
                                                }
                                            }
                                        ]
                                    }
                                },
                                "size": 0,
                            }
                            test_resp = self.opensearch.search(
                                index=index, body=test_params
                            )
                            if "error" not in test_resp:
                                return  # Feature set is ready
                        except Exception:
                            pass
                        if attempt < max_additional_retries - 1:
                            time.sleep(0.5)  # 500ms delay between retries
                    # Still not ready after extra retries, re-raise original error
                raise

        opensearch_client_module.OpenSearchClient.reset_ltr = (
            patched_reset_ltr_opensearch
        )
        opensearch_client_module.OpenSearchClient.create_featureset = (
            patched_create_featureset_opensearch
        )

    # Mark patching as done and store ports
    _patching_state["done"] = True
    _patching_state["ports"] = current_ports


# Note: Patching is NOT done automatically on import to avoid surprising side effects.
# Call patch_clients_for_test_ports() explicitly when needed.
# The test runner (tests/runner.py) injects this as the first cell in notebooks.
