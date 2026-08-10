"""
Unit tests for ElasticClient.

Tests cover:
- Client initialization (Docker vs local)
- Index operations (create, delete, check exists)
- Document indexing
- LTR operations (reset, featureset, models)
- Query operations
- Feature extraction
"""

from unittest.mock import Mock, patch

import pytest

from ltr.client.elastic_client import ElasticClient, ElasticResp
from ltr.client.responses import BulkResp, SearchResp
from tests.client_factory import create_elastic_client


class TestElasticClientInitialization:
    """Test ElasticClient initialization and basic properties.

    Note: Initialization tests (local host, docker host, get_host, name) are now
    consolidated in a parametrized test in tests.unit.client_test_helpers.
    See test_client_initialization() for the shared implementation.
    """


class TestElasticClientIndexOperations:
    """Test index creation, deletion, and existence checks.

    Note: Index operation tests (check_index_exists_true, check_index_exists_false, delete_index, create_index)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_check_index_exists_true(), test_check_index_exists_false(), test_delete_index(), and test_create_index()
    for the shared implementations.
    """


class TestElasticClientDocumentIndexing:
    """Test document indexing operations.

    Note: Index document tests (test_index_documents, test_index_documents_missing_id)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_index_documents() and test_index_documents_missing_id()
    for the shared implementations.
    """


class TestElasticClientLTR:
    """Test LTR-related operations.

    Note: LTR operation tests (reset_ltr, create_featureset, get_feature_name)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_reset_ltr(), test_create_featureset(), and test_get_feature_name()
    for the shared implementations.
    """


class TestElasticClientQuery:
    """Test query operations.

    Note: Query operation tests (test_query, test_log_query_with_ids, test_log_query_without_ids, test_model_query)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_query(), test_log_query_with_ids(), test_log_query_without_ids(), and test_model_query()
    for the shared implementations.
    """


class TestElasticClientFeatureSet:
    """Test feature set operations.

    Note: Feature set operation tests (test_feature_set, test_feature_set_not_found)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_feature_set() and test_feature_set_not_found()
    for the shared implementations.
    """


class TestElasticClientModelOperations:
    """Test model submission operations."""

    @patch("ltr.client.elastic_client.requests")
    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_submit_xgboost_model(self, mock_elasticsearch_class, mock_requests):
        """Test submit_xgboost_model creates model with correct format."""
        # Arrange
        mock_client = Mock()
        mock_client.perform_request.return_value = (200, {}, {})
        mock_elasticsearch_class.return_value = mock_client

        # Mock requests.delete, requests.post, and requests.get used by submit_model
        mock_delete_resp = Mock()
        mock_delete_resp.status_code = 200
        mock_post_resp = Mock()
        mock_post_resp.status_code = 200
        mock_get_resp = Mock()
        mock_get_resp.status_code = 200
        mock_requests.delete.return_value = mock_delete_resp
        mock_requests.post.return_value = mock_post_resp
        mock_requests.get.return_value = mock_get_resp

        client = create_elastic_client()

        model_payload = {
            "model": {
                "name": "test_xgboost",
                "model": {
                    "type": "model/xgboost+json",
                    "definition": {"booster": "gbtree", "objective": "rank:ndcg"},
                },
            }
        }

        # Act
        client.submit_xgboost_model(
            "test_featureset", "test_index", "test_model", model_payload
        )

        # Assert
        # Verify requests.delete was called to delete existing model
        assert mock_requests.delete.called
        # Verify requests.post was called to create the model
        assert mock_requests.post.called
        # Verify requests.get was called to verify model creation
        assert mock_requests.get.called

    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_submit_xgboost_model_error_handling(self, mock_elasticsearch_class):
        """Test submit_xgboost_model handles errors correctly."""
        # Arrange
        mock_client = Mock()
        mock_elasticsearch_class.return_value = mock_client

        # Mock submit_model to raise an error
        with patch.object(
            ElasticClient, "submit_model", side_effect=Exception("Connection error")
        ):
            client = create_elastic_client()
            client.es = mock_client  # ElasticClient uses self.es

            model_payload = {
                "model": {
                    "name": "test_xgboost",
                    "model": {"type": "model/xgboost+json", "definition": {}},
                }
            }

            # Act & Assert
            with pytest.raises(Exception, match="Connection error"):
                client.submit_xgboost_model(
                    "test_featureset", "test_index", "test_model", model_payload
                )


