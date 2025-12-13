"""
Unit tests for OpenSearchClient.

Tests cover:
- Client initialization (Docker vs local)
- Index operations (create, delete, check exists)
- Document indexing
- LTR operations (reset, featureset, models)
- Query operations
- Feature extraction
"""
import os
from unittest.mock import Mock, mock_open, patch

import pytest

from ltr.client.opensearch_client import OpenSearchClient


class TestOpenSearchClientInitialization:
    """Test OpenSearchClient initialization and basic properties."""

    def test_init_local_host(self):
        """Test client initializes with localhost when not in Docker."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True), \
             patch('ltr.client.opensearch_client.OpenSearch'):
            # Act
            client = OpenSearchClient()
            # Assert
            assert client.host == "localhost"
            assert client.opensearch_ep == "http://localhost:9201/_ltr"
            assert not client.docker

    def test_init_docker_host(self):
        """Test client initializes with Docker host when LTR_DOCKER is set."""
        # Arrange
        with patch.dict(os.environ, {"LTR_DOCKER": "yes"}), \
             patch('ltr.client.opensearch_client.OpenSearch'):
            # Act
            client = OpenSearchClient()
            # Assert
            assert client.host == "opensearch-node1"
            assert client.opensearch_ep == "http://opensearch-node1:9201/_ltr"
            assert client.docker

    def test_get_host(self):
        """Test get_host returns correct host."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            # Act
            host = client.get_host()
            # Assert
            assert host == client.host

    def test_name(self):
        """Test name returns 'opensearch'."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            # Act
            name = client.name()
            # Assert
            assert name == "opensearch"


class TestOpenSearchClientIndexOperations:
    """Test index creation, deletion, and existence checks."""

    @patch('ltr.client.opensearch_client.OpenSearch')
    def test_check_index_exists_true(self, mock_opensearch_class):
        """Test check_index_exists returns True when index exists."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.indices.exists.return_value = True
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        # Act
        result = client.check_index_exists("test_index")
        # Assert
        assert result is True
        mock_opensearch.indices.exists.assert_called_once_with(index="test_index")

    @patch('ltr.client.opensearch_client.OpenSearch')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_delete_index(self, mock_resp_msg, mock_opensearch_class):
        """Test delete_index calls OpenSearch delete."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.indices.delete.return_value = {"acknowledged": True}
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        # Act
        client.delete_index("test_index")
        # Assert
        mock_opensearch.indices.delete.assert_called_once_with(index="test_index", ignore=[400, 404])

    @patch('ltr.client.opensearch_client.OpenSearch')
    @patch('ltr.helpers.handle_resp.resp_msg')
    @patch('builtins.open', new_callable=mock_open, read_data='{"settings": {}}')
    def test_create_index(self, mock_file, mock_resp_msg, mock_opensearch_class):
        """Test create_index loads settings and creates index."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.indices.create.return_value = {"acknowledged": True}
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient(configs_dir=".")
        # Act
        client.create_index("test_index")
        # Assert
        mock_opensearch.indices.create.assert_called_once()
        call_args = mock_opensearch.indices.create.call_args
        assert call_args[1]["index"] == "test_index"


