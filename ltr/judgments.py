"""Judgment data structures and file I/O.

This module provides classes and functions for working with relevance judgments,
which are the core training data for Learn-to-Rank models. Judgments represent
query-document pairs with relevance grades and optional feature vectors.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Literal, TextIO, cast, overload

from ltr.compat import accepts_legacy_kwargs
from ltr.logger import get_logger
from ltr.types import QueryKeywordMap
from ltr.validation import ValidationError

logger = get_logger(__name__)

# Type alias for file-like objects that can be used for reading/writing judgments
# Using TextIO for compatibility with open() return type
JudgmentFile = TextIO


class JudgmentsWriter:
    """Writer for judgment lists to file descriptors.

    Buffers judgments in memory and writes them all at once when flush() is called.
    Useful for accumulating judgments before writing to a file.

    Attributes:
        f: File descriptor or file-like object to write to.
        judgments: List of Judgment objects to be written.
    """

    def __init__(self, f: TextIO) -> None:
        """Initialize a JudgmentsWriter.

        Args:
            f: File descriptor or file-like object to write judgments to.
        """
        self.f = f
        self.judgments: list[Judgment] = []

    def write(
        self,
        judgment: Judgment | None = None,
        judgments: list[Judgment] | None = None,
    ) -> None:
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

    def flush(self) -> None:
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

    def __init__(self, f: JudgmentFile) -> None:
        """Initialize a JudgmentsReader.

        Args:
            f: File descriptor or file-like object to read judgments from.
        """
        self.f = f
        self.kw_with_weight: QueryKeywordMap = _queries_from_header(f)
        self.judgments: Iterator[Judgment] = _judgment_rows(f, self.kw_with_weight)

    def keywords(self, qid: int) -> str:
        """Get the search keywords for a query ID.

        Args:
            qid: Query ID to look up.

        Returns:
            str: Search keywords for the specified query ID.
        """
        return self.kw_with_weight[qid][0]

    def __iter__(self) -> Iterator[Judgment]:
        """Make JudgmentsReader iterable.

        Returns:
            Iterator[Judgment]: Iterator over Judgment objects from the file.
        """
        return self.judgments


@overload
def judgments_open(
    path: str, mode: Literal["r", "rt", "rb"] = "r"
) -> AbstractContextManager[JudgmentsReader]:
    """Type overload for reading judgments from a file.

    This is a type hint overload. See the implementation below for full documentation.
    """
    ...


@overload
def judgments_open(
    path: str, mode: Literal["w", "wt", "wb"]
) -> AbstractContextManager[JudgmentsWriter]:
    """Type overload for writing judgments to a file.

    This is a type hint overload. See the implementation below for full documentation.
    """
    ...


@contextmanager
def judgments_open(
    path: str | None = None, mode: str = "r"
) -> Iterator[JudgmentsReader | JudgmentsWriter]:
    """Work with judgments from the filesystem,
    either in a read or write mode"""
    if path is None:
        raise ValidationError("path cannot be None")
    with open(path, mode) as f:
        f_textio: TextIO = cast(TextIO, f)
        if mode[0] == "r":
            yield JudgmentsReader(f_textio)
        elif mode[0] == "w":
            writer = JudgmentsWriter(f_textio)
            yield writer
            writer.flush()


@contextmanager
def judgments_writer(f: JudgmentFile) -> Iterator[JudgmentsWriter]:
    """Write to a judgment list at
    the provided file descripter (like StringIO)"""
    writer: JudgmentsWriter | None = None
    try:
        writer = JudgmentsWriter(f)
        yield writer
    finally:
        if writer is not None:
            writer.flush()


@contextmanager
def judgments_reader(f: JudgmentFile) -> Iterator[JudgmentsReader]:
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

    def __init__(
        self,
        grade: int,
        qid: int,
        keywords: str,
        doc_id: str,
        features: list[float] | None = None,
        weight: int = 1,
    ) -> None:
        """Initialize a Judgment.

        Args:
            grade: Relevance grade (typically 0-4, where higher is more relevant).
            qid: Query ID identifying the query this judgment belongs to.
            keywords: Search keywords for the query.
            doc_id: Document ID being judged.
            features: Optional list of feature values (default: empty list).
                Note: 0th feature corresponds to RankLib feature 1.
            weight: Weight for this judgment in training (default: 1).
        """
        self.grade: int = grade
        self.qid: int = qid
        self.keywords: str = keywords
        self.docId: str = doc_id
        self.features: list[float] = (
            features if features is not None else []
        )  # 0th feature is ranklib feature 1
        self.weight: int = weight

    def same_query_and_doc(self, other: Judgment) -> bool:
        """Check if this judgment is for the same query and document as another.

        Args:
            other: Another Judgment object to compare with.

        Returns:
            bool: True if both judgments have the same qid and docId.
        """
        return self.qid == other.qid and self.docId == other.docId

    def has_features(self) -> bool:
        """Check if this judgment has feature values.

        Returns:
            bool: True if features list exists and is non-empty.
        """
        return self.features is not None and (len(self.features) > 0)

    def __str__(self) -> str:
        """Generate user-friendly string representation.

        Returns:
            str: Human-readable string showing grade, query ID, keywords, and document ID.
        """
        return f"grade:{self.grade} qid:{self.qid} ({self.keywords}) docid:{self.docId}"

    def __repr__(self) -> str:
        """Generate developer-friendly string representation.

        Returns:
            str: String representation suitable for debugging, showing all attributes.
        """
        return "Judgment(grade={grade},qid={qid},keywords={keywords},docId={docId},features={features},weight={weight}".format(
            **vars(self)
        )

    def to_ranklib_format(self) -> str:
        """Convert judgment to RankLib training format string.

        Returns:
            str: Tab-separated string in RankLib format:
                grade qid:QID feat1:val1 feat2:val2 ... # docId keywords

        Note:
            Feature indices are 1-based in RankLib format (0th feature becomes "1:").
            None, NaN, or invalid feature values are replaced with 0.0 to ensure valid numeric format.
        """
        import math

        def safe_feature_value(feature: float | None | str) -> float:
            """Convert feature value to a safe numeric value for RankLib.

            Args:
                feature: Feature value (may be None, NaN, string "None", or invalid).

            Returns:
                float: Valid numeric value (0.0 for None/NaN/invalid values).
            """
            if feature is None:
                return 0.0
            # Explicitly handle string "None" before attempting conversion
            if isinstance(feature, str) and feature.lower() == "none":
                return 0.0
            try:
                value = float(feature)
                # Check for NaN
                if math.isnan(value):
                    return 0.0
                return value
            except (ValueError, TypeError):
                # Handle other invalid values (fallback)
                return 0.0

        features_as_strs = [
            f"{idx + 1}:{safe_feature_value(feature)}"
            for idx, feature in enumerate(self.features)
        ]
        comment = f"# {self.docId}\t{self.keywords}"
        formatted_line = "{}\tqid:{}\t{} {}".format(
            self.grade, self.qid, "\t".join(features_as_strs), comment
        )
        return formatted_line


def _queries_to_header(qid_to_kw_dict: QueryKeywordMap) -> str:
    """Convert query ID to keywords mapping into file header format.

    Args:
        qid_to_kw_dict: Dictionary mapping query IDs to (keywords, weight) tuples.

    Returns:
        str: Header string with query information in format:
            # qid:<qid>: <keywords>*<weight>
    """
    r_val = ""
    for qid, kws in qid_to_kw_dict.items():
        r_val += f"# qid:{qid}: {kws[0]}"
        r_val += f"*{kws[1]}\n"
    r_val += "\n"
    return r_val


def _queries_from_header(lines: JudgmentFile) -> QueryKeywordMap:
    """Parses out mapping between, query id and user keywords
    from header comments, ie:
    # qid:523: First Blood
    returns dict mapping all query ids to search keywords"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96564
    regex = re.compile(r"#\sqid:(\d+?):\s+?(.*)")
    r_val = {}
    for line in lines:
        if line[0] != "#":
            break
        m = re.match(regex, line)
        try:
            if m:
                keyword_and_weight = m.group(2).split("*")
                keyword = keyword_and_weight[0]
                weight = 1
                if len(keyword_and_weight) > 1:
                    weight = int(keyword_and_weight[-1])
                r_val[int(m.group(1))] = (keyword, weight)
        except ValueError as e:
            logger.error(f"Error parsing query header: {e}")
    logger.info(f"Recognizing {len(r_val)} queries")

    return r_val


