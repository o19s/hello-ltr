import json
import requests

def run(config, featureSet='genre_features'):
    elastic_ep = 'http://localhost:9200/_ltr'

    # Remove existing LTR
    resp = requests.delete(elastic_ep)
    print('Removed LTR feature store: {}'.format(resp.status_code))

    # Reinit LTR
    resp = requests.put(elastic_ep)
    print('Initialize LTR: {}'.format(resp.status_code))

    # Create a feature set
    payload = config

    resp = requests.post('{}/_featureset/{}'.format(elastic_ep, featureSet), json=payload)
    print('Created RELEASE feature set: {}'.format(resp.status_code))
