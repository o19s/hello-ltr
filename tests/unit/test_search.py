"""
Unit tests for search.py module.

Tests cover:
- es_ltr_query function
- solr_ltr_query function
- search function for different clients
"""

from unittest.mock import Mock

from ltr.search import es_ltr_query, search, solr_ltr_query, tmdb_fields


class TestEsLtrQuery:
    """Test Elasticsearch LTR query generation."""

    def test_es_ltr_query_sets_keywords(self):
        """Test es_ltr_query sets keywords correctly."""
        # Act
        query = es_ltr_query("test query", "mymodel")
        # Assert
        assert (
            query["query"]["sltr"]["params"]["keywords"] == "test query"
        ), f"Keywords mismatch. Expected 'test query', got {query['query']['sltr']['params'].get('keywords', 'MISSING')}"
        assert (
            query["query"]["sltr"]["params"]["keywordsList"] == ["test query"]
        ), f"KeywordsList mismatch. Expected ['test query'], got {query['query']['sltr']['params'].get('keywordsList', 'MISSING')}"
        assert (
            query["query"]["sltr"]["model"] == "mymodel"
        ), f"Model name mismatch. Expected 'mymodel', got {query['query']['sltr'].get('model', 'MISSING')}"

    def test_es_ltr_query_uses_base_structure(self):
        """Test es_ltr_query uses base query structure."""
        # Act
        query = es_ltr_query("test", "model")
        # Assert
        assert "size" in query
        assert query["size"] == 5
        assert "query" in query
        assert "sltr" in query["query"]


class TestSolrLtrQuery:
    """Test Solr LTR query generation."""

    def test_solr_ltr_query_removes_special_chars(self):
        """Test solr_ltr_query removes special characters."""
        # Act
        query = solr_ltr_query("test_query!@#", "mymodel")
        # Assert
        assert "testquery" in query["q"].lower()
        assert "!@#" not in query["q"]

    def test_solr_ltr_query_adds_fuzzy(self):
        """Test solr_ltr_query adds fuzzy operators."""
        # Act
        query = solr_ltr_query("test query", "mymodel")
        # Assert
        assert "test~" in query["q"]
        assert "query~" in query["q"]

    def test_solr_ltr_query_includes_model(self):
        """Test solr_ltr_query includes model name."""
        # Act
        query = solr_ltr_query("test", "mymodel")
        # Assert
        assert "model=mymodel" in query["q"]

    def test_solr_ltr_query_has_correct_structure(self):
        """Test solr_ltr_query has correct fields."""
        # Act
        query = solr_ltr_query("test", "model")
        # Assert
        assert "fl" in query
        assert "rows" in query
        assert query["rows"] == 5


class TestSearch:
    """Test search function."""

    def test_search_elastic_client(self):
        """Test search with Elasticsearch client."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "elastic"
        mock_client.query.return_value = [
            {"title": "Movie1", "_score": 0.9, "release_year": 2020}
        ]
        # Act
        search(mock_client, "test query", "mymodel", index="tmdb", fields=tmdb_fields)
        # Assert
        assert (
            mock_client.query.called
        ), "Expected query() to be called on Elasticsearch client"
        call_args = mock_client.query.call_args
        assert (
            call_args[0][0] == "tmdb"
        ), f"Index mismatch. Expected 'tmdb', got {call_args[0][0]!r}. Full call args: {call_args}"
        assert (
            call_args[0][1]["query"]["sltr"]["model"] == "mymodel"
        ), f"Model mismatch. Expected 'mymodel', got {call_args[0][1]['query']['sltr'].get('model', 'MISSING')}. Full query: {call_args[0][1]}"

    def test_search_opensearch_client(self):
        """Test search with OpenSearch client."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "opensearch"
        mock_client.query.return_value = [{"title": "Movie1", "_score": 0.9}]
        # Act
        search(mock_client, "test query", "mymodel", index="tmdb", fields=tmdb_fields)
        # Assert
        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args
        assert call_args[0][1]["query"]["sltr"]["model"] == "mymodel"

    def test_search_solr_client(self):
        """Test search with Solr client."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [{"title": "Movie1", "_score": 0.9}]
        # Act
        search(mock_client, "test query", "mymodel", index="tmdb", fields=tmdb_fields)
        # Assert
        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args
        assert call_args[0][0] == "tmdb"
        assert "ltr" in call_args[0][1]["q"]

    def test_search_custom_fields(self):
        """Test search with custom field mapping."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "elastic"
        mock_client.query.return_value = [{"name": "Movie1", "_score": 0.9}]
        custom_fields = {"title": "name", "display_fields": ["year"]}
        # Act
        search(mock_client, "test", "model", index="test", fields=custom_fields)
        # Assert
        mock_client.query.assert_called_once()

    def test_search_default_index(self):
        """Test search uses default index 'tmdb'."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "elastic"
        mock_client.query.return_value = []
        # Act
        search(mock_client, "test", "model")
        # Assert
        call_args = mock_client.query.call_args
        assert call_args[0][0] == "tmdb"
