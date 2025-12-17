"""Conversion-augmented attractiveness adjustment.

This module provides functionality for adjusting document attractiveness based
on conversion data, penalizing clicks that don't lead to conversions while
accounting for action costs.
"""

from __future__ import annotations

from collections import defaultdict

from ltr.clickmodels.session import Session
from ltr.types import AttractivenessMap, CostMap, QueryDocPair


def conv_aug_attracts(
    attracts: AttractivenessMap,
    sessions: list[Session],
    costs: CostMap,
) -> AttractivenessMap:
    """Adjust attractiveness values based on conversion data.

    Rescans sessions using click-derived attractiveness, but penalizes
    attractiveness when clicks don't lead to conversions. The penalty is
    inversely proportional to cost: expensive actions are penalized less
    (user may have been satisfied but didn't convert due to cost), while
    cheap actions are penalized more (user likely wasn't satisfied).

    Args:
        attracts: Dictionary mapping (query, doc_id) tuples to attractiveness values.
        sessions: List of search session objects with click and conversion data.
        costs: Dictionary mapping doc_id to action cost values.

    Returns:
        dict: Dictionary mapping (query, doc_id) tuples to adjusted attractiveness
            values based on conversion data.
    """
    satisfacts: defaultdict[QueryDocPair, float] = defaultdict(lambda: 0.0)
    counts: defaultdict[QueryDocPair, int] = defaultdict(lambda: 0)
    for session in sessions:
        for _rank, doc in enumerate(session.docs):
            attract = attracts[(session.query, doc.doc_id)]
            if doc.click:
                if doc.conversion:
                    # Confirms the attractiveness was real with actual relevance
                    counts[(session.query, doc.doc_id)] += 1
                    satisfacts[(session.query, doc.doc_id)] += attract
                else:
                    # If it costs a lot, and there wasn't a conversion,
                    #  that's ok, we default to attractiveness
                    # If it costs little, and there wasn't a conversion,
                    #  that's generally not ok, why didn't they do (easy action)
                    counts[(session.query, doc.doc_id)] += 1
                    satisfacts[(session.query, doc.doc_id)] += (
                        attract * costs[doc.doc_id]
                    )
            else:
                counts[(session.query, doc.doc_id)] += 1
                satisfacts[(session.query, doc.doc_id)] += attract * costs[doc.doc_id]

    result: AttractivenessMap = {}
    for (query_id, doc_id), count in counts.items():
        result[(query_id, doc_id)] = satisfacts[(query_id, doc_id)] / count

    return result
