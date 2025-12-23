"""Unit tests for solr_escape helper module."""

from ltr.helpers.solr_escape import esc_kw


class TestEscKw:
    """Test Solr keyword escaping functionality."""

    def test_no_escaping_needed(self):
        """Test that normal keywords are unchanged."""
        # Arrange
        keyword = "normal keyword"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "normal keyword"

    def test_backslash_escaping(self):
        """Test that backslashes are escaped first."""
        # Arrange
        keyword = "test\\backslash"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\\\backslash"

    def test_parentheses_escaping(self):
        """Test that parentheses are escaped."""
        # Arrange
        keyword = "test(1)"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\(1\\)"

    def test_operators_escaping(self):
        """Test that query operators are escaped."""
        # Arrange
        keyword = "test+plus-minus:colon"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\+plus\\-minus\\:colon"

    def test_special_chars_escaping(self):
        """Test that all special Solr characters are escaped."""
        # Arrange
        keyword = "test*/?[]{}~"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\*\\/\\?\\[\\]\\{\\}\\~"

    def test_slash_escaping(self):
        """Test that forward slashes are escaped."""
        # Arrange
        keyword = "test/path"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\/path"

    def test_all_special_chars(self):
        """Test escaping all special characters together."""
        # Arrange
        keyword = "\\()+-:/[]*?{}~"

        # Act
        result = esc_kw(keyword)

        # Assert
        # Backslash should be escaped first, then others
        assert "\\\\" in result
        assert "\\(" in result
        assert "\\)" in result
        assert "\\+" in result
        assert "\\-" in result
        assert "\\:" in result
        assert "\\/" in result
        assert "\\[" in result
        assert "\\]" in result
        assert "\\*" in result
        assert "\\?" in result
        assert "\\{" in result
        assert "\\}" in result
        assert "\\~" in result

    def test_empty_string(self):
        """Test that empty string is handled."""
        # Arrange
        keyword = ""

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == ""

    def test_multiple_occurrences(self):
        """Test that multiple occurrences of special chars are all escaped."""
        # Arrange
        keyword = "test++test--test"

        # Act
        result = esc_kw(keyword)

        # Assert
        assert result == "test\\+\\+test\\-\\-test"
