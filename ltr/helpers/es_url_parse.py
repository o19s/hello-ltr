"""Elasticsearch URL parsing utilities.

This module provides functions for parsing Elasticsearch URLs into their
component parts (base URL, index, and search type).
"""


def parseUrl(fullEsUrl):
    """Parse an Elasticsearch URL into its components.

    Splits a full Elasticsearch URL into base URL, index name, and search type.

    Args:
        fullEsUrl: Complete Elasticsearch URL string (e.g.,
            "http://localhost:9200/index_name/_search").

    Returns:
        tuple: A tuple containing:
            - esUrl: Base Elasticsearch URL (scheme + netloc)
            - index: Index name (path component before last slash)
            - searchType: Search type/endpoint (last path component)

    Example:
        >>> parseUrl("http://localhost:9200/tmdb/_search")
        ('http://localhost:9200', 'tmdb', '_search')
    """
    import os.path
    from urllib.parse import urlsplit, urlunsplit

    o = urlsplit(fullEsUrl)

    esUrl = urlunsplit([o.scheme, o.netloc, "", "", ""])

    indexAndSearchType = os.path.split(o.path)

    return (esUrl, indexAndSearchType[0][1:], indexAndSearchType[1])


if __name__ == "__main__":
    from sys import argv

    print(parseUrl(argv[1]))
