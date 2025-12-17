"""RankLib training result parsing and data structures.

This module provides classes and functions for parsing RankLib training output
and representing training results, including cross-validation results.
"""

from __future__ import annotations

import re

from ltr.types import FeatureImpactMap


class RanklibResult:
    """Result of RankLib training operation.

    Represents either a single training operation (where trainingLogs contains
    a single item) or k-fold cross-validation (where foldResults and kcv
    metrics are populated with results for each fold).

    Attributes:
        trainingLogs: List of TrainingLog objects, one per training run.
        foldResults: List of FoldResult objects, one per cross-validation fold.
        kcvTestAvg: Average test metric across all folds (None if not KCV).
        kcvTrainAvg: Average training metric across all folds (None if not KCV).
    """

    def __init__(
        self,
        training_logs: list[TrainingLog],
        fold_results: list[FoldResult],
        kcv_test_avg: float | None,
        kcv_train_avg: float | None,
    ) -> None:
        """Initialize a RanklibResult.

        Args:
            training_logs: List of TrainingLog objects, one per training run.
            fold_results: List of FoldResult objects, one per cross-validation fold.
            kcv_test_avg: Average test metric across all folds (None if not KCV).
            kcv_train_avg: Average training metric across all folds (None if not KCV).
        """
        self.trainingLogs: list[TrainingLog] = training_logs
        self.foldResults: list[FoldResult] = fold_results
        self.kcvTrainAvg: float | None = kcv_train_avg
        self.kcvTestAvg: float | None = kcv_test_avg


class TrainingLog:
    """Log of a single RankLib training run.

    Attributes:
        impacts: Dictionary mapping feature IDs to error reduction values.
        rounds: List of metric values for each training round.
        trainMetricName: Name of the training metric (e.g., "DCG@10").
        trainMetricVal: Final training metric value.
    """

    def __init__(
        self,
        rounds: list[float],
        impacts: FeatureImpactMap,
        train_metric_name: str | None,
        train_metric_val: float,
    ) -> None:
        """Initialize a TrainingLog.

        Args:
            rounds: List of metric values for each training round.
            impacts: Dictionary mapping feature IDs to error reduction values.
            train_metric_name: Name of the training metric (e.g., "DCG@10").
            train_metric_val: Final training metric value.
        """
        self.impacts: FeatureImpactMap = impacts
        self.rounds: list[float] = rounds
        self.trainMetricName: str | None = train_metric_name
        self.trainMetricVal: float = train_metric_val

    def metric(self) -> float:
        """Get the training metric value.

        Returns:
            float: Training metric value, preferring trainMetricVal if available,
                otherwise the last round value, or 0 if no rounds.
        """
        if self.trainMetricName is not None:
            return self.trainMetricVal
        if len(self.rounds) > 0:
            return self.rounds[-1]
        else:
            return 0


class FoldResult:
    """Result of a single cross-validation fold.

    Attributes:
        foldNum: Fold number/identifier.
        trainMetric: Training metric value for this fold.
        testMetric: Test metric value for this fold.
    """

    def __init__(self, fold_id: str, train_metric: float, test_metric: float) -> None:
        """Initialize a FoldResult.

        Args:
            fold_id: Fold number/identifier.
            train_metric: Training metric value for this fold.
            test_metric: Test metric value for this fold.
        """
        self.foldNum: str = fold_id
        self.trainMetric: float = train_metric
        self.testMetric: float = test_metric


IMPACT_RE = re.compile(r" Feature (\d+) reduced error (.*)")
ROUNDS_RE = re.compile(r"(\d+)\s+\| (\d+)")
FOLDS_RE = re.compile(r"^Fold (\d+)\s+\|(.*)\|(.*)")
AVG_RE = re.compile(r"^Avg.\s+\|(.*)\|(.*)")
TRAIN_METRIC_RE = re.compile(r"(.*@.*) on training data: (.*)")


def parse_training_log(raw_result: str) -> RanklibResult:
    """Parse raw RankLib training output into structured result objects.

    Extracts feature impacts, training rounds, cross-validation fold results,
    and average metrics from RankLib's text output.

    Args:
        raw_result: Raw text output from RankLib training command.

    Returns:
        RanklibResult: Parsed result object containing:
            - trainingLogs: List of TrainingLog objects
            - foldResults: List of FoldResult objects (empty if not KCV)
            - kcvTestAvg: Average test metric (None if not KCV)
            - kcvTrainAvg: Average training metric (None if not KCV)
    """
    lines = raw_result.split("\n")
    # Fold 1	|   0.9396	|  0.8764
    train = False
    logs = []
    folds = []
    impacts = {}
    rounds = []
    train_metric_name = None
    train_metric_val = 0.0
    kcv_test_avg = kcv_train_avg = None
    for line in lines:
        if "Training starts..." in line:
            if train:
                log = TrainingLog(
                    rounds=rounds,
                    impacts=impacts,
                    train_metric_name=train_metric_name,
                    train_metric_val=train_metric_val,
                )
                logs.append(log)
            impacts = {}
            rounds = []
            train = True

        if train:
            m = re.match(IMPACT_RE, line)
            if m:
                ftr_id = m.group(1)
                error = float(m.group(2))
                impacts[ftr_id] = error
            m = re.match(ROUNDS_RE, line)
            if m:
                values = line.split("|")
                metric_train = float(values[1])
                rounds.append(metric_train)
            m = re.match(TRAIN_METRIC_RE, line)
            if m:
                train_metric_val = float(m.group(2))
                train_metric_name = m.group(1)

        m = re.match(FOLDS_RE, line)
        if m:
            fold_id = m.group(1)
            train_metric = float(m.group(2))
            test_metric = float(m.group(3))
            folds.append(
                FoldResult(
                    fold_id=fold_id, train_metric=train_metric, test_metric=test_metric
                )
            )
        m = re.match(AVG_RE, line)
        if m:
            kcv_train_avg = float(m.group(1))
            kcv_test_avg = float(m.group(2))

    if train:
        log = TrainingLog(
            rounds=rounds,
            impacts=impacts,
            train_metric_name=train_metric_name,
            train_metric_val=train_metric_val,
        )
        logs.append(log)

    return RanklibResult(
        training_logs=logs,
        fold_results=folds,
        kcv_test_avg=kcv_test_avg,
        kcv_train_avg=kcv_train_avg,
    )