def _judgments_from_body(
    lines: Iterator[str],
) -> Iterator[tuple[int, int, str, list[float]]]:
    """Parses out judgment/grade, query id, docId, and possibly features in line such as:
     4  qid:523   # a01  Grade for Rambo for query Foo

     Or

     4  qid:523  1:42.6 2:0.5  # a01  Grade for Rambo for query Foo
    <judgment> qid:<queryid> # docId <rest of comment ignored...)"""
    # Regex can be debugged here:
    # http://www.regexpal.com/?fam=96565
    regex = re.compile(r"^(\d+)\s+qid:(\d+)\s+#\s+(\w+).*")
    train_regex = re.compile(r"^(\d+)\s+qid:(\d+)\s+1:\d+.+#\s+(\w+).*")
    # Updated regex to also match "None" strings (for backward compatibility with old files)
    # and convert them to 0.0
    ftr_regex = re.compile(r"(\d+):([.\d]+|None)\s")
    for line in lines:
        m = re.match(regex, line)
        if m:
            yield int(m.group(1)), int(m.group(2)), m.group(3), []
        else:
            m = re.match(train_regex, line)
            if m:
                grade = int(m.group(1))
                qid = int(m.group(2))
                doc_id = m.group(3)
                ftr_matches = re.finditer(ftr_regex, line)

                features = {}
                ftr_size = 0

                for m in ftr_matches:
                    ftr_idx = int(m.group(1)) - 1
                    if ftr_idx + 1 > ftr_size:
                        ftr_size = ftr_idx + 1
                    # Handle "None" strings by converting to 0.0 (for backward compatibility)
                    ftr_value_str = m.group(2)
                    ftr_score = 0.0 if ftr_value_str == "None" else float(ftr_value_str)
                    features[ftr_idx] = ftr_score

                features_list: list[float | None] = [None] * ftr_size
                for ftr_idx, value in features.items():
                    features_list[ftr_idx] = value

                # Fill any remaining None values with 0.0 (for backward compatibility)
                for i, feature_val in enumerate(features_list):
                    if feature_val is None:
                        features_list[i] = 0.0

                yield grade, qid, doc_id, cast(list[float], features_list)

            pass
            # print(f"Not Recognized as Judgment {line}")


