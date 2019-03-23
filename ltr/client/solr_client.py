import requests

from .base_client import BaseClient
from ltr.helpers.convert import convert
from ltr.helpers.movies import indexableMovies
from ltr.helpers.handle_resp import resp_msg

class SolrClient(BaseClient):
    def __init__(self):
        self.solr_base_ep = 'http://localhost:8983/solr'

    def name(self):
        return "solr"

    def delete_index(self, index):
        params = {
            'action': 'UNLOAD',
            'core': index,
            'deleteIndex': 'true',
            'deleteDataDir': 'true',
            'deleteInstanceDir': 'true'
        }

        resp = requests.get('{}/admin/cores?'.format(self.solr_base_ep), params=params)
        resp_msg(msg="Deleted index {}".format(index), resp=resp)

    def create_index(self, index, settings):
        params = {
            'action': 'CREATE',
            'name': index,
            'configSet': 'tmdb'
        }
        resp = requests.get('{}/admin/cores?'.format(self.solr_base_ep), params=params)
        resp_msg(msg="Created index {}".format(index), resp=resp)

    def index_documents(self, index, movie_dict={}):
        print('Indexing {} documents'.format(len(movie_dict.keys())))

        def flush(docs):
            print('Flushing {} movies'.format(len(docs)))
            resp = requests.post('{}/{}/update?commitWithin=1500'.format(
                self.solr_base_ep, index), json=docs)
            resp_msg(msg="Done", resp=resp)
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
    # TODO: Probably better to just delete specific models/stores on creation, this is stacking up
    def reset_ltr(self):
        models = ['classic', 'genre', 'latest', 'title', 'title_fuzzy']
        for model in models:
            resp = requests.delete('{}/tmdb/schema/model-store/{}'.format(self.solr_base_ep, model))
            resp_msg(msg='Deleted {} model'.format(model), resp=resp)

        stores = ['_DEFAULT', 'genre', 'release', 'title', 'title_fuzzy']
        for store in stores:
            resp = requests.delete('{}/tmdb/schema/feature-store/{}'.format(self.solr_base_ep, store))
            resp_msg(msg='Deleted {} Featurestore'.format(store), resp=resp)


    def create_featureset(self, index, name, config):
        resp = requests.put('{}/{}/schema/feature-store'.format(
            self.solr_base_ep, index, name), json=config)
        resp_msg(msg='Created {} feature store under {}:'.format(name, index), resp=resp)


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
        resp = requests.post('{}/{}/select'.format(self.solr_base_ep, index), data=params)
        resp_msg(msg='Searching {}'.format(index), resp=resp)
        resp = resp.json()

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
        resp = requests.get('{}/tmdb/schema/feature-store/{}'.format(self.solr_base_ep, featureset))
        resp_msg(msg='Submit Model {} Ftr Set {}'.format(model_name, featureset), resp=resp)
        metadata = resp.json()
        features = metadata['features']

        feature_dict = {}
        for idx, value in enumerate(features):
            feature_dict[idx + 1] = value['name']

        feature_mapping, _ = self.feature_set('tmdb', featureset)

        solr_model = convert(model_payload, model_name, featureset, feature_mapping)

        url = '{}/tmdb/schema/model-store'.format(self.solr_base_ep)
        resp = requests.delete('{}/{}'.format(url, model_name))
        resp_msg(msg='Deleted Model {}'.format(model_name), resp=resp)

        resp = requests.put(url, json=solr_model)
        resp_msg(msg='Created Model {}'.format(model_name), resp=resp)


    def model_query(self, index, model, model_params, query):
        url = '{}/{}/select?'.format(self.solr_base_ep, index)
        params = {
            'q': query,
            'rq': '{{!ltr model={}}}'.format(model),
            'rows': 100
        }

        resp = requests.post(url, data=params)
        resp_msg(msg='Search keywords - {}'.format(query), resp=resp)
        return resp.json()['response']['docs']

    def query(self, index, query):
        url = '{}/{}/select?'.format(self.solr_base_ep, index)

        resp = requests.post(url, data=query)
        resp_msg(msg='Query {}...'.format(str(query)[:10]), resp=resp)
        resp = resp.json()

        # Transform to be consistent
        for doc in resp['response']['docs']:
            if 'score' in doc:
                doc['_score'] = doc['score']

        return resp['response']['docs']


    def feature_set(self, index, name):
        resp = requests.get('{}/{}/schema/feature-store/{}'.format(self.solr_base_ep,
                                                                   index,
                                                                   name))
        resp_msg(msg='Feature Set {}...'.format(name), resp=resp)

        response = resp.json()

        rawFeatureSet = response['features']

        mapping = []
        for feature in response['features']:
            mapping.append({'name': feature['name']})

        return mapping, rawFeatureSet



