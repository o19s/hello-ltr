import plotly.graph_objs as go
from plotly.offline import download_plotlyjs, init_notebook_mode, plot, iplot

def search(client, user_query, model_name):
    if client.name() == 'elastic':
        engine_query = {
            "bool": {
                "must": {"match_all": {} },
                "filter": {
                    "match": {"title": user_query}
<<<<<<< HEAD
                }
=======
                    }
>>>>>>> 0ec9568 (hello-ltr (ES).ipynb now shows top-12 search results for both classic and latest models.)
            }
        }
    else:
        engine_query = 'title:('+ user_query + ')^0'    
    return client.model_query('tmdb', model_name, {}, engine_query)

def plot(client, query):
    init_notebook_mode(connected=True)

    models = ['classic', 'latest']
    modelData = []

    for model in models:
        modelData.append(search(client, query, model))

    xAxes = []
    for i in range(len(modelData[0])):
        xAxes.append(i)

    trace0 = go.Scatter(
        x = xAxes,
        y = [x['release_year'] for x in modelData[0]],
        mode = "lines",
        name = "classic",
        text = [f'{x["title"]} ({x["score"]})' for x in modelData[0]]
    )

    trace1 = go.Scatter(
        x = xAxes,
        y = [x['release_year'] for x in modelData[1]],
        mode = "lines",
        name = "latest",
        text = [f'{x["title"]} ({x["score"]})' for x in modelData[1]]
    )


    data = [trace0, trace1]
    fig = go.Figure(data=data)
    iplot(fig)
