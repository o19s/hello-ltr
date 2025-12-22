"""Year-based rating synthesis for training data generation.

This module provides functions for generating relevance ratings based on movie
release years, creating synthetic training sets with different preferences
(classic movies vs. latest movies).
"""

from ltr.client.base_client import BaseClient
from ltr.logger import get_logger

logger = get_logger(__name__)


def get_classic_rating(year: int) -> int:
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


def get_latest_rating(year: int) -> int:
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
    client: BaseClient,
    feature_set: str = "release",
    latest_training_set_out: str = "data/latest-training.txt",
    classic_training_set_out: str = "data/classic-training.txt",
) -> None:
    """Synthesize training sets with different year-based preferences.

    Generates two training sets from the same documents:
    - Classic preference: Older movies get higher ratings
    - Latest preference: Newer movies get higher ratings

    Args:
        client: Search client instance.
        feature_set: Name of the feature set to use for logging (default: "release").
        latest_training_set_out: Output file path for latest-preference training set
            (default: "data/latest-training.txt").
        classic_training_set_out: Output file path for classic-preference training set
            (default: "data/classic-training.txt").

    Returns:
        None: Training sets are written to the specified output files.

    Note:
        Uses the first feature value (release year) from logged features to
        determine relevance ratings. Documents with rating 0 may be filtered out
        if no_zero is set to True.
    """
    from ltr.judgments import Judgment, judgments_to_file

    no_zero = False

    resp = client.log_query("tmdb", feature_set, None, {})

    # A classic film fan
    judgments = []
    logger.info("Generating 'classic' biased judgments:")
    for hit in resp:
        # Ensure all features are numeric (convert None/string "None" to 0.0)
        features = [
            0.0
            if (f is None or (isinstance(f, str) and f.lower() == "none"))
            else float(f)
            if isinstance(f, (int, float, str))
            else 0.0
            for f in hit["ltr_features"]
        ]
        rating = get_classic_rating(int(features[0]))

        if rating == 0 and no_zero:
            continue

        judgments.append(
            Judgment(
                qid=1,
                doc_id=hit["id"],
                grade=rating,
                features=features,
                keywords="",
            )
        )

    with open(classic_training_set_out, "w") as out:
        judgments_to_file(out, judgments)

    # A current film fan
    judgments = []
    logger.info("Generating 'recent' biased judgments:")
    for hit in resp:
        # Ensure all features are numeric (convert None/string "None" to 0.0)
        features = [
            0.0
            if (f is None or (isinstance(f, str) and f.lower() == "none"))
            else float(f)
            if isinstance(f, (int, float, str))
            else 0.0
            for f in hit["ltr_features"]
        ]
        rating = get_latest_rating(int(features[0]))

        if rating == 0 and no_zero:
            continue

        judgments.append(
            Judgment(
                qid=1,
                doc_id=hit["id"],
                grade=rating,
                features=features,
                keywords="",
            )
        )

    with open(latest_training_set_out, "w") as out:
        judgments_to_file(out, judgments)
