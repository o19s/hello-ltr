import os
import requests

def trainModel(training, out):
    cmd = 'java -jar data/RankyMcRankFace-0.1.1.jar -ranker 6 -tree 10 -train {} -save {}'.format(training, out)
    os.system(cmd)

def run():
    trainModel('data/classic-training.txt', 'data/classic-model.txt')
    trainModel('data/latest-training.txt', 'data/latest-model.txt')

    model_ep = "http://localhost:9200/_ltr/_model/"
    create_ep = "http://localhost:9200/_ltr/_featureset/release/_createmodel"

    models = ['classic', 'latest']
    model_files = {
        'classic': 'data/classic-model.txt',
        'latest': 'data/latest-model.txt'
    }

    print('Syncing models to elastic')
    for model in models:
        resp = requests.delete('{}{}'.format(model_ep, model))
        print('Delete model {}: {}'.format(model, resp.status_code))

        with open(model_files[model]) as src:
            definition = src.read()

        params = {
            'model': {
                'name': model,
                'model': {
                    'type': 'model/ranklib',
                    'definition': definition
                }
            }
        }

        resp = requests.post(create_ep, json=params)
        print('Created model {}: {}'.format(model, resp.status_code))

    print('Done')


