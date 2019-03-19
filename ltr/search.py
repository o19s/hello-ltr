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

baseSolrQuery = {

}

def esLtrQuery(keywords, modelName):
    import json
    baseEsQuery['query']['sltr']['params']['keywords'] = keywords
    baseEsQuery['query']['sltr']['model'] = modelName
    print("%s" % json.dumps(baseEsQuery))
    return baseEsQuery


def run(keywords, modelName):
    results = main_client.query('tmdb', esLtrQuery(keywords, modelName))

    for result in results:
             print("%s " % (result['title']))
             print("%s " % (result['_score']))
             print("%s " % (result['release_year']))
             print("%s " % (result['genres']))
             print("%s " % (result['overview']))
             print("---------------------------------------")



if __name__ == "__main__":
    from sys import argv
    model = "doug"
    if len(argv) > 2:
        model = argv[2]
    keywords = argv[1]

    run(keywords, model)
