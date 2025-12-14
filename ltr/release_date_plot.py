"""Release date-based search result visualization.

This module provides functions for searching with LTR models and visualizing
results, particularly useful for comparing models with different preferences
(e.g., classic vs. latest movies).
"""

import plotly.graph_objs as go
from plotly.offline import init_notebook_mode, iplot


def search(client, user_query, model_name):
    """Execute a search query using an LTR model.

    Args:
        client: Search client instance.
        user_query: User search query string.
        model_name: Name of the LTR model to use for ranking.

    Returns:
        list[dict]: List of search results ranked by the LTR model.
    """
    if client.name() in ["elastic", "opensearch"]:
        engine_query = {
            "bool": {
                "must": {"match_all": {}},
                "filter": {"match": {"title": user_query}},
            }
        }
    else:
        engine_query = "title:(" + user_query + ")^0"
    return client.model_query("tmdb", model_name, {}, engine_query)


def plot(client, query, models=None):
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

    modelData = []

    for model in models:
        modelData.append(search(client, query, model))

    xAxes = []
    for i in range(len(modelData[0])):
        xAxes.append(i)

    trace0 = go.Scatter(
        x=xAxes,
        y=[int(x["release_year"]) for x in modelData[0]],
        mode="lines",
        name=models[0],
        text=[f"{x['title']} ({x['score']})" for x in modelData[0]],
    )

    trace1 = go.Scatter(
        x=xAxes,
        y=[int(x["release_year"]) for x in modelData[1]],
        mode="lines",
        name=models[1],
        text=[f"{x['title']} ({x['score']})" for x in modelData[1]],
    )

    data = [trace0, trace1]
    fig = go.Figure(data=data)
    iplot(fig)
