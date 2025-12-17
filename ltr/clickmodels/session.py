"""Search session data structures for click models.

This module provides classes for representing search sessions and documents
in click model analysis, including click and conversion tracking.
"""

from __future__ import annotations

from typing import Any

from ltr.types import SessionTuple, SessionTupleList


class Doc:
    """Represents a document in a search result with click and conversion information.

    Attributes:
        click: Boolean indicating whether this document was clicked.
        doc_id: Document identifier.
        conversion: Boolean indicating whether a conversion occurred (default: False).
    """

    def __init__(self, click: bool, doc_id: Any, conversion: bool = False) -> None:
        """Initialize a Doc.

        Args:
            click: Boolean indicating whether this document was clicked.
            doc_id: Document identifier.
            conversion: Boolean indicating whether a conversion occurred
                (default: False).
        """
        self.click: bool = click
        self.doc_id: Any = doc_id
        self.conversion: bool = conversion

    def __repr__(self) -> str:
        """Generate developer-friendly string representation.

        Returns:
            str: String representation suitable for debugging.
        """
        return (
            f"Doc(doc_id={self.doc_id}, click={self.click}, "
            f"conversion={self.conversion})"
        )

    def __str__(self) -> str:
        """Generate user-friendly string representation.

        Returns:
            str: Tuple-like string representation of document data.
        """
        return f"({self.doc_id}, {self.click}, {self.conversion})"


class Session:
    """Represents a search session with query and ranked documents.

    A session contains a query and an ordered list of documents that were
    presented to the user, along with click and conversion information.

    Attributes:
        query: Query string or query ID.
        docs: List of Doc objects in rank order.

    Raises:
        ValueError: If the same document appears multiple times in the results.
    """

    def __init__(self, query: Any, docs: list[Doc]) -> None:
        """Initialize a Session.

        Args:
            query: Query string or query ID.
            docs: List of Doc objects in rank order.

        Raises:
            ValueError: If the same document appears multiple times in the results.
        """
        self.query: Any = query
        self.docs: list[Doc] = docs
        # Check if docs are unique
        docset = set()
        for doc in docs:
            if doc.doc_id in docset:
                raise ValueError(
                    "A session may only list a doc exactly once in search results"
                )
            docset.add(doc.doc_id)

    def __repr__(self) -> str:
        """Generate developer-friendly string representation.

        Returns:
            str: String representation suitable for debugging.
        """
        return f"Session(query={self.query}, docs={self.docs})"

    def __str__(self) -> str:
        """Generate user-friendly string representation.

        Returns:
            str: Tuple-like string representation of session data.
        """
        return f"({self.query}, ({self.docs}))"


def build_one(sess_tuple: SessionTuple) -> Session:
    """Build a Session from a tuple representation.

    Converts a tuple format into a Session object. The tuple format is:
    - 0th item: query (a string that uniquely identifies it)
    - 1st item: list of doc tuples, each containing:
        - doc_id: Document identifier
        - click: Boolean indicating if document was clicked
        - conversion: Optional conversion value (default: False)

    Args:
        sess_tuple: Tuple of (query, list of doc tuples).
            Example: ('A', ((1, True), (2, False), (3, True), (0, False)))
            With conversions: ('A', ((1, True, 0.9), (2, False, 0.8),
                (3, True, 1.0), (0, False)))

    Returns:
        Session: Session object constructed from the tuple data.
    """
    query = sess_tuple[0]
    docs = []
    for doc_tuple in sess_tuple[1]:
        conversion = False
        if len(doc_tuple) > 2:
            conversion = doc_tuple[2]
        docs.append(Doc(doc_id=doc_tuple[0], click=doc_tuple[1], conversion=conversion))
    return Session(query=query, docs=docs)


def build(sess_tuples: SessionTupleList) -> list[Session]:
    """Build multiple Session objects from a list of tuple representations.

    Args:
        sess_tuples: List of session tuples, each in the format expected by build_one().

    Returns:
        list: List of Session objects.
    """
    sesss = []
    for sess_tup in sess_tuples:
        sesss.append(build_one(sess_tup))
    return sesss
