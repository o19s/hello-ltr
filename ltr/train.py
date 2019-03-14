import os
import requests
import re

class TrainingLog:
    def __init__(self, rawResult):
        self.rawResult = rawResult
        self.impacts = {}
        self.rounds = []
        lines = rawResult.split('\n')

        impactRe = re.compile(' Feature (\d+) reduced error (.*)')
        roundsRe = re.compile('(\d+)\s+\| (\d+)')
        for line in lines:
            m = re.match(impactRe, line)
            if m:
                ftrId = m.group(1)
                error = float(m.group(2))
                self.impacts[ftrId] = error
            m = re.match(roundsRe, line)
            if m:
                values = line.split('|')
                metricTrain = float(values[1])
                self.rounds.append(metricTrain)



def trainModel(training, out, metric='DCG@10'):

    cmd = 'java -jar data/RankyMcRankFace.jar -ranker 6 -metric2t {} -tree 100 -train {} -save {}'.format(metric, training, out)

    result = os.popen(cmd).read()
    return TrainingLog(result)

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


def run(trainingInFile, modelName, featureSet):
    modelFile='data/{}_model.txt'.format(modelName)
    trainingLog = trainModel(training=trainingInFile,
                             out=modelFile)
    saveModel(modelName, modelFile, featureSet)
    return trainingLog
    print('Done')


if __name__ == "__main__":
    run(trainingInFile='genre_by_date_judgments_train.txt',
        featureSet='genre',
        modelName='doug')
