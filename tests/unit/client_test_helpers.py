"""
Shared test helpers for client initialization and index operation tests.

This module provides parametrized test functions to reduce duplication
across Solr, OpenSearch, and Elastic client test files.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Callable, Union
from unittest.mock import Mock, mock_open, patch

import pytest

from ltr.client.elastic_client import ElasticClient
from ltr.client.opensearch_client import OpenSearchClient
from ltr.client.solr_client import SolrClient
from tests.client_factory import (
    create_elastic_client,
    create_opensearch_client,
    create_solr_client,
)

# Type alias for client classes
ClientClass = type[Union[SolrClient, OpenSearchClient, ElasticClient]]


def _get_client_factory(
    client_class: ClientClass,
) -> Callable[[], SolrClient | OpenSearchClient | ElasticClient]:
    """
    Get the factory function for a client class.

    Uses explicit dependency injection via factory functions instead of direct instantiation.

    Args:
        client_class: The client class (SolrClient, OpenSearchClient, or ElasticClient)

    Returns:
        Callable: Factory function that creates a client instance
    """
    if client_class is SolrClient:
        return create_solr_client
    elif client_class is OpenSearchClient:
        return create_opensearch_client
    elif client_class is ElasticClient:
        return create_elastic_client
    else:
        # Fallback to direct instantiation if unknown class
        return lambda: client_class()


def _get_requests_patch_path(client_type_or_patch_path, method):
    """
    Get the requests patch path based on client type or patch_path.

    Args:
        client_type_or_patch_path: Either "opensearch", "elastic", or a patch_path string
        method: HTTP method name ("get", "post", "put", "delete")

    Returns:
        str: Path to patch for requests.{method}
    """
    if isinstance(client_type_or_patch_path, str):
        if client_type_or_patch_path == "opensearch" or (
            "opensearch" in client_type_or_patch_path
        ):
            return f"ltr.client.opensearch_client.requests.{method}"
        elif client_type_or_patch_path == "elastic" or (
            "elastic" in client_type_or_patch_path
        ):
            return f"ltr.client.elastic_client.requests.{method}"
    return f"ltr.client.elastic_client.requests.{method}"


@contextmanager
def _create_client_with_patch(client_class, patch_path):
    """
    Context manager to create a client with optional patching.

    Uses factory functions for explicit dependency injection instead of direct instantiation.

    Args:
        client_class: The client class to instantiate
        patch_path: Path to patch (None for SolrClient which doesn't need patching)

    Yields:
        Client instance
    """
    # Use factory functions for explicit dependency injection
    factory_func = _get_client_factory(client_class)

    if patch_path:
        with patch(patch_path):
            yield factory_func()
    else:
        yield factory_func()


def _assert_endpoint(client, expected_endpoint):
    """
    Assert that the client has the expected endpoint attribute.

    Args:
        client: Client instance
        expected_endpoint: Expected endpoint URL value
    """
    if hasattr(client, "solr_base_ep"):
        assert client.solr_base_ep == expected_endpoint
    elif hasattr(client, "opensearch_ep"):
        assert client.opensearch_ep == expected_endpoint
    elif hasattr(client, "elastic_ep"):
        assert client.elastic_ep == expected_endpoint


@pytest.mark.parametrize(
    "client_class,expected_name,expected_local_host,expected_docker_host,expected_local_endpoint,expected_docker_endpoint,patch_path",
    [
        (
            SolrClient,
            "solr",
            "localhost",
            "solr",
            "http://localhost:8983/solr",
            "http://solr:8983/solr",
            None,  # Solr doesn't need patching
        ),
        (
            OpenSearchClient,
            "opensearch",
            "localhost",
            "opensearch-node1",
            "http://localhost:9201/_ltr",
            "http://opensearch-node1:9201/_ltr",
            "ltr.client.opensearch_client.OpenSearch",
        ),
        (
            ElasticClient,
            "elastic",
            "localhost",
            "elastic",
            "http://localhost:9200/_ltr",
            "http://elastic:9200/_ltr",
            "ltr.client.elastic_client.Elasticsearch",
        ),
    ],
)
def test_client_initialization(
    client_class,
    expected_name,
    expected_local_host,
    expected_docker_host,
    expected_local_endpoint,
    expected_docker_endpoint,
    patch_path,
):
    """
    Test client initialization patterns.

    This parametrized test covers:
    - Local host initialization
    - Docker host initialization
    - get_host() method
    - name() method

    Args:
        client_class: The client class to test (SolrClient, OpenSearchClient, or ElasticClient)
        expected_name: Expected return value from name() method
        expected_local_host: Expected host when not in Docker
        expected_docker_host: Expected host when in Docker
        expected_local_endpoint: Expected endpoint URL when not in Docker
        expected_docker_endpoint: Expected endpoint URL when in Docker
        patch_path: Path to patch for client initialization (None for SolrClient)
    """
    # Test local host initialization
    with (
        patch.dict(os.environ, {}, clear=True),
        _create_client_with_patch(client_class, patch_path) as client,
    ):
        assert client.host == expected_local_host
        assert not client.docker
        _assert_endpoint(client, expected_local_endpoint)

    # Test docker host initialization
    with (
        patch.dict(os.environ, {"LTR_DOCKER": "yes"}),
        _create_client_with_patch(client_class, patch_path) as client,
    ):
        assert client.host == expected_docker_host
        assert client.docker
        _assert_endpoint(client, expected_docker_endpoint)

    # Test get_host() method
    with (
        patch.dict(os.environ, {}, clear=True),
        _create_client_with_patch(client_class, patch_path) as client,
    ):
        host = client.get_host()
        assert host == client.host
        assert host == expected_local_host

    # Test name() method
    with (
        patch.dict(os.environ, {}, clear=True),
        _create_client_with_patch(client_class, patch_path) as client,
    ):
        name = client.name()
        assert name == expected_name


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_check_index_exists_false(client_class, patch_path, client_type):
    """
    Test check_index_exists returns False when index doesn't exist.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.get and checks response content
        with patch("ltr.client.solr_client.requests.get") as mock_get:
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            # Content without "instanceDir" - this would be the response when index doesn't exist
            mock_response.content = b"no match here"
            mock_get.return_value = mock_response
            # Act
            result = client.check_index_exists("test_index")
            # Assert
            assert result is False
    else:
        # OpenSearch/Elastic use client's indices.exists() method
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.indices.exists.return_value = False
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            result = client.check_index_exists("test_index")
            # Assert
            assert result is False
            mock_client.indices.exists.assert_called_once_with(index="test_index")


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_check_index_exists_true(client_class, patch_path, client_type):
    """
    Test check_index_exists returns True when index exists.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.get and checks response content
        with patch("ltr.client.solr_client.requests.get") as mock_get:
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.content = b"instanceDir"
            mock_get.return_value = mock_response
            # Act
            result = client.check_index_exists("test_index")
            # Assert
            assert result is True
            mock_get.assert_called_once()
    else:
        # OpenSearch/Elastic use client's indices.exists() method
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.indices.exists.return_value = True
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            result = client.check_index_exists("test_index")
            # Assert
            assert result is True
            mock_client.indices.exists.assert_called_once_with(index="test_index")


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_delete_index(client_class, patch_path, client_type):
    """
    Test delete_index operation.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.get with specific params
        with (
            patch("ltr.client.solr_client.requests.get") as mock_get,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            # Act
            client.delete_index("test_index")
            # Assert
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "admin/cores" in call_args[0][0]
            assert call_args[1]["params"]["action"] == "UNLOAD"
            assert call_args[1]["params"]["core"] == "test_index"
    else:
        # OpenSearch/Elastic use client's indices.delete() method
        with (
            patch(patch_path) as mock_client_class,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            mock_client = Mock()
            mock_client.indices.delete.return_value = {"acknowledged": True}
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            client.delete_index("test_index")
            # Assert
            mock_client.indices.delete.assert_called_once_with(
                index="test_index", ignore=[400, 404]
            )


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_create_index(client_class, patch_path, client_type):
    """
    Test create_index operation.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.get with specific params
        with (
            patch("ltr.client.solr_client.requests.get") as mock_get,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            # Act
            client.create_index("test_index")
            # Assert
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "admin/cores" in call_args[0][0]
            assert call_args[1]["params"]["action"] == "CREATE"
            assert call_args[1]["params"]["name"] == "test_index"
    else:
        # OpenSearch/Elastic use client's indices.create() method and need config file
        with (
            patch(patch_path) as mock_client_class,
            patch("ltr.helpers.handle_resp.resp_msg"),
            patch(
                "builtins.open", new_callable=mock_open, read_data='{"settings": {}}'
            ),
        ):
            mock_client = Mock()
            mock_client.indices.create.return_value = {"acknowledged": True}
            mock_client_class.return_value = mock_client
            client = client_class(configs_dir=".")
            # Act
            client.create_index("test_index")
            # Assert
            mock_client.indices.create.assert_called_once()
            call_args = mock_client.indices.create.call_args
            assert call_args[1]["index"] == "test_index"


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_reset_ltr(client_class, patch_path, client_type):
    """
    Test reset_ltr operation.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.get to fetch models/stores, then requests.delete to remove them
        with (
            patch("ltr.client.solr_client.requests.get") as mock_get,
            patch("ltr.client.solr_client.requests.delete") as mock_delete,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            # Mock get_models and get_feature_stores responses
            mock_get.side_effect = [
                Mock(json=lambda: {"models": [{"name": "model1"}, {"name": "model2"}]}),
                Mock(json=lambda: {"featureStores": ["store1", "store2"]}),
            ]
            mock_delete.return_value = Mock(status_code=200)
            # Act
            client.reset_ltr("test_index")
            # Assert
            assert mock_delete.call_count == 4  # 2 models + 2 stores
    else:
        # OpenSearch/Elastic use requests.delete and requests.put
        with (
            patch(patch_path),
            patch(_get_requests_patch_path(client_type, "delete")) as mock_delete,
            patch(_get_requests_patch_path(client_type, "put")) as mock_put,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            mock_delete.return_value = Mock(status_code=200)
            mock_put.return_value = Mock(status_code=200)
            # Act
            client.reset_ltr("test_index")
            # Assert
            assert mock_delete.call_count == 1
            assert mock_put.call_count == 1


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_create_featureset(client_class, patch_path, client_type):
    """
    Test create_featureset operation.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.put with list config, URL contains "schema/feature-store"
        with (
            patch("ltr.client.solr_client.requests.put") as mock_put,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            config = [{"name": "feature1", "store": "mystore"}]
            mock_put.return_value = Mock(status_code=200)
            # Act
            client.create_featureset("test_index", "mystore", config)
            # Assert
            mock_put.assert_called_once()
            call_args = mock_put.call_args
            assert "schema/feature-store" in call_args[0][0]
            assert call_args[1]["json"] == config
    else:
        # OpenSearch/Elastic use requests.post with dict config, URL contains "_featureset/featureset"
        with (
            patch(patch_path),
            patch(_get_requests_patch_path(client_type, "post")) as mock_post,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            config = {"featureset": {"features": []}}
            mock_post.return_value = Mock(status_code=200)
            # Act
            client.create_featureset("test_index", "featureset", config)
            # Assert
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "_featureset/featureset" in call_args[0][0]
            assert call_args[1]["json"] == config


@pytest.mark.parametrize(
    "client_class,patch_path,client_type,config",
    [
        (
            SolrClient,
            None,
            "solr",
            [{"name": "feature1"}, {"name": "feature2"}],
        ),
        (
            OpenSearchClient,
            "ltr.client.opensearch_client.OpenSearch",
            "opensearch",
            {"featureset": {"features": [{"name": "feature1"}, {"name": "feature2"}]}},
        ),
        (
            ElasticClient,
            "ltr.client.elastic_client.Elasticsearch",
            "elastic",
            {"featureset": {"features": [{"name": "feature1"}, {"name": "feature2"}]}},
        ),
    ],
)
def test_get_feature_name(client_class, patch_path, client_type, config):
    """
    Test get_feature_name operation.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic") - part of parametrization
        config: Feature configuration (list for Solr, dict for OpenSearch/Elastic)
    """
    # client_type is part of parametrization but not used in test logic
    _ = client_type  # Mark as intentionally unused
    with _create_client_with_patch(client_class, patch_path) as client:
        # Act
        name = client.get_feature_name(config, 1)
        # Assert
        assert name == "feature1"


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_query(client_class, patch_path, client_type):
    """
    Test query operation transforms response correctly.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.post
        with (
            patch("ltr.client.solr_client.requests.post") as mock_post,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.json.return_value = {
                "response": {"docs": [{"id": "1", "score": 0.5}]}
            }
            mock_post.return_value = mock_response
            query = {"q": "test"}
            # Act
            results = client.query("test_index", query)
            # Assert
            assert len(results) == 1
            assert results[0]["_score"] == 0.5
            assert "score" in results[0]
    else:
        # OpenSearch/Elastic use client.search()
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.search.return_value = {
                "hits": {"hits": [{"_source": {"id": "1"}, "_score": 0.5}]}
            }
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            query = {"query": {"match_all": {}}}
            # Act
            results = client.query("test_index", query)
            # Assert
            assert len(results) == 1
            assert results[0]["_score"] == 0.5
            assert results[0]["id"] == "1"


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_log_query_with_ids(client_class, patch_path, client_type):
    """
    Test log_query with document IDs.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.post
        with patch("ltr.client.solr_client.requests.post") as mock_post:
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.json.return_value = {
                "response": {
                    "docs": [{"id": "1", "[features]": "feature1=0.5,feature2=0.3"}]
                }
            }
            mock_post.return_value = mock_response
            # Act
            results = client.log_query(
                "test_index", "featureset", ["1", "2"], {"param1": "value1"}
            )
            # Assert
            assert len(results) == 1
            assert "ltr_features" in results[0]
            assert results[0]["ltr_features"] == [0.5, 0.3]
    else:
        # OpenSearch/Elastic use client.search()
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.search.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {"id": "1"},
                            "fields": {
                                "_ltrlog": [
                                    {"ltr_features": [{"value": 0.5}, {"value": 0.3}]}
                                ]
                            },
                        }
                    ]
                }
            }
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            results = client.log_query("test_index", "featureset", ["1"], {})
            # Assert
            assert len(results) == 1
            assert "ltr_features" in results[0]
            assert results[0]["ltr_features"] == [0.5, 0.3]


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_model_query(client_class, patch_path, client_type):
    """
    Test model_query sends correct LTR query.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.post
        with (
            patch("ltr.client.solr_client.requests.post") as mock_post,
            patch("ltr.helpers.handle_resp.resp_msg"),
        ):
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"response": {"docs": [{"id": "1"}]}}
            mock_post.return_value = mock_response
            # Act
            results = client.model_query(
                "test_index", "mymodel", {}, {"q": "test query"}
            )
            # Assert
            assert len(results) == 1
            call_args = mock_post.call_args
            assert "rq" in call_args[1]["data"]
            assert "ltr model=mymodel" in call_args[1]["data"]["rq"]
            assert call_args[1]["data"]["q"] == "test query"
    else:
        # OpenSearch/Elastic use client.search()
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.search.return_value = {
                "hits": {"hits": [{"_source": {"id": "1"}, "_score": 0.5}]}
            }
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            query = {"query": {"match_all": {}}}
            # Act
            results = client.model_query("test_index", "mymodel", {}, query)
            # Assert
            assert len(results) == 1
            assert results[0]["score"] == 0.5
            call_args = mock_client.search.call_args
            assert "rescore" in call_args[1]["body"]


@pytest.mark.parametrize(
    "client_class,patch_path",
    [
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch"),
    ],
)
def test_feature_set(client_class, patch_path):
    """
    Test feature_set returns mapping and raw features.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
    """
    with (
        patch(patch_path),
        patch(_get_requests_patch_path(patch_path, "get")) as mock_get,
        patch("ltr.helpers.handle_resp.resp_msg"),
    ):
        client = client_class()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "found": True,
            "_source": {
                "featureset": {"features": [{"name": "feature1"}, {"name": "feature2"}]}
            },
        }
        mock_get.return_value = mock_response
        # Act
        mapping, raw_features = client.feature_set("test_index", "featureset")
        # Assert
        assert len(mapping) == 2
        assert mapping[0]["name"] == "feature1"
        assert len(raw_features) == 2


@pytest.mark.parametrize(
    "client_class,patch_path",
    [
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch"),
    ],
)
def test_feature_set_not_found(client_class, patch_path):
    """
    Test feature_set raises RuntimeError when not found.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
    """
    with (
        patch(patch_path),
        patch(_get_requests_patch_path(patch_path, "get")) as mock_get,
    ):
        client = client_class()
        mock_response = Mock()
        mock_response.json.return_value = {"found": False}
        mock_get.return_value = mock_response
        # Act & Assert
        with pytest.raises(RuntimeError, match="Unable to find"):
            client.feature_set("test_index", "nonexistent")


@pytest.mark.parametrize(
    "client_class,patch_path",
    [
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch"),
    ],
)
def test_submit_model(client_class, patch_path):
    """
    Test submit_model deletes and creates model.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
    """
    with (
        patch(patch_path),
        patch(_get_requests_patch_path(patch_path, "delete")) as mock_delete,
        patch(_get_requests_patch_path(patch_path, "post")) as mock_post,
        patch("ltr.helpers.handle_resp.resp_msg"),
    ):
        client = client_class()
        mock_delete.return_value = Mock(status_code=200)
        mock_post.return_value = Mock(status_code=200)
        payload = {"model": {"name": "test"}}
        # Act
        client.submit_model("featureset", "test_index", "model1", payload)
        # Assert
        assert mock_delete.call_count == 1
        assert mock_post.call_count == 1


@pytest.mark.parametrize(
    "client_class,patch_path,submit_model_patch_path",
    [
        (
            OpenSearchClient,
            "ltr.client.opensearch_client.OpenSearch",
            "ltr.client.opensearch_client.OpenSearchClient.submit_model",
        ),
        (
            ElasticClient,
            "ltr.client.elastic_client.Elasticsearch",
            "ltr.client.elastic_client.ElasticClient.submit_model",
        ),
    ],
)
def test_submit_ranklib_model(client_class, patch_path, submit_model_patch_path):
    """
    Test submit_ranklib_model formats payload correctly.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
        submit_model_patch_path: Path to patch submit_model method
    """
    with patch(patch_path), patch(submit_model_patch_path) as mock_submit:
        client = client_class()
        # Act
        client.submit_ranklib_model("featureset", "test_index", "model1", "xml_content")
        # Assert
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        payload = call_args[0][3]
        assert payload["model"]["model"]["type"] == "model/ranklib"


@pytest.mark.parametrize(
    "client_class,patch_path,client_type,bulk_patch_path",
    [
        (
            OpenSearchClient,
            "ltr.client.opensearch_client.OpenSearch",
            "opensearch",
            "ltr.client.opensearch_client.helpers.bulk",
        ),
        (
            ElasticClient,
            "ltr.client.elastic_client.Elasticsearch",
            "elastic",
            "ltr.client.elastic_client.elasticsearch.helpers.bulk",
        ),
    ],
)
def test_index_documents(client_class, patch_path, client_type, bulk_patch_path):
    """
    Test indexing documents.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
        client_type: Type of client ("opensearch" or "elastic")
        bulk_patch_path: Path to patch bulk helper function
    """
    from tests.unit.test_utils import create_safe_resp_msg_wrapper

    with (
        patch(patch_path) as mock_client_class,
        patch(bulk_patch_path) as mock_bulk,
        patch("ltr.helpers.handle_resp.resp_msg") as mock_resp_msg,
    ):
        mock_client = Mock()
        mock_client.indices.refresh.return_value = None
        mock_client_class.return_value = mock_client
        # bulk returns (success_count, errors) tuple
        mock_bulk.return_value = (10, [])  # 10 successful, 0 errors
        mock_resp_msg.side_effect = create_safe_resp_msg_wrapper()
        client = client_class()
        docs = [{"id": "1", "title": "Test"}]
        # Act
        client.index_documents("test_index", docs)
        # Assert
        mock_bulk.assert_called_once()
        mock_client.indices.refresh.assert_called_once_with(index="test_index")


@pytest.mark.parametrize(
    "client_class,patch_path,client_type,bulk_patch_path,resp_msg_patch_path",
    [
        (
            OpenSearchClient,
            "ltr.client.opensearch_client.OpenSearch",
            "opensearch",
            "ltr.client.opensearch_client.helpers.bulk",
            "ltr.client.opensearch_client.resp_msg",
        ),
        (
            ElasticClient,
            "ltr.client.elastic_client.Elasticsearch",
            "elastic",
            "ltr.client.elastic_client.elasticsearch.helpers.bulk",
            "ltr.client.elastic_client.resp_msg",
        ),
    ],
)
def test_index_documents_missing_id(
    client_class, patch_path, client_type, bulk_patch_path, resp_msg_patch_path
):
    """
    Test indexing documents without id raises ValueError.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
        client_type: Type of client ("opensearch" or "elastic")
        bulk_patch_path: Path to patch bulk helper function
        resp_msg_patch_path: Path to patch resp_msg function
    """
    from tests.unit.test_utils import (
        create_bulk_side_effect_for_missing_id,
        create_safe_resp_msg_wrapper,
    )

    with (
        patch(patch_path) as mock_client_class,
        patch(bulk_patch_path) as mock_bulk,
        patch(resp_msg_patch_path) as mock_resp_msg,
    ):
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_bulk.side_effect = create_bulk_side_effect_for_missing_id()
        mock_resp_msg.side_effect = create_safe_resp_msg_wrapper()
        client = client_class()
        docs = [{"title": "Test"}]  # Missing 'id'
        # Act & Assert
        with pytest.raises(ValueError, match="Expecting docs to have field 'id'"):
            client.index_documents("test_index", docs)


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_get_doc(client_class, patch_path, client_type):
    """
    Test get_doc retrieves document by ID.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.post
        with patch("ltr.client.solr_client.requests.post") as mock_post:
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.json.return_value = {
                "response": {"docs": [{"id": "123", "title": "Test"}]}
            }
            mock_post.return_value = mock_response
            # Act
            # Note: get_doc signature is (doc_id, index) to match base class
            doc = client.get_doc("123", "test_index")
            # Assert
            assert doc["id"] == "123"
            assert doc["title"] == "Test"
    else:
        # OpenSearch/Elastic use client.get()
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.get.return_value = {"_source": {"id": "123", "title": "Test"}}
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            doc = client.get_doc("123", "test_index")
            # Assert
            assert doc["id"] == "123"
            assert doc["title"] == "Test"


@pytest.mark.parametrize(
    "client_class,patch_path,submit_model_patch_path",
    [
        (
            OpenSearchClient,
            "ltr.client.opensearch_client.OpenSearch",
            "ltr.client.opensearch_client.OpenSearchClient.submit_model",
        ),
        (
            ElasticClient,
            "ltr.client.elastic_client.Elasticsearch",
            "ltr.client.elastic_client.ElasticClient.submit_model",
        ),
    ],
)
def test_submit_xgboost_model(client_class, patch_path, submit_model_patch_path):
    """
    Test submit_xgboost_model formats payload correctly.

    Args:
        client_class: The client class to test (OpenSearchClient or ElasticClient)
        patch_path: Path to patch for client initialization
        submit_model_patch_path: Path to patch submit_model method
    """
    with patch(patch_path), patch(submit_model_patch_path) as mock_submit:
        client = client_class()
        # Act
        client.submit_xgboost_model(
            "featureset", "test_index", "model1", "json_content"
        )
        # Assert
        mock_submit.assert_called_once()
        call_args = mock_submit.call_args
        payload = call_args[0][3]
        assert payload["model"]["model"]["type"] == "model/xgboost+json"


@pytest.mark.parametrize(
    "client_class,patch_path,client_type",
    [
        (SolrClient, None, "solr"),
        (OpenSearchClient, "ltr.client.opensearch_client.OpenSearch", "opensearch"),
        (ElasticClient, "ltr.client.elastic_client.Elasticsearch", "elastic"),
    ],
)
def test_log_query_without_ids(client_class, patch_path, client_type):
    """
    Test log_query without document IDs.

    Args:
        client_class: The client class to test
        patch_path: Path to patch for client initialization (None for SolrClient)
        client_type: Type of client ("solr", "opensearch", or "elastic")
    """
    if client_type == "solr":
        # Solr uses requests.post and checks for *:* query
        with patch("ltr.client.solr_client.requests.post") as mock_post:
            client = _get_client_factory(client_class)()
            mock_response = Mock()
            mock_response.json.return_value = {"response": {"docs": []}}
            mock_post.return_value = mock_response
            # Act
            client.log_query("test_index", "featureset", None, {})
            # Assert
            call_args = mock_post.call_args
            assert call_args[1]["data"]["q"] == "*:*"
    else:
        # OpenSearch/Elastic use client.search() and check that "must" is not in query
        with patch(patch_path) as mock_client_class:
            mock_client = Mock()
            mock_client.search.return_value = {"hits": {"hits": []}}
            mock_client_class.return_value = mock_client
            client = _get_client_factory(client_class)()
            # Act
            client.log_query("test_index", "featureset", None, {})
            # Assert
            call_args = mock_client.search.call_args
            query_body = call_args[1]["body"]
            assert "must" not in query_body["query"]["bool"]
