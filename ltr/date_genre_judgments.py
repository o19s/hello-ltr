"""Genre-based judgment generation for training sets.

This module provides functions for generating relevance judgments based on
movie genres and release dates, creating synthetic training data for
Learn-to-Rank models.
"""

from __future__ import annotations

from tqdm import tqdm

from ltr.client.base_client import BaseClient
from ltr.judgments import Judgment, judgments_to_file
from ltr.logger import get_logger
from ltr.types import JSONDict

logger = get_logger(__name__)


def genre_qid(genre: str) -> int:
    """Map genre name to query ID.

    Args:
        genre: Genre name string.

    Returns:
        int: Query ID:
            - 1 for "Science Fiction"
            - 2 for "Drama"
            - 0 for all other genres
    """
    if genre == "Science Fiction":
        return 1
    if genre == "Drama":
        return 2
    else:
        return 0


def genre_grade(movie: JSONDict) -> int:
    """Calculate relevance grade for a movie based on genre and release date.

    Creates a simple training set where:
    - Newer Science Fiction movies are considered more relevant
    - Older Drama movies are considered more relevant

    Args:
        movie: Movie dictionary containing 'genres' and 'release_year' fields.

    Returns:
        int: Relevance grade (0-4):
            - Science Fiction: Higher grades for newer movies (2015+ = 4, 2010+ = 3, etc.)
            - Drama: Higher grades for older movies (pre-1930 = 4, 1930-1950 = 3, etc.)
            - Other genres or missing data: 0
    """
    if "release_year" in movie and movie["release_year"] is not None:
        release_year = int(movie["release_year"])
    else:
        return 0
    if movie["genres"][0] == "Science Fiction":
        if release_year > 2015:
            return 4
        elif release_year > 2010:
            return 3
        elif release_year > 2000:
            return 2
        elif release_year > 1990:
            return 1
        else:
            return 0

    if movie["genres"][0] == "Drama":
        if release_year > 1990:
            return 0
        elif release_year > 1970:
            return 1
        elif release_year > 1950:
            return 2
        elif release_year > 1930:
            return 3
        else:
            return 4
    return 0


def synthesize(
    client: BaseClient,
    judgments_out_file: str = "genre_by_date_judgments.txt",
    auto_negate: bool = False,
) -> list[Judgment]:
    """Synthesize relevance judgments based on movie genres and release dates.

    Queries the search engine for all movies and generates judgments for
    Science Fiction and Drama genres based on release date relevance:
    - Science Fiction: Newer movies are more relevant
    - Drama: Older movies are more relevant

    Args:
        client: Search client instance (Elasticsearch, OpenSearch, or Solr).
        judgments_out_file: Output file path for the generated judgments
            (default: "genre_by_date_judgments.txt").
        auto_negate: If True, also creates negative judgments (grade 0) for
            movies in the opposite genre. For example, a Science Fiction movie
            will get a grade 0 judgment for Drama queries (default: False).

    Returns:
        list: List of Judgment objects that were generated and written to file.
    """
    logger.info("Generating judgments for scifi & drama movies")

    if client.name() in ["elastic", "opensearch"]:
        params = {"query": {"match_all": {}}, "size": 10000, "sort": [{"_id": "asc"}]}
    else:
        params = {"q": "*:*", "rows": 10000, "sort": "id ASC", "wt": "json"}

    resp = client.query("tmdb", params)

    # Build judgments for each film
    judgments = []
    for movie in tqdm(resp):
        if "genres" in movie and len(movie["genres"]) > 0:
            genre = movie["genres"][0]
            qid = genre_qid(genre)
            if qid == 0:
                continue
            judgment = Judgment(
                qid=qid, grade=genre_grade(movie), doc_id=movie["id"], keywords=genre
            )
            judgments.append(judgment)

            # This movie is good for its genre, but
            # a bad result for the opposite genre
            neg_genre = None
            if genre == "Science Fiction":
                neg_genre = "Drama"
            elif genre == "Drama":
                neg_genre = "Science Fiction"

            if auto_negate and neg_genre is not None:
                neg_qid = genre_qid(neg_genre)
                judgment = Judgment(
                    qid=neg_qid, grade=0, doc_id=movie["id"], keywords=neg_genre
                )
                judgments.append(judgment)

    with open(judgments_out_file, "w", encoding="utf-8") as f:
        judgments_to_file(f, judgments_list=judgments)

    return judgments
