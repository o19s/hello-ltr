"""Unit tests for date/genre judgment processing."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from ltr.date_genre_judgments import genre_grade, genre_qid, synthesize


class TestGenreQid:
    """Test genre_qid function."""

    def test_science_fiction(self):
        """Test that Science Fiction maps to query ID 1."""
        # Act & Assert
        assert genre_qid("Science Fiction") == 1

    def test_drama(self):
        """Test that Drama maps to query ID 2."""
        # Act & Assert
        assert genre_qid("Drama") == 2

    def test_other_genres(self):
        """Test that other genres map to query ID 0."""
        # Act & Assert
        assert genre_qid("Action") == 0
        assert genre_qid("Comedy") == 0
        assert genre_qid("Horror") == 0
        assert genre_qid("") == 0


class TestGenreGrade:
    """Test genre_grade function."""

    def test_science_fiction_newer_movies(self):
        """Test that newer Science Fiction movies get higher grades."""
        # Arrange
        test_cases = [
            (2020, 4),  # > 2015
            (2012, 3),  # > 2010
            (2005, 2),  # > 2000
            (1995, 1),  # > 1990
            (1985, 0),  # <= 1990
        ]
        # Act & Assert
        for release_year, expected_grade in test_cases:
            movie = {"genres": ["Science Fiction"], "release_year": release_year}
            assert genre_grade(movie) == expected_grade

    def test_drama_older_movies(self):
        """Test that older Drama movies get higher grades."""
        # Arrange
        test_cases = [
            (1920, 4),  # <= 1930
            (1940, 3),  # > 1930, <= 1950
            (1960, 2),  # > 1950, <= 1970
            (1980, 1),  # > 1970, <= 1990
            (2000, 0),  # > 1990
        ]
        # Act & Assert
        for release_year, expected_grade in test_cases:
            movie = {"genres": ["Drama"], "release_year": release_year}
            assert genre_grade(movie) == expected_grade

    def test_other_genres(self):
        """Test that other genres return grade 0."""
        # Arrange
        movie = {"genres": ["Action"], "release_year": 2020}
        # Act & Assert
        assert genre_grade(movie) == 0

    def test_missing_release_year(self):
        """Test that movies without release_year return grade 0."""
        # Arrange
        movie = {"genres": ["Science Fiction"]}
        # Act & Assert
        assert genre_grade(movie) == 0

    def test_none_release_year(self):
        """Test that movies with None release_year return grade 0."""
        # Arrange
        movie = {"genres": ["Science Fiction"], "release_year": None}
        # Act & Assert
        assert genre_grade(movie) == 0

    def test_empty_genres(self):
        """Test that movies with empty genres cause IndexError."""
        # Arrange
        movie = {"genres": [], "release_year": 2020}
        # Act & Assert
        # Empty genres list will cause IndexError when accessing [0]
        with pytest.raises(IndexError):
            genre_grade(movie)

    def test_boundary_years_science_fiction(self):
        """Test boundary years for Science Fiction."""
        # Arrange
        test_cases = [
            (2016, 4),  # Just above 2015
            (2015, 3),  # Just below 2015
            (2011, 3),  # Just above 2010
            (2010, 2),  # Just below 2010
            (2001, 2),  # Just above 2000
            (2000, 1),  # Just below 2000
            (1991, 1),  # Just above 1990
            (1990, 0),  # Just below 1990
        ]
        # Act & Assert
        for release_year, expected_grade in test_cases:
            movie = {"genres": ["Science Fiction"], "release_year": release_year}
            assert genre_grade(movie) == expected_grade

    def test_boundary_years_drama(self):
        """Test boundary years for Drama."""
        # Arrange
        test_cases = [
            (1931, 3),  # Just above 1930 (> 1930, <= 1950)
            (1930, 4),  # Equal to 1930 (<= 1930)
            (1929, 4),  # Just below 1930 (<= 1930)
            (1951, 2),  # Just above 1950 (> 1950, <= 1970)
            (1950, 3),  # Equal to 1950 (> 1930, <= 1950)
            (1949, 3),  # Just below 1950 (> 1930, <= 1950)
            (1971, 1),  # Just above 1970 (> 1970, <= 1990)
            (1970, 2),  # Equal to 1970 (> 1950, <= 1970)
            (1969, 2),  # Just below 1970 (> 1950, <= 1970)
            (1991, 0),  # Just above 1990 (> 1990)
            (1990, 1),  # Equal to 1990 (> 1970, <= 1990)
            (1989, 1),  # Just below 1990 (> 1970, <= 1990)
        ]
        # Act & Assert
        for release_year, expected_grade in test_cases:
            movie = {"genres": ["Drama"], "release_year": release_year}
            assert genre_grade(movie) == expected_grade


class TestSynthesize:
    """Test synthesize function."""

    def test_synthesize_science_fiction_movies(self):
        """Test that Science Fiction movies generate judgments."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Science Fiction"], "release_year": 2020},
            {"id": "2", "genres": ["Science Fiction"], "release_year": 2010},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            judgments = synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            assert len(judgments) == 2
            assert judgments[0].qid == 1  # Science Fiction
            assert judgments[0].grade == 4  # 2020 > 2015
            assert judgments[0].docId == "1"
            assert judgments[0].keywords == "Science Fiction"
            assert judgments[1].qid == 1  # Science Fiction
            assert judgments[1].grade == 2  # 2010 > 2000, <= 2010
            assert judgments[1].docId == "2"
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_drama_movies(self):
        """Test that Drama movies generate judgments."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Drama"], "release_year": 1920},
            {"id": "2", "genres": ["Drama"], "release_year": 1950},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            judgments = synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            assert len(judgments) == 2
            assert judgments[0].qid == 2  # Drama
            assert judgments[0].grade == 4  # 1920 <= 1930
            assert judgments[0].docId == "1"
            assert judgments[1].qid == 2  # Drama
            assert judgments[1].grade == 3  # 1950 > 1930, <= 1950
            assert judgments[1].docId == "2"
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_skips_other_genres(self):
        """Test that other genres are skipped."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Action"], "release_year": 2020},
            {"id": "2", "genres": ["Comedy"], "release_year": 2010},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            judgments = synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            assert len(judgments) == 0
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_with_auto_negate(self):
        """Test that auto_negate creates negative judgments."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Science Fiction"], "release_year": 2020},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            judgments = synthesize(
                mock_client, judgments_out_file=temp_file, auto_negate=True
            )
            # Assert
            assert len(judgments) == 2
            # Positive judgment for Science Fiction
            assert judgments[0].qid == 1
            assert judgments[0].grade == 4
            assert judgments[0].keywords == "Science Fiction"
            # Negative judgment for Drama
            assert judgments[1].qid == 2
            assert judgments[1].grade == 0
            assert judgments[1].keywords == "Drama"
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_elasticsearch_client(self):
        """Test that Elasticsearch client uses correct query format."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "elastic"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Science Fiction"], "release_year": 2020},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            mock_client.query.assert_called_once()
            call_args = mock_client.query.call_args
            assert call_args[0][0] == "tmdb"
            assert "query" in call_args[0][1]
            assert call_args[0][1]["query"] == {"match_all": {}}
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_solr_client(self):
        """Test that Solr client uses correct query format."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "genres": ["Science Fiction"], "release_year": 2020},
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            mock_client.query.assert_called_once()
            call_args = mock_client.query.call_args
            assert call_args[0][0] == "tmdb"
            assert call_args[0][1]["q"] == "*:*"
        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_synthesize_missing_genres(self):
        """Test that movies without genres are skipped."""
        # Arrange
        mock_client = Mock()
        mock_client.name.return_value = "solr"
        mock_client.query.return_value = [
            {"id": "1", "release_year": 2020},  # No genres
            {"id": "2", "genres": [], "release_year": 2020},  # Empty genres
        ]
        # Act
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", delete=False, suffix=".txt"
        ) as f:
            temp_file = f.name
        try:
            judgments = synthesize(mock_client, judgments_out_file=temp_file)
            # Assert
            assert len(judgments) == 0
        finally:
            Path(temp_file).unlink(missing_ok=True)
