"""Unit tests for validation module."""

import pytest

from ltr.validation import (
    ValidationError,
    sanitize_for_solr_query,
    validate_index_name,
    validate_keywords,
    validate_model_name,
)


class TestValidateIndexName:
    """Test index name validation."""

    def test_valid_index_names(self):
        """Test that valid index names pass validation."""
        # Arrange
        valid_names = ["tmdb", "my_index", "test-123", "index_1", "a", "a1"]
        # Act & Assert
        for name in valid_names:
            assert validate_index_name(name) == name

    def test_invalid_index_names(self):
        """Test that invalid index names raise ValidationError."""
        # Arrange
        invalid_names = [
            "",  # Empty
            " ",  # Whitespace only
            "Invalid Index",  # Spaces
            "InvalidIndex",  # Uppercase start
            "123index",  # Starts with digit (some engines don't allow)
            "index@name",  # Special characters
            "index.name",  # Dots
            "index/name",  # Slashes
        ]
        # Act & Assert
        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_index_name(name)

    def test_index_name_too_long(self):
        """Test that overly long index names are rejected."""
        # Arrange
        long_name = "a" * 256  # Exceeds MAX_INDEX_NAME_LENGTH
        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            validate_index_name(long_name)

    def test_index_name_not_string(self):
        """Test that non-string inputs are rejected."""
        # Arrange
        invalid_inputs = [123, None, []]
        # Act & Assert
        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationError, match="must be a string"):
                validate_index_name(invalid_input)

    def test_index_name_strips_whitespace(self):
        """Test that whitespace is stripped before validation."""
        # Arrange
        name_with_whitespace = "  tmdb  "
        whitespace_only = "   "
        # Act & Assert
        assert validate_index_name(name_with_whitespace) == "tmdb"
        # But whitespace-only should fail
        with pytest.raises(ValidationError):
            validate_index_name(whitespace_only)


class TestValidateModelName:
    """Test model name validation."""

    def test_valid_model_names(self):
        """Test that valid model names pass validation."""
        # Arrange
        valid_names = [
            "my_model",
            "Model-123",
            "test_model",
            "MODEL_NAME",
            "model123",
            "a",
            "A",
        ]
        # Act & Assert
        for name in valid_names:
            assert validate_model_name(name) == name

    def test_invalid_model_names(self):
        """Test that invalid model names raise ValidationError."""
        # Arrange
        invalid_names = [
            "",  # Empty
            " ",  # Whitespace only
            "invalid model name",  # Spaces
            "model@name",  # Special characters
            "model.name",  # Dots
            "model/name",  # Slashes
            "123model",  # Starts with digit
        ]
        # Act & Assert
        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_model_name(name)

    def test_model_name_too_long(self):
        """Test that overly long model names are rejected."""
        # Arrange
        long_name = "a" * 256  # Exceeds MAX_MODEL_NAME_LENGTH
        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            validate_model_name(long_name)

    def test_model_name_not_string(self):
        """Test that non-string inputs are rejected."""
        # Arrange
        invalid_inputs = [123, None]
        # Act & Assert
        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationError, match="must be a string"):
                validate_model_name(invalid_input)


class TestValidateKeywords:
    """Test keywords validation."""

    def test_valid_keywords(self):
        """Test that valid keywords pass validation."""
        # Arrange
        valid_keywords = [
            "action movie",
            "test",
            "multi word query",
            "query\nwith\nnewlines",
            "query\twith\ttabs",
        ]
        # Act & Assert
        for keywords in valid_keywords:
            assert validate_keywords(keywords) == keywords.strip()

    def test_invalid_keywords(self):
        """Test that invalid keywords raise ValidationError."""
        # Arrange
        invalid_keywords = [
            "",  # Empty
            " ",  # Whitespace only
            "query\x00with\x00nulls",  # Null bytes
            "query\x01with\x02control",  # Control characters
        ]
        # Act & Assert
        for keywords in invalid_keywords:
            with pytest.raises(ValidationError):
                validate_keywords(keywords)

    def test_keywords_too_long(self):
        """Test that overly long keywords are rejected."""
        # Arrange
        long_keywords = "a" * 10001  # Exceeds MAX_KEYWORDS_LENGTH
        # Act & Assert
        with pytest.raises(ValidationError, match="too long"):
            validate_keywords(long_keywords)

    def test_keywords_not_string(self):
        """Test that non-string inputs are rejected."""
        # Arrange
        invalid_inputs = [123, None]
        # Act & Assert
        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationError, match="must be a string"):
                validate_keywords(invalid_input)

    def test_keywords_strips_whitespace(self):
        """Test that whitespace is stripped before validation."""
        # Arrange
        keywords_with_whitespace = "  test query  "
        whitespace_only = "   "
        # Act & Assert
        assert validate_keywords(keywords_with_whitespace) == "test query"
        # But whitespace-only should fail
        with pytest.raises(ValidationError):
            validate_keywords(whitespace_only)


class TestSanitizeForSolrQuery:
    """Test Solr query sanitization."""

    def test_sanitize_normal_string(self):
        """Test that normal strings are unchanged."""
        # Arrange
        normal_strings = ["test", "normal query"]
        # Act & Assert
        assert sanitize_for_solr_query(normal_strings[0]) == "test"
        assert sanitize_for_solr_query(normal_strings[1]) == "normal query"

    def test_sanitize_quotes(self):
        """Test that quotes are escaped."""
        # Arrange
        strings_with_quotes = ['test"value', 'test"value"again']
        expected_results = ['test\\"value', 'test\\"value\\"again']
        # Act & Assert
        assert sanitize_for_solr_query(strings_with_quotes[0]) == expected_results[0]
        assert sanitize_for_solr_query(strings_with_quotes[1]) == expected_results[1]

    def test_sanitize_backslashes(self):
        """Test that backslashes are escaped."""
        # Arrange
        strings_with_backslashes = ["test\\value", "test\\value\\again"]
        expected_results = ["test\\\\value", "test\\\\value\\\\again"]
        # Act & Assert
        assert (
            sanitize_for_solr_query(strings_with_backslashes[0]) == expected_results[0]
        )
        assert (
            sanitize_for_solr_query(strings_with_backslashes[1]) == expected_results[1]
        )

    def test_sanitize_control_characters(self):
        """Test that control characters are removed."""
        # Arrange
        strings_with_control_chars = ["test\x00value", "test\x01\x02value"]
        expected_result = "testvalue"
        # Act & Assert
        assert sanitize_for_solr_query(strings_with_control_chars[0]) == expected_result
        assert sanitize_for_solr_query(strings_with_control_chars[1]) == expected_result

    def test_sanitize_not_string(self):
        """Test that non-string inputs raise ValidationError."""
        # Arrange
        invalid_inputs = [123, None]
        # Act & Assert
        for invalid_input in invalid_inputs:
            with pytest.raises(ValidationError, match="must be a string"):
                sanitize_for_solr_query(invalid_input)
