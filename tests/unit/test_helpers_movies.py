"""Unit tests for movies helper module."""

import json
from unittest.mock import patch

from ltr.helpers.movies import Memoize, get_movie, indexable_movies, load_movies, noop


class TestMemoize:
    """Test Memoize decorator functionality."""

    def test_memoization_caches_results(self):
        """Test that Memoize caches function results."""
        # Arrange
        call_count = [0]

        @Memoize
        def test_func(x: int) -> int:
            call_count[0] += 1
            return x * 2

        # Act
        result1 = test_func(5)
        result2 = test_func(5)  # Should use cache
        result3 = test_func(10)  # New argument

        # Assert
        assert result1 == 10
        assert result2 == 10
        assert result3 == 20
        assert call_count[0] == 2  # Called twice, not three times

    def test_memoization_different_arguments(self):
        """Test that different arguments produce different cached results."""

        # Arrange
        @Memoize
        def test_func(x: int, y: int) -> int:
            return x + y

        # Act
        result1 = test_func(1, 2)
        result2 = test_func(2, 3)
        result3 = test_func(1, 2)  # Should use cache

        # Assert
        assert result1 == 3
        assert result2 == 5
        assert result3 == 3

    def test_memoization_returns_same_object(self):
        """Test that memoization returns the same object (not a copy)."""

        # Arrange
        @Memoize
        def test_func() -> dict:
            return {"key": "value"}

        # Act
        result1 = test_func()
        result2 = test_func()

        # Assert
        assert result1 is result2  # Same object reference
        assert result1 == result2


class TestLoadMovies:
    """Test load_movies function."""

    def test_load_movies_from_file(self, tmp_path):
        """Test loading movies from a JSON file."""
        # Arrange
        movies_data = {
            "1": {"title": "Movie 1", "overview": "Description 1"},
            "2": {"title": "Movie 2", "overview": "Description 2"},
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        result = load_movies(str(json_file))

        # Assert
        assert result == movies_data
        assert "1" in result
        assert "2" in result

    def test_load_movies_memoization(self, tmp_path):
        """Test that load_movies uses memoization."""
        # Arrange
        movies_data = {"1": {"title": "Movie 1"}}
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act - First call
        result1 = load_movies(str(json_file))

        # Modify file
        json_file.write_text(json.dumps({"2": {"title": "Movie 2"}}))

        # Act - Second call (should use cache)
        result2 = load_movies(str(json_file))

        # Assert - Should return cached result, not new file content
        assert result1 == result2
        assert "1" in result2
        assert "2" not in result2


class TestGetMovie:
    """Test get_movie function."""

    def test_get_movie_by_string_id(self, tmp_path):
        """Test getting a movie by string ID."""
        # Arrange
        movies_data = {
            "123": {"title": "Test Movie", "overview": "Test description"},
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        result = get_movie("123", str(json_file))

        # Assert
        assert result == movies_data["123"]
        assert result["title"] == "Test Movie"

    def test_get_movie_by_int_id(self, tmp_path):
        """Test getting a movie by integer ID (converted to string)."""
        # Arrange
        movies_data = {
            "456": {"title": "Test Movie 2", "overview": "Test description 2"},
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        result = get_movie(456, str(json_file))

        # Assert
        assert result == movies_data["456"]
        assert result["title"] == "Test Movie 2"


class TestNoop:
    """Test noop enrichment function."""

    def test_noop_returns_base_doc_unchanged(self):
        """Test that noop returns the base document unchanged."""
        # Arrange
        src_movie = {"title": "Source Movie"}
        base_doc = {"id": "123", "title": "Base Movie"}

        # Act
        result = noop(src_movie, base_doc)

        # Assert
        assert result == base_doc
        assert result is base_doc  # Same object reference


class TestIndexableMovies:
    """Test indexable_movies generator function."""

    def test_indexable_movies_basic(self, tmp_path):
        """Test basic indexable_movies functionality."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": "/poster.jpg",
                "vote_average": 7.5,
                "vote_count": 100,
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        movie = movies[0]
        assert movie["id"] == "1"
        assert movie["title"] == "Test Movie"
        assert movie["overview"] == "Description"
        assert movie["tagline"] == "Tagline"
        assert movie["directors"] == ["Director 1"]
        assert movie["cast"] == "Actor 1"
        assert movie["genres"] == ["Action"]
        assert movie["release_date"] == "2020-01-01"
        assert movie["release_year"] == "2020"
        assert movie["poster_path"] == "https://image.tmdb.org/t/p/w185/poster.jpg"
        assert movie["vote_average"] == 7.5
        assert movie["vote_count"] == 100

    def test_indexable_movies_with_enrich(self, tmp_path):
        """Test indexable_movies with custom enrichment function."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": "/poster.jpg",
                "vote_average": 7.5,
                "vote_count": 100,
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        def enrich(src_movie: dict, base_doc: dict) -> dict:
            base_doc["enriched"] = True
            return base_doc

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(enrich=enrich, movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        assert movies[0]["enriched"] is True

    def test_indexable_movies_skips_missing_attributes(self, tmp_path):
        """Test that movies with missing required attributes are skipped."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Complete Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": "/poster.jpg",
                "vote_average": 7.5,
                "vote_count": 100,
            },
            "2": {
                # Missing required attributes
                "title": "Incomplete Movie",
            },
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1  # Only complete movie included
        assert movies[0]["id"] == "1"

    def test_indexable_movies_empty_release_date(self, tmp_path):
        """Test handling of empty release_date."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "",  # Empty
                "poster_path": "/poster.jpg",
                "vote_average": 7.5,
                "vote_count": 100,
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        assert movies[0]["release_date"] is None
        assert movies[0]["release_year"] is None

    def test_indexable_movies_none_poster_path(self, tmp_path):
        """Test handling of None poster_path."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": None,
                "vote_average": 7.5,
                "vote_count": 100,
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        assert movies[0]["poster_path"] == ""

    def test_indexable_movies_missing_vote_average(self, tmp_path):
        """Test handling of missing vote_average."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": "/poster.jpg",
                "vote_count": 100,
                # Missing vote_average
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        assert movies[0]["vote_average"] is None

    def test_indexable_movies_missing_vote_count(self, tmp_path):
        """Test handling of missing vote_count."""
        # Arrange
        movies_data = {
            "1": {
                "title": "Test Movie",
                "overview": "Description",
                "tagline": "Tagline",
                "directors": [{"name": "Director 1"}],
                "cast": [{"name": "Actor 1"}],
                "genres": [{"name": "Action"}],
                "release_date": "2020-01-01",
                "poster_path": "/poster.jpg",
                "vote_average": 7.5,
                # Missing vote_count
            }
        }
        json_file = tmp_path / "movies.json"
        json_file.write_text(json.dumps(movies_data))

        # Act
        with patch("ltr.helpers.movies.tqdm", lambda x, **kwargs: x):  # Mock tqdm
            movies = list(indexable_movies(movies_path=str(json_file)))

        # Assert
        assert len(movies) == 1
        assert movies[0]["vote_count"] == 0
