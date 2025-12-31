"""
Client module for hello-ltr.

Provides client classes and factory functions for creating search engine clients.
Factory functions use dependency injection to configure ports from environment
variables, making them suitable for both development and test environments.
"""

import os
from typing import TYPE_CHECKING

from .elastic_client import ElasticClient
from .opensearch_client import OpenSearchClient
from .solr_client import SolrClient

if TYPE_CHECKING:
    pass  # TYPE_CHECKING imports can be added here if needed in the future

__all__ = [
    "ElasticClient",
    "SolrClient",
    "OpenSearchClient",
    "create_solr_client",
    "create_elastic_client",
    "create_opensearch_client",
]


def create_solr_client() -> SolrClient:
    """
    Create a SolrClient with port configured via dependency injection.

    Uses dependency injection to pass the port parameter to SolrClient.__init__.
    If SOLR_PORT environment variable is set, uses that port. Otherwise uses default (8983).

    This factory function enables explicit dependency injection instead of relying on
    runtime patching, making the code more maintainable and testable.

    Returns:
        SolrClient: Configured SolrClient instance

    Example:
        >>> client = create_solr_client()
        >>> # In test environments, set SOLR_PORT env var to use test ports
        >>> # In development, uses default port 8983
    """
    port_env = os.environ.get("SOLR_PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            raise ValueError(
                f"Invalid SOLR_PORT environment variable: '{port_env}'. Must be an integer."
            )
    else:
        port = 8983  # Default Solr port

    return SolrClient(port=port)


def create_elastic_client(configs_dir: str = ".") -> ElasticClient:
    """
    Create an ElasticClient with port configured via dependency injection.

    Uses dependency injection to pass the port parameter to ElasticClient.__init__.
    If ELASTICSEARCH_PORT environment variable is set, uses that port. Otherwise uses default (9200).

    This factory function enables explicit dependency injection instead of relying on
    runtime patching, making the code more maintainable and testable.

    Args:
        configs_dir: Directory containing Elasticsearch configuration files
            (default: current directory, or NOTEBOOK_CONFIGS_DIR env var if set).

    Returns:
        ElasticClient: Configured ElasticClient instance

    Example:
        >>> client = create_elastic_client()
        >>> # In test environments, set ELASTICSEARCH_PORT env var to use test ports
        >>> # In development, uses default port 9200
    """
    port_env = os.environ.get("ELASTICSEARCH_PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            raise ValueError(
                f"Invalid ELASTICSEARCH_PORT environment variable: '{port_env}'. Must be an integer."
            )
    else:
        port = 9200  # Default Elasticsearch port

    return ElasticClient(configs_dir=configs_dir, port=port)


def create_opensearch_client(configs_dir: str = ".") -> OpenSearchClient:
    """
    Create an OpenSearchClient with port configured via dependency injection.

    Uses dependency injection to pass the port parameter to OpenSearchClient.__init__.
    If OPENSEARCH_PORT environment variable is set, uses that port. Otherwise uses default (9201).

    This factory function enables explicit dependency injection instead of relying on
    runtime patching, making the code more maintainable and testable.

    Args:
        configs_dir: Directory containing OpenSearch configuration files
            (default: current directory, or NOTEBOOK_CONFIGS_DIR env var if set).

    Returns:
        OpenSearchClient: Configured OpenSearchClient instance

    Example:
        >>> client = create_opensearch_client()
        >>> # In test environments, set OPENSEARCH_PORT env var to use test ports
        >>> # In development, uses default port 9201
    """
    port_env = os.environ.get("OPENSEARCH_PORT")
    if port_env:
        try:
            port = int(port_env)
        except ValueError:
            raise ValueError(
                f"Invalid OPENSEARCH_PORT environment variable: '{port_env}'. Must be an integer."
            )
    else:
        port = 9201  # Default OpenSearch port

    return OpenSearchClient(configs_dir=configs_dir, port=port)
