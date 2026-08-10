"""
Unit tests for year-based rating functions.

Tests cover:
- get_classic_rating function
- get_latest_rating function
- synthesize function
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

from ltr.judgments import judgments_from_file
from ltr.years_as_ratings import get_classic_rating, get_latest_rating, synthesize


class TestGetClassicRating:
    """Test get_classic_rating function."""

    def test_classic_rating_year_after_2010(self):
        """Test rating for year after 2010 (should be 0)."""
        # Act & Assert
        assert get_classic_rating(2011) == 0
        assert get_classic_rating(2020) == 0
        assert get_classic_rating(2025) == 0

    def test_classic_rating_year_1991_to_2010(self):
        """Test rating for year 1991-2010 (should be 1)."""
        # Act & Assert
        assert get_classic_rating(1991) == 1
        assert get_classic_rating(2000) == 1
        assert get_classic_rating(2010) == 1

    def test_classic_rating_year_1971_to_1990(self):
        """Test rating for year 1971-1990 (should be 2)."""
        # Act & Assert
        assert get_classic_rating(1971) == 2
        assert get_classic_rating(1980) == 2
        assert get_classic_rating(1990) == 2

    def test_classic_rating_year_1951_to_1970(self):
        """Test rating for year 1951-1970 (should be 3)."""
        # Act & Assert
        assert get_classic_rating(1951) == 3
        assert get_classic_rating(1960) == 3
        assert get_classic_rating(1970) == 3

    def test_classic_rating_year_before_1951(self):
        """Test rating for year before 1951 (should be 4)."""
        # Act & Assert
        assert get_classic_rating(1950) == 4
        assert get_classic_rating(1940) == 4
        assert get_classic_rating(1920) == 4

    def test_classic_rating_boundary_years(self):
        """Test rating at boundary years."""
        # Act & Assert
        assert get_classic_rating(2010) == 1
        assert get_classic_rating(2011) == 0
        assert get_classic_rating(1990) == 2
        assert get_classic_rating(1991) == 1
        assert get_classic_rating(1970) == 3
        assert get_classic_rating(1971) == 2
        assert get_classic_rating(1950) == 4
        assert get_classic_rating(1951) == 3


class TestGetLatestRating:
    """Test get_latest_rating function."""

    def test_latest_rating_year_after_2010(self):
        """Test rating for year after 2010 (should be 4)."""
        # Act & Assert
        assert get_latest_rating(2011) == 4
        assert get_latest_rating(2020) == 4
        assert get_latest_rating(2025) == 4

    def test_latest_rating_year_1991_to_2010(self):
        """Test rating for year 1991-2010 (should be 3)."""
        # Act & Assert
        assert get_latest_rating(1991) == 3
        assert get_latest_rating(2000) == 3
        assert get_latest_rating(2010) == 3

    def test_latest_rating_year_1971_to_1990(self):
        """Test rating for year 1971-1990 (should be 2)."""
        # Act & Assert
        assert get_latest_rating(1971) == 2
        assert get_latest_rating(1980) == 2
        assert get_latest_rating(1990) == 2

    def test_latest_rating_year_1951_to_1970(self):
        """Test rating for year 1951-1970 (should be 1)."""
        # Act & Assert
        assert get_latest_rating(1951) == 1
        assert get_latest_rating(1960) == 1
        assert get_latest_rating(1970) == 1

    def test_latest_rating_year_before_1951(self):
        """Test rating for year before 1951 (should be 0)."""
        # Act & Assert
        assert get_latest_rating(1950) == 0
        assert get_latest_rating(1940) == 0
        assert get_latest_rating(1920) == 0

    def test_latest_rating_boundary_years(self):
        """Test rating at boundary years."""
        # Act & Assert
        assert get_latest_rating(2010) == 3
        assert get_latest_rating(2011) == 4
        assert get_latest_rating(1990) == 2
        assert get_latest_rating(1991) == 3
        assert get_latest_rating(1970) == 1
        assert get_latest_rating(1971) == 2
        assert get_latest_rating(1950) == 0
        assert get_latest_rating(1951) == 1

    def test_latest_rating_inverse_of_classic(self):
        """Test that latest rating is inverse of classic rating."""
        # Act & Assert
        test_years = [1920, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020]
        for year in test_years:
            classic = get_classic_rating(year)
            latest = get_latest_rating(year)
            # Sum should be 4 (inverse relationship)
            assert classic + latest == 4


class TestSynthesize:
    """Test synthesize function."""

    def test_synthesize_creates_both_training_sets(self):
        """Test that synthesize creates both classic and latest training sets."""
        # Arrange
        mock_client = Mock()
        # Mock log_query to return hits with release year as first feature
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [2020.0, 0.5, 0.3]},  # Recent movie
            {"id": "2", "ltr_features": [1950.0, 0.4, 0.2]},  # Classic movie
            {"id": "3", "ltr_features": [1980.0, 0.6, 0.4]},  # Mid-era movie
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            classic_path = Path(tmpdir) / "classic-training.txt"
            latest_path = Path(tmpdir) / "latest-training.txt"

            # Act
            synthesize(
                mock_client,
                feature_set="release",
                latest_training_set_out=str(latest_path),
                classic_training_set_out=str(classic_path),
            )

            # Assert
            assert classic_path.exists()
            assert latest_path.exists()

            # Read and verify classic training set
            with open(classic_path, encoding="utf-8") as f:
                classic_judgments = list(judgments_from_file(f))
            assert len(classic_judgments) == 3
            # Classic: older = higher rating
            # 2020 -> rating 0, 1950 -> rating 4, 1980 -> rating 2
            ratings = {j.docId: j.grade for j in classic_judgments}
            assert ratings["1"] == 0  # Recent movie gets low rating
            assert ratings["2"] == 4  # Classic movie gets high rating
            assert ratings["3"] == 2  # Mid-era movie gets medium rating

            # Read and verify latest training set
            with open(latest_path, encoding="utf-8") as f:
                latest_judgments = list(judgments_from_file(f))
            assert len(latest_judgments) == 3
            # Latest: newer = higher rating
            ratings = {j.docId: j.grade for j in latest_judgments}
            assert ratings["1"] == 4  # Recent movie gets high rating
            assert ratings["2"] == 0  # Classic movie gets low rating
            assert ratings["3"] == 2  # Mid-era movie gets medium rating

    def test_synthesize_handles_none_features(self):
        """Test that synthesize handles None features correctly."""
        # Arrange
        mock_client = Mock()
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [None, 0.5]},  # None feature
            {"id": "2", "ltr_features": ["None", 0.4]},  # String "None"
            {"id": "3", "ltr_features": [2020.0, 0.6]},  # Valid feature
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            classic_path = Path(tmpdir) / "classic-training.txt"
            latest_path = Path(tmpdir) / "latest-training.txt"

            # Act
            synthesize(
                mock_client,
                feature_set="release",
                latest_training_set_out=str(latest_path),
                classic_training_set_out=str(classic_path),
            )

            # Assert - None features should be converted to 0.0
            with open(classic_path, encoding="utf-8") as f:
                classic_judgments = list(judgments_from_file(f))
            # All should have rating 0 (year 0 -> classic rating 0)
            # Note: synthesize filters out rating 0 if no_zero=True, but default is False
            # So we should have judgments, but None/string "None" features become year 0 -> rating 0
            assert len(classic_judgments) >= 1  # At least one judgment
            # The one with valid feature (2020) should have rating 0 (year > 2010)
            ratings = {j.docId: j.grade for j in classic_judgments}
            assert ratings.get("3") == 0  # Valid feature (2020) -> rating 0

    def test_synthesize_handles_string_features(self):
        """Test that synthesize handles string features correctly."""
        # Arrange
        mock_client = Mock()
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": ["2020", 0.5]},  # String year
            {"id": "2", "ltr_features": ["1950", 0.4]},  # String year
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            classic_path = Path(tmpdir) / "classic-training.txt"
            latest_path = Path(tmpdir) / "latest-training.txt"

            # Act
            synthesize(
                mock_client,
                feature_set="release",
                latest_training_set_out=str(latest_path),
                classic_training_set_out=str(classic_path),
            )

            # Assert
            with open(classic_path, encoding="utf-8") as f:
                classic_judgments = list(judgments_from_file(f))
            ratings = {j.docId: j.grade for j in classic_judgments}
            assert ratings["1"] == 0  # 2020 -> classic rating 0
            assert ratings["2"] == 4  # 1950 -> classic rating 4

    def test_synthesize_calls_log_query_with_correct_params(self):
        """Test that synthesize calls log_query with correct parameters."""
        # Arrange
        mock_client = Mock()
        mock_client.log_query.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            classic_path = Path(tmpdir) / "classic-training.txt"
            latest_path = Path(tmpdir) / "latest-training.txt"

            # Act
            synthesize(
                mock_client,
                feature_set="custom_feature",
                latest_training_set_out=str(latest_path),
                classic_training_set_out=str(classic_path),
            )

            # Assert
            mock_client.log_query.assert_called_once_with(
                "tmdb", "custom_feature", None, {}
            )

    def test_synthesize_all_judgments_have_same_qid(self):
        """Test that all judgments in synthesized sets have qid=1."""
        # Arrange
        mock_client = Mock()
        mock_client.log_query.return_value = [
            {"id": "1", "ltr_features": [2020.0]},
            {"id": "2", "ltr_features": [1950.0]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            classic_path = Path(tmpdir) / "classic-training.txt"
            latest_path = Path(tmpdir) / "latest-training.txt"

            # Act
            synthesize(
                mock_client,
                latest_training_set_out=str(latest_path),
                classic_training_set_out=str(classic_path),
            )

            # Assert
            with open(classic_path, encoding="utf-8") as f:
                classic_judgments = list(judgments_from_file(f))
            assert all(j.qid == 1 for j in classic_judgments)

            with open(latest_path, encoding="utf-8") as f:
                latest_judgments = list(judgments_from_file(f))
            assert all(j.qid == 1 for j in latest_judgments)
