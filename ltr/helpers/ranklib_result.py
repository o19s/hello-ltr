"""RankLib training result parsing and data structures.

This module provides classes and functions for parsing RankLib training output
and representing training results, including cross-validation results.
"""

import re


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

    def __init__(self, trainingLogs, foldResults, kcvTestAvg, kcvTrainAvg):
        """Initialize a RanklibResult.

        Args:
            trainingLogs: List of TrainingLog objects, one per training run.
            foldResults: List of FoldResult objects, one per cross-validation fold.
            kcvTestAvg: Average test metric across all folds (None if not KCV).
            kcvTrainAvg: Average training metric across all folds (None if not KCV).
        """
        self.trainingLogs = trainingLogs
        self.foldResults = foldResults
        self.kcvTrainAvg = kcvTrainAvg
        self.kcvTestAvg = kcvTestAvg


class TrainingLog:
    """Log of a single RankLib training run.

    Attributes:
        impacts: Dictionary mapping feature IDs to error reduction values.
        rounds: List of metric values for each training round.
        trainMetricName: Name of the training metric (e.g., "DCG@10").
        trainMetricVal: Final training metric value.
    """

    def __init__(self, rounds, impacts, trainMetricName, trainMetricVal):
        """Initialize a TrainingLog.

        Args:
            rounds: List of metric values for each training round.
            impacts: Dictionary mapping feature IDs to error reduction values.
            trainMetricName: Name of the training metric (e.g., "DCG@10").
            trainMetricVal: Final training metric value.
        """
        self.impacts = impacts
        self.rounds = rounds
        self.trainMetricName = trainMetricName
        self.trainMetricVal = trainMetricVal

    def metric(self):
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

    def __init__(self, foldId, trainMetric, testMetric):
        """Initialize a FoldResult.

        Args:
            foldId: Fold number/identifier.
            trainMetric: Training metric value for this fold.
            testMetric: Test metric value for this fold.
        """
        self.foldNum = foldId
        self.trainMetric = trainMetric
        self.testMetric = testMetric


impactRe = re.compile(r" Feature (\d+) reduced error (.*)")
roundsRe = re.compile(r"(\d+)\s+\| (\d+)")
foldsRe = re.compile(r"^Fold (\d+)\s+\|(.*)\|(.*)")
avgRe = re.compile(r"^Avg.\s+\|(.*)\|(.*)")
trainMetricRe = re.compile(r"(.*@.*) on training data: (.*)")


def parse_training_log(rawResult):
    """Parse raw RankLib training output into structured result objects.

    Extracts feature impacts, training rounds, cross-validation fold results,
    and average metrics from RankLib's text output.

    Args:
        rawResult: Raw text output from RankLib training command.

    Returns:
        RanklibResult: Parsed result object containing:
            - trainingLogs: List of TrainingLog objects
            - foldResults: List of FoldResult objects (empty if not KCV)
            - kcvTestAvg: Average test metric (None if not KCV)
            - kcvTrainAvg: Average training metric (None if not KCV)
    """
    lines = rawResult.split("\n")
    # Fold 1	|   0.9396	|  0.8764
    train = False
    logs = []
    folds = []
    impacts = {}
    rounds = []
    trainMetricName = None
    trainMetricVal = 0.0
    kcvTestAvg = kcvTrainAvg = None
    for line in lines:
        if "Training starts..." in line:
            if train:
                log = TrainingLog(
                    rounds=rounds,
                    impacts=impacts,
                    trainMetricName=trainMetricName,
                    trainMetricVal=trainMetricVal,
                )
                logs.append(log)
            impacts = {}
            rounds = []
            train = True

        if train:
            m = re.match(impactRe, line)
            if m:
                ftrId = m.group(1)
                error = float(m.group(2))
                impacts[ftrId] = error
            m = re.match(roundsRe, line)
            if m:
                values = line.split("|")
                metricTrain = float(values[1])
                rounds.append(metricTrain)
            m = re.match(trainMetricRe, line)
            if m:
                trainMetricVal = float(m.group(2))
                trainMetricName = m.group(1)

        m = re.match(foldsRe, line)
        if m:
            foldId = m.group(1)
            trainMetric = float(m.group(2))
            testMetric = float(m.group(3))
            folds.append(
                FoldResult(
                    foldId=foldId, testMetric=testMetric, trainMetric=trainMetric
                )
            )
        m = re.match(avgRe, line)
        if m:
            kcvTrainAvg = float(m.group(1))
            kcvTestAvg = float(m.group(2))

    if train:
        log = TrainingLog(
            rounds=rounds,
            impacts=impacts,
            trainMetricName=trainMetricName,
            trainMetricVal=trainMetricVal,
        )
        logs.append(log)

    return RanklibResult(
        trainingLogs=logs,
        foldResults=folds,
        kcvTrainAvg=kcvTrainAvg,
        kcvTestAvg=kcvTestAvg,
    )
