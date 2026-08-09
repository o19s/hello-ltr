"""Custom exception hierarchy for Learn-to-Rank operations.

This module defines a structured exception hierarchy for better error categorization
and handling across the LTR library. All exceptions inherit from LTRError,
which allows callers to catch all LTR-specific errors with a single exception type.

Exception Hierarchy:
    LTRError (base)
    ├── ClientError
    │   ├── LTRConnectionError
    │   ├── QueryError
    │   └── LTRIndexError
    ├── ValidationError (already exists in ltr.validation)
    └── ModelError
"""

from __future__ import annotations


class LTRError(Exception):
    """Base exception for all Learn-to-Rank operations.

    This is the root exception class for all LTR-specific errors. It provides
    a common base for error handling and allows callers to catch all LTR errors
    with a single exception type.

    Attributes:
        message: Human-readable error message.
        context: Optional dictionary with additional context about the error.
    """

    def __init__(self, message: str, context: dict[str, str] | None = None) -> None:
        """Initialize an LTR error.

        Args:
            message: Human-readable error message describing what went wrong.
            context: Optional dictionary with additional context (e.g., index name,
                query details, client type).
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        """Return formatted error message with context."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message


class ClientError(LTRError):
    """Exception raised for client-related errors.

    This exception is raised when errors occur during interactions with search
    engine clients (Elasticsearch, OpenSearch, Solr). It includes context about
    which client and operation failed.

    Attributes:
        client_name: Name of the client that raised the error.
        operation: Name of the operation that failed.
    """

    def __init__(
        self,
        message: str,
        client_name: str | None = None,
        operation: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        """Initialize a client error.

        Args:
            message: Human-readable error message.
            client_name: Name of the client (e.g., "elastic", "opensearch", "solr").
            operation: Name of the operation that failed (e.g., "query", "create_index").
            context: Optional additional context dictionary.
        """
        ctx = context or {}
        if client_name:
            ctx["client"] = client_name
        if operation:
            ctx["operation"] = operation
        super().__init__(message, ctx)
        self.client_name = client_name
        self.operation = operation


class LTRConnectionError(ClientError):
    """Exception raised for connection-related errors.

    This exception is raised when the client cannot connect to the search engine
    or when network errors occur during communication.

    Examples:
        - Search engine server is not running
        - Network timeout
        - Connection refused
        - DNS resolution failure
    """

    pass


class QueryError(ClientError):
    """Exception raised for query-related errors.

    This exception is raised when a query fails or returns an error response.
    It includes context about the query that failed.

    Examples:
        - Invalid query syntax
        - Index not found
        - Query timeout
        - Feature set not ready
    """

    def __init__(
        self,
        message: str,
        index: str | None = None,
        query: str | None = None,
        client_name: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        """Initialize a query error.

        Args:
            message: Human-readable error message.
            index: Name of the index that was queried.
            query: Query string or description (may be truncated for security).
            client_name: Name of the client.
            context: Optional additional context dictionary.
        """
        ctx = context or {}
        if index:
            ctx["index"] = index
        if query:
            # Truncate query for security (don't log full queries)
            query_preview = query[:100] + "..." if len(query) > 100 else query
            ctx["query"] = query_preview
        super().__init__(
            message, client_name=client_name, operation="query", context=ctx
        )
        self.index = index
        self.query = query


class LTRIndexError(ClientError):
    """Exception raised for index-related errors.

    This exception is raised when index operations fail (create, delete, etc.).
    It includes context about which index and operation failed.

    Examples:
        - Index creation fails
        - Index not found
        - Index already exists
        - Invalid index configuration

    Note: This is named LTRIndexError to avoid conflict with Python's builtin IndexError.
    """

    def __init__(
        self,
        message: str,
        index: str | None = None,
        operation: str | None = None,
        client_name: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        """Initialize an index error.

        Args:
            message: Human-readable error message.
            index: Name of the index involved in the error.
            operation: Name of the operation (e.g., "create", "delete").
            client_name: Name of the client.
            context: Optional additional context dictionary.
        """
        ctx = context or {}
        if index:
            ctx["index"] = index
        super().__init__(
            message,
            client_name=client_name,
            operation=operation or "index",
            context=ctx,
        )
        self.index = index


class ModelError(LTRError):
    """Exception raised for model-related errors.

    This exception is raised when model operations fail (training, submission, etc.).
    It includes context about which model and operation failed.

    Examples:
        - Model training fails
        - Model submission fails
        - Model not found
        - Invalid model format
    """

    def __init__(
        self,
        message: str,
        model_name: str | None = None,
        operation: str | None = None,
        context: dict[str, str] | None = None,
    ) -> None:
        """Initialize a model error.

        Args:
            message: Human-readable error message.
            model_name: Name of the model involved in the error.
            operation: Name of the operation (e.g., "train", "submit", "query").
            context: Optional additional context dictionary.
        """
        ctx = context or {}
        if model_name:
            ctx["model"] = model_name
        if operation:
            ctx["operation"] = operation
        super().__init__(message, ctx)
        self.model_name = model_name
        self.operation = operation
