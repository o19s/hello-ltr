"""
Unit tests for SolrClient.

Tests cover:
- Client initialization (Docker vs local)
- Index operations (create, delete, check exists)
- Document indexing
- LTR operations (reset, featureset, models)
- Query operations
- Feature extraction
"""
import os
from unittest.mock import Mock, patch

import pytest

from ltr.client.solr_client import SolrClient


class TestSolrClientInitialization:
    """Test SolrClient initialization and basic properties."""

    def test_init_local_host(self):
        """Test client initializes with localhost when not in Docker."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            # Act
            client = SolrClient()
            # Assert
            assert client.host == "localhost"
            assert client.solr_base_ep == "http://localhost:8983/solr"
            assert not client.docker

    def test_init_docker_host(self):
        """Test client initializes with Docker host when LTR_DOCKER is set."""
        # Arrange
        with patch.dict(os.environ, {"LTR_DOCKER": "yes"}):
            # Act
            client = SolrClient()
            # Assert
            assert client.host == "solr"
            assert client.solr_base_ep == "http://solr:8983/solr"
            assert client.docker

    def test_get_host(self):
        """Test get_host returns correct host."""
        # Arrange
        client = SolrClient()
        # Act
        host = client.get_host()
        # Assert
        assert host == client.host

    def test_name(self):
        """Test name returns 'solr'."""
        # Arrange
        client = SolrClient()
        # Act
        name = client.name()
        # Assert
        assert name == "solr"


class TestSolrClientIndexOperations:
    """Test index creation, deletion, and existence checks."""

    @patch('ltr.client.solr_client.requests.get')
    def test_check_index_exists_true(self, mock_get):
        """Test check_index_exists returns True when index exists."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.content = b"instanceDir"
        mock_get.return_value = mock_response
        # Act
        result = client.check_index_exists("test_index")
        # Assert
        assert result is True
        mock_get.assert_called_once()

    @patch('ltr.client.solr_client.requests.get')
    def test_check_index_exists_false(self, mock_get):
        """Test check_index_exists returns False when index doesn't exist."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        # Content without "instanceDir" - this would be the response when index doesn't exist
        mock_response.content = b"no match here"
        mock_get.return_value = mock_response
        # Act
        result = client.check_index_exists("test_index")
        # Assert
        assert result is False, \
            f"Expected False when index doesn't exist, but got {result!r}. " \
            f"Response content: {mock_response.content!r}, " \
            f"URL called: {mock_get.call_args[0][0] if mock_get.called else 'NOT CALLED'}"

    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_delete_index(self, mock_resp_msg, mock_get):
        """Test delete_index sends correct request."""
        # Arrange
        client = SolrClient()
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

    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_create_index(self, mock_resp_msg, mock_get):
        """Test create_index sends correct request."""
        # Arrange
        client = SolrClient()
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


class TestSolrClientDocumentIndexing:
    """Test document indexing operations."""

    @patch('ltr.client.solr_client.requests.post')
    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_index_documents_single_batch(self, mock_resp_msg, mock_get, mock_post):
        """Test indexing documents in a single batch."""
        # Arrange
        client = SolrClient()
        docs = [{"id": "1", "title": "Test"}, {"id": "2", "title": "Test2"}]
        mock_post.return_value = Mock(status_code=200)
        mock_get.return_value = Mock(status_code=200)
        # Act
        client.index_documents("test_index", docs)
        # Assert
        assert mock_post.call_count == 1
        assert mock_get.call_count == 1

    @patch('ltr.client.solr_client.requests.post')
    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_index_documents_release_date_formatting(self, mock_resp_msg, mock_get, mock_post):
        """Test that release_date is formatted with T00:00:00Z."""
        # Arrange
        client = SolrClient()
        docs = [{"id": "1", "release_date": "2020-01-01"}]
        mock_post.return_value = Mock(status_code=200)
        mock_get.return_value = Mock(status_code=200)
        # Capture the docs passed to post (before they're cleared)
        captured_docs = []
        def capture_post(*args, **kwargs):
            if 'json' in kwargs:
                # Make a copy since docs.clear() will empty the list
                captured_docs.extend(kwargs['json'].copy())
            return Mock(status_code=200)
        mock_post.side_effect = capture_post
        # Act
        client.index_documents("test_index", docs)
        # Assert
        assert len(captured_docs) > 0
        assert captured_docs[0]["release_date"] == "2020-01-01T00:00:00Z"

    @patch('ltr.client.solr_client.requests.post')
    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_index_documents_large_batch(self, mock_resp_msg, mock_get, mock_post):
        """Test indexing documents triggers multiple batches."""
        # Arrange
        client = SolrClient()
        # Create 6000 docs to trigger batch flush (BATCH_SIZE=5000)
        docs = [{"id": str(i), "title": f"Test{i}"} for i in range(6000)]
        mock_post.return_value = Mock(status_code=200)
        mock_get.return_value = Mock(status_code=200)
        # Act
        client.index_documents("test_index", docs)
        # Assert
        # Should have 2 flush calls (5000 + 1000) + 1 final flush
        assert mock_post.call_count >= 2


class TestSolrClientLTR:
    """Test LTR-related operations."""

    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.client.solr_client.requests.delete')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_reset_ltr(self, mock_resp_msg, mock_delete, mock_get):
        """Test reset_ltr deletes models and feature stores."""
        # Arrange
        client = SolrClient()
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

    def test_validate_featureset_valid(self):
        """Test validate_featureset passes with correct store name."""
        # Arrange
        client = SolrClient()
        config = [
            {"name": "feature1", "store": "mystore"},
            {"name": "feature2", "store": "mystore"},
        ]
        # Act & Assert - should not raise
        client.validate_featureset("mystore", config)

    def test_validate_featureset_invalid(self):
        """Test validate_featureset raises ValueError with wrong store name."""
        # Arrange
        client = SolrClient()
        config = [
            {"name": "feature1", "store": "wrongstore"},
            {"name": "feature2", "store": "mystore"},
        ]
        # Act & Assert
        with pytest.raises(ValueError, match="needs to be created with"):
            client.validate_featureset("mystore", config)

    @patch('ltr.client.solr_client.requests.put')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_create_featureset(self, mock_resp_msg, mock_put):
        """Test create_featureset sends correct request."""
        # Arrange
        client = SolrClient()
        config = [{"name": "feature1", "store": "mystore"}]
        mock_put.return_value = Mock(status_code=200)
        # Act
        client.create_featureset("test_index", "mystore", config)
        # Assert
        mock_put.assert_called_once()
        call_args = mock_put.call_args
        assert "schema/feature-store" in call_args[0][0]
        assert call_args[1]["json"] == config

    def test_get_feature_name(self):
        """Test get_feature_name returns correct feature name."""
        # Arrange
        client = SolrClient()
        config = [{"name": "feature1"}, {"name": "feature2"}]
        # Act
        name = client.get_feature_name(config, "1")
        # Assert
        assert name == "feature1"

    def test_get_feature_name_index_1_based(self):
        """Test get_feature_name uses 1-based indexing."""
        # Arrange
        client = SolrClient()
        config = [{"name": "feature1"}, {"name": "feature2"}]
        # Act
        name = client.get_feature_name(config, "2")
        # Assert
        assert name == "feature2"


class TestSolrClientQuery:
    """Test query operations."""

    @patch('ltr.client.solr_client.requests.post')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_query(self, mock_resp_msg, mock_post):
        """Test query sends request and transforms response."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": {"docs": [{"id": "1", "score": 0.5}]}
        }
        mock_post.return_value = mock_response
        query = {"q": "test"}
        # Act
        results = client.query("test_index", query)
        # Assert
        assert len(results) == 1, \
            f"Expected 1 result, got {len(results)}. Results: {results}"
        assert results[0]["_score"] == 0.5, \
            f"Expected _score=0.5, got {results[0].get('_score', 'MISSING')}. Full result: {results[0]}"
        # Note: The implementation adds _score but doesn't remove score, so both exist
        assert "score" in results[0], \
            f"Expected 'score' field in result. Available fields: {list(results[0].keys())}"

    @patch('ltr.client.solr_client.requests.post')
    def test_log_query_with_ids(self, mock_post):
        """Test log_query with document IDs."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": {
                "docs": [
                    {"id": "1", "[features]": "feature1=0.5,feature2=0.3"}
                ]
            }
        }
        mock_post.return_value = mock_response
        # Act
        results = client.log_query("test_index", "featureset", ["1", "2"], {"param1": "value1"})
        # Assert
        assert len(results) == 1
        assert "ltr_features" in results[0]
        assert results[0]["ltr_features"] == [0.5, 0.3]

    @patch('ltr.client.solr_client.requests.post')
    def test_log_query_without_ids(self, mock_post):
        """Test log_query without document IDs uses *:* query."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {"response": {"docs": []}}
        mock_post.return_value = mock_response
        # Act
        client.log_query("test_index", "featureset", None, {})
        # Assert
        call_args = mock_post.call_args
        assert call_args[1]["data"]["q"] == "*:*"

    @patch('ltr.client.solr_client.requests.post')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_model_query(self, mock_resp_msg, mock_post):
        """Test model_query sends correct LTR query."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"docs": [{"id": "1"}]}}
        mock_post.return_value = mock_response
        # Act
        results = client.model_query("test_index", "mymodel", {}, "test query")
        # Assert
        assert len(results) == 1
        call_args = mock_post.call_args
        assert "rq" in call_args[1]["data"]
        assert "ltr model=mymodel" in call_args[1]["data"]["rq"]


class TestSolrClientFeatureSet:
    """Test feature set operations."""

    @patch('ltr.client.solr_client.requests.get')
    @patch('ltr.helpers.handle_resp.resp_msg')
    def test_feature_set(self, mock_resp_msg, mock_get):
        """Test feature_set returns mapping and raw features."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [
                {"name": "feature1"},
                {"name": "feature2"}
            ]
        }
        mock_get.return_value = mock_response
        # Act
        mapping, raw_features = client.feature_set("test_index", "featureset")
        # Assert
        assert len(mapping) == 2
        assert mapping[0]["name"] == "feature1"
        assert len(raw_features) == 2

    @patch('ltr.client.solr_client.requests.get')
    def test_get_feature_stores(self, mock_get):
        """Test get_feature_stores returns list of stores."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {"featureStores": ["store1", "store2"]}
        mock_get.return_value = mock_response
        # Act
        stores = client.get_feature_stores("test_index")
        # Assert
        assert stores == ["store1", "store2"]

    @patch('ltr.client.solr_client.requests.get')
    def test_get_models(self, mock_get):
        """Test get_models returns list of model names."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "model1"},
                {"name": "model2"}
            ]
        }
        mock_get.return_value = mock_response
        # Act
        models = client.get_models("test_index")
        # Assert
        assert models == ["model1", "model2"]

    @patch('ltr.client.solr_client.requests.post')
    def test_get_doc(self, mock_post):
        """Test get_doc retrieves document by ID."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "response": {"docs": [{"id": "123", "title": "Test"}]}
        }
        mock_post.return_value = mock_response
        # Act
        doc = client.get_doc("test_index", "123")
        # Assert
        assert doc["id"] == "123"
        assert doc["title"] == "Test"

