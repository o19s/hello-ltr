import os
from ltr.helpers.ranklib_result import parse_training_log


def trainModel(training, out, features=None, kcv=None, leafs=10, trees=50, metric2t='DCG@10'):

    cmd = 'java -jar data/RankyMcRankFace.jar -ranker 6 -metric2t {} -tree {} -leaf {} -train {} -save {} '.format(metric2t, leafs, trees, training, out)

    if features is not None:
        with open('features.txt', 'w') as f:
            f.write("\n".join([str(feature) for feature in features]))
        cmd += " -feature features.txt "

    if kcv is not None and kcv > 0:
        cmd += " -kcv {} ".format(kcv)

    print("Running %s" % cmd)
    result = os.popen(cmd).read()
    print("DONE")
    return parse_training_log(result)

def save_model(client, modelName, modelFile, featureSet):
    with open(modelFile) as src:
        definition = src.read()
        client.submit_model(featureSet, modelName, definition)


def train(client, trainingInFile, modelName, featureSet,
          features=None,
          metric2t='DCG@10', leafs=10, trees=50):
    """ Train and store a model into the search engine
        with the provided parameters"""
    modelFile='data/{}_model.txt'.format(modelName)
    ranklibResult = trainModel(training=trainingInFile,
                               out=modelFile,
                               metric2t=metric2t,
                               features=features,
                               leafs=leafs,
                               kcv=None,
                               trees=trees)
    save_model(client, modelName, modelFile, featureSet)
    assert len(ranklibResult.trainingLogs) == 1
    return ranklibResult.trainingLogs[0]
    print('Done')


def feature_search(client, trainingInFile, featureSet,
                   features=None,
                   featureCost=0.0,
                   metric2t='DCG@10',
                   kcv=5, leafs=10, trees=10):
    from itertools import combinations
    modelFile='data/{}_model.txt'.format('temp')
    best = 0
    bestCombo = None
    metricPerFeature = {}
    for i in range(1, len(features)+1):
        metricPerFeature[i] = [0,0] # count, sum
    for i in range(1, len(features)+1):
        for combination in combinations(features, i):
            cost = (1.0 - featureCost)**(len(combination)-1)
            ranklibResult = trainModel(training=trainingInFile,
                                       out=modelFile,
                                       kcv=kcv,
                                       metric2t=metric2t,
                                       features=combination,
                                       leafs=leafs,
                                       trees=trees)
            kcvTestMetric = ranklibResult.kcvTestAvg
            if featureCost != 0.0:
                print("Trying features %s TEST %s=%s after cost %s" % (repr([combo for combo in combination]), metric2t, kcvTestMetric, kcvTestMetric*cost))
            else:
                print("Trying features %s TEST %s=%s" % (repr([combo for combo in combination]), metric2t, kcvTestMetric))

            if kcvTestMetric > best:
                best=kcvTestMetric
                bestCombo = ranklibResult

            for feature in combination:
                metricPerFeature[feature][0] += 1
                metricPerFeature[feature][1] += ranklibResult.kcvTestAvg

    # Compute avg metric with each feature
    for i in range(1, len(features)+1):
        metricPerFeature[i] = metricPerFeature[i][1] / metricPerFeature[i][0]  # count, sum


    return bestCombo, metricPerFeature
    print('Done')
