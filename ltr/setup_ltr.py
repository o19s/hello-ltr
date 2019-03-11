import json
import requests

def run():
    elastic_ep = 'http://localhost:9200/_ltr'

    # Remove existing LTR
    resp = requests.delete(elastic_ep)
    print('Removed LTR feature store: {}'.format(resp.status_code))

    # Reinit LTR
    resp = requests.put(elastic_ep)
    print('Initialize LTR: {}'.format(resp.status_code))

    # Create a feature set
    payload = {
	"featureset": {
	    "features": [
		{
		    "name": "release_year",
		    "params": [],
		    "template": {
			"function_score": {
			    "field_value_factor": {
				"field": "release_year",
				"missing": 2000
			    },
			    "query": { "match_all": {} }
			}
		    }
		}
	    ]
	}
    }

    resp = requests.post('{}/_featureset/release'.format(elastic_ep), json=payload)
    print('Created RELEASE feature set: {}'.format(resp.status_code))
