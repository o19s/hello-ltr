"""
Test helper to patch client classes and requests library to use test ports 
without modifying production code. This module should be imported before any 
notebooks are executed.
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
    if 'ltr.client.solr_client' in sys.modules:
        import importlib
        import ltr.client.solr_client as solr_client_module
        importlib.reload(solr_client_module)
    else:
        import ltr.client.solr_client as solr_client_module
    
    if 'ltr.client.elastic_client' in sys.modules:
        import importlib
        import ltr.client.elastic_client as elastic_client_module
        importlib.reload(elastic_client_module)
    else:
        import ltr.client.elastic_client as elastic_client_module
    
    if 'ltr.client.opensearch_client' in sys.modules:
        import importlib
        import ltr.client.opensearch_client as opensearch_client_module
        importlib.reload(opensearch_client_module)
    else:
        import ltr.client.opensearch_client as opensearch_client_module
    
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

# Auto-patch when module is imported (for notebooks that import this directly)
patch_clients_for_test_ports()

