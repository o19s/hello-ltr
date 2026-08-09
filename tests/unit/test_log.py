"""
Unit tests for FeatureLogger module.

Tests cover:
- FeatureLogger initialization
- log_for_qid method (feature logging, batch processing, missing documents)
- clear method
- Keyword sanitization
- drop_missing behavior
"""

import logging
from unittest.mock import Mock

from ltr.judgments import Judgment
from ltr.log import FeatureLogger


class TestFeatureLoggerInitialization:
    """Test FeatureLogger initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default drop_missing=True."""
        # Arrange
        mock_client = Mock()

        # Act
        logger = FeatureLogger(mock_client, "tmdb", "title")

        # Assert
        assert logger.client == mock_client
        assert logger.index == "tmdb"
        assert logger.feature_set == "title"
        assert logger.drop_missing is True
        assert logger.logged == []

    def test_init_with_drop_missing_false(self):
        """Test initialization with drop_missing=False."""
        # Arrange
        mock_client = Mock()

        # Act
        logger = FeatureLogger(mock_client, "tmdb", "title", drop_missing=False)

        # Assert
        assert logger.drop_missing is False
        assert logger.logged == []

    def test_init_with_custom_index_and_feature_set(self):
        """Test initialization with custom index and feature set."""
        # Arrange
        mock_client = Mock()

        # Act
        logger = FeatureLogger(mock_client, "movies", "genre")

        # Assert
        assert logger.index == "movies"
        assert logger.feature_set == "genre"


class TestFeatureLoggerClear:
    """Test FeatureLogger.clear method."""

    def test_clear_empties_logged_list(self):
        """Test that clear() empties the logged list."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment = Judgment(
            grade=1, qid=1, keywords="test", doc_id="1", features=[1.0, 2.0]
        )
        logger.logged = [judgment]

        # Act
        logger.clear()

        # Assert
        assert logger.logged == []

    def test_clear_allows_reuse(self):
        """Test that clear() allows logger to be reused."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment1 = Judgment(
            grade=1, qid=1, keywords="test", doc_id="1", features=[1.0]
        )
        logger.logged = [judgment1]

        # Act
        logger.clear()
        judgment2 = Judgment(
            grade=2, qid=2, keywords="test2", doc_id="2", features=[2.0]
        )
        logger.logged = [judgment2]

        # Assert
        assert len(logger.logged) == 1
        assert logger.logged[0] == judgment2


