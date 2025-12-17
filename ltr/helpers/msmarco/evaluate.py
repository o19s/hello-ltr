"""MS MARCO dataset evaluation utilities.

This module provides classes and functions for working with MS MARCO
(Microsoft Machine Reading Comprehension) dataset query relevance judgments
and evaluating rankings using metrics like Reciprocal Rank.
"""

from __future__ import annotations

import csv
import gzip
from collections.abc import Iterator


class QRel:
    """Represents a query relevance judgment from MS MARCO dataset.

    A QRel (query relevance) object represents a single relevant document
    for a query, used for evaluation purposes.

    Attributes:
        qid: Query ID.
        docid: Relevant document ID.
        keywords: Query keywords/text.
    """

    def __init__(self, qid: str, docid: str, keywords: str | None) -> None:
        """Initialize a QRel object.

        Args:
            qid: Query ID.
            docid: Relevant document ID.
            keywords: Query keywords/text.
        """
        self.qid: str = qid
        self.docid: str = docid
        self.keywords: str | None = keywords

    def eval_rr(self, doc_ranking: list[str]) -> float:
        """Evaluate document ranking using Reciprocal Rank metric.

        Calculates 1/rank where rank is the position of the relevant document
        in the provided ranking.

        Args:
            doc_ranking: List of document IDs in rank order.

        Returns:
            float: Reciprocal rank (1/rank) if relevant document is found,
                0.0 if the relevant document is not in the ranking.
        """

        for rank, docid in enumerate(doc_ranking, start=1):
            if docid == self.docid:
                return 1.0 / rank
        return 0.0

    @staticmethod
    def read_qrels(
        qrels_fname: str = "data/msmarco-doctrain-qrels.tsv.gz",
        queries_fname: str = "data/msmarco-doctrain-queries.tsv.gz",
    ) -> Iterator[QRel]:
        """Read QRel objects from MS MARCO qrels and queries files.

        Args:
            qrels_fname: Path to gzipped TSV file containing qrels (query-doc pairs).
            queries_fname: Path to gzipped TSV file containing query ID to keywords mapping.

        Yields:
            QRel: QRel objects for each query-document relevance pair.

        Note:
            Files are expected to be gzipped TSV format. Missing keywords
            for queries will result in None keywords and a warning message.
        """
        qids_to_keywords = QRel.get_keyword_lookup(queries_fname)

        with gzip.open(qrels_fname, "rt") as f:
            reader = csv.reader(f, delimiter=" ")
            for row in reader:
                qid = row[0]
                keywords = None
                if qid in qids_to_keywords:
                    keywords = qids_to_keywords[qid]
                else:
                    # Import here to avoid circular dependency
                    from ltr.logger import get_logger

                    logger = get_logger(__name__)
                    logger.warning(f"Missing keywords for {qid}")
                yield QRel(qid=row[0], docid=row[2], keywords=keywords)

    @staticmethod
    def get_keyword_lookup(
        fname: str = "data/msmarco-doctrain-queries.tsv.gz",
    ) -> dict[str, str]:
        """Build a dictionary mapping query IDs to keywords.

        Args:
            fname: Path to gzipped TSV file containing query ID and keyword pairs.

        Returns:
            dict: Dictionary mapping query ID strings to keyword strings.
        """
        qids_to_keywords = {}
        with gzip.open(fname, "rt") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                qids_to_keywords[row[0]] = row[1]
        return qids_to_keywords

    def __str__(self) -> str:
        """Generate string representation of the QRel.

        Returns:
            str: Human-readable string showing query ID, keywords, and document ID.
        """
        return f"qid:{self.qid}({self.keywords}) => doc:{self.docid}"


if __name__ == "__main__":
    qrels = {}
    for qrel in QRel.read_qrels():
        qrels[qrel.qid] = qrel

    print(qrels["1185869"].eval_rr(["1", "1"]))
