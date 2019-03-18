import requests

from .base_client import BaseClient
from ltr.helpers.movies import indexableMovies

import elasticsearch.helpers
from elasticsearch import Elasticsearch

class ElasticClient(BaseClient):
    def __init__(self):
        self.elastic_ep = 'http://localhost:9200/_ltr'
        self.es = Elasticsearch('http://localhost:9200')

    def delete_index(self, index):
        print('Deleting index: {}'.format(index))
        self.es.indices.delete(index, ignore=[400, 404])

    def create_index(self, index, settings):
        print('Creating index: {}'.format(index))
        self.es.indices.create(index, body=settings)

    def index_documents(self, index, movie_dict={}):
        print('Indexing {} documents'.format(len(movie_dict.keys())))

        def bulkDocs(movie_dict):
            for movie in indexableMovies(movie_dict):
                addCmd = {"_index": index,
                          "_type": "movie",
                          "_id": movie['id'],
                          "_source": movie}
                yield addCmd
                if 'title' in movie:
                    print("%s added to %s" % (movie['title'], index))

        elasticsearch.helpers.bulk(self.es, bulkDocs(movie_dict), chunk_size=100)

    def reset_ltr(self):
        resp = requests.delete(self.elastic_ep)
        print('Removed LTR feature store: {}'.format(resp.status_code))
        resp = requests.put(self.elastic_ep)
        print('Initialize LTR: {}'.format(resp.status_code))

    def create_featureset(self, name, config):
        resp = requests.post('{}/_featureset/{}'.format(self.elastic_ep, name), json=config)
        print('Created {} feature set: {}'.format(name, resp.status_code))
        if resp.status_code > 300:
            print(resp.text)

    # TODO: Add query as must boolean clause
    def log_query(self, index, featureset, query):
        params = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "sltr": {
                                "_name": "logged_features",
                                "featureset": featureset,
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

        return self.es.search(index, body=params)


    def submit_model(self, featureset, model_name, model_payload):
        model_ep = "http://localhost:9200/_ltr/_model/"
        create_ep = "http://localhost:9200/_ltr/_featureset/{}/_createmodel".format(featureset)

        resp = requests.delete('{}{}'.format(model_ep, model_name))
        print('Delete model {}: {}'.format(model_name, resp.status_code))

        params = {
            'model': {
                'name': model_name,
                'model': {
                    'type': 'model/ranklib',
                    'definition': model_payload
                }
            }
        }

        resp = requests.post(create_ep, json=params)
        print(resp.text)
        print('Created model {}: {}'.format(modelName, resp.status_code))


    def model_query(self, index, model, model_params, query):
        params = {
            "query": query,
            "rescore": {
                "window_size": 1000,
                "query": {
                    "rescore_query": {
                        "sltr": {
                            "params": model_params,
                            "model": model
                        }
                    }
                }
            },
            "size": 1000
        }

        return self.es.search(index, body=params)



