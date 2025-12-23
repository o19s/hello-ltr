"""
Client Factory for Test Environments

This module provides factory functions to create search engine clients with test ports
using dependency injection instead of monkey patching.

Usage:
    from tests.client_factory import create_solr_client, create_elastic_client, create_opensearch_client

    # In test environments, these will use test ports from environment variables
    solr_client = create_solr_client()
    elastic_client = create_elastic_client()
    opensearch_client = create_opensearch_client()
"""

from __future__ import annotations

from tests.port_management import get_port


def create_solr_client():
    """
    Create a SolrClient with test port if available.

    Uses dependency injection to pass the port parameter to SolrClient.__init__.
    If SOLR_PORT environment variable is set, uses that port. Otherwise uses default (8983).

    Returns:
        SolrClient: Configured SolrClient instance
    """
    from ltr.client import SolrClient

    port = get_port("SOLR_PORT", default=8983)
    return SolrClient(port=port)


def create_elastic_client(configs_dir: str = "."):
    """
    Create an ElasticClient with test port if available.

    Uses dependency injection to pass the port parameter to ElasticClient.__init__.
    If ELASTICSEARCH_PORT environment variable is set, uses that port. Otherwise uses default (9200).

    Args:
        configs_dir: Directory containing Elasticsearch configuration files

    Returns:
        ElasticClient: Configured ElasticClient instance
    """
    from ltr.client import ElasticClient

    port = get_port("ELASTICSEARCH_PORT", default=9200)
    return ElasticClient(configs_dir=configs_dir, port=port)


def create_opensearch_client(configs_dir: str = "."):
    """
    Create an OpenSearchClient with test port if available.

    Uses dependency injection to pass the port parameter to OpenSearchClient.__init__.
    If OPENSEARCH_PORT environment variable is set, uses that port. Otherwise uses default (9201).

    Args:
        configs_dir: Directory containing OpenSearch configuration files

    Returns:
        OpenSearchClient: Configured OpenSearchClient instance
    """
    from ltr.client import OpenSearchClient

    port = get_port("OPENSEARCH_PORT", default=9201)
    return OpenSearchClient(configs_dir=configs_dir, port=port)


def get_client_creation_code(engine: str) -> str:
    """
    Get Python code to create a client for the specified engine using dependency injection.

    This function generates code that can be injected into notebooks to replace
    direct client instantiation with factory function calls that use test ports.

    Args:
        engine: Engine name ("solr", "elasticsearch", "opensearch")

    Returns:
        str: Python code string that creates the appropriate client

    Example:
        >>> code = get_client_creation_code("solr")
        >>> # Returns: "from tests.client_factory import create_solr_client; Client = create_solr_client()"
    """
    if engine == "solr":
        return (
            "from tests.client_factory import create_solr_client\n"
            "SolrClient = create_solr_client()\n"
            "# Alias for backward compatibility\n"
            "Client = SolrClient"
        )
    elif engine == "elasticsearch" or engine == "elastic":
        return (
            "from tests.client_factory import create_elastic_client\n"
            "ElasticClient = create_elastic_client()\n"
            "# Alias for backward compatibility\n"
            "Client = ElasticClient"
        )
    elif engine == "opensearch":
        return (
            "from tests.client_factory import create_opensearch_client\n"
            "OpenSearchClient = create_opensearch_client()\n"
            "# Alias for backward compatibility\n"
            "Client = OpenSearchClient"
        )
    else:
        raise ValueError(f"Unknown engine: {engine}")
