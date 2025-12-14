"""Kendall's Tau rank correlation coefficient.

This module provides functions for calculating Kendall's Tau, a measure of
rank correlation between two rankings. Higher values indicate better agreement.
"""


def sign(a):
    """Get the sign of a number.

    Args:
        a: Numeric value.

    Returns:
        int: 1 if positive, -1 if negative, 0 if zero.
    """
    return (a > 0) - (a < 0)


def pairs_in_order(ranking, both_ways=True):
    """Generate all ordered pairs from a ranking.

    Args:
        ranking: List of ranked items.
        both_ways: If True, generate pairs in both directions (default: True).

    Yields:
        tuple: Tuples of (item1, item2, sign) where sign indicates order:
            - 1 if item1 comes before item2
            - -1 if item1 comes after item2

    Raises:
        AssertionError: If ranking has fewer than 2 items.
    """
    assert len(ranking) > 1
    for idx1, val1 in enumerate(ranking):
        for idx2, val2 in enumerate(ranking):
            if idx2 > idx1:
                yield val1, val2, sign(idx2 - idx1)
                if both_ways:
                    yield val2, val1, sign(idx1 - idx2)


def tau(rank1, rank2, at=4):
    """Calculate Kendall's Tau rank correlation coefficient.

    Measures the correlation between two rankings by counting concordant and
    discordant pairs. Returns a value between -1 (perfect negative correlation)
    and 1 (perfect positive correlation).

    Args:
        rank1: First ranking as a list of items.
        rank2: Second ranking as a list of items.
        at: Consider only the top 'at' items from each ranking (default: 4).

    Returns:
        float: Kendall's Tau coefficient between -1 and 1.

    Raises:
        ValueError: If either ranking is shorter than the 'at' parameter.
    """
    rank1in = {}

    if len(rank1) < at or len(rank2) < at:
        raise ValueError(f"rankings must be larger than provided at param({at})")

    # Handle 1 as a special case
    if at == 1:
        if rank1[0] == rank2[0]:
            return 1
        return -1

    rank1 = rank1[:at]
    rank2 = rank2[:at]

    # gather concordances/discords for rank1
    for val1, val2, order in pairs_in_order(rank1, both_ways=True):
        rank1in[(val1, val2)] = order

    # check rank2
    concords = 0
    discords = 0
    for val1, val2, order in pairs_in_order(rank2, both_ways=False):
        try:
            rank1order = rank1in[(val1, val2)]
            if order == rank1order:
                concords += 1
            else:
                discords += 1
        except KeyError:
            discords += 1

    return (concords - discords) / ((at * (at - 1)) / 2)


def avg_tau(rank1, rank2, at=4):
    """Calculate average Kendall's Tau across top-k positions.

    Computes the average of Kendall's Tau coefficients calculated at each
    position k from 1 to 'at', providing a measure that considers agreement
    at all top positions rather than just the full top-k.

    Args:
        rank1: First ranking as a list of items.
        rank2: Second ranking as a list of items.
        at: Consider only the top 'at' items from each ranking (default: 4).

    Returns:
        float: Average Kendall's Tau coefficient across positions 1 to 'at'.

    Raises:
        ValueError: If either ranking is shorter than the 'at' parameter.
    """
    if len(rank1) < at or len(rank2) < at:
        raise ValueError(f"rankings must be larger than provided at param({at})")

    rank1 = rank1[:at]
    rank2 = rank2[:at]

    tot = 0
    for i in range(1, at + 1):
        tot += tau(rank1, rank2, at=i)
    return tot / (at)


if __name__ == "__main__":
    print(tau([1, 2, 3, 4], [4, 3, 2, 1]))
    print(tau([1, 2, 3, 4], [1, 2, 3, 4]))
    print(tau([1, 2, 4, 3], [1, 2, 3, 4]))
    print(tau([5, 6, 7, 8], [1, 2, 3, 4]))
    print(tau([1, 2, 3, 5], [1, 2, 3, 4]))
    print(tau([5, 3, 2, 1], [4, 3, 2, 1]))
    l1 = [1, 2, 4, 3]
    l2 = [1, 2, 3, 4]
    l3 = [2, 1, 3, 4]
    print(f"avg_tau({l1},{l1},at=4) {avg_tau(l1, l1)}")
    print(f"avg_tau({l1},{l2},at=4) {avg_tau(l1, l2)}")
    print(f"avg_tau({l2},{l3},at=4) {avg_tau(l1, l3)}")
    print(f"tau({l1},{l2},at=4) {tau(l1, l2)}")
    print(f"tau({l2},{l3},at=4) {tau(l1, l3)}")
