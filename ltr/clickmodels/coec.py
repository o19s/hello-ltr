"""COEC (Clicks Over Expected Clicks) click model.

This module implements the COEC metric for analyzing click behavior in search
sessions. COEC compares actual clicks to expected clicks based on position-based
CTR to identify query-document pairs that perform above or below average.
"""

from __future__ import annotations

from collections import defaultdict

from ltr.clickmodels.session import Session
from ltr.types import AttractivenessMap, CTRByRank, QueryDocPair


class Model:
    """COEC model storing statistics for query-document pairs.

    Attributes:
        coecs: Dictionary mapping (query_id, doc_id) tuples to COEC values.
        ctrs: Dictionary mapping query-doc pairs to CTR values (currently unused).
    """

    def __init__(self) -> None:
        """Initialize a COEC model with empty statistics.

        Initializes empty dictionaries for COEC values and CTR values.
        These will be populated by the coec() function.
        """
        # COEC statistic
        self.coecs: AttractivenessMap = {}

        # CTR for each query-doc pair in this session
        self.ctrs: AttractivenessMap = {}


def coec(ctr_by_rank: CTRByRank, sessions: list[Session]) -> Model:
    """Calculate COEC (Clicks Over Expected Clicks) for query-document pairs.

    COEC is a metric used to identify items that perform above or below average
    CTR for their rank position. Based on the paper:
    "Personalized Click Prediction in Sponsored Search" by Cheng, Cantu Paz.

    Args:
        ctr_by_rank: Dictionary mapping rank position (0-based) to global CTR value.
        sessions: List of search session objects, each containing:
            - query: Query string or ID
            - docs: List of document objects with doc_id and click attributes

    Returns:
        Model: Model object containing coecs dictionary mapping (query_id, doc_id)
            tuples to COEC values.

    Note:
        - COEC > 1 means above average CTR for that position
        - COEC < 1 means below average CTR for that position
        - COEC = 1 means average CTR for that position
    """
    clicks: defaultdict[QueryDocPair, int] = defaultdict(lambda: 0)
    weighted_impressions: defaultdict[QueryDocPair, float] = defaultdict(lambda: 0.0)

    for session in sessions:
        for rank, doc in enumerate(session.docs):
            weighted_impressions[(session.query, doc.doc_id)] += ctr_by_rank[rank]
            if doc.click:
                clicks[(session.query, doc.doc_id)] += 1

    model = Model()
    for query_id, doc_id in weighted_impressions:
        model.coecs[(query_id, doc_id)] = (
            clicks[(query_id, doc_id)] / weighted_impressions[(query_id, doc_id)]
        )

    return model
