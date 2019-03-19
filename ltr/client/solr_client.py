import requests

from .base_client import BaseClient
from ltr.helpers.ranklib_solr import ranklibMartToSolr
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

    # TODO: Fetch metadata from feature/model store and wipe everything
    def reset_ltr(self):
        models = ['classic', 'genre', 'latest']
        for model in models:
            resp = requests.delete('{}/tmdb/schema/model-store/{}'.format(self.solr_base_ep, model))
            print('Deleted {} model: {}'.format(model, resp.status_code))

        stores = ['_DEFAULT', 'genre', 'release']
        for store in stores:
            resp = requests.delete('{}/tmdb/schema/feature-store/{}'.format(self.solr_base_ep, store))
            print('Delete {} feature store: {}'.format(store, resp.status_code))


    def create_featureset(self, index, name, config):
        resp = requests.put('{}/{}/schema/feature-store'.format(
            self.solr_base_ep, index, name), json=config)
        print('Created {} feature store under {}: {}'.format(name, index, resp.status_code))


    def log_query(self, index, featureset, query, options={}):
        if query is None:
            query = '*:*'

        efi_options = []
        for key, val in options.items():
            efi_options.append('efi.{}="{}"'.format(key, val))

        efi_str = ' '.join(efi_options)

        params = {
            'fl': 'id,[features store={} {}]'.format(featureset, efi_str),
            'q': query,
            'rows': 1000,
            'wt': 'json'
        }
        resp = requests.post('{}/{}/select'.format(self.solr_base_ep, index), data=params).json()

        def parseFeatures(features):
            fv = []

            all_features = features.split(',')

            for feature in all_features:
                elements = feature.split('=')
                fv.append(float(elements[1]))

            return fv

        # Clean up features to consistent format
        for doc in resp['response']['docs']:
            doc['ltr_features'] = parseFeatures(doc['[features]'])

        return resp['response']['docs']


    def submit_model(self, featureset, model_name, model_payload):
        # Fetch feature metadata
        metadata = requests.get('{}/tmdb/schema/feature-store/{}'.format(self.solr_base_ep, featureset)).json()
        features = metadata['features']

        feature_dict = {}
        for idx, value in enumerate(features):
            feature_dict[idx + 1] = value['name']

        solr_model = ranklibMartToSolr(model_payload, model_name, featureset, feature_dict)

        url = '{}/tmdb/schema/model-store'.format(self.solr_base_ep)
        resp = requests.delete('{}/{}'.format(url, model_name))
        print('Deleted {} model [{}]'.format(model_name, resp.status_code))

        resp = requests.put(url, json=solr_model)
        print('PUT {} model under {}: {}'.format(model_name, featureset, resp.status_code))


    def model_query(self, index, model, model_params, query):
        url = '{}/{}/select?'.format(self.solr_base_ep, index)
        params = {
            'q': query,
            'rq': '{{!ltr model={}}}'.format(model),
            'rows': 100
        }

        resp = requests.post(url, data=params).json()
        return resp['response']['docs']

    def query(self, index, query):
        url = '{}/{}/select?'.format(self.solr_base_ep, index)

        resp = requests.post(url, data=query).json()

        # Transform to be consistent
        for doc in resp['response']['docs']:
            if 'score' in doc:
                doc['_score'] = doc['score']

        return resp['response']['docs']



