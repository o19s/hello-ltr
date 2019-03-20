import re

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

# TODO: Parse params and add efi dynamically instead of adding manually to query below
def solrLtrQuery(keywords, modelName):
    keywords = re.sub('([^\s\w]|_)+', '', keywords)
    fuzzy_keywords = ' '.join([x + '~' for x in keywords.split(' ')])

    return {
        'fl': '*,score',
        'rows': 5,
        'q': '{{!ltr reRankDocs=30000 model={} efi.keywords="{}" efi.fuzzy_keywords="{}"}}'.format(modelName, keywords, fuzzy_keywords)
    }

def run(client, keywords, modelName):
    if client.name() == 'elastic':
        results = client.query('tmdb', esLtrQuery(keywords, modelName))
    else:
        results = client.query('tmdb', solrLtrQuery(keywords, modelName))

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
