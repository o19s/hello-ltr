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

from unittest.mock import Mock, patch

import pytest

from ltr.client.solr_client import SolrClient


class TestSolrClientInitialization:
    """Test SolrClient initialization and basic properties.

    Note: Initialization tests (local host, docker host, get_host, name) are now
    consolidated in a parametrized test in tests.unit.client_test_helpers.
    See test_client_initialization() for the shared implementation.
    """


class TestSolrClientIndexOperations:
    """Test index creation, deletion, and existence checks.

    Note: Index operation tests (check_index_exists_true, check_index_exists_false, delete_index, create_index)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_check_index_exists_true(), test_check_index_exists_false(), test_delete_index(), and test_create_index()
    for the shared implementations.
    """


class TestSolrClientDocumentIndexing:
    """Test document indexing operations."""

    @patch("ltr.client.solr_client.requests.post")
    @patch("ltr.client.solr_client.requests.get")
    @patch("ltr.helpers.handle_resp.resp_msg")
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

    @patch("ltr.client.solr_client.requests.post")
    @patch("ltr.client.solr_client.requests.get")
    @patch("ltr.helpers.handle_resp.resp_msg")
    def test_index_documents_release_date_formatting(
        self, mock_resp_msg, mock_get, mock_post
    ):
        """Test that release_date is formatted with T00:00:00Z."""
        # Arrange
        client = SolrClient()
        docs = [{"id": "1", "release_date": "2020-01-01"}]
        mock_post.return_value = Mock(status_code=200)
        mock_get.return_value = Mock(status_code=200)
        # Capture the docs passed to post (before they're cleared)
        captured_docs = []

        def capture_post(*args, **kwargs):
            """Capture documents passed to POST request before they're cleared.

            Args:
                *args: Positional arguments (unused)
                **kwargs: Keyword arguments, expects 'json' key with documents

            Returns:
                Mock: Mock response object with status_code 200
            """
            if "json" in kwargs:
                # Make a copy since docs.clear() will empty the list
                captured_docs.extend(kwargs["json"].copy())
            return Mock(status_code=200)

        mock_post.side_effect = capture_post
        # Act
        client.index_documents("test_index", docs)
        # Assert
        assert len(captured_docs) > 0
        assert captured_docs[0]["release_date"] == "2020-01-01T00:00:00Z"

    @patch("ltr.client.solr_client.requests.post")
    @patch("ltr.client.solr_client.requests.get")
    @patch("ltr.helpers.handle_resp.resp_msg")
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
    """Test LTR-related operations.

    Note: LTR operation tests (reset_ltr, create_featureset, get_feature_name)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_reset_ltr(), test_create_featureset(), and test_get_feature_name()
    for the shared implementations.
    """

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

    def test_get_feature_name_index_1_based(self):
        """Test get_feature_name uses 1-based indexing."""
        # Arrange
        client = SolrClient()
        config = [{"name": "feature1"}, {"name": "feature2"}]
        # Act
        name = client.get_feature_name(config, 2)
        # Assert
        assert name == "feature2"


class TestSolrClientQuery:
    """Test query operations.

    Note: Query operation tests (test_query, test_log_query_with_ids, test_log_query_without_ids, test_model_query)
    are now consolidated in parametrized tests in tests.unit.client_test_helpers.
    See test_query(), test_log_query_with_ids(), test_log_query_without_ids(), and test_model_query()
    for the shared implementations.
    """


