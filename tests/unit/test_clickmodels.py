"""
Unit tests for clickmodels modules.

Tests cover:
- cascade.py: cascade_model function
- ubm.py: user_browse_model, update_attractiveness, update_examines
- Other click model modules
"""

import pytest

from ltr.clickmodels.cascade import cascade_model
from ltr.clickmodels.session import Session, build
from ltr.clickmodels.ubm import Model as UBMModel
from ltr.clickmodels.ubm import (
    update_attractiveness,
    update_examines,
    user_browse_model,
)


class TestCascadeModel:
    """Test cascade model functionality."""

    def test_cascade_model_calculates_attractiveness(self):
        """Test cascade_model calculates attractiveness correctly."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),  # Click on doc 1, stops here
                (
                    "query1",
                    ((1, False), (2, True)),
                ),  # Doc 1 no click, doc 2 clicked, stops here
                ("query1", ((1, True), (2, False))),  # Click on doc 1, stops here
            ]
        )
        # Act
        model = cascade_model(sessions)
        # Assert
        # Doc 1: appears in all 3 sessions, clicked in 2 = 2/3
        assert model.attracts[("query1", 1)] == pytest.approx(2 / 3, rel=1e-6)
        # Doc 2: appears in session 2 only, clicked in that session = 1/1 = 1.0
        # (Cascade model stops at first click, so doc 2 only gets counted in session 2)
        assert model.attracts[("query1", 2)] == pytest.approx(1.0, rel=1e-6)

    def test_cascade_model_stops_at_first_click(self):
        """Test cascade_model stops counting at first click."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, True))),  # Should only count doc 1
            ]
        )
        # Act
        model = cascade_model(sessions)
        # Assert
        assert model.attracts[("query1", 1)] == 1.0
        # Doc 2 should not be counted (stopped at first click)
        assert ("query1", 2) not in model.attracts or model.attracts[
            ("query1", 2)
        ] == 0.0

    def test_cascade_model_no_clicks(self):
        """Test cascade_model handles sessions with no clicks."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, False), (2, False))),
            ]
        )
        # Act
        model = cascade_model(sessions)
        # Assert
        assert model.attracts[("query1", 1)] == 0.0
        assert model.attracts[("query1", 2)] == 0.0


class TestUBMModel:
    """Test User Browse Model functionality."""

    def test_user_browse_model_initializes(self):
        """Test user_browse_model initializes model."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        # Act
        model = user_browse_model(sessions, rounds=1)
        # Assert
        assert isinstance(model, UBMModel)
        assert hasattr(model, "ranks")
        assert hasattr(model, "attracts")

    def test_user_browse_model_multiple_rounds(self):
        """Test user_browse_model runs multiple rounds."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        # Act
        model = user_browse_model(sessions, rounds=5)
        # Assert
        # Model should have been updated through multiple rounds
        assert isinstance(model, UBMModel)

    def test_update_attractiveness_with_clicks(self):
        """Test update_attractiveness updates attractiveness for clicked docs."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        model = UBMModel()
        # Act
        update_attractiveness(sessions, model)
        # Assert
        # Clicked doc should have higher attractiveness
        assert model.attracts[("query1", 1)] > 0.0

    def test_update_attractiveness_bounds(self):
        """Test update_attractiveness keeps values in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        model = UBMModel()
        # Act
        update_attractiveness(sessions, model)
        # Assert
        for _key, value in model.attracts.items():
            assert 0.0 <= value <= 1.0

    def test_update_examines_updates_ranks(self):
        """Test update_examines updates rank probabilities."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        model = UBMModel()
        # Act
        update_examines(sessions, model)
        # Assert
        # Rank probabilities should be updated
        assert len(model.ranks) > 0

    def test_update_examines_bounds(self):
        """Test update_examines keeps probabilities in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True), (2, False))),
            ]
        )
        model = UBMModel()
        # Act
        update_examines(sessions, model)
        # Assert
        for _key, value in model.ranks.items():
            assert 0.0 <= value <= 1.0


class TestSessionBuild:
    """Test session building functionality."""

    def test_build_creates_sessions(self):
        """Test build creates Session objects."""
        # Arrange
        data = [
            ("query1", ((1, True), (2, False))),
        ]
        # Act
        sessions = build(data)
        # Assert
        assert len(sessions) == 1
        assert isinstance(sessions[0], Session)
        assert sessions[0].query == "query1"

    def test_build_creates_docs(self):
        """Test build creates Doc objects with correct clicks."""
        # Arrange
        data = [
            ("query1", ((1, True), (2, False))),
        ]
        # Act
        sessions = build(data)
        # Assert
        assert len(sessions[0].docs) == 2
        assert sessions[0].docs[0].doc_id == 1
        assert sessions[0].docs[0].click is True
        assert sessions[0].docs[1].doc_id == 2
        assert sessions[0].docs[1].click is False

    def test_build_multiple_sessions(self):
        """Test build creates multiple sessions."""
        # Arrange
        data = [
            ("query1", ((1, True),)),
            ("query2", ((2, False),)),
        ]
        # Act
        sessions = build(data)
        # Assert
        assert len(sessions) == 2
        assert sessions[0].query == "query1"
        assert sessions[1].query == "query2"


class TestCascadeModelEdgeCases:
    """Test cascade model edge cases."""

    def test_cascade_model_empty_sessions(self):
        """Test cascade_model handles empty sessions."""
        # Arrange
        sessions = []
        # Act
        model = cascade_model(sessions)
        # Assert
        assert len(model.attracts) == 0

    def test_cascade_model_different_queries(self):
        """Test cascade_model handles different queries separately."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True),)),
                ("query2", ((1, False),)),
            ]
        )
        # Act
        model = cascade_model(sessions)
        # Assert
        assert model.attracts[("query1", 1)] == 1.0
        assert model.attracts[("query2", 1)] == 0.0


class TestUBMModelEdgeCases:
    """Test UBM model edge cases."""

    def test_ubm_model_empty_sessions(self):
        """Test user_browse_model handles empty sessions."""
        # Arrange
        sessions = []
        # Act
        model = user_browse_model(sessions, rounds=1)
        # Assert
        assert isinstance(model, UBMModel)
        assert len(model.attracts) == 0

    def test_ubm_model_zero_rounds(self):
        """Test user_browse_model with zero rounds."""
        # Arrange
        sessions = build(
            [
                ("query1", ((1, True),)),
            ]
        )
        # Act
        model = user_browse_model(sessions, rounds=0)
        # Assert
        assert isinstance(model, UBMModel)
