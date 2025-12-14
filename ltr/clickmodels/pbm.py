"""PBM (Position-Based Model) click model implementation.

This module implements the Position-Based Model, a click model that considers
both document attractiveness and position-based examination probability.
Based on Expectation Maximization algorithm from "Click Models for Web Search"
by Chuklin, Markov, de Rijke.
"""

from collections import Counter, defaultdict

from ltr.clickmodels.session import build
from ltr.helpers.defaultlist import defaultlist


class Model:
    """PBM model storing examination probabilities and document attractiveness.

    Attributes:
        ranks: DefaultList storing examination probability for each rank position.
        attracts: Dictionary mapping (query, doc_id) tuples to attractiveness values.
    """

    def __init__(self):
        """Initialize a PBM model with default values.

        Initializes examination probabilities to 0.4 for all ranks and
        attractiveness values to 0.5 for all query-document pairs.
        """
        # Examine prob per-rank
        self.ranks = defaultlist(lambda: 0.4)

        # Attractiveness per query-doc
        self.attracts = defaultdict(lambda: 0.5)


def update_attractiveness(sessions, model):
    """Update document attractiveness based on session clicks and examination probabilities.

    Runs one step of the Expectation Maximization algorithm to update attractiveness
    values for query-document pairs based on observed clicks and current rank-based
    examination probabilities.

    Args:
        sessions: List of search session objects containing queries and clicked documents.
        model: PBM Model object to update. The model.attracts dictionary will be modified.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4 of
        "Click Models for Web Search" by Chuklin, Markov, de Rijke.
    """
    attractions = Counter()  # Track query-doc attractiveness in this round
    num_sessions = Counter()  # Track num sessions where query-doc appears
    for session in sessions:
        for rank, doc in enumerate(session.docs):
            query_doc_key = (session.query, doc.doc_id)
            att = 0
            if doc.click:
                # By PBM rules, if its clicked,
                # the user thought it was attractive
                att = 1
            else:
                exam = model.ranks[rank]
                assert exam <= 1.0
                doc_a = model.attracts[query_doc_key]
                # Not examined, but attractive /
                # 1 - (examined and attractive)
                # When not clicked:
                #  If somehow this is currently a rank examined
                #  a lot and this doc is historically attractive, then
                #  we might still count it as mostly attractive
                # OR if the doc IS examined a lot AND its not
                #  attractive, then we do the opposite, add
                #  close to 0
                att = ((1 - exam) * doc_a) / (1 - (exam * doc_a))

            # Store away a_sum and
            assert att <= 1.0
            attractions[query_doc_key] += att
            num_sessions[query_doc_key] += 1
            assert attractions[query_doc_key] <= num_sessions[query_doc_key]

    # Update the main query attractiveness from the attractions / num sessions
    for (query_id, doc_id), a_sum in attractions.items():
        query_doc_key = (query_id, doc_id)
        att = a_sum / num_sessions[query_doc_key]
        assert att <= 1.0
        model.attracts[query_doc_key] = att


def update_examines(sessions, model):
    """Update position-based examination probabilities.

    Runs one step of the Expectation Maximization algorithm to update
    examination probabilities for each rank position based on observed
    clicks and current query-document attractiveness values.

    Args:
        sessions: List of search session objects containing queries and clicked documents.
        model: PBM Model object to update. The model.ranks dictionary will be modified.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4 of
        "Click Models for Web Search" by Chuklin, Markov, de Rijke.
    """
    new_rank_probs = defaultlist(lambda: 0)

    for session in sessions:
        for rank, doc in enumerate(session.docs):
            if doc.click:
                new_rank_probs[rank] += 1
            else:
                # attractiveness at this query/doc pair
                a_qd = model.attracts[(session.query, doc.doc_id)]
                numerator = (1 - a_qd) * model.ranks[rank]
                denominator = 1 - (a_qd * model.ranks[rank])
                # When not clicked - was it examined? We have to guess!
                #  - If it has seemed very attractive, we assume it
                #    was not examined. Because who could pass up such
                #    a yummy looking search result? (numerator)
                #
                #  - If its not attractive, but this rank gets examined
                #    a lot, the new rank prob is closer to 1
                #    (approaches ranks[rank] / ranks[rank])
                #
                #  - If its not examined much, wont contribute much
                new_rank_probs[rank] += numerator / denominator
    for i in range(len(new_rank_probs)):
        model.ranks[i] = new_rank_probs[i] / len(sessions)


def position_based_model(sessions, rounds=20):
    """Train a Position-Based Model using Expectation Maximization.

    Iteratively updates examination probabilities and document attractiveness
    values until convergence or the specified number of rounds is reached.

    Args:
        sessions: List of search session objects containing queries and clicked documents.
        rounds: Number of EM iterations to perform (default: 20).

    Returns:
        Model: Trained PBM model with updated examination probabilities and
            attractiveness values.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4
        (table 4.1) of "Click Models for Web Search" by Chuklin, Markov, de Rijke.
        The model is initialized with:
        - Examination probability of 0.4 for each rank position
        - Attractiveness of 0.5 for each query-document pair
    """
    model = Model()
    for _ in range(rounds):
        update_attractiveness(sessions, model)
        update_examines(sessions, model)
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
    position_based_model(sessions, rounds=100)