def _judgment_rows(
    f: JudgmentFile, qid_to_keywords: QueryKeywordMap
) -> Iterator[Judgment]:
    """Parse judgment rows from file body and yield Judgment objects.

    Args:
        f: File-like object to read from.
        qid_to_keywords: Dictionary mapping query IDs to (keywords, weight) tuples.

    Yields:
        Judgment: Judgment objects parsed from the file.

    Raises:
        ValueError: If judgments are not sorted by qid in the file.
    """
    last_qid = -1
    for grade, qid, doc_id, features in _judgments_from_body(f):
        if qid < last_qid:
            raise ValidationError("Judgments not sorted by qid in file")
        # if last_qid != qid and qid % 100 == 0:
        #     print(f"Parsing QID {qid}")
        yield Judgment(
            grade=grade,
            qid=qid,
            keywords=qid_to_keywords[qid][0],
            weight=qid_to_keywords[qid][1],
            doc_id=doc_id,
            features=features,
        )
        last_qid = qid


def judgments_from_file(f: JudgmentFile) -> Iterator[Judgment]:
    """Read judgments from a SVMRank File
    f is a file object
    """
    qid_to_keywords = _queries_from_header(f)
    yield from _judgment_rows(f, qid_to_keywords)


@accepts_legacy_kwargs(judgmentsList="judgments_list")
def judgments_to_file(
    f: JudgmentFile, judgments_list: list[Judgment] | Iterator[Judgment]
) -> None:
    """Write judgments to a SVMRank File.

    Writes judgments in RankLib format with query headers. Optimized to handle
    both lists and iterators, using streaming when judgments are already sorted by qid.

    Args:
        f: File object to write to.
        judgments_list: List or iterator of Judgment objects to write.
            If an iterator and judgments are already sorted by qid, uses streaming
            to reduce memory usage. Otherwise, materializes all judgments for sorting.

    Note:
        For large datasets, prefer passing an iterator of judgments that are
        already sorted by qid to enable streaming and reduce memory usage.
    """
    # Convert iterator to list if needed, or use list directly
    if isinstance(judgments_list, Iterator):
        judgments_list = list(judgments_list)

    # Group judgments by qid to extract header information
    # This requires one pass through all judgments
    judg_to_qid = _judgments_by_qid(judgments_list)
    file_header = _queries_to_header(
        {
            qid: (judgs[0].keywords, judgs[0].weight)
            for qid, judgs in judg_to_qid.items()
        }
    )

    # Sort judgments by qid for consistent output
    # Note: This still requires all judgments in memory, but allows
    # the function to accept iterators without forcing callers to materialize lists
    judg_by_qid = sorted(judgments_list, key=lambda j: j.qid)
    f.write(file_header)
    for judg in judg_by_qid:
        f.write(judg.to_ranklib_format() + "\n")