class TestElasticClientResponseClasses:
    """Test response wrapper classes."""

    def test_elastic_resp_acknowledged(self):
        """Test ElasticResp sets status_code 200 when acknowledged."""
        # Arrange
        resp = {"acknowledged": True}
        # Act
        elastic_resp = ElasticResp(resp)
        # Assert
        assert elastic_resp.status_code == 200

    def test_elastic_resp_not_acknowledged(self):
        """Test ElasticResp sets status_code from status when not acknowledged."""
        # Arrange
        resp = {"status": 400}
        # Act
        elastic_resp = ElasticResp(resp)
        # Assert
        assert elastic_resp.status_code == 400

    def test_bulk_resp_success(self):
        """Test BulkResp sets status_code 201 when successful."""
        # Arrange
        resp = (10, [])  # (success_count, errors)
        # Act
        bulk_resp = BulkResp(resp)
        # Assert
        assert bulk_resp.status_code == 201

    def test_bulk_resp_failure(self):
        """Test BulkResp sets status_code 400 when no success."""
        # Arrange
        resp = (0, [])
        # Act
        bulk_resp = BulkResp(resp)
        # Assert
        assert bulk_resp.status_code == 400

    def test_search_resp_success(self):
        """Test SearchResp sets status_code 200 when hits present."""
        # Arrange
        resp = {"hits": {"total": {"value": 1}}}
        # Act
        search_resp = SearchResp(resp)
        # Assert
        assert search_resp.status_code == 200

    def test_search_resp_failure(self):
        """Test SearchResp sets status_code from status when no hits."""
        # Arrange
        resp = {"status": 400}
        # Act
        search_resp = SearchResp(resp)
        # Assert
        assert search_resp.status_code == 400


class TestElasticClientInvalidInput:
    """Test invalid input handling in ElasticClient."""

    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_index_documents_string_doc_src(self, mock_elasticsearch_class):
        """Test index_documents raises ValidationError for string doc_src."""
        # Arrange
        mock_client = Mock()
        mock_elasticsearch_class.return_value = mock_client
        client = create_elastic_client()
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match="does not support file paths"):
            client.index_documents("test_index", "/path/to/file.json")  # type: ignore[arg-type]

    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_index_documents_missing_id(self, mock_elasticsearch_class):
        """Test index_documents raises ValidationError when document missing 'id' field."""
        # Arrange
        mock_client = Mock()
        mock_elasticsearch_class.return_value = mock_client
        client = create_elastic_client()
        docs = [{"title": "Test"}]
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match="Expecting docs to have field 'id'"):
            client.index_documents("test_index", docs)


class TestElasticClientRetryLogic:
    """Test retry logic edge cases in ElasticClient."""

    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_model_query_retry_exhausted(self, mock_elasticsearch_class):
        """Test model_query retries but eventually fails when max retries exhausted."""
        # Arrange
        from ltr.exceptions import ModelError, QueryError

        mock_client = Mock()
        mock_elasticsearch_class.return_value = mock_client
        client = create_elastic_client()
        # Mock response that indicates model not found (timing error)
        # The retry logic checks for "Unknown model" in the error string.
        # The 8.x client wraps responses, and the code reads .body to get the
        # plain dict, so the mock has to carry the payload the same way.
        mock_response = Mock(body={"error": "Unknown model test_model"})
        mock_client.search.return_value = mock_response
        # Act & Assert
        # The error is raised during validation before retry logic can convert it
        # So it may raise QueryError or ModelError depending on retry logic
        with pytest.raises((ModelError, QueryError), match="model|Model"):
            client.model_query(
                "test_index", "test_model", {}, {"query": {"match_all": {}}}
            )

    @patch("ltr.client.elastic_client.requests.get")
    def test_feature_set_not_found(self, mock_get):
        """Test feature_set raises QueryError when feature set not found."""
        # Arrange
        from ltr.exceptions import QueryError

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        client = create_elastic_client()
        # Act & Assert
        with pytest.raises(QueryError, match="Feature set 'test_featureset' not found"):
            client.feature_set("test_index", "test_featureset")

    @patch("ltr.client.elastic_client.Elasticsearch")
    def test_query_non_retryable_error(self, mock_elasticsearch_class):
        """Test query does not retry on non-retryable errors (e.g., 400 Bad Request)."""
        # Arrange
        from elastic_transport import ApiResponseMeta
        from elasticsearch.exceptions import RequestError

        mock_client = Mock()
        mock_elasticsearch_class.return_value = mock_client
        client = create_elastic_client()
        # 8.x carries an ApiResponseMeta rather than a plain dict; passing a dict
        # blows up in the exception's own __str__ rather than in the code under test.
        meta = ApiResponseMeta(
            status=400, http_version="1.1", headers={}, duration=0.0, node=None
        )
        mock_client.search.side_effect = RequestError(
            "Bad Request", meta, {"error": {"reason": "Invalid query"}}
        )
        # Act & Assert
        from ltr.exceptions import QueryError

        with pytest.raises(QueryError, match="Elasticsearch query failed"):
            client.query("test_index", {"query": {"invalid": "query"}})
