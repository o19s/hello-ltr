"""Feature logging for building training sets.

This module provides functionality for logging LTR features from search
engines and building training sets from judgments.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ltr.client.base_client import BaseClient
from ltr.judgments import Judgment


class FeatureLogger:
    """Logs LTR features from search engine queries, building up a training set.

    This class facilitates the collection of feature vectors from a search engine
    for documents associated with query-judgment pairs. Features are fetched in
    batches and attached to judgment objects.

    Attributes:
        client: Search client instance.
        index: Name of the search index.
        feature_set: Name of the feature set to use.
        drop_missing: If True, discard judgments for missing documents (default: True).
        logged: List of judgments that have been successfully logged with features.
    """

    def __init__(
        self,
        client: BaseClient,
        index: str,
        feature_set: str,
        drop_missing: bool = True,
    ) -> None:
        """Initialize a FeatureLogger.

        Args:
            client: Search client instance.
            index: Name of the search index.
            feature_set: Name of the feature set to use.
            drop_missing: If True, discard judgments for missing documents (default: True).
        """
        self.client: BaseClient = client
        self.index: str = index
        self.feature_set: str = feature_set
        self.drop_missing: bool = drop_missing
        self.logged: list[Judgment] = []

    def clear(self) -> None:
        """Clear all logged judgments.

        Resets the logged list to empty, allowing reuse of the logger
        for a new training set.
        """
        self.logged = []

    def log_for_qid(
        self,
        qid: int,
        judgments: Iterable[Judgment],
        keywords: str,
    ) -> tuple[list[Judgment], list[Judgment]]:
        """Log features for a set of judgments associated with a query ID.

        Fetches LTR features from the search engine for all documents in the
        judgments iterable and attaches them to the judgment objects. Documents
        are fetched in batches of 500.

        Args:
            qid: Query ID associated with these judgments.
            judgments: Iterable of Judgment objects to log features for.
            keywords: Search keywords used for the query (sanitized automatically).

        Returns:
            tuple: A tuple containing:
                - training_set: List of judgments with successfully logged features.
                - discarded: List of judgments that were discarded (if drop_missing=True)
                  or empty list (if drop_missing=False).

        Note:
            The judgments are converted to a list internally and modified in-place
            with features attached. Keywords are sanitized to remove special characters
            for Solr compatibility. Missing documents are handled according to the
            drop_missing setting.
        """
        features_per_doc = {}
        judgments = list(judgments)
        doc_ids = [judgment.docId for judgment in judgments]

        # Check for dupes of documents
        for doc_id in doc_ids:
            indices = [i for i, x in enumerate(doc_ids) if x == doc_id]
            if len(indices) > 1:
                # print("Duplicate Doc in qid:%s %s" % (qid, doc_id))
                pass

        # For every batch of N docs to generate judgments for
        batch_size = 500
        num_left = len(doc_ids)
        for i in range(0, 1 + (len(doc_ids) // batch_size)):
            num_fetch = min(batch_size, num_left)
            start = i * batch_size
            if start >= len(doc_ids):
                break
            ids = doc_ids[start : start + num_fetch]

            # Sanitize (Solr has a strict syntax that can easily be tripped up)
            # This removes anything but alphanumeric and spaces
            keywords = re.sub(r"([^\s\w]|_)+", "", keywords)

            params = {
                "keywords": keywords,
                "fuzzy_keywords": " ".join([x + "~" for x in keywords.split(" ")]),
                "keywordsList": [keywords],  # Needed by TSQ for the time being
            }

            res = self.client.log_query(self.index, self.feature_set, ids, params)

            # Add feature back to each judgment
            for doc in res:
                doc_id = str(doc["id"])
                features = doc["ltr_features"]
                features_per_doc[doc_id] = features
            num_left -= batch_size

        # Append features from search engine back to ranklib judgment list
        for judgment in judgments:
            try:
                features = features_per_doc[
                    judgment.docId
                ]  # If KeyError, then we have a judgment but no movie in index
                judgment.features = features
            except KeyError:
                pass
                # print("Missing doc %s" % judgment.docId)

        # Return a paired down judgments if we are missing features for judgments
        training_set = []
        discarded = []
        for judgment in judgments:
            if self.drop_missing:
                if judgment.has_features():
                    training_set.append(judgment)
                else:
                    discarded.append(judgment)
            else:
                training_set.append(judgment)
        # print("Discarded %s Keep %s" % (len(discarded), len(training_set)))
        self.logged.extend(training_set)
        return training_set, discarded
