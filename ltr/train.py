import os
import requests

def trainModel(training, out):
    cmd = 'java -jar data/RankyMcRankFace-0.1.1.jar -ranker 6 -tree 10 -train {} -save {}'.format(training, out)
    os.system(cmd)

def saveModel(modelName, modelFile, featureSet):
    model_ep = "http://localhost:9200/_ltr/_model/"
    create_ep = "http://localhost:9200/_ltr/_featureset/{}/_createmodel".format(featureSet)

    resp = requests.delete('{}{}'.format(model_ep, modelName))
    print('Delete model {}: {}'.format(modelName, resp.status_code))
    with open(modelFile) as src:
        definition = src.read()

        params = {
            'model': {
                'name': modelName,
                'model': {
                    'type': 'model/ranklib',
                    'definition': definition
                }
            }
        }

        resp = requests.post(create_ep, json=params)
        print('Created model {}: {}'.format(modelName, resp.status_code))


def run(trainingSetIn, modelName, featureSet):
    modelFile='data/{}_model.txt'.format(modelName)
    trainModel(training=trainingSetIn, out=modelFile)
    saveModel(modelName, modelFile, featureSet)
    print('Done')


if __name__ == "__main__":
    run(training='genre_by_date_judgments_train.txt', featureSet='genre', modelName='doug')
