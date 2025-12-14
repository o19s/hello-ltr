"""Judgment data structures and file I/O.

This module provides classes and functions for working with relevance judgments,
which are the core training data for Learn-to-Rank models. Judgments represent
query-document pairs with relevance grades and optional feature vectors.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal, Optional, overload


class JudgmentsWriter:
    """Writer for judgment lists to file descriptors.

    Buffers judgments in memory and writes them all at once when flush() is called.
    Useful for accumulating judgments before writing to a file.

    Attributes:
        f: File descriptor or file-like object to write to.
        judgments: List of Judgment objects to be written.
    """

    def __init__(self, f):
        """Initialize a JudgmentsWriter.

        Args:
            f: File descriptor or file-like object to write judgments to.
        """
        self.f = f
        self.judgments = []

    def write(self, judgment=None, judgments=None):
        """Add one or more judgments to the buffer.

        Args:
            judgment: Optional single Judgment object to add.
            judgments: Optional list of Judgment objects to add.

        Note:
            Exactly one of judgment or judgments should be provided.
        """
        if judgment is not None:
            self.judgments.append(judgment)
        elif judgments is not None:
            self.judgments.extend(judgments)

    def flush(self):
        """Write all buffered judgments to the file and clear the buffer."""
        judgments_to_file(self.f, self.judgments)


class JudgmentsReader:
    """Reader for judgment lists from file descriptors.

    Provides lazy reading of judgments from a file, parsing query headers
    and judgment rows on-demand.

    Attributes:
        f: File descriptor or file-like object to read from.
        kw_with_weight: Dictionary mapping query IDs to (keywords, weight) tuples.
        judgments: Iterator over Judgment objects.
    """

    def __init__(self, f):
        """Initialize a JudgmentsReader.

        Args:
            f: File descriptor or file-like object to read judgments from.
        """
        self.f = f
        self.kw_with_weight = _queriesFromHeader(f)
        self.judgments = _judgment_rows(f, self.kw_with_weight)

    def keywords(self, qid):
        """Get the search keywords for a query ID.

        Args:
            qid: Query ID to look up.

        Returns:
            str: Search keywords for the specified query ID.
        """
        return self.kw_with_weight[qid][0]

    def __iter__(self):
        """Make JudgmentsReader iterable.

        Returns:
            Iterator[Judgment]: Iterator over Judgment objects from the file.
        """
        return self.judgments


@overload
@contextmanager
def judgments_open(
    path: Optional[str], mode: Literal["r", "rt", "rb"] = ...
) -> Iterator[JudgmentsReader]:
    """Type overload for reading judgments from a file.

    This is a type hint overload. See the implementation below for full documentation.
    """
    ...


@overload
@contextmanager
def judgments_open(
    path: Optional[str], mode: Literal["w", "wt", "wb"] = ...
) -> Iterator[JudgmentsWriter]:
    """Type overload for writing judgments to a file.

    This is a type hint overload. See the implementation below for full documentation.
    """
    ...


@contextmanager
def judgments_open(path: Optional[str] = None, mode: str = "r"):
    """Work with judgments from the filesystem,
    either in a read or write mode"""
    if path is None:
        raise ValueError("path cannot be None")
    with open(path, mode) as f:
        if mode[0] == "r":
            yield JudgmentsReader(f)
        elif mode[0] == "w":
            writer = JudgmentsWriter(f)
            yield writer
            writer.flush()


@contextmanager
def judgments_writer(f):
    """Write to a judgment list at
    the provided file descripter (like StringIO)"""
    try:
        writer = JudgmentsWriter(f)
        yield writer
    finally:
        writer.flush()
        pass


@contextmanager
def judgments_reader(f):
    """Read from a judgment list at
    the provided file descripter (like StringIO)"""
    try:
        yield JudgmentsReader(f)
    finally:
        pass


class Judgment:
    """Represents a single relevance judgment.

    A judgment is a query-document pair with a relevance grade. It may also
    include feature vectors extracted from the search engine for training
    Learn-to-Rank models.

    Attributes:
        grade: Relevance grade (typically 0-4, where higher is more relevant).
        qid: Query ID identifying the query this judgment belongs to.
        keywords: Search keywords for the query.
        docId: Document ID being judged.
        features: Optional list of feature values (default: empty list).
            Note: 0th feature corresponds to RankLib feature 1.
        weight: Weight for this judgment in training (default: 1).
    """

    def __init__(self, grade, qid, keywords, docId, features=None, weight=1):
        """Initialize a Judgment.

        Args:
            grade: Relevance grade (typically 0-4, where higher is more relevant).
            qid: Query ID identifying the query this judgment belongs to.
            keywords: Search keywords for the query.
            docId: Document ID being judged.
            features: Optional list of feature values (default: empty list).
                Note: 0th feature corresponds to RankLib feature 1.
            weight: Weight for this judgment in training (default: 1).
        """
        self.grade = grade
        self.qid = qid
        self.keywords = keywords
        self.docId = docId
        self.features = (
            features if features is not None else []
        )  # 0th feature is ranklib feature 1
        self.weight = weight

    def sameQueryAndDoc(self, other):
        """Check if this judgment is for the same query and document as another.

        Args:
            other: Another Judgment object to compare with.

        Returns:
            bool: True if both judgments have the same qid and docId.
        """
        return self.qid == other.qid and self.docId == other.docId

    def has_features(self):
        """Check if this judgment has feature values.

        Returns:
            bool: True if features list exists and is non-empty.
        """
        return self.features is not None and (len(self.features) > 0)

    def __str__(self):
        """Generate user-friendly string representation.

        Returns:
            str: Human-readable string showing grade, query ID, keywords, and document ID.
        """
        return f"grade:{self.grade} qid:{self.qid} ({self.keywords}) docid:{self.docId}"

    def __repr__(self):
        """Generate developer-friendly string representation.

        Returns:
            str: String representation suitable for debugging, showing all attributes.
        """
        return "Judgment(grade={grade},qid={qid},keywords={keywords},docId={docId},features={features},weight={weight}".format(
            **vars(self)
        )

    def toRanklibFormat(self):
        """Convert judgment to RankLib training format string.

        Returns:
            str: Tab-separated string in RankLib format:
                grade qid:QID feat1:val1 feat2:val2 ... # docId keywords

        Note:
            Feature indices are 1-based in RankLib format (0th feature becomes "1:").
        """
        featuresAsStrs = [
            f"{idx + 1}:{feature}" for idx, feature in enumerate(self.features)
        ]
        comment = f"# {self.docId}\t{self.keywords}"
        return "{}\tqid:{}\t{} {}".format(
            self.grade, self.qid, "\t".join(featuresAsStrs), comment
        )


def _queriesToHeader(qidToKwDict):
    """Convert query ID to keywords mapping into file header format.

    Args:
        qidToKwDict: Dictionary mapping query IDs to (keywords, weight) tuples.

    Returns:
        str: Header string with query information in format:
            # qid:<qid>: <keywords>*<weight>
    """
    rVal = ""
    for qid, kws in qidToKwDict.items():
        rVal += f"# qid:{qid}: {kws[0]}"
        rVal += f"*{kws[1]}\n"
    rVal += "\n"
    return rVal


def _queriesFromHeader(lines):
    """Parses out mapping between, query id and user keywords
    from header comments, ie:
    # qid:523: First Blood
    returns dict mapping all query ids to search keywords"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96564
    regex = re.compile(r"#\sqid:(\d+?):\s+?(.*)")
    rVal = {}
    for line in lines:
        if line[0] != "#":
            break
        m = re.match(regex, line)
        try:
            if m:
                keywordAndWeight = m.group(2).split("*")
                keyword = keywordAndWeight[0]
                weight = 1
                if len(keywordAndWeight) > 1:
                    weight = int(keywordAndWeight[-1])
                rVal[int(m.group(1))] = (keyword, weight)
        except ValueError as e:
            print(e)
    #    print(f"Recognizing {len(rVal)} queries in: {lines.name}")
    print(f"Recognizing {len(rVal)} queries")

    return rVal


