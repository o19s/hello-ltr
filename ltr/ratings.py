import json
import requests

def get_classic_rating(year):
    if year > 2010:
        return 0
    elif year > 1990:
        return 1
    elif year > 1970:
        return 2
    elif year > 1950:
        return 3
    else:
        return 4

def get_latest_rating(year):
    if year > 2010:
        return 4
    elif year > 1990:
        return 3
    elif year > 1970:
        return 2
    elif year > 1950:
        return 1
    else:
        return 0

def run():
    print('Generating ratings for classic and latest model')
    elastic_ep = 'http://localhost:9200/tmdb/_search'
    NO_ZERO = False

    params = {
        "query": {
            "bool": {
                "filter": [
                    {
                        "sltr": {
                            "_name": "logged_features",
                            "featureset": "release",
                            "params": {}
                        }
                    }
                ]
            }
        },
        "ext": {
            "ltr_log": {
                "log_specs": {
                    "name": "ltr_features",
                    "named_query": "logged_features"
                }
            }
        },
        "size": 1000
    }

    resp = requests.post(elastic_ep, json=params).json()

    docs = []
    for hit in resp['hits']['hits']:
        feature = hit["fields"]["_ltrlog"][0]['ltr_features'][0]['value']

        docs.append([feature]) # Treat features as ordered lists

    # Classic film fan
    with open('data/classic-training.txt', 'w') as out:
        for fv in docs:
            rating = get_classic_rating(fv[0])

            if rating == 0 and NO_ZERO:
                continue

            out.write("{}\tqid:1\t1:{}\n".format(rating, fv[0]))

    # Newer film fan
    with open('data/latest-training.txt', 'w') as out:
        for fv in docs:
            rating = get_latest_rating(fv[0])

            if rating == 0 and NO_ZERO:
                continue

            out.write("{}\tqid:1\t1:{}\n".format(rating, fv[0]))

    print('Done')




