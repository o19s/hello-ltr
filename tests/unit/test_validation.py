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
        valid_names = ["tmdb", "my_index", "test-123", "index_1", "a", "a1"]
        for name in valid_names:
            assert validate_index_name(name) == name

    def test_invalid_index_names(self):
        """Test that invalid index names raise ValidationError."""
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
        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_index_name(name)

    def test_index_name_too_long(self):
        """Test that overly long index names are rejected."""
        long_name = "a" * 256  # Exceeds MAX_INDEX_NAME_LENGTH
        with pytest.raises(ValidationError, match="too long"):
            validate_index_name(long_name)

    def test_index_name_not_string(self):
        """Test that non-string inputs are rejected."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_index_name(123)
        with pytest.raises(ValidationError, match="must be a string"):
            validate_index_name(None)
        with pytest.raises(ValidationError, match="must be a string"):
            validate_index_name([])

    def test_index_name_strips_whitespace(self):
        """Test that whitespace is stripped before validation."""
        assert validate_index_name("  tmdb  ") == "tmdb"
        # But whitespace-only should fail
        with pytest.raises(ValidationError):
            validate_index_name("   ")


class TestValidateModelName:
    """Test model name validation."""

    def test_valid_model_names(self):
        """Test that valid model names pass validation."""
        valid_names = [
            "my_model",
            "Model-123",
            "test_model",
            "MODEL_NAME",
            "model123",
            "a",
            "A",
        ]
        for name in valid_names:
            assert validate_model_name(name) == name

    def test_invalid_model_names(self):
        """Test that invalid model names raise ValidationError."""
        invalid_names = [
            "",  # Empty
            " ",  # Whitespace only
            "invalid model name",  # Spaces
            "model@name",  # Special characters
            "model.name",  # Dots
            "model/name",  # Slashes
            "123model",  # Starts with digit
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_model_name(name)

    def test_model_name_too_long(self):
        """Test that overly long model names are rejected."""
        long_name = "a" * 256  # Exceeds MAX_MODEL_NAME_LENGTH
        with pytest.raises(ValidationError, match="too long"):
            validate_model_name(long_name)

    def test_model_name_not_string(self):
        """Test that non-string inputs are rejected."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_model_name(123)
        with pytest.raises(ValidationError, match="must be a string"):
            validate_model_name(None)


class TestValidateKeywords:
    """Test keywords validation."""

    def test_valid_keywords(self):
        """Test that valid keywords pass validation."""
        valid_keywords = [
            "action movie",
            "test",
            "multi word query",
            "query\nwith\nnewlines",
            "query\twith\ttabs",
        ]
        for keywords in valid_keywords:
            assert validate_keywords(keywords) == keywords.strip()

    def test_invalid_keywords(self):
        """Test that invalid keywords raise ValidationError."""
        invalid_keywords = [
            "",  # Empty
            " ",  # Whitespace only
            "query\x00with\x00nulls",  # Null bytes
            "query\x01with\x02control",  # Control characters
        ]
        for keywords in invalid_keywords:
            with pytest.raises(ValidationError):
                validate_keywords(keywords)

    def test_keywords_too_long(self):
        """Test that overly long keywords are rejected."""
        long_keywords = "a" * 10001  # Exceeds MAX_KEYWORDS_LENGTH
        with pytest.raises(ValidationError, match="too long"):
            validate_keywords(long_keywords)

    def test_keywords_not_string(self):
        """Test that non-string inputs are rejected."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_keywords(123)
        with pytest.raises(ValidationError, match="must be a string"):
            validate_keywords(None)

    def test_keywords_strips_whitespace(self):
        """Test that whitespace is stripped before validation."""
        assert validate_keywords("  test query  ") == "test query"
        # But whitespace-only should fail
        with pytest.raises(ValidationError):
            validate_keywords("   ")


class TestSanitizeForSolrQuery:
    """Test Solr query sanitization."""

    def test_sanitize_normal_string(self):
        """Test that normal strings are unchanged."""
        assert sanitize_for_solr_query("test") == "test"
        assert sanitize_for_solr_query("normal query") == "normal query"

    def test_sanitize_quotes(self):
        """Test that quotes are escaped."""
        assert sanitize_for_solr_query('test"value') == 'test\\"value'
        assert sanitize_for_solr_query('test"value"again') == 'test\\"value\\"again'

    def test_sanitize_backslashes(self):
        """Test that backslashes are escaped."""
        assert sanitize_for_solr_query("test\\value") == "test\\\\value"
        assert sanitize_for_solr_query("test\\value\\again") == "test\\\\value\\\\again"

    def test_sanitize_control_characters(self):
        """Test that control characters are removed."""
        assert sanitize_for_solr_query("test\x00value") == "testvalue"
        assert sanitize_for_solr_query("test\x01\x02value") == "testvalue"

    def test_sanitize_not_string(self):
        """Test that non-string inputs raise ValidationError."""
        with pytest.raises(ValidationError, match="must be a string"):
            sanitize_for_solr_query(123)
        with pytest.raises(ValidationError, match="must be a string"):
            sanitize_for_solr_query(None)
