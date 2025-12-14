"""Cascade click model implementation.

This module implements the Cascade model, which assumes users examine results
sequentially and stop at the first click. Documents appearing before a click
are considered examined but not clicked (negative signal), while the clicked
document receives positive signal.
"""

from collections import Counter, defaultdict

from ltr.clickmodels.session import build


class Model:
    """Cascade model storing document attractiveness values.

    Attributes:
        attracts: Dictionary mapping (query, doc_id) tuples to attractiveness values.
    """

    def __init__(self):
        """Initialize a Cascade model with default values.

        Initializes attractiveness values to 0.5 for all query-document pairs.
        """
        # Attractiveness per query-doc
        self.attracts = defaultdict(lambda: 0.5)


def cascade_model(sessions):
    """Train a Cascade click model from search sessions.

    The Cascade model can be solved directly without iterative optimization:
    - Sessions with skips (documents examined but not clicked) count against a doc
    - Sessions with clicks count for the clicked document
    - Model stops at first click (assumes user satisfaction)

    Args:
        sessions: List of search session objects containing queries and clicked documents.

    Returns:
        Model: Trained Cascade model with attractiveness values for query-document pairs.
    """
    session_counts = Counter()
    click_counts = Counter()
    model = Model()

    for session in sessions:
        for doc in session.docs:
            query_doc_key = (session.query, doc.doc_id)
            session_counts[query_doc_key] += 1

            if doc.click:
                # Cascading model doesn't consider
                # clicks past the last one, so we count
                # this one and break out
                click_counts[query_doc_key] += 1
                break

    for (query_id, doc_id), count in session_counts.items():
        query_doc_key = (query_id, doc_id)
        model.attracts[query_doc_key] = click_counts[query_doc_key] / count
    return model


if __name__ == "__main__":
    sessions = build(
        [
            ("A", ((1, True), (2, False), (3, True), (0, False))),
            ("B", ((5, False), (2, True), (3, True), (0, False))),
            ("A", ((1, False), (2, False), (3, True), (0, False))),
            ("B", ((1, False), (2, False), (3, False), (9, True))),
            ("A", ((9, False), (2, False), (1, True), (0, True))),
            ("B", ((6, True), (2, False), (3, True), (1, False))),
            ("A", ((7, False), (4, True), (1, False), (3, False))),
            ("B", ((8, True), (2, False), (3, True), (1, False))),
            ("A", ((1, False), (4, True), (2, False), (3, False))),
            ("B", ((7, True), (4, False), (5, True), (1, True))),
        ]
    )
    cascade_model(sessions)
