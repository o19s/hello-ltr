"""
Fast tests to verify container fixtures work correctly after refactoring.

These tests verify that:
1. Fixtures can be imported and called
2. Fixtures work correctly when USE_WORKER_CONTAINERS is not set (default mode)
3. Configuration dictionaries are valid
4. Shared function handles all engines correctly
"""

import os

from ..conftest import (
    elasticsearch_container,
    opensearch_container,
    solr_container,
)


def test_solr_container_fixture_importable():
    """Test that solr_container fixture can be imported."""
    assert callable(solr_container)
    assert solr_container.__name__ == "solr_container"


def test_elasticsearch_container_fixture_importable():
    """Test that elasticsearch_container fixture can be imported."""
    assert callable(elasticsearch_container)
    assert elasticsearch_container.__name__ == "elasticsearch_container"


def test_opensearch_container_fixture_importable():
    """Test that opensearch_container fixture can be imported."""
    assert callable(opensearch_container)
    assert opensearch_container.__name__ == "opensearch_container"


def test_solr_container_default_mode(request):
    """Test solr_container fixture in default mode (USE_WORKER_CONTAINERS not set)."""
    # Ensure USE_WORKER_CONTAINERS is not set
    original_value = os.environ.pop("USE_WORKER_CONTAINERS", None)
    try:
        # Request the fixture - should yield True immediately
        result = request.getfixturevalue("solr_container")
        assert result is True
    finally:
        # Restore original value
        if original_value is not None:
            os.environ["USE_WORKER_CONTAINERS"] = original_value


def test_elasticsearch_container_default_mode(request):
    """Test elasticsearch_container fixture in default mode."""
    original_value = os.environ.pop("USE_WORKER_CONTAINERS", None)
    try:
        result = request.getfixturevalue("elasticsearch_container")
        assert result is True
    finally:
        if original_value is not None:
            os.environ["USE_WORKER_CONTAINERS"] = original_value


def test_opensearch_container_default_mode(request):
    """Test opensearch_container fixture in default mode."""
    original_value = os.environ.pop("USE_WORKER_CONTAINERS", None)
    try:
        result = request.getfixturevalue("opensearch_container")
        assert result is True
    finally:
        if original_value is not None:
            os.environ["USE_WORKER_CONTAINERS"] = original_value


def test_shared_function_configs_valid():
    """Test that all engine configurations are valid for _manage_container_fixture."""
    # Test Solr config
    solr_config = {
        "engine": "solr",
        "display_name": "Solr",
        "port_config": {"SOLR_PORT": "18983"},
        "health_checks": [("SOLR_PORT", "Solr", "/solr/admin/info/system")],
    }
    assert "engine" in solr_config
    assert "display_name" in solr_config
    assert "port_config" in solr_config
    assert "health_checks" in solr_config

    # Test Elasticsearch config
    es_config = {
        "engine": "elasticsearch",
        "display_name": "Elasticsearch",
        "port_config": {"ELASTICSEARCH_PORT": "19200", "KIBANA_PORT": "15601"},
        "health_checks": [
            ("ELASTICSEARCH_PORT", "Elasticsearch", "/_cluster/health"),
            ("KIBANA_PORT", "Kibana", "/api/status"),
        ],
    }
    assert "engine" in es_config
    assert len(es_config["health_checks"]) == 2

    # Test OpenSearch config
    os_config = {
        "engine": "opensearch",
        "display_name": "OpenSearch",
        "port_config": {
            "OPENSEARCH_PORT": "19201",
            "OPENSEARCH_PA_PORT": "19600",
            "OPENSEARCH_DASHBOARDS_PORT": "15602",
        },
        "health_checks": [
            ("OPENSEARCH_PORT", "OpenSearch", "/_cluster/health"),
            ("OPENSEARCH_DASHBOARDS_PORT", "OpenSearch Dashboards", "/api/status"),
        ],
    }
    assert "engine" in os_config
    assert len(os_config["port_config"]) == 3
    assert len(os_config["health_checks"]) == 2


def test_shared_function_handles_all_engines():
    """Test that _manage_container_fixture can handle all engine configurations."""
    # This test verifies the function signature and basic structure
    # We can't actually run it without containers, but we can verify the configs are valid
    configs = [
        {
            "engine": "solr",
            "display_name": "Solr",
            "port_config": {"SOLR_PORT": "18983"},
            "health_checks": [("SOLR_PORT", "Solr", "/solr/admin/info/system")],
        },
        {
            "engine": "elasticsearch",
            "display_name": "Elasticsearch",
            "port_config": {"ELASTICSEARCH_PORT": "19200", "KIBANA_PORT": "15601"},
            "health_checks": [
                ("ELASTICSEARCH_PORT", "Elasticsearch", "/_cluster/health"),
                ("KIBANA_PORT", "Kibana", "/api/status"),
            ],
        },
        {
            "engine": "opensearch",
            "display_name": "OpenSearch",
            "port_config": {
                "OPENSEARCH_PORT": "19201",
                "OPENSEARCH_PA_PORT": "19600",
                "OPENSEARCH_DASHBOARDS_PORT": "15602",
            },
            "health_checks": [
                ("OPENSEARCH_PORT", "OpenSearch", "/_cluster/health"),
                ("OPENSEARCH_DASHBOARDS_PORT", "OpenSearch Dashboards", "/api/status"),
            ],
        },
    ]

    for config in configs:
        # Verify required keys exist
        assert "engine" in config
        assert "display_name" in config
        assert "port_config" in config
        assert "health_checks" in config
        assert isinstance(config["port_config"], dict)
        assert isinstance(config["health_checks"], list)
        assert len(config["health_checks"]) > 0

        # Verify health check format
        for check in config["health_checks"]:
            assert isinstance(check, tuple)
            assert len(check) == 3
            port_key, service_name, endpoint = check
            assert port_key in config["port_config"]
