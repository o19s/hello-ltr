"""
Pytest fixtures for unit tests.

This module provides shared fixtures for mocking client dependencies
to reduce boilerplate in unit tests.
"""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_opensearch_client():
    """
    Fixture providing a mocked OpenSearch client.

    This fixture patches the OpenSearch class and returns both the mock client
    instance and the mock class. Use this fixture to avoid repetitive patching
    boilerplate in tests.

    Yields:
        tuple: (mock_client, mock_class) where:
            - mock_client: Mock instance of the OpenSearch client
            - mock_class: Mock class that was patched

    Example:
        from tests.client_factory import create_opensearch_client

        def test_something(mock_opensearch_client):
            mock_client, mock_class = mock_opensearch_client
            mock_client.search.return_value = {"hits": {"hits": []}}
            client = create_opensearch_client()
            # ... test code ...
    """
    with patch("ltr.client.opensearch_client.OpenSearch") as mock_class:
        mock_client = Mock()
        mock_class.return_value = mock_client
        yield mock_client, mock_class


@pytest.fixture
def mock_elasticsearch_client():
    """
    Fixture providing a mocked Elasticsearch client.

    This fixture patches the Elasticsearch class and returns both the mock client
    instance and the mock class. Use this fixture to avoid repetitive patching
    boilerplate in tests.

    Yields:
        tuple: (mock_client, mock_class) where:
            - mock_client: Mock instance of the Elasticsearch client
            - mock_class: Mock class that was patched

    Example:
        from tests.client_factory import create_elastic_client

        def test_something(mock_elasticsearch_client):
            mock_client, mock_class = mock_elasticsearch_client
            mock_client.search.return_value = {"hits": {"hits": []}}
            client = create_elastic_client()
            # ... test code ...
    """
    with patch("ltr.client.elastic_client.Elasticsearch") as mock_class:
        mock_client = Mock()
        mock_class.return_value = mock_client
        yield mock_client, mock_class
