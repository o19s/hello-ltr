"""Unit tests for the legacy-keyword compatibility shim.

Tests cover:
- accepts_legacy_kwargs decorator behaviour
- the public functions that carry legacy keyword aliases
"""

# The shim deliberately preserves each wrapped function's real signature, so
# pyright correctly rejects the deprecated keyword names everywhere else in the
# codebase. This file is the one place that must call them on purpose.
# pyright: reportCallIssue=false

import inspect
import io
import json
import warnings

import pytest

from ltr.compat import accepts_legacy_kwargs
from ltr.helpers.movies import indexable_movies
from ltr.judgments import Judgment, judgments_to_file
from ltr.ranklib import feature_search, save_model, train
from ltr.search import search

# Every legacy keyword that published blog posts and book chapters may still use,
# paired with the current name it forwards to.
LEGACY_ALIASES = [
    (search, "modelName", "model_name"),
    (train, "modelName", "model_name"),
    (train, "featureSet", "feature_set"),
    (save_model, "modelName", "model_name"),
    (save_model, "modelFile", "model_file"),
    (save_model, "featureSet", "feature_set"),
    (feature_search, "featureSet", "feature_set"),
    (feature_search, "featureCost", "feature_cost"),
    (judgments_to_file, "judgmentsList", "judgments_list"),
    (indexable_movies, "movies", "movies_path"),
]


class TestAcceptsLegacyKwargs:
    """Test the accepts_legacy_kwargs decorator."""

    @staticmethod
    def _decorated():
        @accepts_legacy_kwargs(oldName="new_name")
        def func(new_name: str = "default") -> str:
            return new_name

        return func

    def test_legacy_keyword_is_forwarded(self):
        """Test that a legacy keyword reaches the renamed parameter."""
        # Arrange
        func = self._decorated()
        # Act
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = func(oldName="value")
        # Assert
        assert result == "value"

    def test_legacy_keyword_warns(self):
        """Test that using a legacy keyword raises a DeprecationWarning."""
        # Arrange
        func = self._decorated()
        # Act & Assert
        with pytest.warns(DeprecationWarning, match="use new_name=... instead"):
            func(oldName="value")

    def test_current_keyword_does_not_warn(self):
        """Test that the current keyword name produces no warning."""
        # Arrange
        func = self._decorated()
        # Act
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            func(new_name="value")
        # Assert
        assert caught == []

    def test_supplying_both_names_raises(self):
        """Test that passing legacy and current names together is an error."""
        # Arrange
        func = self._decorated()
        # Act & Assert
        with pytest.raises(TypeError, match="got both 'oldName' and 'new_name'"):
            func(oldName="a", new_name="b")

    def test_positional_arguments_are_untouched(self):
        """Test that positional calls pass straight through."""
        # Arrange
        func = self._decorated()
        # Act
        result = func("positional")
        # Assert
        assert result == "positional"


class TestPublicApiAliases:
    """Test that renamed public keywords still accept their legacy names."""

    @pytest.mark.parametrize(
        ("func", "legacy", "current"),
        LEGACY_ALIASES,
        ids=[f"{f.__name__}-{legacy}" for f, legacy, _ in LEGACY_ALIASES],
    )
    def test_legacy_alias_is_registered(self, func, legacy, current):
        """Test that each documented legacy keyword is still accepted."""
        # Arrange / Act
        signature = inspect.signature(func)
        # Assert - the shim rewrites `legacy` to `current`, which must exist
        assert current in signature.parameters

    def test_judgments_to_file_accepts_legacy_keyword(self):
        """Test judgments_to_file(judgmentsList=...) still writes judgments."""
        # Arrange
        judgments = [Judgment(grade=1, qid=1, keywords="rambo", doc_id="7555")]
        buffer = io.StringIO()
        # Act
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            judgments_to_file(buffer, judgmentsList=judgments)
        # Assert
        assert "rambo" in buffer.getvalue()

    def test_judgments_to_file_legacy_keyword_warns(self):
        """Test judgments_to_file warns when given the legacy keyword."""
        # Arrange
        judgments = [Judgment(grade=1, qid=1, keywords="rambo", doc_id="7555")]
        # Act & Assert
        with pytest.warns(DeprecationWarning, match="judgmentsList"):
            judgments_to_file(io.StringIO(), judgmentsList=judgments)

    def test_indexable_movies_accepts_legacy_keyword(self, tmp_path):
        """Test indexable_movies(movies=...) still resolves the corpus path."""
        # Arrange - movies missing any required attribute are skipped silently
        corpus = tmp_path / "tmdb.json"
        corpus.write_text(
            json.dumps(
                {
                    "7555": {
                        "title": "Rambo",
                        "overview": "John Rambo returns",
                        "tagline": "This time he's fighting for his life",
                        "directors": [{"name": "Sylvester Stallone"}],
                        "cast": [{"name": "Sylvester Stallone"}],
                        "genres": [{"name": "Action"}],
                        "release_date": "2008-01-24",
                        "poster_path": "/rambo.jpg",
                        "vote_average": 6.2,
                        "vote_count": 1000,
                    }
                }
            )
        )
        # Act
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            movies = list(indexable_movies(movies=str(corpus)))
        # Assert
        assert movies[0]["title"] == "Rambo"
