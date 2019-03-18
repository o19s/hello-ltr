from ltr import main_client
import requests

def run(config, featureset='genre_features'):
    main_client.reset_ltr()
    main_client.create_featureset(featureset, config)

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
    run(config=config, featureset='title')
