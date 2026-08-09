"""Release date-based search result visualization.

This module provides functions for searching with LTR models and visualizing
results, particularly useful for comparing models with different preferences
(e.g., classic vs. latest movies).
"""

from __future__ import annotations

import plotly.graph_objs as go
from plotly.offline import init_notebook_mode, iplot

from ltr.client.base_client import BaseClient
from ltr.types import JSONDictList, QueryParams


def search(client: BaseClient, user_query: str, model_name: str) -> JSONDictList:
    """Execute a search query using an LTR model.

    Args:
        client: Search client instance.
        user_query: User search query string.
        model_name: Name of the LTR model to use for ranking.

    Returns:
        list[dict]: List of search results ranked by the LTR model.
    """
    if client.name() in ["elastic", "opensearch"]:
        engine_query: QueryParams = {
            "bool": {
                "must": {"match_all": {}},
                "filter": {"match": {"title": user_query}},
            }
        }
        return client.model_query("tmdb", model_name, {}, engine_query)
    else:
        # Solr accepts QueryParams dict with "q" key for query string
        engine_query: QueryParams = {"q": f"title:({user_query})^0"}
        return client.model_query("tmdb", model_name, {}, engine_query)


def plot(client: BaseClient, query: str, models: list[str] | None = None) -> None:
    """Plot search results from multiple LTR models for comparison.

    Executes the same query with different models and visualizes the results
    in a Plotly chart, showing how different models rank the same documents.

    Args:
        client: Search client instance.
        query: User search query string.
        models: List of model names to compare (default: ["classic", "latest"]).

    Returns:
        None: Chart is displayed in the notebook output.

    Note:
        Requires plotly and is designed for use in Jupyter notebooks.
    """
    if models is None:
        models = ["classic", "latest"]
    init_notebook_mode(connected=True)

    model_data = []

    for model in models:
        model_data.append(search(client, query, model))

    x_axes = []
    for i in range(len(model_data[0])):
        x_axes.append(i)

    trace0 = go.Scatter(
        x=x_axes,
        y=[int(x["release_year"]) for x in model_data[0]],
        mode="lines",
        name=models[0],
        text=[f"{x['title']} ({x['score']})" for x in model_data[0]],
    )

    trace1 = go.Scatter(
        x=x_axes,
        y=[int(x["release_year"]) for x in model_data[1]],
        mode="lines",
        name=models[1],
        text=[f"{x['title']} ({x['score']})" for x in model_data[1]],
    )

    data = [trace0, trace1]
    fig = go.Figure(data=data)
    iplot(fig)
