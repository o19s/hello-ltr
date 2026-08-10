"""TMDB movie data loading and processing utilities.

This module provides functions for loading and processing The Movie Database (TMDB)
data for indexing into search engines. Includes memoization for efficient repeated
loading and a generator for bulk indexing operations.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

from tqdm import tqdm

from ltr.compat import accepts_legacy_kwargs
from ltr.types import JSONDict, NestedJSONDict


class Memoize:
    """Memoization decorator for caching function results.

    Caches function results based on arguments to avoid repeated computation.
    Adapted from:
    https://stackoverflow.com/questions/1988804/what-is-memoization-and-how-can-i-use-it-in-python

    Attributes:
        f: Function being memoized.
        memo: Dictionary cache mapping argument tuples to results.
    """

    def __init__(self, f: Callable[..., Any]) -> None:
        """Initialize a Memoize decorator.

        Args:
            f: Function to be memoized.
        """
        self.f: Callable[..., Any] = f
        self.memo: dict[tuple[Any, ...], Any] = {}

    def __call__(self, *args: Any) -> Any:
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
def load_movies(json_path: str) -> NestedJSONDict:
    """Load TMDB movie data from JSON file with memoization.

    Args:
        json_path: Path to JSON file containing TMDB movie data.

    Returns:
        dict: Dictionary mapping movie IDs to movie data dictionaries.

    Note:
        Results are cached after first load for efficient repeated access.
    """
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


@accepts_legacy_kwargs(movies="movies_path")
def get_movie(tmdb_id: str | int, movies_path: str = "data/tmdb.json") -> JSONDict:
    """Get a single movie by TMDB ID.

    Args:
        tmdb_id: TMDB movie ID (will be converted to string).
        movies_path: Path to TMDB JSON file (default: "data/tmdb.json").

    Returns:
        dict: Movie data dictionary for the specified ID.
    """
    movies_dict = load_movies(movies_path)
    tmdb_id_str = str(tmdb_id)
    return movies_dict[tmdb_id_str]


def noop(src_movie: JSONDict, base_doc: JSONDict) -> JSONDict:
    """No-op enrichment function that returns the base document unchanged.

    Args:
        src_movie: Source movie data (unused).
        base_doc: Base document dictionary.

    Returns:
        dict: Unchanged base document.
    """
    return base_doc


@accepts_legacy_kwargs(movies="movies_path")
def indexable_movies(
    enrich: Callable[[JSONDict, JSONDict], JSONDict] = noop,
    movies_path: str = "data/tmdb.json",
) -> Iterator[JSONDict]:
    """Generate TMDB movies as indexable documents.

    Processes TMDB movie data and yields documents ready for bulk indexing,
    similar to how Elasticsearch bulk indexing uses generators.

    Args:
        enrich: Function to enrich base documents with additional data.
            Takes (src_movie, base_doc) and returns enriched document (default: noop).
        movies_path: Path to TMDB JSON file (default: "data/tmdb.json").

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
    movies_dict = load_movies(movies_path)
    idx = 0
    for movie_id, tmdb_movie in tqdm(movies_dict.items(), total=len(movies_dict)):
        try:
            release_date = None
            release_year = None
            if "release_date" in tmdb_movie and len(tmdb_movie["release_date"]) > 0:
                release_date = tmdb_movie["release_date"]
                release_year = release_date[0:4]

            full_poster_path = ""
            if (
                "poster_path" in tmdb_movie
                and tmdb_movie["poster_path"] is not None
                and len(tmdb_movie["poster_path"]) > 0
            ):
                full_poster_path = (
                    "https://image.tmdb.org/t/p/w185" + tmdb_movie["poster_path"]
                )

            base_doc = {
                "id": movie_id,
                "title": tmdb_movie["title"],
                "overview": tmdb_movie["overview"],
                "tagline": tmdb_movie["tagline"],
                "directors": [director["name"] for director in tmdb_movie["directors"]],
                "cast": " ".join(
                    [castMember["name"] for castMember in tmdb_movie["cast"]]
                ),
                "genres": [genre["name"] for genre in tmdb_movie["genres"]],
                "release_date": release_date,
                "release_year": release_year,
                "poster_path": full_poster_path,
                "vote_average": float(tmdb_movie["vote_average"])
                if "vote_average" in tmdb_movie
                else None,
                "vote_count": int(tmdb_movie["vote_count"])
                if "vote_count" in tmdb_movie
                else 0,
            }
            yield enrich(tmdb_movie, base_doc)
            idx += 1
        except KeyError:  # Ignore any movies missing these attributes
            continue
