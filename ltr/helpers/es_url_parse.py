"""Elasticsearch URL parsing utilities.

This module provides functions for parsing Elasticsearch URLs into their
component parts (base URL, index, and search type).
"""

from __future__ import annotations


def parse_url(full_es_url: str) -> tuple[str, str, str]:
    """Parse an Elasticsearch URL into its components.

    Splits a full Elasticsearch URL into base URL, index name, and search type.

    Args:
        full_es_url: Complete Elasticsearch URL string (e.g.,
            "http://localhost:9200/index_name/_search").

    Returns:
        tuple: A tuple containing:
            - es_url: Base Elasticsearch URL (scheme + netloc)
            - index: Index name (path component before last slash)
            - search_type: Search type/endpoint (last path component)

    Example:
        >>> parse_url("http://localhost:9200/tmdb/_search")
        ('http://localhost:9200', 'tmdb', '_search')
    """
    import os.path
    from urllib.parse import urlsplit, urlunsplit

    o = urlsplit(full_es_url)

    es_url = urlunsplit([o.scheme, o.netloc, "", "", ""])

    index_and_search_type = os.path.split(o.path)

    return (es_url, index_and_search_type[0][1:], index_and_search_type[1])


if __name__ == "__main__":
    from sys import argv

    print(parse_url(argv[1]))
