"""Tests for ltr.exceptions module.

This module tests the exception hierarchy and error handling functionality.
"""

import pytest

from ltr.exceptions import (
    ClientError,
    LTRConnectionError,
    LTRError,
    LTRIndexError,
    ModelError,
    QueryError,
)


class TestLTRError:
    """Test the base LTRError exception class."""

    def test_basic_error_creation(self):
        """Test creating a basic error without context."""
        error = LTRError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.context == {}

    def test_error_with_context(self):
        """Test creating an error with context."""
        context = {"index": "test_index", "operation": "query"}
        error = LTRError("Test error", context=context)
        assert error.message == "Test error"
        assert error.context == context
        assert "index=test_index" in str(error)
        assert "operation=query" in str(error)

    def test_error_inheritance(self):
        """Test that LTRError is a proper Exception."""
        error = LTRError("Test")
        assert isinstance(error, Exception)


class TestClientError:
    """Test the ClientError exception class."""

    def test_basic_client_error(self):
        """Test creating a basic client error."""
        error = ClientError("Connection failed", client_name="solr")
        assert error.message == "Connection failed"
        assert error.client_name == "solr"
        assert error.operation is None
        assert "client=solr" in str(error)

    def test_client_error_with_operation(self):
        """Test creating a client error with operation."""
        error = ClientError(
            "Query failed", client_name="elasticsearch", operation="query"
        )
        assert error.client_name == "elasticsearch"
        assert error.operation == "query"
        assert "client=elasticsearch" in str(error)
        assert "operation=query" in str(error)

    def test_client_error_inheritance(self):
        """Test that ClientError inherits from LTRError."""
        error = ClientError("Test", client_name="solr")
        assert isinstance(error, LTRError)
        assert isinstance(error, Exception)

    def test_client_error_with_additional_context(self):
        """Test client error with additional context."""
        context = {"timeout": "30s", "retries": "3"}
        error = ClientError(
            "Request failed",
            client_name="opensearch",
            operation="search",
            context=context,
        )
        assert error.context["client"] == "opensearch"
        assert error.context["operation"] == "search"
        assert error.context["timeout"] == "30s"
        assert error.context["retries"] == "3"


class TestLTRConnectionError:
    """Test the LTRConnectionError exception class."""

    def test_connection_error_creation(self):
        """Test creating a connection error."""
        error = LTRConnectionError("Cannot connect", client_name="solr")
        assert isinstance(error, ClientError)
        assert isinstance(error, LTRError)
        assert error.client_name == "solr"
        assert "Cannot connect" in str(error)

    def test_connection_error_context(self):
        """Test connection error includes client context."""
        error = LTRConnectionError(
            "Connection refused", client_name="elasticsearch", operation="connect"
        )
        assert "client=elasticsearch" in str(error)
        assert "operation=connect" in str(error)


class TestQueryError:
    """Test the QueryError exception class."""

    def test_query_error_creation(self):
        """Test creating a query error."""
        error = QueryError(
            "Query failed", index="test_index", query="test query", client_name="solr"
        )
        assert error.index == "test_index"
        assert error.query == "test query"
        assert error.client_name == "solr"
        assert error.operation == "query"

    def test_query_error_includes_index(self):
        """Test that query error includes index in context."""
        error = QueryError(
            "Invalid query", index="my_index", client_name="elasticsearch"
        )
        assert "index=my_index" in str(error)
        assert error.index == "my_index"

    def test_query_error_truncates_long_queries(self):
        """Test that long queries are truncated in context."""
        long_query = "a" * 200
        error = QueryError("Query failed", query=long_query, client_name="solr")
        # Query should be truncated to 100 chars + "..."
        assert len(error.context["query"]) == 103  # 100 + "..."
        assert error.context["query"].endswith("...")
        # Original query should be preserved
        assert error.query == long_query

    def test_query_error_short_query_not_truncated(self):
        """Test that short queries are not truncated."""
        short_query = "test query"
        error = QueryError("Query failed", query=short_query, client_name="solr")
        assert error.context["query"] == short_query
        assert error.query == short_query

    def test_query_error_inheritance(self):
        """Test that QueryError inherits from ClientError."""
        error = QueryError("Test", client_name="solr")
        assert isinstance(error, ClientError)
        assert isinstance(error, LTRError)


