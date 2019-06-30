import os
import requests

from .base_client import BaseClient
from ltr.helpers.convert import convert
from ltr.helpers.handle_resp import resp_msg

class SolrClient(BaseClient):
    def __init__(self):
        self.docker = os.environ.get('LTR_DOCKER') != None

        if self.docker is not None:
            self.solr_base_ep = 'http://solr:8983/solr'
        else:
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
        resp_msg(msg="Deleted index {}".format(index), resp=resp, throw=False)

    def create_index(self, index, settings):
        params = {
            'action': 'CREATE',
            'name': index,
            'configSet': 'tmdb'
        }
        resp = requests.get('{}/admin/cores?'.format(self.solr_base_ep), params=params)
        resp_msg(msg="Created index {}".format(index), resp=resp)

    def index_documents(self, index, movie_source):
        def flush(docs):
            print('Flushing {} movies'.format(len(docs)))
            resp = requests.post('{}/{}/update?commitWithin=1500'.format(
                self.solr_base_ep, index), json=docs)
            resp_msg(msg="Done", resp=resp)
            docs.clear()

        BATCH_SIZE = 500
        docs = []
        for movie in movie_source:
            if 'release_date' in movie and movie['release_date'] is not None:
                movie['release_date'] += 'T00:00:00Z'

            docs.append(movie)

            if len(docs) % BATCH_SIZE == 0:
                flush(docs)

        flush(docs)

    # TODO: Probably better to just delete specific models/stores on creation, this is stacking up
    def reset_ltr(self, index='tmdb'):
        models = self.get_models(index)
        for model in models:
            resp = requests.delete('{}/{}/schema/model-store/{}'.format(self.solr_base_ep, index, model))
            resp_msg(msg='Deleted {} model'.format(model), resp=resp)

        stores = self.get_feature_stores(index)
        for store in stores:
            resp = requests.delete('{}/{}/schema/feature-store/{}'.format(self.solr_base_ep, index, store))
            resp_msg(msg='Deleted {} Featurestore'.format(store), resp=resp)


    def validate_featureset(self, name, config):
        for feature in config:
            if 'store' not in feature or feature['store'] != name:
                raise ValueError("Feature {} needs to be created with \"store\": \"{}\" ".format(feature['name'], name))

    def create_featureset(self, index, name, config):
        self.validate_featureset(name, config)
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

    def get_feature_stores(self, index):
        resp = requests.get('{}/{}/schema/feature-store'.format(self.solr_base_ep,
                                                                index))
        response = resp.json()
        return response['featureStores']

    def get_models(self, index):
        resp = requests.get('{}/{}/schema/model-store'.format(self.solr_base_ep,
                                                              index))
        response = resp.json()
        return [model['name'] for model in response['models']]


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

    def get_doc(self, doc_id):
        params = {
            'q': 'id:{}'.format(doc_id),
            'wt': 'json'
        }

        resp = requests.post('{}/{}/select'.format(self.solr_base_ep, 'tmdb'), data=params).json()
        return resp['response']['docs'][0]