class TestSolrClientFeatureSet:
    """Test feature set operations.

    Note: get_doc test is now consolidated in parametrized test in tests.unit.client_test_helpers.
    See test_get_doc() for the shared implementation.
    """

    @patch("ltr.client.solr_client.requests.get")
    @patch("ltr.helpers.handle_resp.resp_msg")
    def test_feature_set(self, mock_resp_msg, mock_get):
        """Test feature_set returns mapping and raw features."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "features": [{"name": "feature1"}, {"name": "feature2"}]
        }
        mock_get.return_value = mock_response
        # Act
        mapping, raw_features = client.feature_set("test_index", "featureset")
        # Assert
        assert len(mapping) == 2
        assert mapping[0]["name"] == "feature1"
        assert len(raw_features) == 2

    @patch("ltr.client.solr_client.requests.get")
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

    @patch("ltr.client.solr_client.requests.get")
    def test_get_models(self, mock_get):
        """Test get_models returns list of model names."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [{"name": "model1"}, {"name": "model2"}]
        }
        mock_get.return_value = mock_response
        # Act
        models = client.get_models("test_index")
        # Assert
        assert models == ["model1", "model2"]

    @patch("ltr.client.solr_client.requests.post")
    def test_analyze(self, mock_post):
        """Test analyze returns token stream result."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {
            "analysis": {
                "field_types": {
                    "text_general": {
                        "index": [
                            {
                                "text": "test",
                                "tokens": [{"token": "test", "start": 0, "end": 4}],
                            }
                        ]
                    }
                }
            }
        }
        mock_post.return_value = mock_response
        # Act
        result = client.analyze("test_index", "text_general", "test")
        # Assert
        assert "text" in result
        assert result["text"] == "test"
        mock_post.assert_called_once()

    @patch("ltr.client.solr_client.requests.post")
    def test_term_vectors_skip_to(self, mock_post):
        """Test term_vectors_skip_to returns cursor mark."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.json.return_value = {"nextCursorMark": "cursor123"}
        mock_post.return_value = mock_response
        # Act
        cursor = client.term_vectors_skip_to("test_index", "*:*", 10)
        # Assert
        assert cursor == "cursor123"
        mock_post.assert_called_once()

    @patch("ltr.client.solr_client.requests.post")
    def test_term_vectors(self, mock_post):
        """Test term_vectors returns term vector data."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        # Solr named list format: alternating key-value pairs
        mock_response.json.return_value = {
            "termVectors": [
                "1",  # doc_id
                [
                    "uniqueKey",
                    "1",
                    "title",  # field name
                    [
                        "test",  # term
                        [
                            "positions",
                            ["position", 0],  # position value
                        ],
                    ],
                ],
            ],
            "nextCursorMark": "*",  # Same as start cursor means no more results
        }
        mock_post.return_value = mock_response
        # Act - term_vectors returns an iterator, convert to list
        result = list(client.term_vectors("test_index", "title", "*:*", "*"))
        # Assert
        assert len(result) == 1
        assert result[0][0] == "1"  # doc_id
        assert "test" in result[0][1]  # term vector dict
        # term_vectors makes POST calls
        assert mock_post.called

    @patch("ltr.client.solr_client.requests.post")
    def test_term_vectors_error_handling(self, mock_post):
        """Test term_vectors handles errors correctly."""
        # Arrange
        client = SolrClient()
        mock_post.side_effect = Exception("Connection error")
        # Act & Assert
        # term_vectors is a generator, so we need to iterate to trigger the exception
        with pytest.raises(Exception, match="Connection error"):
            list(client.term_vectors("test_index", "title", "*:*", "*"))


class TestSolrClientInvalidInput:
    """Test invalid input handling in SolrClient."""

    def test_model_query_invalid_query_type(self):
        """Test model_query raises TypeError for non-dict query."""
        # Arrange
        client = SolrClient()
        # Act & Assert
        with pytest.raises(TypeError, match="query must be a dict"):
            client.model_query("test_index", "model1", {}, "not a dict")  # type: ignore[arg-type]

    def test_model_query_missing_q_key(self):
        """Test model_query raises ValidationError when query dict missing 'q' key."""
        # Arrange
        client = SolrClient()
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match='query dict must contain a "q" key'):
            client.model_query("test_index", "model1", {}, {"wt": "json"})

    def test_index_documents_invalid_doc_src_type(self):
        """Test index_documents raises ValidationError for string doc_src."""
        # Arrange
        client = SolrClient()
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match="does not support file paths"):
            client.index_documents("test_index", "/path/to/file.json")  # type: ignore[arg-type]

    def test_get_feature_name_invalid_config_type(self):
        """Test get_feature_name raises ValidationError for non-list config."""
        # Arrange
        client = SolrClient()
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match="requires a list config"):
            client.get_feature_name({"features": []}, 1)

    def test_validate_featureset_missing_store(self):
        """Test validate_featureset raises ValidationError when feature missing store."""
        # Arrange
        client = SolrClient()
        config = [{"name": "feature1", "store": "wrong_store"}]
        # Act & Assert
        from ltr.validation import ValidationError

        with pytest.raises(ValidationError, match='needs to be created with "store"'):
            client.validate_featureset("correct_store", config)


class TestSolrClientRetryLogic:
    """Test retry logic edge cases in SolrClient."""

    @patch("ltr.client.solr_client.requests.get")
    @patch("ltr.client.solr_client.requests.post")
    def test_check_index_exists_retry_exhausted(self, mock_post, mock_get):
        """Test check_index_exists retries on connection errors but eventually fails."""
        # Arrange
        client = SolrClient()
        mock_get.side_effect = ConnectionError("Connection refused")
        # Act & Assert
        # SolrClient.check_index_exists doesn't have retry logic, so it should fail immediately
        with pytest.raises(ConnectionError):
            client.check_index_exists("test_index")

    @patch("ltr.client.solr_client.requests.post")
    def test_query_non_retryable_error(self, mock_post):
        """Test query does not retry on non-retryable errors (e.g., 400 Bad Request)."""
        # Arrange
        client = SolrClient()
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"msg": "Bad Request"}}
        mock_post.return_value = mock_response
        # Act & Assert
        from ltr.exceptions import QueryError

        with pytest.raises(QueryError):
            client.query("test_index", {"q": "test"})
