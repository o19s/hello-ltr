"""RankLib model training and management.

This module provides functionality for training Learn-to-Rank models using
RankLib (via RankyMcRankFace.jar), saving models to search engines, and
performing feature selection.
"""

import os
import shlex
import subprocess

from ltr import download
from ltr.helpers.ranklib_result import parse_training_log


def check_for_rankymcrankface():
    """Ensure RankyMcRankFace.jar is available in the system temp directory.

    Downloads the RankyMcRankFace.jar file if it doesn't already exist.

    Returns:
        str: Path to the RankyMcRankFace.jar file.

    Note:
        The jar file is downloaded from a remote URL and cached in the
        system temp directory.
    """
    ranky_url = "http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar"
    import tempfile

    tempdir = tempfile.gettempdir()
    download([ranky_url], dest=tempdir, force=False)
    return os.path.join(tempdir, "RankyMcRankFace.jar")


def write_training_set(training_set):
    """Write training set judgments to a temporary file in RankLib format.

    Args:
        training_set: List of Judgment objects to write to file.

    Returns:
        str: Path to the temporary training file.

    Note:
        The file is created in the system temp directory and will be
        cleaned up automatically by the OS.
    """
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
    """Train a RankLib model using the provided training set.

    Args:
        training_set: List of Judgment objects for training.
        out: Output file path where the trained model will be saved.
        features: Optional list of feature indices to use. If None, all features are used.
        kcv: Optional integer for k-fold cross-validation. If provided and > 0,
            cross-validation is performed instead of saving a model.
        ranker: Ranker algorithm to use:
            - 6: LambdaMART (default)
            - 8: RandomForest
        leafs: Number of leaves per tree (default: 10).
        trees: Number of trees in the ensemble (default: 50).
        frate: Feature rate - proportion of features considered at each split
            (default: 1.0, only used for RandomForest).
        shrinkage: Learning rate/shrinkage parameter (default: 0.1).
        srate: Sample rate - proportion of queries examined for each ensemble
            (default: 1.0, only used for RandomForest).
        bag: Bagging fraction (default: 1).
        metric2t: Metric to optimize during training (default: "DCG@10").

    Returns:
        RanklibResult: Object containing training logs and metrics.

    Raises:
        RuntimeError: If RankLib execution fails or produces no training logs.

    Note:
        RandomForest-specific parameters (frate, srate) are only used when
        ranker=8. For LambdaMART (ranker=6), these parameters are ignored.
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
    result = subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return parse_training_log(result)


def save_model(client, modelName, modelFile, index, featureSet):
    """Save a trained RankLib model to the search engine.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        modelName: Name to assign to the model in the search engine.
        modelFile: Path to the file containing the trained model definition.
        index: Name of the search index where the model will be stored.
        featureSet: Name of the feature set associated with this model.
    """
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
    """Train a RankLib model and store it in the search engine.

    This function trains a model using RankLib, validates the training results,
    and saves the model to the specified search engine index.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        training_set: List of Judgment objects for training.
        modelName: Name to assign to the trained model.
        featureSet: Name of the feature set to use with this model.
        index: Name of the search index where the model will be stored.
        features: Optional list of feature indices to use. If None, all features are used.
        kcv: Optional integer for k-fold cross-validation. If provided, cross-validation
            is performed and no model is saved (RankLib doesn't save models when using KCV).
        metric2t: Metric to optimize during training (default: "DCG@10").
        leafs: Number of leaves per tree (default: 10).
        trees: Number of trees in the ensemble (default: 50).
        frate: Feature rate for RandomForest (default: 1.0).
        srate: Sample rate for RandomForest (default: 1.0).
        bag: Bagging fraction (default: 1).
        ranker: Ranker algorithm to use, 6 for LambdaMART or 8 for RandomForest (default: 6).
        shrinkage: Learning rate/shrinkage parameter (default: 0.1).

    Returns:
        RanklibResult: Object containing training logs and metrics.

    Raises:
        RuntimeError: If training fails or produces no training logs.
    """
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
    """Perform feature selection by testing all combinations of features.

    This function exhaustively tests all combinations of features to find
    the best performing feature set. It uses k-fold cross-validation to
    evaluate each combination.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        training_set: List of Judgment objects for training.
        featureSet: Name of the feature set to use.
        features: List of feature indices to test combinations from. Required.
        featureCost: Cost penalty for using more features (0.0 = no penalty, default: 0.0).
            Higher values penalize larger feature sets.
        metric2t: Metric to optimize during training (default: "DCG@10").
        kcv: Number of folds for k-fold cross-validation (default: 5).
        leafs: Number of leaves per tree (default: 10).
        trees: Number of trees in the ensemble (default: 10).
        frate: Feature rate for RandomForest (default: 1.0).
        srate: Sample rate for RandomForest (default: 1.0).
        bag: Bagging fraction (default: 1).
        ranker: Ranker algorithm to use, 6 for LambdaMART or 8 for RandomForest (default: 6).
        shrinkage: Learning rate/shrinkage parameter (default: 0.1).

    Returns:
        tuple: A tuple containing:
            - bestCombo: RanklibResult object for the best performing feature combination,
              or None if no valid combination was found.
            - metricPerFeature: Dictionary mapping feature index to average metric value
              when that feature is included. Features not tested have value -1.

    Raises:
        ValueError: If features parameter is None or empty.

    Note:
        This function tests all combinations from size 1 to len(features),
        which can be computationally expensive for large feature sets.
        Failed training attempts for specific combinations are skipped with a warning.
    """
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