def _judgments_by_qid(
    judgments: list[Judgment] | Iterator[Judgment],
) -> dict[int, list[Judgment]]:
    """Create a dictionary of qid->judgments.

    Groups judgments by query ID (qid) into a dictionary mapping qid to list of judgments.
    Uses defaultdict for efficient grouping without try/except overhead.
    Accepts both lists and iterators for flexibility.

    Args:
        judgments: List or iterator of Judgment objects to group.

    Returns:
        Dictionary mapping qid (int) to list of Judgment objects.
    """
    r_val: dict[int, list[Judgment]] = defaultdict(list)
    for judgment in judgments:
        r_val[judgment.qid].append(judgment)
    return dict(r_val)  # Convert back to regular dict for return type


def judgments_by_qid(
    judgments: list[Judgment],
) -> dict[int, list[Judgment]]:
    """Create a dictionary of qid->judgments
    Public wrapper for _judgments_by_qid"""
    return _judgments_by_qid(judgments)


def judgments_to_nparray(
    judgments: list[Judgment],
) -> tuple[Any, Any]:
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


def judgments_to_dataframe(judgments: list[Judgment], unnest: bool = True) -> Any:
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
    def unnesting(df: Any, explode: list[str]) -> Any:
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


def judgments_dataframe_to_long(judgments_df: Any) -> Any:
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


def duplicate_judgments_by_weight(
    judgments_by_qid: dict[int, list[Judgment]],
) -> dict[int, list[Judgment]]:
    """Duplicate judgments based on their weight.

    For each query with weight > 1, creates additional copies of all judgments
    for that query, assigning them new query IDs. This effectively multiplies
    the training data for queries with higher weights.

    Args:
        judgments_by_qid: Dictionary mapping query IDs to lists of Judgment objects.

    Returns:
        dict: Dictionary mapping query IDs to lists of Judgment objects,
            with duplicated queries added for weights > 1.
    """

    def copy_judgments(src_judgments: list[Judgment]) -> list[Judgment]:
        """Create a deep copy of a list of judgments.

        Args:
            src_judgments: List of Judgment objects to copy.

        Returns:
            list: New list containing copied Judgment objects.
        """
        dest_judgments = []
        for judg in src_judgments:
            dest_judgments.append(
                Judgment(
                    grade=judg.grade,
                    qid=judg.qid,
                    keywords=judg.keywords,
                    weight=judg.weight,
                    doc_id=judg.docId,
                )
            )
        return dest_judgments

    r_val = {}
    max_qid = 0
    for qid, _judgments in judgments_by_qid.items():
        max_qid = qid
    for qid, judgments in judgments_by_qid.items():
        r_val[qid] = judgments
        if qid % 100 == 0:
            logger.debug(f"Duping {qid}")
        if judgments[0].weight > 1:
            for _i in range(judgments[0].weight - 1):
                copied_judgments = copy_judgments(judgments)
                r_val[max_qid] = copied_judgments
                for judg in copied_judgments:
                    judg.qid = max_qid
                max_qid += 1

    return r_val
