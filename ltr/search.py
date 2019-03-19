from ltr import client_mode, main_client

baseEsQuery = {
    "size": 5,
    "query": {
        "sltr": {
            "params": {
                "keywords": "",
            },
            "model": ""
        }
      }
}

def esLtrQuery(keywords, modelName):
    import json
    baseEsQuery['query']['sltr']['params']['keywords'] = keywords
    baseEsQuery['query']['sltr']['model'] = modelName
    print("%s" % json.dumps(baseEsQuery))
    return baseEsQuery

def solrLtrQuery(keywords, modelName):
    return {
        'fl': '*,score',
        'rows': 5,
        'q': '{{!ltr reRankDocs=30000 model={} efi.keywords="{}"}}'.format(modelName, keywords)
    }

def run(keywords, modelName):
    if client_mode == 'elastic':
        results = main_client.query('tmdb', esLtrQuery(keywords, modelName))
    else:
        results = main_client.query('tmdb', solrLtrQuery(keywords, modelName))

    for result in results:
             print("%s " % (result['title'] if 'title' in result else 'N/A'))
             print("%s " % (result['_score']))
             print("%s " % (result['release_year']))
             print("%s " % (result['genres'] if 'genres' in result else 'N/A'))
             print("%s " % (result['overview']))
             print("---------------------------------------")



if __name__ == "__main__":
    from sys import argv
    model = "doug"
    if len(argv) > 2:
        model = argv[2]
    keywords = argv[1]

    run(keywords, model)
