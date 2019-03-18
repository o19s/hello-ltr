import requests

from .base_client import BaseClient
from ltr.helpers.movies import indexableMovies

class SolrClient(BaseClient):
    def __init__(self):
        self.solr_base_ep = 'http://localhost:8983/solr'

    def delete_index(self, index):
        params = {
            'action': 'UNLOAD',
            'core': index,
            'deleteIndex': 'true',
            'deleteDataDir': 'true',
            'deleteInstanceDir': 'true'
        }

        resp = requests.get('{}/admin/cores?'.format(self.solr_base_ep), params=params)
        print('Deleted index: {} [Status: {}]'.format(index, resp.status_code))

    def create_index(self, index, settings):
        params = {
            'action': 'CREATE',
            'name': index,
            'configSet': 'tmdb'
        }
        resp = requests.get('{}/admin/cores?'.format(self.solr_base_ep), params=params)
        print('Created index: {} [Status: {}]'.format(index, resp.status_code))

    def index_documents(self, index, movie_dict={}):
        print('Indexing {} documents'.format(len(movie_dict.keys())))

        def flush(docs):
            print('Flushing {} movies'.format(len(docs)))
            requests.post('{}/{}/update?commitWithin=1500'.format(
                self.solr_base_ep, index), json=docs)
            docs.clear()

        BATCH_SIZE = 500
        docs = []
        for movie in indexableMovies(movie_dict):
            if 'release_date' in movie and movie['release_date'] is not None:
                movie['release_date'] += 'T00:00:00Z'

            docs.append(movie)

            if len(docs) % BATCH_SIZE == 0:
                flush(docs)

        flush(docs)

    def reset_ltr(self):
        pass

    def create_featureset(self, name, config):
        pass

    # TODO: Add query as must boolean clause
    def log_query(self, index, featureset, query):
        pass


    def submit_model(self, featureset, model_name, model_payload):
        pass


    def model_query(self, index, model, model_params, query):
        pass



