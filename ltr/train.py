import os
from ltr.helpers.ranklib_result import parse_training_log
from ltr import download

def check_for_rankymcrankface():
    """ Ensure ranky jar is in a temp dir somewhere..."""
    ranky_url='http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar'
    import tempfile
    tempdir = tempfile.gettempdir()
    import pdb; pdb.set_trace()
    download([ranky_url], dest=tempdir, force=False)
    return os.path.join(tempdir, 'RankyMcRankFace.jar')


def trainModel(training, out, features=None, kcv=None, ranker=6,
               leafs=10, trees=50, frate=1.0, shrinkage=0.1,
               srate=1.0, bag=1, metric2t='DCG@10'):
    """
    ranker
    - 6 for LambdaMART
    - 8 for RandomForest

    RandomForest params
        frate - what proportion of features are candidates at each split
        srate - what proportion of the queries should be examined for each ensemble
    """

    ranky_loc = check_for_rankymcrankface()
    cmd = 'java -jar {} -ranker {} -shrinkage {} -metric2t {} -tree {} -bag {} -leaf {} -frate {} -srate {} -train {} -save {} '.format(
            ranky_loc, ranker, shrinkage, metric2t, trees, bag, leafs, frate, srate, training, out)

    if features is not None:
        with open('data/features.txt', 'w') as f:
            f.write("\n".join([str(feature) for feature in features]))
        cmd += " -feature data/features.txt "

    if kcv is not None and kcv > 0:
        cmd += " -kcv {} ".format(kcv)

    print("Running %s" % cmd)
    result = os.popen(cmd).read()
    print("DONE")
    return parse_training_log(result)

def save_model(client, modelName, modelFile, index, featureSet):
    with open(modelFile) as src:
        definition = src.read()
        client.submit_ranklib_model(featureSet, index, modelName, definition)


def train(client, trainingInFile, modelName, featureSet,
          index, features=None,
          metric2t='DCG@10', leafs=10, trees=50,
          frate=1.0, srate=1.0, bag=1, ranker=6, shrinkage=0.1):
    """ Train and store a model into the search engine
        with the provided parameters"""
    modelFile='data/{}_model.txt'.format(modelName)
    ranklibResult = trainModel(training=trainingInFile,
                               out=modelFile,
                               metric2t=metric2t,
                               features=features,
                               leafs=leafs,
                               kcv=None,
                               ranker=ranker,
                               bag=bag,
                               srate=srate,
                               frate=frate,
                               trees=trees,
                               shrinkage=shrinkage)
    save_model(client, modelName, modelFile, index, featureSet)
    assert len(ranklibResult.trainingLogs) == 1
    return ranklibResult.trainingLogs[0]
    print('Done')


def kcv(client, trainingInFile, modelName, featureSet,
        index, features=None, kcv=5,
        metric2t='DCG@10', leafs=10, trees=50,
        frate=1.0, srate=1.0, bag=1, ranker=6,
        shrinkage=0.1):
    """ Train and store a model into the search engine
        with the provided parameters"""
    modelFile='data/{}_model.txt'.format(modelName)
    ranklibResult = trainModel(training=trainingInFile,
                               out=modelFile,
                               metric2t=metric2t,
                               features=features,
                               leafs=leafs,
                               kcv=kcv,
                               ranker=ranker,
                               bag=bag,
                               srate=srate,
                               frate=frate,
                               trees=trees,
                               shrinkage=shrinkage)
    return ranklibResult


def feature_search(client, trainingInFile, featureSet,
                   features=None,
                   featureCost=0.0,
                   metric2t='DCG@10',
                   kcv=5, leafs=10, trees=10,
                   frate=1.0, srate=1.0, bag=1, ranker=6,
                   shrinkage=0.1):
    from itertools import combinations
    modelFile='data/{}_model.txt'.format('temp')
    best = 0
    bestCombo = None
    metricPerFeature = {}
    for i in range(1, max(features)+1):
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
                                       trees=trees,
                                       ranker=ranker,
                                       bag=bag,
                                       srate=srate,
                                       frate=frate,
                                       shrinkage=shrinkage)
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
    for i in range(1, max(features)+1):
        if metricPerFeature[i][0] > 0:
            metricPerFeature[i] = metricPerFeature[i][1] / metricPerFeature[i][0]  # count, sum
        else:
            metricPerFeature[i] = -1


    return bestCombo, metricPerFeature
    print('Done')
