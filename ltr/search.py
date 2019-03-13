baseQuery = {
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

def ltrQuery(keywords, modelName):
    import json
    baseQuery['query']['sltr']['params']['keywords'] = keywords
    baseQuery['query']['sltr']['model'] = model
    print("%s" % json.dumps(baseQuery))
    return baseQuery


if __name__ == "__main__":
    import configparser
    from sys import argv
    from elasticsearch import Elasticsearch

    config = configparser.ConfigParser()
    esUrl='http://localhost:9200'

    es = Elasticsearch(esUrl, timeout=1000)
    model = "doug"
    if len(argv) > 2:
        model = argv[2]
    keywords = argv[1]
    results = es.search(index='tmdb', doc_type='movie', body=ltrQuery(keywords, model))
    for result in results['hits']['hits']:
             print("%s " % (result['_source']['title']))
             print("%s " % (result['_score']))
             print("%s " % (result['_source']['release_year']))
             print("%s " % (result['_source']['genres']))
             print("%s " % (result['_source']['overview']))
             print("---------------------------------------")

