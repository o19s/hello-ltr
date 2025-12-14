"""Search functionality for Learn-to-Rank queries.

This module provides functions to construct and execute LTR queries
for Elasticsearch/OpenSearch and Solr search engines.
"""

import re

baseEsQuery = {
    "size": 5,
    "query": {
        "sltr": {
            "params": {
                "keywords": "",
            },
            "model": "",
        }
    },
}


def esLtrQuery(keywords, modelName):
    """Construct an Elasticsearch/OpenSearch LTR query.

    Args:
        keywords: Search keywords string to query for.
        modelName: Name of the LTR model to use for ranking.

    Returns:
        dict: Elasticsearch/OpenSearch query dictionary with LTR parameters.

    Note:
        Modifies the global baseEsQuery dictionary. The keywordsList parameter
        is added for compatibility with TSQ (Term Statistics Query).
    """
    import json

    baseEsQuery["query"]["sltr"]["params"]["keywords"] = keywords
    baseEsQuery["query"]["sltr"]["params"]["keywordsList"] = [
        keywords
    ]  # Needed by TSQ for now
    baseEsQuery["query"]["sltr"]["model"] = modelName
    print(f"{json.dumps(baseEsQuery)}")
    return baseEsQuery


def solrLtrQuery(keywords, modelName):
    """Construct a Solr LTR query.

    Args:
        keywords: Search keywords string to query for.
        modelName: Name of the LTR model to use for ranking.

    Returns:
        dict: Solr query dictionary with LTR parameters including:
            - fl: Field list to return
            - rows: Number of results to return
            - q: LTR query with model and external feature information (EFI)

    Note:
        The keywords are sanitized (special characters removed) and fuzzy
        matching is applied by appending '~' to each keyword.
        TODO: Parse params and add efi dynamically instead of adding manually to query.
    """
    keywords = re.sub(r"([^\s\w]|_)+", "", keywords)
    fuzzy_keywords = " ".join([x + "~" for x in keywords.split(" ")])

    return {
        "fl": "*,score",
        "rows": 5,
        "q": f'{{!ltr reRankDocs=30000 model={modelName} efi.keywords="{keywords}" efi.fuzzy_keywords="{fuzzy_keywords}"}}',
    }


tmdbFields = {
    "title": "title",
    "display_fields": ["release_year", "genres", "overview"],
}


def search(client, keywords, modelName, index="tmdb", fields=tmdbFields):
    """Execute a Learn-to-Rank search query and display results.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        keywords: Search keywords string to query for.
        modelName: Name of the LTR model to use for ranking.
        index: Name of the search index to query (default: "tmdb").
        fields: Dictionary specifying field mappings:
            - title: Field name for document title
            - display_fields: List of additional fields to display

    Returns:
        None: Results are printed to stdout.

    Example:
        >>> from ltr.client.elastic_client import ElasticClient
        >>> client = ElasticClient()
        >>> search(client, "action movie", "my_model", index="tmdb")
    """
    if client.name() == "elastic" or client.name() == "opensearch":
        results = client.query(index, esLtrQuery(keywords, modelName))
    else:
        q = solrLtrQuery(keywords, modelName)
        print(q)
        results = client.query(index, q)

    ti = fields["title"]

    for result in results:
        print("{} ".format(result.get(ti, "N/A")))
        print(f"{result['_score']} ")

        for df in fields["display_fields"]:
            print("{} ".format(result.get(df, "N/A")))

        print("---------------------------------------")
