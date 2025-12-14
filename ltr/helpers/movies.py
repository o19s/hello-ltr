"""TMDB movie data loading and processing utilities.

This module provides functions for loading and processing The Movie Database (TMDB)
data for indexing into search engines. Includes memoization for efficient repeated
loading and a generator for bulk indexing operations.
"""

import json

from tqdm import tqdm


class Memoize:
    """Memoization decorator for caching function results.

    Caches function results based on arguments to avoid repeated computation.
    Adapted from:
    https://stackoverflow.com/questions/1988804/what-is-memoization-and-how-can-i-use-it-in-python

    Attributes:
        f: Function being memoized.
        memo: Dictionary cache mapping argument tuples to results.
    """

    def __init__(self, f):
        """Initialize a Memoize decorator.

        Args:
            f: Function to be memoized.
        """
        self.f = f
        self.memo = {}

    def __call__(self, *args):
        """Call the memoized function with caching.

        Args:
            *args: Arguments to pass to the memoized function.

        Returns:
            Cached result if available, otherwise computes and caches the result.

        Note:
            Warning: You may wish to do a deepcopy here if returning objects,
            as the same cached object is returned for identical arguments.
        """
        if args not in self.memo:
            self.memo[args] = self.f(*args)
        # Warning: You may wish to do a deepcopy here if returning objects
        return self.memo[args]


@Memoize
def load_movies(json_path):
    """Load TMDB movie data from JSON file with memoization.

    Args:
        json_path: Path to JSON file containing TMDB movie data.

    Returns:
        dict: Dictionary mapping movie IDs to movie data dictionaries.

    Note:
        Results are cached after first load for efficient repeated access.
    """
    with open(json_path) as f:
        return json.load(f)


def get_movie(tmdb_id, movies="data/tmdb.json"):
    """Get a single movie by TMDB ID.

    Args:
        tmdb_id: TMDB movie ID (will be converted to string).
        movies: Path to TMDB JSON file (default: "data/tmdb.json").

    Returns:
        dict: Movie data dictionary for the specified ID.
    """
    movies = load_movies(movies)
    tmdb_id = str(tmdb_id)
    return movies[tmdb_id]


def noop(src_movie, base_doc):
    """No-op enrichment function that returns the base document unchanged.

    Args:
        src_movie: Source movie data (unused).
        base_doc: Base document dictionary.

    Returns:
        dict: Unchanged base document.
    """
    return base_doc


def indexable_movies(enrich=noop, movies="data/tmdb.json"):
    """Generate TMDB movies as indexable documents.

    Processes TMDB movie data and yields documents ready for bulk indexing,
    similar to how Elasticsearch bulk indexing uses generators.

    Args:
        enrich: Function to enrich base documents with additional data.
            Takes (src_movie, base_doc) and returns enriched document (default: noop).
        movies: Path to TMDB JSON file (default: "data/tmdb.json").

    Yields:
        dict: Indexable document dictionaries containing:
            - id: Movie ID
            - title: Movie title
            - overview: Movie description
            - tagline: Movie tagline
            - directors: List of director names
            - cast: Space-separated cast member names
            - genres: List of genre names
            - release_date: Release date string
            - release_year: Release year
            - poster_path: Full URL to poster image
            - vote_average: Average vote score
            - vote_count: Number of votes

    Note:
        Movies missing required attributes are skipped silently.
        Progress is displayed using tqdm progress bar.
    """
    movies = load_movies(movies)
    idx = 0
    for movieId, tmdbMovie in tqdm(movies.items(), total=len(movies)):
        try:
            releaseDate = None
            if "release_date" in tmdbMovie and len(tmdbMovie["release_date"]) > 0:
                releaseDate = tmdbMovie["release_date"]
                releaseYear = releaseDate[0:4]

            full_poster_path = ""
            if (
                "poster_path" in tmdbMovie
                and tmdbMovie["poster_path"] is not None
                and len(tmdbMovie["poster_path"]) > 0
            ):
                full_poster_path = (
                    "https://image.tmdb.org/t/p/w185" + tmdbMovie["poster_path"]
                )

            base_doc = {
                "id": movieId,
                "title": tmdbMovie["title"],
                "overview": tmdbMovie["overview"],
                "tagline": tmdbMovie["tagline"],
                "directors": [director["name"] for director in tmdbMovie["directors"]],
                "cast": " ".join(
                    [castMember["name"] for castMember in tmdbMovie["cast"]]
                ),
                "genres": [genre["name"] for genre in tmdbMovie["genres"]],
                "release_date": releaseDate,
                "release_year": releaseYear,
                "poster_path": full_poster_path,
                "vote_average": float(tmdbMovie["vote_average"])
                if "vote_average" in tmdbMovie
                else None,
                "vote_count": int(tmdbMovie["vote_count"])
                if "vote_count" in tmdbMovie
                else 0,
            }
            yield enrich(tmdbMovie, base_doc)
            idx += 1
        except KeyError:  # Ignore any movies missing these attributes
            continue
