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

from ltr.client.elastic_client import ElasticResp
from ltr.client.responses import BulkResp, SearchResp


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
    """Test model submission operations.

    Note: Model operation tests (test_submit_model, test_submit_ranklib_model, test_submit_xgboost_model)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_submit_model(), test_submit_ranklib_model(), and test_submit_xgboost_model()
    for the shared implementations.
    """


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
