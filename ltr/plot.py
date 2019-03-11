import plotly.graph_objs as go
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot
import requests

def run():
    init_notebook_mode(connected=True)

    es_ep = 'http://localhost:9200/tmdb/_search'

    models = ['classic', 'latest']
    modelData = []

    for model in models:
        params = {
            "query": {
                "bool": {
                    "must": {"match_all": {} },
                    "filter": {
                        "match": {"title": "batman"}
                    }
                }
            },
            "rescore": {
                "window_size": 1000,
                "query": {
                    "rescore_query": {
                        "sltr": {
                            "params": {},
                            "model": model
                        }
                    }
                }
            },
            "size": 1000
        }


        resp = requests.post(es_ep, json=params).json()
        modelData.append(resp['hits']['hits'])

    xAxes = []
    for i in range(len(modelData[0])):
        xAxes.append(i)

    trace0 = go.Scatter(
        x = xAxes,
        y = [x['_source']['release_year'] for x in modelData[0]],
        mode = "lines",
        name = "classic"
    )

    trace1 = go.Scatter(
        x = xAxes,
        y = [x['_source']['release_year'] for x in modelData[1]],
        mode = "lines",
        name = "latest"
    )


    data = [trace0, trace1]
    fig = go.Figure(data=data)
    iplot(fig)
