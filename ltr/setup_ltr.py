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
    print('Created {} feature set: {}'.format(featureSet, resp.status_code))

if __name__ == "__main__":
    config = {"featureset": {
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
            },
             {
                "name": "is_sci_fi",
                "params": [],
                "template": {
                    "constant_score": {
                        "filter": {
                            "match_phrase": {"genres": "Science Fiction"}
                        },
                        "boost": 10.0
                    }
            }
            },
             {
                "name": "is_drama",
                "params": [],
                "template": {
                    "constant_score": {
                        "filter": {
                            "match_phrase": {"genres": "Drama"}
                        },
                        "boost": 4.0
                    }
                }
            },
             {
                "name": "is_genre_match",
                "params": ["keywords"],
                "template": {
                    "constant_score": {
                        "filter": {
                            "match_phrase": {"genres": "{{keywords}}"}
                        },
                        "boost": 100.0
                    }
                }
            }
    ]
    }}
    run(config=config, featureSet='genre')
