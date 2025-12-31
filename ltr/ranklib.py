"""RankLib model training and management.

This module provides functionality for training Learn-to-Rank models using
RankLib (via RankyMcRankFace.jar), saving models to search engines, and
performing feature selection.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from itertools import combinations
from typing import Any

import requests

from ltr import download
from ltr.client.base_client import BaseClient
from ltr.exceptions import ModelError
from ltr.helpers.ranklib_result import RanklibResult, parse_training_log
from ltr.judgments import Judgment
from ltr.logger import get_logger
from ltr.validation import ValidationError

logger = get_logger(__name__)


def check_for_rankymcrankface() -> str:
    """Ensure RankyMcRankFace.jar is available in the system temp directory.

    Downloads the RankyMcRankFace.jar file if it doesn't already exist.

    Returns:
        str: Path to the RankyMcRankFace.jar file.

    Raises:
        ModelError: If the JAR file download fails or cannot be accessed.

    Note:
        The jar file is downloaded from a remote URL and cached in the
        system temp directory.
    """
    ranky_url = "http://es-learn-to-rank.labs.o19s.com/RankyMcRankFace.jar"

    tempdir = tempfile.gettempdir()
    jar_path = os.path.join(tempdir, "RankyMcRankFace.jar")

    try:
        download([ranky_url], dest=tempdir, force=False)
    except requests.exceptions.RequestException as e:
        raise ModelError(
            f"Failed to download RankyMcRankFace.jar from {ranky_url}. "
            f"This may indicate:\n"
            f"  1. Network connectivity issues\n"
            f"  2. The download server is unavailable\n"
            f"  3. Firewall or proxy blocking the connection\n\n"
            f"Error details: {str(e)}\n\n"
            f"To resolve:\n"
            f"  - Check your internet connection\n"
            f"  - Verify the URL is accessible: {ranky_url}\n"
            f"  - Check firewall/proxy settings\n"
            f"  - Try downloading manually and placing at: {jar_path}",
            operation="check_for_rankymcrankface",
        ) from e
    except Exception as e:
        raise ModelError(
            f"Unexpected error while downloading RankyMcRankFace.jar: {str(e)}",
            operation="check_for_rankymcrankface",
        ) from e

    # Verify the JAR file exists and is readable
    if not os.path.exists(jar_path):
        raise ModelError(
            f"RankyMcRankFace.jar was not found at expected location: {jar_path}. "
            f"The download may have failed silently. "
            f"Please check network connectivity and try again.",
            operation="check_for_rankymcrankface",
        )

    if not os.access(jar_path, os.R_OK):
        raise ModelError(
            f"RankyMcRankFace.jar exists but is not readable: {jar_path}. "
            f"Please check file permissions.",
            operation="check_for_rankymcrankface",
        )

    return jar_path


def write_training_set(training_set: list[Judgment]) -> str:
    """Write training set judgments to a temporary file in RankLib format.

    Args:
        training_set: List of Judgment objects to write to file.

    Returns:
        str: Path to the temporary training file.

    Raises:
        ModelError: If the training set file cannot be written.

    Note:
        The file is created in the system temp directory and will be
        cleaned up automatically by the OS.
    """
    from .judgments import judgments_to_file

    tempdir = tempfile.gettempdir()
    train_path = os.path.join(tempdir, "training.txt")

    try:
        with open(train_path, "w") as out_f:
            judgments_to_file(out_f, training_set)
    except OSError as e:
        raise ModelError(
            f"Failed to write training set to file: {train_path}. "
            f"This may indicate:\n"
            f"  1. Insufficient disk space\n"
            f"  2. Permission denied writing to temp directory\n"
            f"  3. Temp directory is not accessible\n\n"
            f"Error details: {str(e)}",
            operation="write_training_set",
        ) from e
    except Exception as e:
        raise ModelError(
            f"Unexpected error while writing training set: {str(e)}",
            operation="write_training_set",
        ) from e

    # Verify the file was created and has content
    if not os.path.exists(train_path):
        raise ModelError(
            f"Training set file was not created: {train_path}. "
            f"File write operation may have failed silently.",
            operation="write_training_set",
        )

    return train_path


def train_model(
    training_set: list[Judgment],
    out: str,
    features: list[int] | None = None,
    kcv: int | None = None,
    ranker: int = 6,
    leafs: int | None = 10,
    trees: int | None = 50,
    frate: float = 1.0,
    shrinkage: float = 0.1,
    srate: float = 1.0,
    bag: int | None = 1,
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
        leafs: Number of leaves per tree (default: 10). If None, defaults to 10.
        trees: Number of trees in the ensemble (default: 50). If None, defaults to 50.
        frate: Feature rate - proportion of features considered at each split
            (default: 1.0, only used for RandomForest).
        shrinkage: Learning rate/shrinkage parameter (default: 0.1).
        srate: Sample rate - proportion of queries examined for each ensemble
            (default: 1.0, only used for RandomForest).
        bag: Bagging fraction (default: 1). If None, defaults to 1.
        metric2t: Metric to optimize during training (default: "DCG@10").

    Returns:
        RanklibResult: Object containing training logs and metrics.

    Raises:
        ValidationError: If the training set is empty, has no judgments with features,
            or has insufficient data (less than 2 judgments with features).
        ModelError: If RankLib execution fails, times out, or produces no training logs.

    Note:
        RandomForest-specific parameters (frate, srate) are only used when
        ranker=8. For LambdaMART (ranker=6), these parameters are ignored.

        The leafs, trees, and bag parameters accept None for defensive handling
        (e.g., when called from test wrappers), but will use their default values
        in such cases. In normal use, these should be positive integers.

        Training operations have a default timeout of 300 seconds (5 minutes) to
        prevent hanging indefinitely if RankLib becomes unresponsive. If training
        times out, a ModelError will be raised with suggestions for resolution.
    """

    # Validate training set before proceeding
    if not training_set:
        raise ValidationError(
            "Training set is empty. Cannot train a model without training data. "
            "Ensure you have created judgments and logged features before training."
        )

    # Check if training set has features
    judgments_with_features = [j for j in training_set if j.has_features()]
    if not judgments_with_features:
        raise ValidationError(
            "No judgments in the training set have features. "
            "Features must be logged before training. "
            "Use log_query() or FeatureLogger to log features for your judgments."
        )

    # Check if training set has sufficient data
    if len(judgments_with_features) < 2:
        raise ValidationError(
            f"Training set has only {len(judgments_with_features)} judgment(s) with features. "
            "At least 2 judgments with features are required for training."
        )

    # Check for consistent feature counts
    feature_counts = {len(j.features) for j in judgments_with_features if j.features}
    if len(feature_counts) > 1:
        logger.warning(
            f"Training set has inconsistent feature counts: {feature_counts}. "
            "This may cause training issues. Ensure all judgments have the same number of features."
        )

    # Check Java availability before proceeding
    java_path = shutil.which("java")
    if not java_path:
        raise ModelError(
            "Java is not installed or not found in PATH. "
            "RankLib requires Java to run. "
            "Please install Java (OpenJDK 11+ or Oracle JDK 11+) and ensure it's in your PATH.\n\n"
            "To verify Java installation:\n"
            "  - Run: java -version\n"
            "  - Check PATH environment variable includes Java bin directory",
            operation="train",
        )

    ranky_loc = check_for_rankymcrankface()
    training_set_path = write_training_set(training_set)
    # Use default values if parameters are None (can happen when called from test wrapper)
    trees_val = trees if trees is not None else 50
    bag_val = bag if bag is not None else 1
    leafs_val = leafs if leafs is not None else 10

    # Build command as a list to avoid shell injection vulnerabilities
    cmd = [
        "java",
        "-jar",
        ranky_loc,
        "-ranker",
        str(ranker),
        "-shrinkage",
        str(shrinkage),
        "-metric2t",
        metric2t,
        "-tree",
        str(trees_val),
        "-bag",
        str(bag_val),
        "-leaf",
        str(leafs_val),
        "-frate",
        str(frate),
        "-srate",
        str(srate),
        "-train",
        training_set_path,
        "-save",
        out,
    ]

    features_file = None
    if features is not None:
        features_file = os.path.join(tempfile.gettempdir(), "features.txt")
        try:
            with open(features_file, "w") as f:
                f.write("\n".join([str(feature) for feature in features]))
        except OSError as e:
            raise ModelError(
                f"Failed to write features file: {features_file}. "
                f"This may indicate:\n"
                f"  1. Insufficient disk space\n"
                f"  2. Permission denied writing to temp directory\n"
                f"  3. Temp directory is not accessible\n\n"
                f"Error details: {str(e)}",
                operation="train",
            ) from e
        except Exception as e:
            raise ModelError(
                f"Unexpected error while writing features file: {str(e)}",
                operation="train",
            ) from e
        cmd.extend(["-feature", features_file])

    if kcv is not None and kcv > 0:
        cmd.extend(["-kcv", str(kcv)])

    logger.info(f"Running RankLib command: {' '.join(cmd)}")

    # Default timeout: 5 minutes (300 seconds) for training operations
    # This prevents hanging indefinitely if RankLib gets stuck
    timeout_seconds = 300

    try:
        process_result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as e:
        raise ModelError(
            f"RankLib training timed out after {timeout_seconds} seconds. "
            f"This may indicate:\n"
            f"  1. Training data is too large for the current timeout\n"
            f"  2. RankLib is stuck or unresponsive\n"
            f"  3. System resources are constrained\n\n"
            f"Consider:\n"
            f"  - Reducing training set size\n"
            f"  - Using fewer trees or features\n"
            f"  - Checking system resources\n"
            f"  - Increasing timeout if needed for very large datasets",
            operation="train",
        ) from e
    except FileNotFoundError as e:
        # This should not happen if we checked Java availability, but handle it defensively
        raise ModelError(
            f"Java executable not found when running RankLib command. "
            f"This may indicate Java was removed or PATH changed during execution.\n\n"
            f"Command attempted: {' '.join(cmd)}\n"
            f"Error details: {str(e)}\n\n"
            f"To resolve:\n"
            f"  - Verify Java is installed: java -version\n"
            f"  - Check PATH includes Java bin directory",
            operation="train",
        ) from e
    except OSError as e:
        raise ModelError(
            f"OS error while running RankLib subprocess. "
            f"This may indicate:\n"
            f"  1. Insufficient system resources\n"
            f"  2. Process creation failed\n"
            f"  3. File descriptor limits exceeded\n\n"
            f"Command attempted: {' '.join(cmd)}\n"
            f"Error details: {str(e)}",
            operation="train",
        ) from e

    # Check if RankLib execution failed
    if process_result.returncode != 0:
        # Combine stderr and stdout for comprehensive error reporting
        # RankLib may output errors to either stream
        error_output = ""
        if process_result.stderr:
            error_output += f"STDERR:\n{process_result.stderr}\n"
        if process_result.stdout:
            error_output += f"STDOUT:\n{process_result.stdout}\n"

        # Convert to string if it's not already (handles Mock objects in tests)
        error_msg_str = str(error_output) if error_output else "Unknown error"

        # Extract error preview (first 1000 chars for better context)
        error_preview = error_msg_str[:1000] if error_msg_str else "Unknown error"

        # Try to extract the most relevant error line(s)
        error_lines = error_msg_str.split("\n")
        relevant_errors = [
            line.strip()
            for line in error_lines
            if any(
                keyword in line.lower()
                for keyword in ["error", "exception", "failed", "cannot", "invalid"]
            )
        ]
        if relevant_errors:
            error_summary = "\n".join(relevant_errors[:5])  # Top 5 relevant lines
        else:
            error_summary = error_preview

        # Provide more helpful error messages based on common issues
        error_msg_lower = error_msg_str.lower()

        if (
            "filenotfoundexception" in error_msg_lower
            or "no such file" in error_msg_lower
        ):
            raise ModelError(
                f"RankLib training failed: Could not find required file.\n\n"
                f"Return code: {process_result.returncode}\n"
                f"Error details:\n{error_summary}\n\n"
                f"This may indicate:\n"
                f"  - Training set file was not created properly\n"
                f"  - Features file path is incorrect\n"
                f"  - RankLib JAR file is missing\n\n"
                f"Full error output:\n{error_preview}",
                operation="train",
            )
        elif "parseexception" in error_msg_lower or "parse" in error_msg_lower:
            raise ModelError(
                f"RankLib training failed: Training data format error.\n\n"
                f"Return code: {process_result.returncode}\n"
                f"Error details:\n{error_summary}\n\n"
                f"This may indicate:\n"
                f"  - Training set is malformed or contains invalid data\n"
                f"  - Invalid feature values (NaN, infinity, or out of range)\n"
                f"  - Missing required fields in judgments\n"
                f"  - Incorrect RankLib format\n\n"
                f"Full error output:\n{error_preview}",
                operation="train",
            )
        elif (
            "outofmemoryerror" in error_msg_lower or "out of memory" in error_msg_lower
        ):
            raise ModelError(
                f"RankLib training failed: Out of memory.\n\n"
                f"Return code: {process_result.returncode}\n"
                f"Error details:\n{error_summary}\n\n"
                f"This may indicate:\n"
                f"  - Training set is too large for available memory\n"
                f"  - Too many trees or features\n"
                f"  - Insufficient Java heap space\n\n"
                f"Consider:\n"
                f"  - Reducing training set size\n"
                f"  - Using fewer trees or features\n"
                f"  - Increasing Java heap size (-Xmx flag)\n\n"
                f"Full error output:\n{error_preview}",
                operation="train",
            )
        elif len(training_set) == 0:
            raise ModelError(
                f"RankLib training failed: Empty training set.\n\n"
                f"Return code: {process_result.returncode}\n"
                f"Error details:\n{error_summary}\n\n"
                f"Ensure you have:\n"
                f"  1. Created judgments\n"
                f"  2. Logged features using log_query() or FeatureLogger\n"
                f"  3. Passed the judgments with features to train()\n\n"
                f"Full error output:\n{error_preview}",
                operation="train",
            )
        else:
            # Generic error with comprehensive information
            raise ModelError(
                f"RankLib training failed with return code {process_result.returncode}.\n\n"
                f"Error details:\n{error_summary}\n\n"
                f"Common causes:\n"
                f"  - Invalid training data or missing features\n"
                f"  - RankLib configuration issues (invalid parameters)\n"
                f"  - Insufficient training data\n"
                f"  - Java/RankLib runtime errors\n\n"
                f"Full error output:\n{error_preview}",
                operation="train",
            )

    # Parse training logs
    parsed_result = parse_training_log(process_result.stdout)

    # If no training logs were parsed, raise an error
    if len(parsed_result.trainingLogs) == 0:
        error_context = (
            "RankLib did not produce any training logs. "
            "This may indicate an error in the training data or RankLib execution. "
            "Common causes:\n"
            "  1. Empty or invalid training set\n"
            "  2. Missing or invalid features in judgments\n"
            "  3. Insufficient training data (need at least 2 judgments with features)\n"
            "  4. RankLib configuration issues (invalid parameters)"
        )
        if process_result.stderr:
            error_msg = process_result.stderr[:500]
            raise ModelError(
                f"{error_context}\n\nStderr output: {error_msg}",
                operation="train",
            )
        elif process_result.stdout:
            stdout_preview = (
                process_result.stdout[:500] if process_result.stdout else "No output"
            )
            raise ModelError(
                f"{error_context}\n\nStdout output: {stdout_preview}",
                operation="train",
            )
        else:
            # Even without stderr, no training logs is an error condition
            raise ModelError(error_context, operation="train")

    # Verify model file was created (only when not using KCV, as KCV doesn't save models)
    if kcv is None or kcv == 0:
        if not os.path.exists(out):
            error_context = (
                f"RankLib training completed but model file was not created: {out}. "
                f"This may indicate:\n"
                f"  1. RankLib encountered an error during model saving\n"
                f"  2. Insufficient disk space\n"
                f"  3. Permission denied writing to output location\n"
                f"  4. RankLib process was interrupted\n\n"
            )
            if process_result.stderr:
                error_msg = process_result.stderr[:500]
                raise ModelError(
                    f"{error_context}Stderr output: {error_msg}",
                    operation="train",
                )
            elif process_result.stdout:
                stdout_preview = (
                    process_result.stdout[:500]
                    if process_result.stdout
                    else "No output"
                )
                raise ModelError(
                    f"{error_context}Stdout output: {stdout_preview}",
                    operation="train",
                )
            else:
                raise ModelError(
                    f"{error_context}No output from RankLib process.",
                    operation="train",
                )

        # Verify the model file has content
        try:
            if os.path.getsize(out) == 0:
                raise ModelError(
                    f"Model file was created but is empty: {out}. "
                    f"This indicates RankLib did not write a valid model. "
                    f"Please check training logs for errors.",
                    operation="train",
                )
        except OSError as e:
            raise ModelError(
                f"Failed to verify model file: {out}. Error details: {str(e)}",
                operation="train",
            ) from e

    return parsed_result


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

    Raises:
        ModelError: If the model file doesn't exist, is empty, or model submission fails.
    """
    import os

    # Validate model file exists and has content
    if not os.path.exists(model_file):
        raise ModelError(
            f"Model file not found: {model_file}. "
            f"This indicates RankLib training did not produce a model file. "
            f"Please check training logs for errors.",
            operation="save_model",
            model_name=model_name,
        )

    with open(model_file) as src:
        definition = src.read().strip()

    if not definition:
        raise ModelError(
            f"Model file is empty: {model_file}. "
            f"This indicates RankLib training did not produce a valid model. "
            f"Please check training logs for errors.",
            operation="save_model",
            model_name=model_name,
        )

    # Submit the model (this includes verification that the model was created)
    client.submit_ranklib_model(feature_set, index, model_name, definition)


def _validate_training_prerequisites(
    client: BaseClient,
    feature_set: str,
    index: str,
    training_set: list[Judgment],
) -> None:
    """Validate that prerequisites for training are met.

    Checks that:
    - Feature set exists and is accessible
    - Training set has data with features
    - Index exists (implicitly checked via feature set)

    Args:
        client: Search client instance.
        feature_set: Name of the feature set to validate.
        index: Index name (for error messages).
        training_set: Training set to validate.

    Raises:
        RuntimeError: If prerequisites are not met, with helpful error messages.
        ValueError: If training set is invalid.
    """
    # Validate feature set exists
    try:
        client.feature_set(index=index, name=feature_set)
        logger.debug(f"Feature set '{feature_set}' validated successfully")
    except RuntimeError as e:
        raise ModelError(
            f"Cannot train model: Feature set '{feature_set}' not found or not accessible. "
            f"This usually means:\n"
            f"  1. The feature set hasn't been created yet - run client.create_featureset() first\n"
            f"  2. The feature set was created in a different index\n"
            f"  3. There was an error creating the feature set\n\n"
            f"Original error: {e}\n\n"
            f"To fix: Ensure you run cells in this order:\n"
            f"  1. client.create_index('{index}')\n"
            f"  2. client.create_featureset(index='{index}', name='{feature_set}', ftr_config=...)\n"
            f"  3. Log features using log_query() or FeatureLogger\n"
            f"  4. Train model using train()",
            operation="train",
            context={"feature_set": feature_set, "index": index},
        ) from e

    # Validate training set
    if not training_set:
        raise ValidationError(
            "Cannot train model: Training set is empty. "
            "Ensure you have:\n"
            "  1. Created judgments\n"
            "  2. Logged features using log_query() or FeatureLogger\n"
            "  3. Passed the judgments with features to train()"
        )

    judgments_with_features = [j for j in training_set if j.has_features()]
    if not judgments_with_features:
        raise ValidationError(
            "Cannot train model: No judgments in the training set have features. "
            "Features must be logged before training. "
            "Use log_query() or FeatureLogger.log_for_qid() to log features for your judgments."
        )


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
        RuntimeError: If the feature set is not found or training fails or produces no training logs.
        ValueError: If the training set is empty or has no judgments with features.
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

    # Validate prerequisites before training
    _validate_training_prerequisites(client, feature_set, index, training_set)

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
        raise ModelError(
            "Training failed: RankLib did not produce any training logs. This may indicate an error in the training data or RankLib execution.",
            operation="train",
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
        raise ValidationError("features parameter is required for feature_search")

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