class TestLTRIndexError:
    """Test the LTRIndexError exception class."""

    def test_index_error_creation(self):
        """Test creating an index error."""
        error = LTRIndexError(
            "Index not found",
            index="test_index",
            operation="delete",
            client_name="solr",
        )
        assert error.index == "test_index"
        assert error.operation == "delete"
        assert error.client_name == "solr"

    def test_index_error_default_operation(self):
        """Test that index error defaults operation to 'index'."""
        error = LTRIndexError("Index error", index="test_index", client_name="solr")
        assert error.operation == "index"
        assert "operation=index" in str(error)

    def test_index_error_includes_index_in_context(self):
        """Test that index error includes index in context."""
        error = LTRIndexError(
            "Index exists", index="my_index", client_name="opensearch"
        )
        assert "index=my_index" in str(error)
        assert error.context["index"] == "my_index"

    def test_index_error_inheritance(self):
        """Test that LTRIndexError inherits from ClientError."""
        error = LTRIndexError("Test", client_name="solr")
        assert isinstance(error, ClientError)
        assert isinstance(error, LTRError)


class TestModelError:
    """Test the ModelError exception class."""

    def test_model_error_creation(self):
        """Test creating a model error."""
        error = ModelError(
            "Model training failed",
            model_name="test_model",
            operation="train",
        )
        assert error.model_name == "test_model"
        assert error.operation == "train"
        assert "model=test_model" in str(error)
        assert "operation=train" in str(error)

    def test_model_error_without_operation(self):
        """Test model error without operation."""
        error = ModelError("Model not found", model_name="my_model")
        assert error.model_name == "my_model"
        assert error.operation is None
        assert "model=my_model" in str(error)
        # Operation should not be in context if not provided
        assert "operation" not in error.context

    def test_model_error_inheritance(self):
        """Test that ModelError inherits from LTRError."""
        error = ModelError("Test", model_name="test")
        assert isinstance(error, LTRError)
        assert isinstance(error, Exception)

    def test_model_error_context(self):
        """Test model error includes model and operation in context."""
        error = ModelError(
            "Submission failed", model_name="rank_model", operation="submit"
        )
        assert error.context["model"] == "rank_model"
        assert error.context["operation"] == "submit"


class TestExceptionHierarchy:
    """Test the exception hierarchy and error handling patterns."""

    def test_catch_all_ltr_errors(self):
        """Test that catching LTRError catches all LTR exceptions."""
        exceptions = [
            LTRError("base"),
            ClientError("client", client_name="solr"),
            LTRConnectionError("connection", client_name="solr"),
            QueryError("query", client_name="solr"),
            LTRIndexError("index", client_name="solr"),
            ModelError("model", model_name="test"),
        ]

        for exc in exceptions:
            with pytest.raises(LTRError):
                raise exc

    def test_catch_client_errors(self):
        """Test that catching ClientError catches client-related exceptions."""
        client_exceptions = [
            ClientError("client", client_name="solr"),
            LTRConnectionError("connection", client_name="solr"),
            QueryError("query", client_name="solr"),
            LTRIndexError("index", client_name="solr"),
        ]

        for exc in client_exceptions:
            with pytest.raises(ClientError):
                raise exc

    def test_error_message_formatting(self):
        """Test that error messages are properly formatted with context."""
        error = QueryError(
            "Query execution failed",
            index="test_index",
            query="test",
            client_name="elasticsearch",
            context={"timeout": "5s"},
        )
        error_str = str(error)
        assert "Query execution failed" in error_str
        assert "index=test_index" in error_str
        assert "query=test" in error_str
        assert "client=elasticsearch" in error_str
        assert "operation=query" in error_str
        assert "timeout=5s" in error_str
