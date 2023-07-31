import plotly.graph_objs as go
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot

def search(client, user_query, model_name):
    if client.name() in ['elastic', 'opensearch']:
        engine_query = {
            "bool": {
                "must": {"match_all": {} },
                "filter": {
                    "match": {"title": user_query}
                }
            }
        }
    else:
        engine_query = 'title:('+ user_query + ')^0'    
    return client.model_query('tmdb', model_name, {}, engine_query)

def plot(client, query, models = ['classic', 'latest']):
    init_notebook_mode(connected=True)

    modelData = []

    for model in models:
        modelData.append(search(client, query, model))

    xAxes = []
    for i in range(len(modelData[0])):
        xAxes.append(i)

    trace0 = go.Scatter(
        x = xAxes,
        y = [int(x['release_year']) for x in modelData[0]],
        mode = "lines",
        name = models[0],
        text = [f'{x["title"]} ({x["score"]})' for x in modelData[0]]
    )

    trace1 = go.Scatter(
        x = xAxes,
        y = [int(x['release_year']) for x in modelData[1]],
        mode = "lines",
        name = models[1],
        text = [f'{x["title"]} ({x["score"]})' for x in modelData[1]]
    )


    data = [trace0, trace1]
    fig = go.Figure(data=data)
    iplot(fig)
