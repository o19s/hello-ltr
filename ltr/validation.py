"""Input validation utilities for Learn-to-Rank operations.

This module provides validation functions for user-provided inputs to prevent
injection attacks and ensure data integrity.
"""

import re
from typing import Any

from ltr.logger import get_logger

logger = get_logger(__name__)

# Valid characters for index names: alphanumeric, underscore, hyphen
# Elasticsearch/OpenSearch/Solr index names must start with lowercase letter or underscore
# Cannot start with a digit
INDEX_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]*$")

# Valid characters for model/feature set names: alphanumeric, underscore, hyphen
# Similar to index names but may allow uppercase
# Cannot start with a digit
MODEL_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

# Maximum lengths to prevent DoS attacks
MAX_INDEX_NAME_LENGTH = 255
MAX_MODEL_NAME_LENGTH = 255
MAX_KEYWORDS_LENGTH = 10000  # Allow longer keywords for search queries


class ValidationError(ValueError):
    """Raised when input validation fails."""

    pass


def validate_index_name(index: Any) -> str:
    """Validate an index name.

    Index names must:
    - Start with a lowercase letter, digit, or underscore
    - Contain only lowercase letters, digits, underscores, and hyphens
    - Be between 1 and 255 characters
    - Not be empty

    Args:
        index: Index name to validate.

    Returns:
        str: The validated index name (unchanged if valid).

    Raises:
        ValidationError: If the index name is invalid.

    Examples:
        >>> validate_index_name("tmdb")
        'tmdb'
        >>> validate_index_name("my_index")
        'my_index'
        >>> validate_index_name("Invalid Index")
        Traceback (most recent call last):
        ...
        ValidationError: Invalid index name: 'Invalid Index'
    """
    if not isinstance(index, str):
        raise ValidationError(
            f"Index name must be a string, got {type(index).__name__}"
        )

    index = index.strip()

    if not index:
        raise ValidationError("Index name cannot be empty")

    if len(index) > MAX_INDEX_NAME_LENGTH:
        raise ValidationError(
            f"Index name too long (max {MAX_INDEX_NAME_LENGTH} characters): {len(index)}"
        )

    if not INDEX_NAME_PATTERN.match(index):
        raise ValidationError(
            f"Invalid index name: {index!r}. "
            "Must start with lowercase letter, digit, or underscore, "
            "and contain only lowercase letters, digits, underscores, and hyphens."
        )

    return index


def validate_model_name(model_name: Any) -> str:
    """Validate a model or feature set name.

    Model names must:
    - Start with a letter, digit, or underscore
    - Contain only letters, digits, underscores, and hyphens
    - Be between 1 and 255 characters
    - Not be empty

    Args:
        model_name: Model or feature set name to validate.

    Returns:
        str: The validated model name (unchanged if valid).

    Raises:
        ValidationError: If the model name is invalid.

    Examples:
        >>> validate_model_name("my_model")
        'my_model'
        >>> validate_model_name("Model-123")
        'Model-123'
        >>> validate_model_name("invalid model name")
        Traceback (most recent call last):
        ...
        ValidationError: Invalid model name: 'invalid model name'
    """
    if not isinstance(model_name, str):
        raise ValidationError(
            f"Model name must be a string, got {type(model_name).__name__}"
        )

    model_name = model_name.strip()

    if not model_name:
        raise ValidationError("Model name cannot be empty")

    if len(model_name) > MAX_MODEL_NAME_LENGTH:
        raise ValidationError(
            f"Model name too long (max {MAX_MODEL_NAME_LENGTH} characters): {len(model_name)}"
        )

    if not MODEL_NAME_PATTERN.match(model_name):
        raise ValidationError(
            f"Invalid model name: {model_name!r}. "
            "Must start with letter, digit, or underscore, "
            "and contain only letters, digits, underscores, and hyphens."
        )

    return model_name


def validate_keywords(keywords: Any) -> str:
    """Validate search keywords.

    Keywords must:
    - Be a non-empty string
    - Not exceed maximum length
    - Not contain control characters (except newlines/tabs for multi-line queries)

    Args:
        keywords: Search keywords to validate.

    Returns:
        str: The validated keywords (unchanged if valid).

    Raises:
        ValidationError: If the keywords are invalid.

    Examples:
        >>> validate_keywords("action movie")
        'action movie'
        >>> validate_keywords("")
        Traceback (most recent call last):
        ...
        ValidationError: Keywords cannot be empty
    """
    if not isinstance(keywords, str):
        raise ValidationError(
            f"Keywords must be a string, got {type(keywords).__name__}"
        )

    keywords = keywords.strip()

    if not keywords:
        raise ValidationError("Keywords cannot be empty")

    if len(keywords) > MAX_KEYWORDS_LENGTH:
        raise ValidationError(
            f"Keywords too long (max {MAX_KEYWORDS_LENGTH} characters): {len(keywords)}"
        )

    # Check for control characters (except newline, tab, carriage return)
    if re.search(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", keywords):
        raise ValidationError(
            "Keywords contain invalid control characters. "
            "Only printable characters, spaces, newlines, and tabs are allowed."
        )

    return keywords


def sanitize_for_solr_query(value: Any) -> str:
    """Sanitize a value for use in Solr query strings.

    This function escapes special characters that could be used for query injection.
    Note: This is a basic sanitization. For complex queries, use parameterized
    queries or query builders instead.

    Args:
        value: String value to sanitize.

    Returns:
        str: Sanitized string safe for use in Solr queries.

    Examples:
        >>> sanitize_for_solr_query("test")
        'test'
        >>> sanitize_for_solr_query('test"value')
        'test\\"value'
    """
    if not isinstance(value, str):
        raise ValidationError(f"Value must be a string, got {type(value).__name__}")

    # Escape Solr special characters: " \ and control characters
    # Replace quotes and backslashes
    sanitized = value.replace("\\", "\\\\").replace('"', '\\"')

    # Remove or escape control characters
    sanitized = re.sub(r"[\x00-\x1f]", "", sanitized)

    return sanitized
