"""RankLib model training and management.

This module provides functionality for training Learn-to-Rank models using
RankLib (via RankyMcRankFace.jar), saving models to search engines, and
performing feature selection.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any

from ltr import download
from ltr.client.base_client import BaseClient
from ltr.helpers.ranklib_result import RanklibResult, parse_training_log
from ltr.judgments import Judgment
from ltr.logger import get_logger

logger = get_logger(__name__)


def check_for_rankymcrankface() -> str:
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


def write_training_set(training_set: list[Judgment]) -> str:
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
    with open(train_path, "w") as out_f:
        judgments_to_file(out_f, training_set)
    return train_path


def train_model(
    training_set: list[Judgment],
    out: str,
    features: list[int] | None = None,
    kcv: int | None = None,
    ranker: int = 6,
    leafs: int = 10,
    trees: int = 50,
    frate: float = 1.0,
    shrinkage: float = 0.1,
    srate: float = 1.0,
    bag: int = 1,
    metric2t: str = "DCG@10",
) -> RanklibResult:
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

    logger.info(f"Running RankLib command: {cmd}")
    result = subprocess.run(
        shlex.split(cmd),
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return parse_training_log(result)


def save_model(
    client: BaseClient,
    model_name: str,
    model_file: str,
    index: str,
    feature_set: str,
) -> None:
    """Save a trained RankLib model to the search engine.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        model_name: Name to assign to the model in the search engine.
        model_file: Path to the file containing the trained model definition.
        index: Name of the search index where the model will be stored.
        feature_set: Name of the feature set associated with this model.
    """
    with open(model_file) as src:
        definition = src.read()
        client.submit_ranklib_model(feature_set, index, model_name, definition)


def train(
    client: BaseClient,
    training_set: list[Judgment],
    model_name: str,
    feature_set: str,
    index: str,
    features: list[int] | None = None,
    kcv: int | None = None,
    metric2t: str = "DCG@10",
    leafs: int = 10,
    trees: int = 50,
    frate: float = 1.0,
    srate: float = 1.0,
    bag: int = 1,
    ranker: int = 6,
    shrinkage: float = 0.1,
    **kwargs: Any,
) -> RanklibResult:
    """Train a RankLib model and store it in the search engine.

    This function trains a model using RankLib, validates the training results,
    and saves the model to the specified search engine index.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        training_set: List of Judgment objects for training.
        model_name: Name to assign to the trained model.
        feature_set: Name of the feature set to use with this model.
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
        TypeError: If camelCase parameter names are used (e.g., featureSet instead of feature_set).
    """
    # Check for common camelCase parameter name mistakes
    camel_case_mappings = {
        "featureSet": "feature_set",
        "modelName": "model_name",
        "featureCost": "feature_cost",
    }

    for camel_name, snake_name in camel_case_mappings.items():
        if camel_name in kwargs:
            raise TypeError(
                f"{train.__name__}() got an unexpected keyword argument '{camel_name}'. "
                f"Did you mean '{snake_name}'? The codebase uses snake_case for parameter names."
            )

    # Reject any unexpected keyword arguments
    if kwargs:
        unexpected = ", ".join(f"'{k}'" for k in kwargs)
        raise TypeError(
            f"{train.__name__}() got unexpected keyword argument(s): {unexpected}. "
            f"Valid parameters are: model_name, feature_set, index, features, kcv, metric2t, "
            f"leafs, trees, frate, srate, bag, ranker, shrinkage"
        )

    model_file = f"data/{model_name}_model.txt"
    ranklib_result = train_model(
        training_set,
        out=model_file,
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

    if len(ranklib_result.trainingLogs) == 0:
        raise RuntimeError(
            "Training failed: RankLib did not produce any training logs. This may indicate an error in the training data or RankLib execution."
        )

    if not kcv:
        # Ranklib doesn't save a model to disk if KCV is used
        save_model(client, model_name, model_file, index, feature_set)
        logger.info("Model saved successfully")

    return ranklib_result


def feature_search(
    client: BaseClient,
    training_set: list[Judgment],
    feature_set: str,
    features: list[int] | None = None,
    feature_cost: float = 0.0,
    metric2t: str = "DCG@10",
    kcv: int = 5,
    leafs: int = 10,
    trees: int = 10,
    frate: float = 1.0,
    srate: float = 1.0,
    bag: int = 1,
    ranker: int = 6,
    shrinkage: float = 0.1,
    **kwargs: Any,
) -> tuple[RanklibResult | None, dict[int, float]]:
    """Perform feature selection by testing all combinations of features.

    This function exhaustively tests all combinations of features to find
    the best performing feature set. It uses k-fold cross-validation to
    evaluate each combination.

    Args:
        client: Search client instance (ElasticClient, OpenSearchClient, or SolrClient).
        training_set: List of Judgment objects for training.
        feature_set: Name of the feature set to use.
        features: List of feature indices to test combinations from. Required.
        feature_cost: Cost penalty for using more features (0.0 = no penalty, default: 0.0).
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
            - best_combo: RanklibResult object for the best performing feature combination,
              or None if no valid combination was found.
            - metric_per_feature: Dictionary mapping feature index to average metric value
              when that feature is included. Features not tested have value -1.

    Raises:
        ValueError: If features parameter is None or empty.
        TypeError: If camelCase parameter names are used (e.g., featureSet instead of feature_set).

    Note:
        This function tests all combinations from size 1 to len(features),
        which can be computationally expensive for large feature sets.
        Failed training attempts for specific combinations are skipped with a warning.
    """
    from itertools import combinations

    # Check for common camelCase parameter name mistakes
    camel_case_mappings = {
        "featureSet": "feature_set",
        "modelName": "model_name",
        "featureCost": "feature_cost",
    }

    for camel_name, snake_name in camel_case_mappings.items():
        if camel_name in kwargs:
            raise TypeError(
                f"{feature_search.__name__}() got an unexpected keyword argument '{camel_name}'. "
                f"Did you mean '{snake_name}'? The codebase uses snake_case for parameter names."
            )

    # Reject any unexpected keyword arguments
    if kwargs:
        unexpected = ", ".join(f"'{k}'" for k in kwargs)
        raise TypeError(
            f"{feature_search.__name__}() got unexpected keyword argument(s): {unexpected}. "
            f"Valid parameters are: feature_set, features, feature_cost, metric2t, kcv, leafs, "
            f"trees, frate, srate, bag, ranker, shrinkage"
        )

    if features is None:
        raise ValueError("features parameter is required for feature_search")

    model_file = "data/{}_model.txt".format("temp")
    best = 0
    best_combo = None
    metric_per_feature = {}
    for i in range(1, max(features) + 1):
        metric_per_feature[i] = [0, 0]  # count, sum
    for i in range(1, len(features) + 1):
        for combination in combinations(features, i):
            cost = (1.0 - feature_cost) ** (len(combination) - 1)
            ranklib_result = train_model(
                training_set=training_set,
                out=model_file,
                kcv=kcv,
                metric2t=metric2t,
                features=list(combination),
                leafs=leafs,
                trees=trees,
                ranker=ranker,
                bag=bag,
                srate=srate,
                frate=frate,
                shrinkage=shrinkage,
            )
            kcv_test_metric = ranklib_result.kcvTestAvg
            if kcv_test_metric is None:
                logger.warning(
                    f"Training failed for features {repr(list(combination))}, "
                    "skipping..."
                )
                continue
            if feature_cost != 0.0:
                logger.info(
                    f"Trying features {repr(list(combination))} TEST "
                    f"{metric2t}={kcv_test_metric} after cost "
                    f"{kcv_test_metric * cost}"
                )
            else:
                logger.info(
                    f"Trying features {repr(list(combination))} TEST "
                    f"{metric2t}={kcv_test_metric}"
                )

            if kcv_test_metric > best:
                best = kcv_test_metric
                best_combo = ranklib_result

            for feature in combination:
                metric_per_feature[feature][0] += 1
                metric_per_feature[feature][1] += ranklib_result.kcvTestAvg

    # Compute avg metric with each feature
    for i in range(1, max(features) + 1):
        if metric_per_feature[i][0] > 0:
            metric_per_feature[i] = (
                metric_per_feature[i][1] / metric_per_feature[i][0]
            )  # count, sum
        else:
            metric_per_feature[i] = -1

    return best_combo, metric_per_feature
