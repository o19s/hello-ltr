"""Unit tests for es_url_parse helper module."""

from ltr.helpers.es_url_parse import parse_url


class TestParseUrl:
    """Test Elasticsearch URL parsing functionality."""

    def test_parse_basic_url(self):
        """Test parsing a basic Elasticsearch URL."""
        # Arrange
        url = "http://localhost:9200/tmdb/_search"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == "tmdb"
        assert search_type == "_search"

    def test_parse_url_with_different_port(self):
        """Test parsing URL with different port."""
        # Arrange
        url = "http://localhost:9201/myindex/_search"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9201"
        assert index == "myindex"
        assert search_type == "_search"

    def test_parse_url_https(self):
        """Test parsing HTTPS URL."""
        # Arrange
        url = "https://example.com:9200/index/_search"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "https://example.com:9200"
        assert index == "index"
        assert search_type == "_search"

    def test_parse_url_with_path(self):
        """Test parsing URL with nested path."""
        # Arrange
        url = "http://localhost:9200/my_index/_doc"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == "my_index"
        assert search_type == "_doc"

    def test_parse_url_minimal(self):
        """Test parsing minimal URL structure."""
        # Arrange
        url = "http://localhost:9200/index/type"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == "index"
        assert search_type == "type"

    def test_parse_url_with_query_string(self):
        """Test parsing URL with query parameters."""
        # Arrange
        url = "http://localhost:9200/index/_search?q=test"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == "index"
        assert search_type == "_search"

    def test_parse_url_with_fragment(self):
        """Test parsing URL with fragment."""
        # Arrange
        url = "http://localhost:9200/index/_search#fragment"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == "index"
        assert search_type == "_search"

    def test_parse_url_no_path(self):
        """Test parsing URL with no path components."""
        # Arrange
        url = "http://localhost:9200/"

        # Act
        es_url, index, search_type = parse_url(url)

        # Assert
        assert es_url == "http://localhost:9200"
        assert index == ""
        assert search_type == ""