class TestOpenSearchClientDocumentIndexing:
    """Test document indexing operations."""

    @patch('ltr.client.opensearch_client.OpenSearch')
    @patch('ltr.client.opensearch_client.helpers.bulk')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_index_documents(self, mock_resp_msg, mock_bulk, mock_opensearch_class):
        """Test indexing documents."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.indices.refresh.return_value = None
        mock_opensearch_class.return_value = mock_opensearch
        # bulk returns (success_count, errors) tuple
        mock_bulk.return_value = (10, [])  # 10 successful, 0 errors
        client = OpenSearchClient()
        docs = [{"id": "1", "title": "Test"}]
        # Act
        client.index_documents("test_index", docs)
        # Assert
        mock_bulk.assert_called_once()
        mock_opensearch.indices.refresh.assert_called_once_with(index="test_index")

    @patch('ltr.client.opensearch_client.OpenSearch')
    @patch('ltr.client.opensearch_client.helpers.bulk')
    @patch('ltr.client.opensearch_client.resp_msg')
    def test_index_documents_missing_id(self, mock_resp_msg, mock_bulk, mock_opensearch_class):
        """Test indexing documents without id raises ValueError."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch_class.return_value = mock_opensearch
        # bulk will raise ValueError when iterating over docs without 'id'
        def bulk_side_effect(opensearch, actions, **kwargs):
            # Try to iterate to trigger the ValueError
            list(actions)  # Consume generator to trigger ValueError
            return (0, [])
        mock_bulk.side_effect = bulk_side_effect
        # Patch resp_msg to handle BulkResp (which doesn't have text attribute)
        def safe_resp_msg(msg, resp, throw=True, ignore=None):
            if ignore is None:
                ignore = []
            rsc = resp.status_code
            print(f"{msg} [Status: {rsc}]")
            if rsc >= 400 and rsc not in ignore and throw:
                text = getattr(resp, 'text', '')
                raise RuntimeError(text)
        mock_resp_msg.side_effect = safe_resp_msg
        client = OpenSearchClient()
        docs = [{"title": "Test"}]  # Missing 'id'
        # Act & Assert
        with pytest.raises(ValueError, match="Expecting docs to have field 'id'"):
            client.index_documents("test_index", docs)


class TestOpenSearchClientLTR:
    """Test LTR-related operations."""

    @patch('ltr.client.opensearch_client.requests.delete')
    @patch('ltr.client.opensearch_client.requests.put')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_reset_ltr(self, mock_resp_msg, mock_put, mock_delete):
        """Test reset_ltr deletes and recreates LTR feature store."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            mock_delete.return_value = Mock(status_code=200)
            mock_put.return_value = Mock(status_code=200)
            # Act
            client.reset_ltr("test_index")
            # Assert
            assert mock_delete.call_count == 1
            assert mock_put.call_count == 1

    @patch('ltr.client.opensearch_client.requests.post')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_create_featureset(self, mock_resp_msg, mock_post):
        """Test create_featureset sends correct request."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            config = {"featureset": {"features": []}}
            mock_post.return_value = Mock(status_code=200)
            # Act
            client.create_featureset("test_index", "featureset", config)
            # Assert
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "_featureset/featureset" in call_args[0][0]
            assert call_args[1]["json"] == config

    def test_get_feature_name(self):
        """Test get_feature_name returns correct feature name."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            config = {
                "featureset": {
                    "features": [
                        {"name": "feature1"},
                        {"name": "feature2"}
                    ]
                }
            }
            # Act
            name = client.get_feature_name(config, "1")
            # Assert
            assert name == "feature1"


class TestOpenSearchClientQuery:
    """Test query operations."""

    @patch('ltr.client.opensearch_client.OpenSearch')
    def test_query(self, mock_opensearch_class):
        """Test query transforms response correctly."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"id": "1"}, "_score": 0.5}
                ]
            }
        }
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        query = {"query": {"match_all": {}}}
        # Act
        results = client.query("test_index", query)
        # Assert
        assert len(results) == 1
        assert results[0]["_score"] == 0.5

    @patch('ltr.client.opensearch_client.OpenSearch')
    def test_log_query_with_ids(self, mock_opensearch_class):
        """Test log_query with document IDs."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {"id": "1"},
                        "fields": {
                            "_ltrlog": [{
                                "ltr_features": [
                                    {"value": 0.5},
                                    {"value": 0.3}
                                ]
                            }]
                        }
                    }
                ]
            }
        }
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        # Act
        results = client.log_query("test_index", "featureset", ["1"], {})
        # Assert
        assert len(results) == 1
        assert "ltr_features" in results[0]
        assert results[0]["ltr_features"] == [0.5, 0.3]

    @patch('ltr.client.opensearch_client.OpenSearch')
    def test_model_query(self, mock_opensearch_class):
        """Test model_query sends correct LTR query."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"id": "1"}, "_score": 0.5}
                ]
            }
        }
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        query = {"query": {"match_all": {}}}
        # Act
        results = client.model_query("test_index", "mymodel", {}, query)
        # Assert
        assert len(results) == 1
        assert results[0]["score"] == 0.5
        call_args = mock_opensearch.search.call_args
        assert "rescore" in call_args[1]["body"]


