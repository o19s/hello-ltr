"""UBM (User Browsing Model) click model implementation.

This module implements the User Browsing Model, which considers both document
attractiveness and position-based examination probability, accounting for the
user's browsing behavior including the last clicked position.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from ltr.clickmodels.session import Session, build
from ltr.types import QueryDocPair, UBMRankPair


class Model:
    """UBM model storing examination probabilities and document attractiveness.

    Attributes:
        ranks: Dictionary mapping rank positions to examination probabilities.
            Rank 0 is the first result displayed.
        attracts: Dictionary mapping (query, doc_id) tuples to attractiveness values.
    """

    def __init__(self) -> None:
        """Initialize a UBM model with default values.

        Initializes examination probabilities to 0.4 for all (last_click, rank)
        position pairs and attractiveness values to 0.5 for all query-document pairs.
        Rank 0 is the first result displayed on the page. Rank -1 indicates
        no previous click in the session.
        """
        # Examine prob per-rank
        # Rank 0 is first displayed on page
        # Rank -1 indicates no previous click
        self.ranks: defaultdict[UBMRankPair, float] = defaultdict(lambda: 0.4)

        # Attractiveness per query-doc
        self.attracts: defaultdict[QueryDocPair, float] = defaultdict(lambda: 0.5)


def update_attractiveness(sessions: list[Session], model: Model) -> None:
    """Update document attractiveness using UBM Expectation Maximization.

    Runs one step of the EM algorithm to update attractiveness values based on
    observed clicks, current rank-based examination probabilities, and the
    position of the last click in each session.

    Args:
        sessions: List of search session objects containing queries and
            clicked documents.
        model: UBM Model object to update. The model.attracts dictionary will
            be modified.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4 of
        "Click Models for Web Search" by Chuklin, Markov, de Rijke.
    """
    attractions: defaultdict[QueryDocPair, float] = defaultdict(
        lambda: 0.0
    )  # Track query-doc attractiveness in this round
    num_sessions = Counter()  # Track num sessions where query-doc appears
    for session in sessions:
        last_click = -1
        for rank, doc in enumerate(session.docs):
            query_doc_key = (session.query, doc.doc_id)
            att = 0
            if doc.click:
                last_click = rank

                att = 1
            else:
                exam = model.ranks[(last_click, rank)]
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


def update_examines(sessions: list[Session], model: Model) -> None:
    """Update position-based examination probabilities using UBM.

    Runs one step of the Expectation Maximization algorithm to update
    examination probabilities for (last_click, rank) position pairs based on
    observed clicks and current query-document attractiveness values.

    Args:
        sessions: List of search session objects containing queries and
            clicked documents.
        model: UBM Model object to update. The model.ranks dictionary will be
            modified.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4 of
        "Click Models for Web Search" by Chuklin, Markov, de Rijke.
        Unlike PBM, UBM considers the last clicked position when computing
        examination probabilities.
    """
    new_rank_probs: defaultdict[UBMRankPair, float] = defaultdict(lambda: 0.0)
    counts = defaultdict(lambda: 0)

    for session in sessions:
        last_click = -1
        for rank, doc in enumerate(session.docs):
            if doc.click:
                new_rank_probs[(last_click, rank)] += 1
                counts[(last_click, rank)] += 1
                if last_click == -1 and rank == 3:
                    print(counts[(last_click, rank)])

                last_click = rank
            else:
                # attractiveness at this query/doc pair
                a_qd = model.attracts[(session.query, doc.doc_id)]
                numerator = (1 - a_qd) * model.ranks[(last_click, rank)]
                denominator = 1 - (a_qd * model.ranks[(last_click, rank)])
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
                new_rank_probs[(last_click, rank)] += numerator / denominator
                counts[(last_click, rank)] += 1
                if last_click == -1 and rank == 3:
                    print(counts[(last_click, rank)])

    for (last_click, click), count in counts.items():
        model.ranks[(last_click, click)] = new_rank_probs[(last_click, click)] / count


def user_browse_model(sessions: list[Session], rounds: int = 20) -> Model:
    """Train a User Browsing Model using Expectation Maximization.

    Iteratively updates examination probabilities and document attractiveness
    values until convergence or the specified number of rounds is reached.
    Unlike PBM, UBM accounts for the last clicked position when computing
    examination probabilities.

    Args:
        sessions: List of search session objects containing queries and
            clicked documents.
        rounds: Number of EM iterations to perform (default: 20).

    Returns:
        Model: Trained UBM model with updated examination probabilities and
            attractiveness values.

    Note:
        Algorithm based on Expectation Maximization derived in chapter 4
        (table 4.1) of "Click Models for Web Search" by Chuklin, Markov, de Rijke.
        The model is initialized with:
        - Examination probability of 0.4 for each (last_click, rank) pair
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
            ("A", [(1, True), (2, False), (3, True), (0, False)]),
            ("B", [(5, False), (2, True), (3, True), (0, False)]),
            ("A", [(1, False), (2, False), (3, True), (0, False)]),
            ("B", [(1, False), (2, False), (3, False), (9, True)]),
            ("A", [(9, False), (2, False), (1, True), (0, True)]),
            ("B", [(6, True), (2, False), (3, True), (1, False)]),
            ("A", [(7, False), (4, True), (1, False), (3, False)]),
            ("B", [(8, True), (2, False), (3, True), (1, False)]),
            ("A", [(1, False), (4, True), (2, False), (3, False)]),
            ("B", [(7, True), (4, False), (5, True), (1, True)]),
        ]
    )
    user_browse_model(sessions, rounds=100)
