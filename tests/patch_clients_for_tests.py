"""
Test Port Patching for hello-ltr

This module patches client classes and the requests library to use test ports
instead of default ports, enabling integration tests to run without conflicts
with production services.

Port Mapping:
- Solr: 8983 → 18983 (if SOLR_PORT env var set)
- Elasticsearch: 9200 → 19200 (if ELASTICSEARCH_PORT env var set)
- OpenSearch: 9201 → 19201 (if OPENSEARCH_PORT env var set)

Usage:
    from tests.patch_clients_for_tests import patch_clients_for_test_ports, patch_requests_for_test_ports
    patch_clients_for_test_ports()
    patch_requests_for_test_ports()

Note: This module does NOT auto-patch on import. Functions must be called explicitly.
The test runner (tests/runner.py) automatically injects these calls as the first
cell in notebooks during test execution.

Implementation:
- Uses monkey patching to modify __init__ methods of client classes
- Patches are applied via importlib.reload to ensure changes take effect
- Only patches clients when corresponding environment variables are set
"""
import os
import sys

def patch_requests_for_test_ports():
    """Patch requests library to rewrite URLs with hardcoded ports."""
    solr_port = os.environ.get('SOLR_PORT')
    elasticsearch_port = os.environ.get('ELASTICSEARCH_PORT')
    opensearch_port = os.environ.get('OPENSEARCH_PORT')
    
    if not any([solr_port, elasticsearch_port, opensearch_port]):
        return
    
    try:
        import requests
    except ImportError:
        return
    
    # Store original request method
    if not hasattr(requests.Session, '_original_request'):
        requests.Session._original_request = requests.Session.request
    
    def rewrite_url(url):
        """Rewrite URL to use test ports if they match standard ports."""
        if solr_port and ':8983' in url:
            url = url.replace(':8983', f':{solr_port}')
        if elasticsearch_port and ':9200' in url:
            url = url.replace(':9200', f':{elasticsearch_port}')
        if opensearch_port and ':9201' in url:
            url = url.replace(':9201', f':{opensearch_port}')
        return url
    
    def patched_request(self, method, url, **kwargs):
        """Patched request method that rewrites URLs."""
        url = rewrite_url(url)
        return self._original_request(method, url, **kwargs)
    
    requests.Session.request = patched_request
    
    # Also patch the module-level functions
    if not hasattr(requests, '_original_get'):
        requests._original_get = requests.get
        requests._original_post = requests.post
        requests._original_put = requests.put
        requests._original_delete = requests.delete
    
    def patched_get(url, **kwargs):
        return requests._original_get(rewrite_url(url), **kwargs)
    
    def patched_post(url, **kwargs):
        return requests._original_post(rewrite_url(url), **kwargs)
    
    def patched_put(url, **kwargs):
        return requests._original_put(rewrite_url(url), **kwargs)
    
    def patched_delete(url, **kwargs):
        return requests._original_delete(rewrite_url(url), **kwargs)
    
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

def patch_clients_for_test_ports():
    """Patch client classes to use test ports from environment variables."""
    # Only patch if test ports are set (indicating we're running tests)
    solr_port = os.environ.get('SOLR_PORT')
    elasticsearch_port = os.environ.get('ELASTICSEARCH_PORT')
    opensearch_port = os.environ.get('OPENSEARCH_PORT')
    
    if not any([solr_port, elasticsearch_port, opensearch_port]):
        # Not running tests, don't patch
        return
    
    # Patch requests library first to handle hardcoded URLs
    patch_requests_for_test_ports()
    
    # Import here to avoid circular imports and ensure clients are loaded
    # Force reload to ensure we're patching the right modules
    # Use helper function to eliminate code duplication
    solr_client_module = _reload_or_import_module('ltr.client.solr_client')
    elastic_client_module = _reload_or_import_module('ltr.client.elastic_client')
    opensearch_client_module = _reload_or_import_module('ltr.client.opensearch_client')
    
    # Patch SolrClient
    if solr_port:
        original_init = solr_client_module.SolrClient.__init__
        def patched_solr_init(self):
            original_init(self)
            if not self.docker:  # Only patch non-docker connections
                self.solr_base_ep = f'http://localhost:{solr_port}/solr'
        solr_client_module.SolrClient.__init__ = patched_solr_init
    
    # Patch ElasticClient
    if elasticsearch_port:
        original_init = elastic_client_module.ElasticClient.__init__
        def patched_elastic_init(self, configs_dir='.'):
            original_init(self, configs_dir)
            if not self.docker:  # Only patch non-docker connections
                self.elastic_ep = f'http://{self.host}:{elasticsearch_port}/_ltr'
                from elasticsearch import Elasticsearch
                self.es = Elasticsearch(f'http://{self.host}:{elasticsearch_port}')
        elastic_client_module.ElasticClient.__init__ = patched_elastic_init
    
    # Patch OpenSearchClient
    if opensearch_port:
        original_init = opensearch_client_module.OpenSearchClient.__init__
        def patched_opensearch_init(self, configs_dir='.'):
            original_init(self, configs_dir)
            if not self.docker:  # Only patch non-docker connections
                self.opensearch_ep = f'http://{self.host}:{opensearch_port}/_ltr'
                from opensearchpy import OpenSearch
                self.opensearch = OpenSearch(f'http://{self.host}:{opensearch_port}')
        opensearch_client_module.OpenSearchClient.__init__ = patched_opensearch_init

# Note: Patching is NOT done automatically on import to avoid surprising side effects.
# Call patch_clients_for_test_ports() explicitly when needed.
# The test runner (tests/runner.py) injects this as the first cell in notebooks.