class TestOpenSearchClientFeatureSet:
    """Test feature set operations."""

    @patch('ltr.client.opensearch_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_feature_set(self, mock_resp_msg, mock_get):
        """Test feature_set returns mapping and raw features."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "found": True,
                "_source": {
                    "featureset": {
                        "features": [
                            {"name": "feature1"},
                            {"name": "feature2"}
                        ]
                    }
                }
            }
            mock_get.return_value = mock_response
            # Act
            mapping, raw_features = client.feature_set("test_index", "featureset")
            # Assert
            assert len(mapping) == 2
            assert mapping[0]["name"] == "feature1"
            assert len(raw_features) == 2

    @patch('ltr.client.opensearch_client.requests.get')
    def test_feature_set_not_found(self, mock_get):
        """Test feature_set raises RuntimeError when not found."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            mock_response = Mock()
            mock_response.json.return_value = {"found": False}
            mock_get.return_value = mock_response
            # Act & Assert
            with pytest.raises(RuntimeError, match="Unable to find"):
                client.feature_set("test_index", "nonexistent")

    @patch('ltr.client.opensearch_client.OpenSearch')
    def test_get_doc(self, mock_opensearch_class):
        """Test get_doc retrieves document by ID."""
        # Arrange
        mock_opensearch = Mock()
        mock_opensearch.get.return_value = {
            "_source": {"id": "123", "title": "Test"}
        }
        mock_opensearch_class.return_value = mock_opensearch
        client = OpenSearchClient()
        # Act
        doc = client.get_doc("123", "test_index")
        # Assert
        assert doc["id"] == "123"
        assert doc["title"] == "Test"


class TestOpenSearchClientModelOperations:
    """Test model submission operations."""

    @patch('ltr.client.opensearch_client.requests.delete')
    @patch('ltr.client.opensearch_client.requests.post')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_submit_model(self, mock_resp_msg, mock_post, mock_delete):
        """Test submit_model deletes and creates model."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            mock_delete.return_value = Mock(status_code=200)
            mock_post.return_value = Mock(status_code=200)
            payload = {"model": {"name": "test"}}
            # Act
            client.submit_model("featureset", "test_index", "model1", payload)
            # Assert
            assert mock_delete.call_count == 1
            assert mock_post.call_count == 1

    @patch('ltr.client.opensearch_client.OpenSearchClient.submit_model')
    def test_submit_ranklib_model(self, mock_submit):
        """Test submit_ranklib_model formats payload correctly."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            # Act
            client.submit_ranklib_model("featureset", "test_index", "model1", "xml_content")
            # Assert
            mock_submit.assert_called_once()
            call_args = mock_submit.call_args
            payload = call_args[0][3]
            assert payload["model"]["model"]["type"] == "model/ranklib"

    @patch('ltr.client.opensearch_client.OpenSearchClient.submit_model')
    def test_submit_xgboost_model(self, mock_submit):
        """Test submit_xgboost_model formats payload correctly."""
        # Arrange
        with patch('ltr.client.opensearch_client.OpenSearch'):
            client = OpenSearchClient()
            # Act
            client.submit_xgboost_model("featureset", "test_index", "model1", "json_content")
            # Assert
            mock_submit.assert_called_once()
            call_args = mock_submit.call_args
            payload = call_args[0][3]
            assert payload["model"]["model"]["type"] == "model/xgboost+json"