class TestFeatureLoggerLogForQid:
    """Test FeatureLogger.log_for_qid method."""

    def test_log_for_qid_successful_logging(self):
        """Test successful feature logging for judgments."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="2")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0, 2.0, 3.0]},
            {"id": "2", "ltr_features": [4.0, 5.0, 6.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(
            1, [judgment1, judgment2], "test query"
        )

        # Assert
        assert len(training_set) == 2
        assert len(discarded) == 0
        assert judgment1.features == [1.0, 2.0, 3.0]
        assert judgment2.features == [4.0, 5.0, 6.0]
        assert len(logger.logged) == 2
        mock_client.log_query.assert_called_once()
        call_args = mock_client.log_query.call_args
        assert call_args[0][0] == "tmdb"  # index
        assert call_args[0][1] == "title"  # feature_set
        assert call_args[0][2] == ["1", "2"]  # ids
        assert "keywords" in call_args[0][3]
        assert "fuzzy_keywords" in call_args[0][3]

    def test_log_for_qid_with_missing_documents_drop_missing_true(self):
        """Test logging with missing documents when drop_missing=True."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title", drop_missing=True)
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="2")
        judgment3 = Judgment(grade=3, qid=1, keywords="test", doc_id="3")

        # Only return features for doc 1 and 3, missing doc 2
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0, 2.0]},
            {"id": "3", "ltr_features": [3.0, 4.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(
            1, [judgment1, judgment2, judgment3], "test"
        )

        # Assert
        assert len(training_set) == 2
        assert len(discarded) == 1
        assert judgment1 in training_set
        assert judgment3 in training_set
        assert judgment2 in discarded
        assert judgment2.features == []  # Missing doc has no features

    def test_log_for_qid_with_missing_documents_drop_missing_false(self):
        """Test logging with missing documents when drop_missing=False."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title", drop_missing=False)
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="2")

        # Only return features for doc 1
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0, 2.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(1, [judgment1, judgment2], "test")

        # Assert
        assert len(training_set) == 2  # All judgments kept
        assert len(discarded) == 0
        assert judgment1 in training_set
        assert judgment2 in training_set
        assert judgment2.features == []  # Missing doc has no features but kept

    def test_log_for_qid_keyword_sanitization(self):
        """Test that keywords are sanitized for Solr compatibility."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment = Judgment(grade=1, qid=1, keywords="test", doc_id="1")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0]},
        ]

        # Act - keywords with special characters and underscores
        logger.log_for_qid(
            1, [judgment], "test_query_with_special-chars_and_underscores!"
        )

        # Assert
        call_args = mock_client.log_query.call_args
        sanitized_keywords = call_args[0][3]["keywords"]
        # Should remove special chars, underscores, but keep alphanumeric and spaces
        # Input has no spaces, so output has no spaces either
        assert sanitized_keywords == "testquerywithspecialcharsandunderscores"
        assert "_" not in sanitized_keywords
        assert "!" not in sanitized_keywords
        assert "-" not in sanitized_keywords

    def test_log_for_qid_fuzzy_keywords_generation(self):
        """Test that fuzzy keywords are generated correctly."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment = Judgment(grade=1, qid=1, keywords="test", doc_id="1")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0]},
        ]

        # Act
        logger.log_for_qid(1, [judgment], "test query")

        # Assert
        call_args = mock_client.log_query.call_args
        fuzzy_keywords = call_args[0][3]["fuzzy_keywords"]
        assert fuzzy_keywords == "test~ query~"

    def test_log_for_qid_batch_processing(self):
        """Test that documents are processed in batches of 500."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")

        # Create 750 judgments (should require 2 batches)
        judgments = [
            Judgment(grade=1, qid=1, keywords="test", doc_id=str(i)) for i in range(750)
        ]

        # Mock return value for each batch
        def log_query_side_effect(index, feature_set, ids, params):
            return [{"id": doc_id, "ltr_features": [float(doc_id)]} for doc_id in ids]

        mock_client.log_query.side_effect = log_query_side_effect

        # Act
        training_set, discarded = logger.log_for_qid(1, judgments, "test")

        # Assert
        assert len(training_set) == 750
        assert len(discarded) == 0
        assert mock_client.log_query.call_count == 2  # 500 + 250
        # First batch should have 500 docs
        first_call_ids = mock_client.log_query.call_args_list[0][0][2]
        assert len(first_call_ids) == 500
        # Second batch should have 250 docs
        second_call_ids = mock_client.log_query.call_args_list[1][0][2]
        assert len(second_call_ids) == 250

    def test_log_for_qid_empty_judgments(self):
        """Test logging with empty judgments list."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")

        # Act
        training_set, discarded = logger.log_for_qid(1, [], "test")

        # Assert
        assert len(training_set) == 0
        assert len(discarded) == 0
        assert discarded == []
        assert len(logger.logged) == 0
        mock_client.log_query.assert_not_called()

    def test_log_for_qid_duplicate_documents(self):
        """Test logging with duplicate document IDs."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        # Two judgments for same document
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="1")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0, 2.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(1, [judgment1, judgment2], "test")

        # Assert
        # Both judgments should get features (last one wins in features_per_doc dict)
        assert len(training_set) == 2
        assert len(discarded) == 0
        assert judgment1.features == [1.0, 2.0]
        assert judgment2.features == [1.0, 2.0]

    def test_log_for_qid_all_judgments_discarded_warning(self, caplog):
        """Test that warning is logged when all judgments are discarded."""
        # Arrange
        from ltr.logger import get_logger

        # Add caplog handler to the logger so it can capture logs
        ltr_logger = get_logger("ltr.log")
        caplog.handler.setLevel(logging.WARNING)
        ltr_logger.addHandler(caplog.handler)

        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title", drop_missing=True)
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="2")

        # Return empty result (no documents found)
        mock_client.log_query.return_value = []

        # Act
        training_set, discarded = logger.log_for_qid(1, [judgment1, judgment2], "test")

        # Assert
        assert len(training_set) == 0
        assert len(discarded) == 2
        # Check log records
        log_messages = " ".join([record.message for record in caplog.records])
        assert "All" in log_messages
        assert "judgments" in log_messages
        assert "discarded" in log_messages

    def test_log_for_qid_partial_discard_warning(self, caplog):
        """Test that warning is logged when more judgments are discarded than kept."""
        # Arrange
        from ltr.logger import get_logger

        # Add caplog handler to the logger so it can capture logs
        ltr_logger = get_logger("ltr.log")
        caplog.handler.setLevel(logging.WARNING)
        ltr_logger.addHandler(caplog.handler)

        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title", drop_missing=True)
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=1, keywords="test", doc_id="2")
        judgment3 = Judgment(grade=3, qid=1, keywords="test", doc_id="3")

        # Only return features for doc 1 (1 kept, 2 discarded)
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(
            1, [judgment1, judgment2, judgment3], "test"
        )

        # Assert
        assert len(training_set) == 1
        assert len(discarded) == 2
        # Check log records
        log_messages = " ".join([record.message for record in caplog.records])
        assert "discarded" in log_messages
        assert "kept" in log_messages

    def test_log_for_qid_accumulates_logged(self):
        """Test that log_for_qid accumulates judgments in logged list."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment1 = Judgment(grade=1, qid=1, keywords="test", doc_id="1")
        judgment2 = Judgment(grade=2, qid=2, keywords="test2", doc_id="2")

        def log_query_side_effect(index, feature_set, ids, params):
            return [{"id": doc_id, "ltr_features": [float(doc_id)]} for doc_id in ids]

        mock_client.log_query.side_effect = log_query_side_effect

        # Act
        logger.log_for_qid(1, [judgment1], "test")
        logger.log_for_qid(2, [judgment2], "test2")

        # Assert
        assert len(logger.logged) == 2
        assert judgment1 in logger.logged
        assert judgment2 in logger.logged

    def test_log_for_qid_with_iterable(self):
        """Test that log_for_qid accepts iterables (not just lists)."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")

        def judgment_generator():
            for i in range(3):
                yield Judgment(grade=i, qid=1, keywords="test", doc_id=str(i))

        mock_client.log_query.return_value = [
            {"id": "0", "ltr_features": [0.0]},
            {"id": "1", "ltr_features": [1.0]},
            {"id": "2", "ltr_features": [2.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(1, judgment_generator(), "test")

        # Assert
        assert len(training_set) == 3
        assert len(discarded) == 0

    def test_log_for_qid_keywords_list_parameter(self):
        """Test that keywordsList parameter is included in log_query call."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment = Judgment(grade=1, qid=1, keywords="test", doc_id="1")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0]},
        ]

        # Act
        logger.log_for_qid(1, [judgment], "test query")

        # Assert
        call_args = mock_client.log_query.call_args
        params = call_args[0][3]
        assert "keywordsList" in params
        assert params["keywordsList"] == ["test query"]

    def test_log_for_qid_empty_keywords(self):
        """Test logging with empty keywords string."""
        # Arrange
        mock_client = Mock()
        logger = FeatureLogger(mock_client, "tmdb", "title")
        judgment = Judgment(grade=1, qid=1, keywords="", doc_id="1")

        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [1.0]},
        ]

        # Act
        training_set, discarded = logger.log_for_qid(1, [judgment], "")

        # Assert
        assert len(training_set) == 1
        assert len(discarded) == 0
        call_args = mock_client.log_query.call_args
        params = call_args[0][3]
        assert params["keywords"] == ""
        assert params["fuzzy_keywords"] == ""
