"""
Unit tests for client factory functions.

Tests verify that factory functions correctly inject ports from environment variables
and use dependency injection instead of monkey patching.
"""

import os
from unittest.mock import patch

from tests.client_factory import (
    create_elastic_client,
    create_opensearch_client,
    create_solr_client,
)


class TestClientFactoryPortInjection:
    """Test that factory functions correctly inject ports from environment variables."""

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
            # Mock both worker ports and BASE_PORTS to ensure we get the default
            with (
                patch("tests.port_management.get_worker_ports", return_value=None),
                patch("tests.port_management.BASE_PORTS", {}),
            ):
                client = create_solr_client()
                assert client.port == 8983
        finally:
            if original_port:
                os.environ["SOLR_PORT"] = original_port

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
            with (
                patch("ltr.client.elastic_client.Elasticsearch"),
                patch("tests.port_management.get_worker_ports", return_value=None),
                patch("tests.port_management.BASE_PORTS", {}),
            ):
                client = create_elastic_client()
                assert client.port == 9200
        finally:
            if original_port:
                os.environ["ELASTICSEARCH_PORT"] = original_port

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
            with (
                patch("ltr.client.opensearch_client.OpenSearch"),
                patch("tests.port_management.get_worker_ports", return_value=None),
                patch("tests.port_management.BASE_PORTS", {}),
            ):
                client = create_opensearch_client()
                assert client.port == 9201
        finally:
            if original_port:
                os.environ["OPENSEARCH_PORT"] = original_port


class TestClientFactoryConfigsDir:
    """Test that factory functions correctly pass configs_dir parameter."""

    def test_create_elastic_client_passes_configs_dir(self):
        """Test create_elastic_client passes configs_dir parameter."""
        with patch("ltr.client.elastic_client.Elasticsearch"):
            client = create_elastic_client(configs_dir="/custom/path")
            assert client.configs_dir == "/custom/path"

    def test_create_opensearch_client_passes_configs_dir(self):
        """Test create_opensearch_client passes configs_dir parameter."""
        with patch("ltr.client.opensearch_client.OpenSearch"):
            client = create_opensearch_client(configs_dir="/custom/path")
            assert client.configs_dir == "/custom/path"
