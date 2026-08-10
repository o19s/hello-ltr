"""MART (Multiple Additive Regression Trees) model analysis.

This module provides functionality for loading and analyzing MART models from
RankLib XML output, including identifying prediction errors ("whoopsies") and
analyzing model behavior.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from typing import Any

from ltr.judgments import Judgment, _judgments_by_qid
from ltr.logger import get_logger
from ltr.types import FeatureList

logger = get_logger(__name__)


def fold_whoopsies(
    whoopsies1: list[Whoopsie], whoopsies2: list[Whoopsie]
) -> list[Whoopsie]:
    """Merge two lists of whoopsies, sorted by query and magnitude.

    Combines whoopsies2 into whoopsies1 and sorts the result first by query ID,
    then by descending magnitude (largest errors first).

    Args:
        whoopsies1: First list of whoopsie objects (will be modified).
        whoopsies2: Second list of whoopsie objects to merge in.

    Returns:
        list: Merged and sorted list of whoopsies (same reference as whoopsies1).
    """
    whoopsies1.extend(whoopsies2)
    whoopsies1.sort(key=lambda x: (x.qid, 1000 - x.magnitude()))
    return whoopsies1


def dedup_whoopsies(sorted_whoopsies: list[Whoopsie]) -> list[Whoopsie]:
    """Deduplicate whoopsies, keeping only the worst error per query.

    Takes whoopsies sorted first by query ID, then by magnitude, and returns
    only the worst (highest magnitude) whoopsie for each query.

    Args:
        sorted_whoopsies: List of whoopsie objects, sorted by qid then magnitude.

    Returns:
        list: List containing only the worst whoopsie per query.
    """
    merged_whoopsies = iter(sorted_whoopsies)

    whoopsies = []
    whoopsie = None
    last_qid = -1
    try:
        while True:
            # Read ahead to next query
            while whoopsie is None or last_qid == whoopsie.qid:
                whoopsie = next(merged_whoopsies)
            whoopsies.append(whoopsie)
            last_qid = whoopsie.qid
    except StopIteration:
        pass
    return whoopsies


class MARTModel:
    """MART (Multiple Additive Regression Trees) model parser and analyzer.

    Parses RankLib XML model output and provides methods for making predictions
    and analyzing model behavior, including identifying prediction errors.

    Attributes:
        trees: List of tree structures parsed from RankLib XML.
        features: List of feature dictionaries mapping indices to names.
    """

    def __init__(self, ranklib_xml: str, features: FeatureList) -> None:
        """Create a MART model from RankLib XML output.

        Args:
            ranklib_xml: String containing RankLib XML model output.
            features: Array of named features where the 0th item corresponds to
                RankLib feature 1. Format: [{'name': 'release_date'}, ...]
        """
        # Clean up header
        valid = False
        lines_split = ranklib_xml.split("\n")
        if lines_split[0] == "## LambdaMART":
            logger.debug("Processing LambdaMART model")
            valid = True
        if (
            lines_split[0] == "## Random Forests"
            and lines_split[1] == "## No. of bags = 1"
        ):
            logger.debug("Processing Random Forest model with 1 bag")
            valid = True

        if not valid:
            raise ValueError(
                "Whoopsies only support LambdaMART of Random Forest of bags=1"
            )

        header_at = 0
        for line in lines_split:
            if len(line) > 0 and line[0] == "#":
                header_at += 1
            else:
                break

        logger.debug(f"Header at line {header_at}")
        valid_xml = "\n".join(ranklib_xml.split("\n")[header_at:])
        lambda_model = ET.fromstring(valid_xml)

        # List of tuples (weight, root split)
        self.trees: list[tuple[float, Split]] = []
        for node in lambda_model:
            self.trees.append((float(node.attrib["weight"]), Split(node[0], features)))

    def __str__(self) -> str:
        """Generate string representation of the model.

        Returns:
            str: Human-readable representation of all trees in the ensemble,
                with each tree separated by blank lines.
        """
        r_val = ""
        for tree in self.trees:
            weight = tree[0]
            tree = tree[1]
            r_val += tree.tree_string(weight=weight)
            r_val += "\n\n"
        return r_val

    def whoopsies(self) -> dict[int, QueryWhoopsie]:
        """Identify the most glaring query-document inconsistencies after evaluation.

        Analyzes prediction errors ("whoopsies") across the entire ensemble,
        identifying queries where the model makes inconsistent predictions
        for documents with different relevance grades.

        Returns:
            dict: Dictionary mapping query IDs to QueryWhoopsie objects,
                containing aggregated error information per query.

        Note:
            Requires eval() to be called first with judgments.
        """
        whoops_queries: dict[int, QueryWhoopsie] = {}
        per_tree_whoops: list[Whoopsie | None] = []
        for _ in self.trees:
            per_tree_whoops.append(None)
        for tree_no, tree in enumerate(self.trees):
            tree_whoopsies = tree[1].whoopsies()

            for whoops in dedup_whoopsies(tree_whoopsies):
                if whoops.qid not in whoops_queries:
                    whoops_queries[whoops.qid] = QueryWhoopsie(
                        qid=whoops.qid,
                        total_magnitude=0,
                        count=0,
                        max_grade=0,
                        min_grade=0,
                        per_tree_whoops=per_tree_whoops,
                    )

                whoops_queries[whoops.qid].count += 1
                whoops_queries[whoops.qid].totalMagnitude += whoops.magnitude()
                whoops_queries[whoops.qid].minGrade = whoops.minGrade
                whoops_queries[whoops.qid].maxGrade = whoops.maxGrade
                whoops_queries[whoops.qid].perTreeWhoops[tree_no] = whoops

        return whoops_queries

    def eval(self, judgments: Iterable[Judgment]) -> None:
        """Evaluate the model against a set of judgments.

        Runs judgments through each tree in the ensemble and collects
        evaluation statistics for analysis.

        Args:
            judgments: List of Judgment objects to evaluate.
        """
        for tree in self.trees:
            # weight = tree[0]
            tree = tree[1]
            tree.eval(judgments)


class QueryWhoopsie:
    """Aggregated prediction errors for a single query across all trees.

    Attributes:
        qid: Query ID.
        count: Number of whoopsies found for this query.
        totalMagnitude: Sum of magnitudes of all whoopsies for this query.
        maxGrade: Maximum relevance grade in the judgments for this query.
        minGrade: Minimum relevance grade in the judgments for this query.
        perTreeWhoops: List of Whoopsie objects, one per tree (None if no whoopsie for that tree).
    """

    def __init__(
        self,
        qid: int,
        total_magnitude: float,
        count: int,
        max_grade: int,
        min_grade: int,
        per_tree_whoops: list[Whoopsie | None],
    ) -> None:
        """Initialize a QueryWhoopsie.

        Args:
            qid: Query ID.
            total_magnitude: Sum of magnitudes of all whoopsies for this query.
            count: Number of whoopsies found for this query.
            max_grade: Maximum relevance grade in the judgments for this query.
            min_grade: Minimum relevance grade in the judgments for this query.
            per_tree_whoops: List of Whoopsie objects, one per tree (None if no whoopsie for that tree).
        """
        self.qid: int = qid
        self.count: int = count
        self.totalMagnitude: float = total_magnitude
        self.maxGrade: int = max_grade
        self.minGrade: int = min_grade
        self.perTreeWhoops: list[Whoopsie | None] = per_tree_whoops

    def per_tree_report(self) -> str:
        """Generate a summary report of whoopsies per tree.

        Returns:
            str: Semicolon-separated string describing whoopsies for each tree,
                or "<None>" if no whoopsie exists for that tree.
        """
        tree_summary = []
        for tree_no, whoops in enumerate(self.perTreeWhoops):
            if whoops is None:
                tree_summary.append("<None>")
            else:
                tree_summary.append(
                    f"tree:{tree_no}=>{whoops.minGrade}({whoops.minGradeDocId})-{whoops.maxGrade}({whoops.maxGradeDocId})"
                )
        return ";".join(tree_summary)


class Whoopsie:
    """Represents a prediction error where documents with different grades receive the same score.

    A whoopsie occurs when a tree node (leaf) contains judgments with different
    relevance grades, indicating the model is making inconsistent predictions.

    Attributes:
        qid: Query ID.
        judgList: List of Judgment objects that ended up in this node.
        minGrade: Minimum relevance grade in judgList.
        maxGrade: Maximum relevance grade in judgList.
        minGradeDocId: Document ID with the minimum grade.
        maxGradeDocId: Document ID with the maximum grade.
        output: Tree node output value (predicted score).
    """

    def __init__(
        self,
        qid: int,
        judg_list: list[Judgment],
        min_grade: int,
        max_grade: int,
        min_grade_doc_id: str,
        max_grade_doc_id: str,
        output: float,
    ) -> None:
        """Initialize a Whoopsie.

        Args:
            qid: Query ID.
            judg_list: List of Judgment objects that ended up in this node.
            min_grade: Minimum relevance grade in judg_list.
            max_grade: Maximum relevance grade in judg_list.
            min_grade_doc_id: Document ID with the minimum grade.
            max_grade_doc_id: Document ID with the maximum grade.
            output: Tree node output value (predicted score).
        """
        self.qid: int = qid
        self.judgList: list[Judgment] = judg_list
        self.minGrade: int = min_grade
        self.maxGrade: int = max_grade
        self.minGradeDocId: str = min_grade_doc_id
        self.maxGradeDocId: str = max_grade_doc_id
        self.output: float = output

    def magnitude(self) -> float:
        """Calculate the magnitude of the prediction error.

        Returns:
            float: Difference between maxGrade and minGrade, representing
                the severity of the inconsistency.
        """
        return self.maxGrade - self.minGrade


class EvalReport:
    """Evaluation report for a tree leaf node.

    Contains statistics about judgments that ended up in a particular leaf,
    including identified prediction errors (whoopsies).

    Attributes:
        split: Split object representing the leaf node.
        count: Number of judgments that ended up in this leaf.
        whoopsies: List of Whoopsie objects representing prediction errors.
    """

    def __init__(self, split: Split) -> None:
        """Initialize an EvalReport for a leaf node.

        Args:
            split: Split object representing a leaf node (must have output set).

        Raises:
            ValueError: If split is not a leaf node (output is None).
        """
        if split.output is None:
            raise ValueError("Split not a leaf")

        self.split: Split = split
        self.count: int = len(split.evals)
        self.whoopsies: list[Whoopsie] = []

        self.compute_whoopsies()

    def compute_whoopsies(self) -> None:
        """Compute prediction errors (whoopsies) for this leaf node.

        Identifies queries where documents with different relevance grades
        ended up in the same leaf node, indicating inconsistent predictions.
        Results are sorted by magnitude (largest errors first).
        """
        judgments_by_qid = _judgments_by_qid(self.split.evals)
        report = []
        for qid, judg_list in judgments_by_qid.items():
            if len(judg_list) > 1:
                min_grade_doc_id = judg_list[0].docId
                max_grade_doc_id = judg_list[0].docId
                min_grade = max_grade = judg_list[0].grade
                for judg in judg_list:
                    if judg.grade < min_grade:
                        min_grade = judg.grade
                        min_grade_doc_id = judg.docId
                    if judg.grade > max_grade:
                        max_grade = judg.grade
                        max_grade_doc_id = judg.docId
                if min_grade != max_grade:
                    if self.split.output is None:
                        raise ValueError("Cannot create Whoopsie: split.output is None")
                    report.append(
                        Whoopsie(
                            qid=qid,
                            judg_list=judg_list,
                            min_grade=min_grade,
                            max_grade=max_grade,
                            min_grade_doc_id=min_grade_doc_id,
                            max_grade_doc_id=max_grade_doc_id,
                            output=self.split.output,
                        )
                    )
        report.sort(key=lambda x: x.maxGrade - x.minGrade, reverse=True)
        self.whoopsies = report

    def __str__(self) -> str:
        """Generate string representation of the evaluation report.

        Returns:
            str: Format "{count}/{whoopsie_count}/{whoopsie_details}" where
                count is the number of judgments, whoopsie_count is the number
                of whoopsies found, and whoopsie_details is a semicolon-separated
                list of whoopsie information.
        """
        report_str = ";".join(
            [
                f"qid:{report.qid}:{report.minGrade}({report.minGradeDocId})-{report.maxGrade}({report.maxGradeDocId})"
                for report in self.whoopsies
            ]
        )
        return f"{self.count}/{len(self.whoopsies)}/{report_str}"

    def __repr__(self) -> str:
        """Generate string representation for debugging.

        Returns:
            str: Same as __str__().
        """
        return str(self)


class Split:
    """Represents a node in a decision tree (either a split node or leaf node).

    Attributes:
        feature: Name of the feature used for splitting (None for leaf nodes).
        featureOrd: One-based feature ordinal in the RankLib model (None for leaf nodes).
        featureIdx: Zero-based feature index for lookups (None for leaf nodes).
        threshold: Threshold value for splitting (None for leaf nodes).
        value: Node value (unused, kept for compatibility).
        left: Left child Split node (None for leaf nodes).
        right: Right child Split node (None for leaf nodes).
        output: Output value for leaf nodes (None for split nodes).
        evalReport: EvalReport object containing evaluation statistics (None until eval() is called).
        evals: List of judgments that ended up in this node during evaluation.
    """

    def __init__(self, split_el: ET.Element, features: FeatureList) -> None:
        """Initialize a Split node from XML element.

        Args:
            split_el: XML ElementTree element representing a tree node.
            features: List of feature dictionaries mapping indices to names.
        """
        self.feature: str | None = None  # Name of the feature
        self.featureOrd: int | None = (
            None  # ONE BASED, feature ord in the ranklib model
        )
        self.featureIdx: int | None = None  # Zero BASED - use for lookups
        self.threshold: float | None = None
        self.value: Any | None = None
        self.left: Split | None = None
        self.right: Split | None = None
        self.output: float | None = None
        self.evalReport: EvalReport | None = None

        self.evals: list[Judgment] = []

        for el in split_el:
            if el.tag == "feature":
                self.featureOrd = int(el.text.strip())
                self.featureIdx = self.featureOrd - 1
                self.feature = features[self.featureIdx]["name"]
            elif el.tag == "threshold":
                self.threshold = float(el.text.strip())
            elif el.tag == "split" and "pos" in el.attrib:
                if el.attrib["pos"] == "right":
                    self.right = Split(split_el=el, features=features)
                elif el.attrib["pos"] == "left":
                    self.left = Split(split_el=el, features=features)
                else:
                    raise ValueError(
                        "Unrecognized Split Pos {}".format(el.attrib["pos"])
                    )
            elif el.tag == "output":
                self.output = float(el.text.strip())

    def clear_evals(self) -> None:
        """Clear evaluation state from this node and all descendants.

        Resets evals list and evalReport to None, allowing the tree
        to be re-evaluated with new judgments.
        """
        if self.output:
            self.evals = []
            self.evalReport = None
        elif self.right:
            self.right.clear_evals()
        elif self.left:
            self.left.clear_evals()

    def _eval_append(self, judgment: Judgment) -> None:
        """Recursively evaluate a judgment through the tree.

        Traverses the tree based on feature values, placing the judgment
        in the appropriate leaf node for analysis purposes.

        Args:
            judgment: Judgment object with a features attribute containing
                a list of floating point numbers where the 0th element
                corresponds to RankLib's 1st feature.
        """
        if self.output:
            self.evals.append(judgment)
            return

        ftr_to_eval = self.featureIdx
        if ftr_to_eval is None:
            raise ValueError("Cannot evaluate judgment: featureIdx is None")
        if self.threshold is None:
            raise ValueError("Cannot evaluate judgment: threshold is None")
        feature_val = judgment.features[ftr_to_eval]
        if feature_val > self.threshold:
            assert self.right is not None
            self.right._eval_append(judgment)
        else:
            assert self.left is not None
            self.left._eval_append(judgment)

    def _compute_eval_stats(self) -> None:
        """Compute evaluation statistics for this node and all descendants.

        For leaf nodes, creates an EvalReport. For split nodes, recursively
        computes stats for child nodes.
        """
        if self.output:
            self.evalReport = EvalReport(self)
            return
        else:
            assert self.right is not None
            assert self.left is not None
            self.right._compute_eval_stats()
            self.left._compute_eval_stats()

    def eval(self, judgments: Iterable[Judgment]) -> None:
        """Evaluate a set of judgments through this tree.

        Clears previous evaluation state, runs all judgments through the tree,
        and computes evaluation statistics.

        Args:
            judgments: List of Judgment objects to evaluate.
        """
        self.clear_evals()
        for judgment in judgments:
            self._eval_append(judgment)
        self._compute_eval_stats()

    def whoopsies(self) -> list[Whoopsie]:
        """Get all prediction errors (whoopsies) from this node and descendants.

        Returns:
            list: List of Whoopsie objects, ordered first by query ID,
                then by magnitude descending (e.g., [(1,4), (1,3), (2,2), (2,0), ...]).

        Note:
            For leaf nodes, returns whoopsies from this node's evalReport.
            For split nodes, returns merged whoopsies from child nodes.
        """
        if self.output:
            if self.evalReport is None:
                return []
            return self.evalReport.whoopsies
        else:
            assert self.right is not None
            assert self.left is not None
            r_whoopsies = self.right.whoopsies()
            l_whoopsies = self.left.whoopsies()
            return fold_whoopsies(l_whoopsies, r_whoopsies)

    def tree_string(self, weight: float = 1.0, nest_level: int = 0) -> str:
        """Generate a human-readable string representation of the tree.

        Args:
            weight: Weight multiplier for leaf output values (default: 1.0).
            nest_level: Current nesting level for indentation (default: 0).

        Returns:
            str: Python-like code representation of the decision tree.

        Note:
            Includes evaluation report information if available.
        """

        def idt(nest_level: int) -> str:
            """Generate indentation string for a given nesting level.

            Args:
                nest_level: Nesting level.

            Returns:
                str: Indentation string (2 spaces per level).
            """
            # return ("%s" % nest_level) * 2 * nest_level
            return (" ") * 2 * nest_level

        r_val = ""
        if self.feature:
            r_val += idt(nest_level)
            r_val += f"if {self.feature} > {self.threshold}:\n"
            assert self.right is not None
            assert self.left is not None
            if self.right:
                r_val += self.right.tree_string(
                    weight=weight, nest_level=nest_level + 1
                )
            if self.left:
                r_val += idt(nest_level)
                r_val += "else:\n"
                r_val += self.left.tree_string(weight=weight, nest_level=nest_level + 1)
        if self.output:
            r_val += idt(nest_level)
            r_val += f"<= {self.output * weight:.4f}"
            if self.evalReport:
                r_val += f"({self.evalReport})"
            r_val += "\n"
        return r_val


def dump_model(model_name: str, features: FeatureList) -> None:
    """Print a model in Python-like code format.

    Loads a RankLib model from disk and prints a human-readable representation
    of all trees in the ensemble.

    Args:
        model_name: Name of the model. The model file will be read from
            data/{model_name}_model.txt.
        features: List of feature dictionaries, where the 0th item corresponds
            to RankLib feature 1. Each feature must have a 'name' parameter.
    """
    with open(f"data/{model_name}_model.txt", encoding="utf-8") as f:
        ensemble_xml = f.read()
        model = MARTModel(ensemble_xml, features)
        for tree in model.trees:
            weight = tree[0]
            tree = tree[1]
            logger.debug(tree.tree_string(weight=weight))


def eval_model(
    model_name: str, features: FeatureList, judgments: Iterable[Judgment]
) -> MARTModel:
    """Evaluate a model against a set of judgments and return the model.

    Loads a RankLib model from disk, evaluates it against the provided judgments,
    and returns the model with evaluation statistics populated.

    Args:
        model_name: Name of the model. The model file will be read from
            data/{model_name}_model.txt.
        features: List of feature dictionaries, where the 0th item corresponds
            to RankLib feature 1. Each feature must have a 'name' parameter.
        judgments: Iterable of Judgment objects to evaluate.

    Returns:
        MARTModel: Model object with evaluation statistics populated.
    """
    judgment_list = list(judgments)
    with open(f"data/{model_name}_model.txt", encoding="utf-8") as f:
        ensemble_xml = f.read()
        model = MARTModel(ensemble_xml, features)
        model.eval(judgment_list)
        return model
