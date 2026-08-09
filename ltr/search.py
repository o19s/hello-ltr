"""Search functionality for Learn-to-Rank queries.

This module provides functions to construct and execute LTR queries
for Elasticsearch/OpenSearch and Solr search engines.
"""

import json
import re

from ltr.client.base_client import BaseClient
from ltr.compat import accepts_legacy_kwargs
from ltr.exceptions import QueryError
from ltr.logger import get_logger
from ltr.types import JSONDict
from ltr.validation import (
    sanitize_for_solr_query,
    validate_index_name,
    validate_keywords,
    validate_model_name,
)

logger = get_logger(__name__)


def es_ltr_query(keywords: str, model_name: str) -> JSONDict:
    """Construct an Elasticsearch/OpenSearch LTR query.

    Args:
        keywords: Search keywords string to query for.
        model_name: Name of the LTR model to use for ranking.

    Returns:
        dict: Elasticsearch/OpenSearch query dictionary with LTR parameters.

    Raises:
        ValidationError: If keywords or model_name are invalid.

    Note:
        The keywordsList parameter is added for compatibility with TSQ
        (Term Statistics Query).
    """
    keywords = validate_keywords(keywords)
    model_name = validate_model_name(model_name)

    query: JSONDict = {
        "size": 5,
        "query": {
            "sltr": {
                "params": {
                    "keywords": keywords,
                    "keywordsList": [keywords],  # Needed by TSQ for now
                },
                "model": model_name,
            }
        },
    }
    logger.debug(f"ES LTR query: {json.dumps(query)}")
    return query


def solr_ltr_query(keywords: str, model_name: str) -> JSONDict:
    """Construct a Solr LTR query.

    Args:
        keywords: Search keywords string to query for.
        model_name: Name of the LTR model to use for ranking.

    Returns:
        dict: Solr query dictionary with LTR parameters including:
            - fl: Field list to return
            - rows: Number of results to return
            - q: LTR query with model and external feature information (EFI)

    Raises:
        ValidationError: If keywords or model_name are invalid.

    Note:
        The keywords are sanitized (special characters removed) and fuzzy
        matching is applied by appending '~' to each keyword.
        Model name is validated and sanitized to prevent query injection.
        TODO: Parse params and add efi dynamically instead of adding manually to query.
    """
    keywords = validate_keywords(keywords)
    model_name = validate_model_name(model_name)

    # Sanitize model_name for use in query string (prevents injection)
    sanitized_model_name = sanitize_for_solr_query(model_name)

    # Sanitize keywords for fuzzy matching (remove special chars)
    keywords = re.sub(r"([^\s\w]|_)+", "", keywords)
    fuzzy_keywords = " ".join([x + "~" for x in keywords.split(" ")])

    return {
        "fl": "*,score",
        "rows": 5,
        "q": (
            f"{{!ltr reRankDocs=30000 model={sanitized_model_name} "
            f'efi.keywords="{keywords}" efi.fuzzy_keywords="{fuzzy_keywords}"}}'
        ),
    }


tmdb_fields: JSONDict = {
    "title": "title",
    "display_fields": ["release_year", "genres", "overview"],
}


@accepts_legacy_kwargs(modelName="model_name")
def search(
    client: BaseClient,
    keywords: str,
    model_name: str,
    index: str = "tmdb",
    fields: JSONDict = tmdb_fields,
) -> None:
    """Execute a Learn-to-Rank search query and display results.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        keywords: Search keywords string to query for.
        model_name: Name of the LTR model to use for ranking.
        index: Name of the search index to query (default: "tmdb").
        fields: Dictionary specifying field mappings:
            - title: Field name for document title
            - display_fields: List of additional fields to display

    Returns:
        None: Results are printed to stdout.

    Raises:
        ValidationError: If keywords, model_name, or index are invalid.
        QueryError: If the query fails due to network errors, index not found,
            or other client-related issues.

    Example:
        >>> from ltr.client.elastic_client import ElasticClient
        >>> client = ElasticClient()
        >>> search(client, "action movie", "my_model", index="tmdb")
    """
    # Validate all inputs
    keywords = validate_keywords(keywords)
    model_name = validate_model_name(model_name)
    index = validate_index_name(index)

    client_name = client.name()
    try:
        if client_name == "elastic" or client_name == "opensearch":
            query = es_ltr_query(keywords, model_name)
            results = client.query(index, query)
        else:
            q = solr_ltr_query(keywords, model_name)
            logger.debug(f"Solr LTR query: {q}")
            results = client.query(index, q)
    except Exception as e:
        # Wrap client exceptions with context
        query_str = f"keywords={keywords!r}, model={model_name!r}"
        raise QueryError(
            f"Search query failed: {e}",
            index=index,
            query=query_str,
            client_name=client_name,
        ) from e

    ti = fields["title"]

    # Print results to stdout for user-facing output
    # (keeping print for user-facing display, but logging the query)
    for result in results:
        print("{} ".format(result.get(ti, "N/A")))
        print(f"{result['_score']} ")

        for df in fields["display_fields"]:
            print("{} ".format(result.get(df, "N/A")))

        print("---------------------------------------")