def _judgmentsFromBody(lines):
    """Parses out judgment/grade, query id, docId, and possibly features in line such as:
     4  qid:523   # a01  Grade for Rambo for query Foo

     Or

     4  qid:523  1:42.6 2:0.5  # a01  Grade for Rambo for query Foo
    <judgment> qid:<queryid> # docId <rest of comment ignored...)"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96565
    regex = re.compile(r"^(\d+)\s+qid:(\d+)\s+#\s+(\w+).*")
    trainRegex = re.compile(r"^(\d+)\s+qid:(\d+)\s+1:\d+.+#\s+(\w+).*")
    ftrRegex = re.compile(r"(\d+):([.\d]+)\s")
    for line in lines:
        m = re.match(regex, line)
        if m:
            yield int(m.group(1)), int(m.group(2)), m.group(3), []
        else:
            m = re.match(trainRegex, line)
            if m:
                grade = int(m.group(1))
                qid = int(m.group(2))
                docId = m.group(3)
                ftrMatches = re.finditer(ftrRegex, line)

                features = {}
                ftrSize = 0

                for m in ftrMatches:
                    ftrIdx = int(m.group(1)) - 1
                    if ftrIdx + 1 > ftrSize:
                        ftrSize = ftrIdx + 1
                    ftrScore = float(m.group(2))
                    features[ftrIdx] = ftrScore

                featuresList = [None] * ftrSize
                for ftrIdx, value in features.items():
                    featuresList[ftrIdx] = value

                for featureVal in featuresList:
                    if featureVal is None:
                        raise ValueError(
                            "Missing Features Detected When Parsing Training Set"
                        )

                yield grade, qid, docId, featuresList

            pass
            # print(f"Not Recognized as Judgment {line}")


def _judgment_rows(f, qidToKeywords):
    """Parse judgment rows from file body and yield Judgment objects.

    Args:
        f: File-like object to read from.
        qidToKeywords: Dictionary mapping query IDs to (keywords, weight) tuples.

    Yields:
        Judgment: Judgment objects parsed from the file.

    Raises:
        ValueError: If judgments are not sorted by qid in the file.
    """
    lastQid = -1
    for grade, qid, docId, features in _judgmentsFromBody(f):
        if qid < lastQid:
            raise ValueError("Judgments not sorted by qid in file")
        # if lastQid != qid and qid % 100 == 0:
        #     print(f"Parsing QID {qid}")
        yield Judgment(
            grade=grade,
            qid=qid,
            keywords=qidToKeywords[qid][0],
            weight=qidToKeywords[qid][1],
            docId=docId,
            features=features,
        )
        lastQid = qid


def judgments_from_file(f):
    """Read judgments from a SVMRank File
    f is a file object
    """
    qidToKeywords = _queriesFromHeader(f)
    yield from _judgment_rows(f, qidToKeywords)


def judgments_to_file(f, judgmentsList):
    """Write judgments from a SVMRank File
    f is a file object
    """
    # TODO - consider if a groupby approach would work instead of needing everything in memory
    judgToQid = _judgments_by_qid(judgmentsList)  # Pretty hideously slow stuff
    fileHeader = _queriesToHeader(
        {qid: (judgs[0].keywords, judgs[0].weight) for qid, judgs in judgToQid.items()}
    )
    judgByQid = sorted(judgmentsList, key=lambda j: j.qid)
    f.write(fileHeader)
    for judg in judgByQid:
        f.write(judg.toRanklibFormat() + "\n")


def _judgments_by_qid(judgments):
    """Create a dictionary of qid->judgments
    Prefer itertools groupby"""
    rVal = {}
    for judgment in judgments:
        try:
            rVal[judgment.qid].append(judgment)
        except KeyError:
            rVal[judgment.qid] = [judgment]
    return rVal


def judgments_by_qid(judgments):
    """Create a dictionary of qid->judgments
    Public wrapper for _judgments_by_qid"""
    return _judgments_by_qid(judgments)


def judgments_to_nparray(judgments):
    """Return
    - features - num samples x num features
    - predictors - num samples x grade, qid
    """
    import numpy as np

    predictors = []
    features = []
    for judg in judgments:
        predictors.append([judg.grade, judg.qid])
        features.append(judg.features)
    features = np.array(features)
    predictors = np.array(predictors)
    return features, predictors


def judgments_to_dataframe(judgments, unnest=True):
    """Convert a list of judgments to a pandas DataFrame.

    Args:
        judgments: Iterable of Judgment objects to convert.
        unnest: If True, expand the features list into separate columns
            (features0, features1, etc.). If False, keep features as a list column.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - uid: Unique identifier combining qid and docId
            - qid: Query ID
            - keywords: Search keywords
            - docId: Document ID
            - grade: Relevance grade
            - features: Feature values (as list if unnest=False, or expanded columns if unnest=True)
    """
    import pandas as pd

    ret = []
    for j in judgments:
        ret.append(
            {
                "uid": str(j.qid) + "_" + j.docId,
                "qid": j.qid,
                "keywords": j.keywords,
                "docId": j.docId,
                "grade": j.grade,
                "features": j.features,
            }
        )
    dat = pd.DataFrame(ret)

    # https://stackoverflow.com/questions/53218931/how-to-unnest-explode-a-column-in-a-pandas-dataframe
    def unnesting(df, explode):
        """Expand nested list columns into separate columns.

        Args:
            df: DataFrame to process.
            explode: List of column names to expand.

        Returns:
            pd.DataFrame: DataFrame with expanded columns.
        """
        df1 = pd.concat(
            [
                pd.DataFrame(df[x].tolist(), index=df.index).add_prefix(x)
                for x in explode
            ],
            axis=1,
        )
        return df1.join(df.drop(explode, axis=1), how="left")

    if unnest:
        dat = unnesting(dat, ["features"])

    return dat


def judgments_dataframe_to_long(judgments_df):
    """Convert a wide-format judgments DataFrame to long format.

    Transforms feature columns (features0, features1, etc.) into rows,
    creating a feature_id column to identify which feature each row represents.

    Args:
        judgments_df: DataFrame in wide format with feature columns.

    Returns:
        pd.DataFrame: DataFrame in long format with one row per judgment-feature pair.
    """
    import pandas as pd

    return pd.wide_to_long(
        judgments_df, ["features"], i="uid", j="feature_id"
    ).reset_index()


def duplicateJudgmentsByWeight(judgmentsByQid):
    """Duplicate judgments based on their weight.

    For each query with weight > 1, creates additional copies of all judgments
    for that query, assigning them new query IDs. This effectively multiplies
    the training data for queries with higher weights.

    Args:
        judgmentsByQid: Dictionary mapping query IDs to lists of Judgment objects.

    Returns:
        dict: Dictionary mapping query IDs to lists of Judgment objects,
            with duplicated queries added for weights > 1.
    """

    def copyJudgments(srcJudgments):
        """Create a deep copy of a list of judgments.

        Args:
            srcJudgments: List of Judgment objects to copy.

        Returns:
            list: New list containing copied Judgment objects.
        """
        destJudgments = []
        for judg in srcJudgments:
            destJudgments.append(
                Judgment(
                    grade=judg.grade,
                    qid=judg.qid,
                    keywords=judg.keywords,
                    weight=judg.weight,
                    docId=judg.docId,
                )
            )
        return destJudgments

    rVal = {}
    maxQid = 0
    for qid, _judgments in judgmentsByQid.items():
        maxQid = qid
    for qid, judgments in judgmentsByQid.items():
        rVal[qid] = judgments
        if qid % 100 == 0:
            print(f"Duping {qid}")
        if judgments[0].weight > 1:
            for _i in range(judgments[0].weight - 1):
                rVal[maxQid] = copyJudgments(judgments)
                for judg in judgments:
                    judg.qid = maxQid
                maxQid += 1

    return rVal
