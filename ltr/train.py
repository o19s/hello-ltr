import os
import requests
import re

from ltr import main_client

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



def trainModel(training, out, metric2t='DCG@10'):

    cmd = 'java -jar data/RankyMcRankFace.jar -ranker 6 -metric2t {} -tree 100 -train {} -save {}'.format(metric2t, training, out)

    print("Running %s" % cmd)
    result = os.popen(cmd).read()
    print("DONE")
    return TrainingLog(result)

def saveModel(modelName, modelFile, featureSet):
    with open(modelFile) as src:
        definition = src.read()
        main_client.submit_model(featureSet, modelName, definition)

def run(trainingInFile, modelName, featureSet, metric2t='DCG@10'):
    modelFile='data/{}_model.txt'.format(modelName)
    trainingLog = trainModel(training=trainingInFile,
                             out=modelFile,
                             metric2t=metric2t)
    saveModel(modelName, modelFile, featureSet)
    return trainingLog
    print('Done')


if __name__ == "__main__":
    run(trainingInFile='genre_by_date_judgments_train.txt',
        featureSet='title',
        modelName='doug')
