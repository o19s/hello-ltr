"""Shared response wrapper classes for Elasticsearch/OpenSearch clients.

This module provides generic response wrapper classes that convert search engine
API responses into a format compatible with the resp_msg error handling function.
These classes are used by both Elasticsearch and OpenSearch clients.
"""

from __future__ import annotations

import json
from typing import Any

from ltr.types import JSONDict


class APIResp:
    """Response wrapper for search engine API responses.

    Converts JSON responses into a format compatible with the resp_msg error
    handling function.

    Attributes:
        status_code: HTTP status code (200 for success, 400 for errors).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize an APIResp wrapper.

        Args:
            resp: API response dictionary.
        """
        self.status_code: int = 400
        if "acknowledged" in resp and resp["acknowledged"]:
            self.status_code = 200
        else:
            self.status_code = resp.get("status", 400)
            self.text: str = json.dumps(resp, indent=2)


class BulkResp:
    """Response wrapper for bulk operation responses.

    Attributes:
        status_code: HTTP status code (201 if documents indexed, 400 otherwise).
    """

    def __init__(self, resp: tuple[int, Any]) -> None:
        """Initialize a BulkResp wrapper.

        Args:
            resp: Bulk operation response tuple (count, items).
        """
        self.status_code: int = 400
        if resp[0] > 0:
            self.status_code = 201


class SearchResp:
    """Response wrapper for search responses.

    Attributes:
        status_code: HTTP status code (200 if hits found, 400 otherwise).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize a SearchResp wrapper.

        Args:
            resp: Search API response dictionary.
        """
        self.status_code: int = 400
        if "hits" in resp:
            self.status_code = 200
        else:
            self.status_code = resp.get("status", 400)
            self.text: str = json.dumps(resp, indent=2)
