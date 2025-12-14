"""Year-based rating synthesis for training data generation.

This module provides functions for generating relevance ratings based on movie
release years, creating synthetic training sets with different preferences
(classic movies vs. latest movies).
"""


def get_classic_rating(year):
    """Get relevance rating for classic movie preference.

    Older movies receive higher ratings, with the highest rating (4) for
    movies from 1950 or earlier.

    Args:
        year: Release year of the movie.

    Returns:
        int: Relevance rating (0-4):
            - 0: Year > 2010
            - 1: Year 1991-2010
            - 2: Year 1971-1990
            - 3: Year 1951-1970
            - 4: Year <= 1950
    """
    if year > 2010:
        return 0
    elif year > 1990:
        return 1
    elif year > 1970:
        return 2
    elif year > 1950:
        return 3
    else:
        return 4


def get_latest_rating(year):
    """Get relevance rating for latest movie preference.

    Newer movies receive higher ratings, with the highest rating (4) for
    movies from 2011 or later.

    Args:
        year: Release year of the movie.

    Returns:
        int: Relevance rating (0-4):
            - 4: Year > 2010
            - 3: Year 1991-2010
            - 2: Year 1971-1990
            - 1: Year 1951-1970
            - 0: Year <= 1950
    """
    if year > 2010:
        return 4
    elif year > 1990:
        return 3
    elif year > 1970:
        return 2
    elif year > 1950:
        return 1
    else:
        return 0


def synthesize(
    client,
    featureSet="release",
    latestTrainingSetOut="data/latest-training.txt",
    classicTrainingSetOut="data/classic-training.txt",
):
    """Synthesize training sets with different year-based preferences.

    Generates two training sets from the same documents:
    - Classic preference: Older movies get higher ratings
    - Latest preference: Newer movies get higher ratings

    Args:
        client: Search client instance.
        featureSet: Name of the feature set to use for logging (default: "release").
        latestTrainingSetOut: Output file path for latest-preference training set
            (default: "data/latest-training.txt").
        classicTrainingSetOut: Output file path for classic-preference training set
            (default: "data/classic-training.txt").

    Returns:
        None: Training sets are written to the specified output files.

    Note:
        Uses the first feature value (release year) from logged features to
        determine relevance ratings. Documents with rating 0 may be filtered out
        if NO_ZERO is set to True.
    """
    from ltr.judgments import Judgment, judgments_to_file

    NO_ZERO = False

    resp = client.log_query("tmdb", "release", None)

    # A classic film fan
    judgments = []
    print("Generating 'classic' biased judgments:")
    for hit in resp:
        rating = get_classic_rating(hit["ltr_features"][0])

        if rating == 0 and NO_ZERO:
            continue

        judgments.append(
            Judgment(
                qid=1,
                docId=hit["id"],
                grade=rating,
                features=hit["ltr_features"],
                keywords="",
            )
        )

    with open(classicTrainingSetOut, "w") as out:
        judgments_to_file(out, judgments)

    # A current film fan
    judgments = []
    print("Generating 'recent' biased judgments:")
    for hit in resp:
        rating = get_latest_rating(hit["ltr_features"][0])

        if rating == 0 and NO_ZERO:
            continue

        judgments.append(
            Judgment(
                qid=1,
                docId=hit["id"],
                grade=rating,
                features=hit["ltr_features"],
                keywords="",
            )
        )

    with open(latestTrainingSetOut, "w") as out:
        judgments_to_file(out, judgments)
