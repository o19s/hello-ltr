"""Index management and rebuilding functionality.

This module provides functions for rebuilding search engine indices
with configuration reloading and document reindexing.
"""


def rebuild(client, index, doc_src, force=False):
    """Rebuild a search index with configuration reloading and reindexing.

    Reloads the configuration from disk (configset for Solr, JSON file for Elasticsearch)
    and reindexes all documents. If the index already exists, it will only be
    rebuilt if force=True.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        index: Name of the index to rebuild.
        doc_src: Source of documents to index. Can be a file path, iterable of documents,
            or a callable that returns documents.
        force: If True and index exists, delete and recreate it. If False and index exists,
            print a message and return None (default: False).

    Returns:
        None: Returns None if index exists and force=False, otherwise returns None
        after successful rebuild.

    Example:
        >>> from ltr.client.elastic_client import ElasticClient
        >>> client = ElasticClient()
        >>> rebuild(client, "tmdb", "data/tmdb.json", force=True)
    """

    if client.check_index_exists(index):
        if force:
            client.delete_index(index)
            client.create_index(index)
            client.index_documents(index, doc_src=doc_src)
        else:
            print(
                f"Index {index} already exists. Use `force = True` to delete and recreate"
            )
            return None
    else:
        client.create_index(index)
        client.index_documents(index, doc_src=doc_src)
