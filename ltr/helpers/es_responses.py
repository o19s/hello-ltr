"""Helper functions for handling Elasticsearch API responses in notebooks.

This module provides utility functions for safely working with Elasticsearch
API responses, particularly useful in educational notebooks where we want
to keep error handling minimal and unobtrusive.
"""

from __future__ import annotations

import json

from ltr.exceptions import QueryError
from ltr.types import JSONDict


def safe_search_response(resp: JSONDict) -> JSONDict:
    """Safely extract hits from an Elasticsearch search response.

    Validates the response structure and returns the response if valid.
    Raises ValueError with a clear message if the response is invalid.

    Args:
        resp: Elasticsearch search API response dictionary.

    Returns:
        The validated response dictionary.

    Raises:
        ValueError: If the response contains an error or is missing the 'hits' key.

    Example:
        >>> resp = requests.get(url, json=query).json()
        >>> resp = safe_search_response(resp)
        >>> for hit in resp["hits"]["hits"]:
        ...     print(hit["_source"]["title"])
    """
    if "error" in resp:
        error_detail = resp.get("error", {})
        if isinstance(error_detail, dict):
            error_msg = error_detail.get("reason", str(error_detail))
        else:
            error_msg = str(error_detail)
        raise QueryError(
            f"Elasticsearch search failed: {error_msg}",
            client_name="elastic",
        )

    if "hits" not in resp:
        raise QueryError(
            f"Unexpected response structure: missing 'hits' key. "
            f"Response: {json.dumps(resp, indent=2)[:500]}",
            client_name="elastic",
        )

    return resp


def get_first_hit(resp: JSONDict) -> JSONDict:
    """Get the first hit from an Elasticsearch search response.

    Validates the response and returns the first document hit.

    Args:
        resp: Elasticsearch search API response dictionary (must be validated).

    Returns:
        The first hit document dictionary.

    Raises:
        ValueError: If there are no hits in the response.

    Example:
        >>> resp = requests.get(url, json=query).json()
        >>> resp = safe_search_response(resp)
        >>> first_hit = get_first_hit(resp)
        >>> print(json.dumps(first_hit, indent=2))
    """
    hits = resp.get("hits", {}).get("hits", [])
    if not hits:
        raise QueryError(
            "No hits returned in response",
            client_name="elastic",
        )
    return hits[0]


def get_hits(resp: JSONDict) -> list[JSONDict]:
    """Get all hits from an Elasticsearch search response.

    Validates the response and returns the list of document hits.

    Args:
        resp: Elasticsearch search API response dictionary (must be validated).

    Returns:
        List of hit document dictionaries.

    Example:
        >>> resp = requests.get(url, json=query).json()
        >>> resp = safe_search_response(resp)
        >>> for hit in get_hits(resp):
        ...     print(hit["_source"]["title"])
    """
    return resp.get("hits", {}).get("hits", [])
