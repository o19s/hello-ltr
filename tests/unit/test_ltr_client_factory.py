"""
Unit tests for ltr.client factory functions.

Tests verify that factory functions in ltr.client module correctly inject ports
from environment variables and use dependency injection.
"""

import os
from unittest.mock import patch

import pytest

from ltr.client import (
    create_elastic_client,
    create_opensearch_client,
    create_solr_client,
)


class TestLtrClientFactoryPortInjection:
    """Test that ltr.client factory functions correctly inject ports from environment variables."""

    @patch.dict(os.environ, {"SOLR_PORT": "19999"}, clear=False)
    def test_create_solr_client_uses_env_port(self):
        """Test create_solr_client uses SOLR_PORT environment variable."""
        client = create_solr_client()
        assert client.port == 19999

    def test_create_solr_client_uses_default_port(self):
        """Test create_solr_client uses default port when env var not set."""
        # Remove SOLR_PORT if it exists to test default behavior
        original_port = os.environ.pop("SOLR_PORT", None)
        try:
            client = create_solr_client()
            assert client.port == 8983
        finally:
            if original_port:
                os.environ["SOLR_PORT"] = original_port

    @patch.dict(os.environ, {"SOLR_PORT": "invalid"}, clear=False)
    def test_create_solr_client_invalid_port_raises_error(self):
        """Test create_solr_client raises ValueError for invalid port."""
        with pytest.raises(ValueError, match="Invalid SOLR_PORT"):
            create_solr_client()

    @patch.dict(os.environ, {"ELASTICSEARCH_PORT": "19998"}, clear=False)
    def test_create_elastic_client_uses_env_port(self):
        """Test create_elastic_client uses ELASTICSEARCH_PORT environment variable."""
        with patch("ltr.client.elastic_client.Elasticsearch"):
            client = create_elastic_client()
            assert client.port == 19998

    def test_create_elastic_client_uses_default_port(self):
        """Test create_elastic_client uses default port when env var not set."""
        original_port = os.environ.pop("ELASTICSEARCH_PORT", None)
        try:
            with patch("ltr.client.elastic_client.Elasticsearch"):
                client = create_elastic_client()
                assert client.port == 9200
        finally:
            if original_port:
                os.environ["ELASTICSEARCH_PORT"] = original_port

    @patch.dict(os.environ, {"ELASTICSEARCH_PORT": "invalid"}, clear=False)
    def test_create_elastic_client_invalid_port_raises_error(self):
        """Test create_elastic_client raises ValueError for invalid port."""
        with pytest.raises(ValueError, match="Invalid ELASTICSEARCH_PORT"):
            create_elastic_client()

    def test_create_elastic_client_passes_configs_dir(self):
        """Test create_elastic_client passes configs_dir parameter."""
        with patch("ltr.client.elastic_client.Elasticsearch"):
            client = create_elastic_client(configs_dir="/custom/path")
            assert client.configs_dir == "/custom/path"

    @patch.dict(os.environ, {"OPENSEARCH_PORT": "19997"}, clear=False)
    def test_create_opensearch_client_uses_env_port(self):
        """Test create_opensearch_client uses OPENSEARCH_PORT environment variable."""
        with patch("ltr.client.opensearch_client.OpenSearch"):
            client = create_opensearch_client()
            assert client.port == 19997

    def test_create_opensearch_client_uses_default_port(self):
        """Test create_opensearch_client uses default port when env var not set."""
        original_port = os.environ.pop("OPENSEARCH_PORT", None)
        try:
            with patch("ltr.client.opensearch_client.OpenSearch"):
                client = create_opensearch_client()
                assert client.port == 9201
        finally:
            if original_port:
                os.environ["OPENSEARCH_PORT"] = original_port

    @patch.dict(os.environ, {"OPENSEARCH_PORT": "invalid"}, clear=False)
    def test_create_opensearch_client_invalid_port_raises_error(self):
        """Test create_opensearch_client raises ValueError for invalid port."""
        with pytest.raises(ValueError, match="Invalid OPENSEARCH_PORT"):
            create_opensearch_client()

    def test_create_opensearch_client_passes_configs_dir(self):
        """Test create_opensearch_client passes configs_dir parameter."""
        with patch("ltr.client.opensearch_client.OpenSearch"):
            client = create_opensearch_client(configs_dir="/custom/path")
            assert client.configs_dir == "/custom/path"
