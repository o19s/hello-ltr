import os

from ltr import download
from ltr.helpers.ranklib_result import parse_training_log


def check_for_rankymcrankface():
    """Ensure ranky jar is in a temp dir somewhere..."""
    ranky_url = "http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar"
    import tempfile

    tempdir = tempfile.gettempdir()
    download([ranky_url], dest=tempdir, force=False)
    return os.path.join(tempdir, "RankyMcRankFace.jar")


def write_training_set(training_set):
    import tempfile

    from .judgments import judgments_to_file

    tempdir = tempfile.gettempdir()
    train_path = os.path.join(tempdir, "training.txt")
    with open(train_path, "w") as outF:
        judgments_to_file(outF, training_set)
    return train_path


def trainModel(
    training_set,
    out,
    features=None,
    kcv=None,
    ranker=6,
    leafs=10,
    trees=50,
    frate=1.0,
    shrinkage=0.1,
    srate=1.0,
    bag=1,
    metric2t="DCG@10",
):
    """
    ranker
    - 6 for LambdaMART
    - 8 for RandomForest

    RandomForest params
        frate - what proportion of features are candidates at each split
        srate - what proportion of the queries should be examined for each ensemble
    """

    ranky_loc = check_for_rankymcrankface()
    training_set_path = write_training_set(training_set)
    cmd = f"java -jar {ranky_loc} -ranker {ranker} -shrinkage {shrinkage} -metric2t {metric2t} -tree {trees} -bag {bag} -leaf {leafs} -frate {frate} -srate {srate} -train {training_set_path} -save {out} "

    if features is not None:
        import tempfile

        features_file = os.path.join(tempfile.gettempdir(), "features.txt")
        with open(features_file, "w") as f:
            f.write("\n".join([str(feature) for feature in features]))
        cmd += f" -feature {features_file}"

    if kcv is not None and kcv > 0:
        cmd += f" -kcv {kcv} "

    print(f"Running {cmd}")
    result = os.popen(cmd).read()
    return parse_training_log(result)


def save_model(client, modelName, modelFile, index, featureSet):
    with open(modelFile) as src:
        definition = src.read()
        client.submit_ranklib_model(featureSet, index, modelName, definition)


def train(
    client,
    training_set,
    modelName,
    featureSet,
    index,
    features=None,
    kcv=None,
    metric2t="DCG@10",
    leafs=10,
    trees=50,
    frate=1.0,
    srate=1.0,
    bag=1,
    ranker=6,
    shrinkage=0.1,
):
    """Train and store a model into the search engine
    with the provided parameters"""
    modelFile = f"data/{modelName}_model.txt"
    ranklibResult = trainModel(
        training_set,
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
        shrinkage=shrinkage,
    )

    if len(ranklibResult.trainingLogs) == 0:
        raise RuntimeError(
            "Training failed: RankLib did not produce any training logs. This may indicate an error in the training data or RankLib execution."
        )

    if not kcv:
        # Ranklib doesn't save a model to disk if KCV is used
        save_model(client, modelName, modelFile, index, featureSet)
        print("Model saved")

    return ranklibResult


def feature_search(
    client,
    training_set,
    featureSet,
    features=None,
    featureCost=0.0,
    metric2t="DCG@10",
    kcv=5,
    leafs=10,
    trees=10,
    frate=1.0,
    srate=1.0,
    bag=1,
    ranker=6,
    shrinkage=0.1,
):
    from itertools import combinations

    if features is None:
        raise ValueError("features parameter is required for feature_search")

    modelFile = "data/{}_model.txt".format("temp")
    best = 0
    bestCombo = None
    metricPerFeature = {}
    for i in range(1, max(features) + 1):
        metricPerFeature[i] = [0, 0]  # count, sum
    for i in range(1, len(features) + 1):
        for combination in combinations(features, i):
            cost = (1.0 - featureCost) ** (len(combination) - 1)
            ranklibResult = trainModel(
                training_set=training_set,
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
                shrinkage=shrinkage,
            )
            kcvTestMetric = ranklibResult.kcvTestAvg
            if kcvTestMetric is None:
                print(
                    f"Warning: Training failed for features {repr(list(combination))}, skipping..."
                )
                continue
            if featureCost != 0.0:
                print(
                    f"Trying features {repr(list(combination))} TEST {metric2t}={kcvTestMetric} after cost {kcvTestMetric * cost}"
                )
            else:
                print(
                    f"Trying features {repr(list(combination))} TEST {metric2t}={kcvTestMetric}"
                )

            if kcvTestMetric > best:
                best = kcvTestMetric
                bestCombo = ranklibResult

            for feature in combination:
                metricPerFeature[feature][0] += 1
                metricPerFeature[feature][1] += ranklibResult.kcvTestAvg

    # Compute avg metric with each feature
    for i in range(1, max(features) + 1):
        if metricPerFeature[i][0] > 0:
            metricPerFeature[i] = (
                metricPerFeature[i][1] / metricPerFeature[i][0]
            )  # count, sum
        else:
            metricPerFeature[i] = -1

    return bestCombo, metricPerFeature
