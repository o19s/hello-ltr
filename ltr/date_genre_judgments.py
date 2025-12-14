"""Genre-based judgment generation for training sets.

This module provides functions for generating relevance judgments based on
movie genres and release dates, creating synthetic training data for
Learn-to-Rank models.
"""

from tqdm import tqdm

from .judgments import Judgment, judgments_to_file


def genreQid(genre):
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


def genreGrade(movie):
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
        releaseYear = int(movie["release_year"])
    else:
        return 0
    if movie["genres"][0] == "Science Fiction":
        if releaseYear > 2015:
            return 4
        elif releaseYear > 2010:
            return 3
        elif releaseYear > 2000:
            return 2
        elif releaseYear > 1990:
            return 1
        else:
            return 0

    if movie["genres"][0] == "Drama":
        if releaseYear > 1990:
            return 0
        elif releaseYear > 1970:
            return 1
        elif releaseYear > 1950:
            return 2
        elif releaseYear > 1930:
            return 3
        else:
            return 4
    return 0


def synthesize(
    client, judgmentsOutFile="genre_by_date_judgments.txt", autoNegate=False
):
    """Synthesize relevance judgments based on movie genres and release dates.

    Queries the search engine for all movies and generates judgments for
    Science Fiction and Drama genres based on release date relevance:
    - Science Fiction: Newer movies are more relevant
    - Drama: Older movies are more relevant

    Args:
        client: Search client instance (Elasticsearch, OpenSearch, or Solr).
        judgmentsOutFile: Output file path for the generated judgments
            (default: "genre_by_date_judgments.txt").
        autoNegate: If True, also creates negative judgments (grade 0) for
            movies in the opposite genre. For example, a Science Fiction movie
            will get a grade 0 judgment for Drama queries (default: False).

    Returns:
        list: List of Judgment objects that were generated and written to file.
    """
    print("Generating judgments for scifi & drama movies")

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
            qid = genreQid(genre)
            if qid == 0:
                continue
            judgment = Judgment(
                qid=qid, grade=genreGrade(movie), docId=movie["id"], keywords=genre
            )
            judgments.append(judgment)

            # This movie is good for its genre, but
            # a bad result for the opposite genre
            negGenre = None
            if genre == "Science Fiction":
                negGenre = "Drama"
            elif genre == "Drama":
                negGenre = "Science Fiction"

            if autoNegate and negGenre is not None:
                negQid = genreQid(negGenre)
                judgment = Judgment(
                    qid=negQid, grade=0, docId=movie["id"], keywords=negGenre
                )
                judgments.append(judgment)

    with open(judgmentsOutFile, "w") as f:
        judgments_to_file(f, judgmentsList=judgments)

    return judgments
