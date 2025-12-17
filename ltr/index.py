"""Index management and rebuilding functionality.

This module provides functions for rebuilding search engine indices
with configuration reloading and document reindexing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ltr.client.base_client import BaseClient
from ltr.logger import get_logger
from ltr.types import JSONDict

logger = get_logger(__name__)


def rebuild(
    client: BaseClient,
    index: str,
    doc_src: Iterable[JSONDict] | Callable[[], Iterable[JSONDict]],
    force: bool = False,
) -> None:
    """Rebuild a search index with configuration reloading and reindexing.

    Reloads the configuration from disk (configset for Solr, JSON file for
    Elasticsearch) and reindexes all documents. If the index already exists,
    it will only be rebuilt if force=True.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or
            SolrClient).
        index: Name of the index to rebuild.
        doc_src: Source of documents to index. Can be an iterable of document
            dictionaries or a callable that returns an iterable. Note: File
            paths (str) are not supported.
        force: If True and index exists, delete and recreate it. If False and
            index exists, print a message and return None (default: False).

    Returns:
        None: Returns None if index exists and force=False, otherwise returns None
        after successful rebuild.

    Example:
        >>> from ltr.client.elastic_client import ElasticClient
        >>> from ltr.helpers.movies import Movies
        >>> client = ElasticClient()
        >>> movies = Movies()
        >>> rebuild(client, "tmdb", movies, force=True)
    """

    if client.check_index_exists(index):  # type: ignore[attr-defined]
        if force:
            client.delete_index(index)
            client.create_index(index)
            client.index_documents(index, doc_src=doc_src)
        else:
            logger.warning(
                f"Index {index} already exists. Use `force = True` to delete "
                f"and recreate"
            )
            return None
    else:
        client.create_index(index)
        client.index_documents(index, doc_src=doc_src)
