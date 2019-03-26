import os
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

    def metric(self):
        if len(self.rounds) > 0:
            return self.rounds[-1]
        else:
            return 0



def trainModel(training, out, features=None, leafs=10, trees=10, metric2t='DCG@10'):

    if features is None:
        cmd = 'java -jar data/RankyMcRankFace.jar -ranker 6 -metric2t {} -tree {} -leaf {} -train {} -save {}'.format(metric2t, leafs, trees, training, out)

    else:
        with open('features.txt', 'w') as f:
            f.write("\n".join([str(feature) for feature in features]))
        cmd = 'java -jar data/RankyMcRankFace.jar -ranker 6 -feature features.txt -metric2t {} -tree {} -leaf {} -train {} -save {}'.format(metric2t, leafs, trees, training, out)
    print("Running %s" % cmd)
    result = os.popen(cmd).read()
    print("DONE")
    return TrainingLog(result)

def save_model(client, modelName, modelFile, featureSet):
    with open(modelFile) as src:
        definition = src.read()
        client.submit_model(featureSet, modelName, definition)


def train(client, trainingInFile, modelName, featureSet, features=None, metric2t='DCG@10', leafs=10, trees=10):
    modelFile='data/{}_model.txt'.format(modelName)
    trainingLog = trainModel(training=trainingInFile,
                             out=modelFile,
                             metric2t=metric2t,
                             features=features,
                             leafs=leafs,
                             trees=trees)
    save_model(client, modelName, modelFile, featureSet)
    return trainingLog
    print('Done')

def feature_search(client, trainingInFile, featureSet, features=None, metric2t='DCG@10', leafs=10, trees=10):
    from itertools import combinations
    modelFile='data/{}_model.txt'.format('temp')
    best = 0
    bestCombo = None
    for i in range(1, len(features)+1):
        for combination in combinations(features, i):
            print("Trying features %s" % repr([combo for combo in combination]))
            trainingLog = trainModel(training=trainingInFile,
                                     out=modelFile,
                                     metric2t=metric2t,
                                     features=combination,
                                     leafs=leafs,
                                     trees=trees)
            if trainingLog.metric() > best:
                best=trainingLog.metric()
                bestCombo = trainingLog

    return bestCombo
    print('Done')
