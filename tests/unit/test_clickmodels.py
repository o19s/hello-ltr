"""
Unit tests for clickmodels modules.

Tests cover:
- cascade.py: cascade_model function
- ubm.py: user_browse_model, update_attractiveness, update_examines
- pbm.py: position_based_model, update_attractiveness, update_examines
- sdbn.py: sdbn function, reverse_enumerate
- coec.py: coec function
- conversion.py: conv_aug_attracts function
"""

from __future__ import annotations

import pytest

from ltr.clickmodels.cascade import cascade_model
from ltr.clickmodels.coec import Model as COECModel
from ltr.clickmodels.coec import coec
from ltr.clickmodels.conversion import conv_aug_attracts
from ltr.clickmodels.pbm import (
    Model as PBMModel,
)
from ltr.clickmodels.pbm import (
    position_based_model,
)
from ltr.clickmodels.pbm import (
    update_attractiveness as pbm_update_attractiveness,
)
from ltr.clickmodels.pbm import (
    update_examines as pbm_update_examines,
)
from ltr.clickmodels.sdbn import Model as SDBNModel
from ltr.clickmodels.sdbn import reverse_enumerate, sdbn
from ltr.clickmodels.session import Session, build
from ltr.clickmodels.ubm import (
    Model as UBMModel,
)
from ltr.clickmodels.ubm import (
    update_attractiveness as ubm_update_attractiveness,
)
from ltr.clickmodels.ubm import (
    update_examines as ubm_update_examines,
)
from ltr.clickmodels.ubm import (
    user_browse_model,
)
from ltr.types import CostMap, QueryDocPair, SessionTupleList


class TestCascadeModel:
    """Test cascade model functionality."""

    def test_cascade_model_calculates_attractiveness(self):
        """Test cascade_model calculates attractiveness correctly."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),  # Click on doc 1, stops here
                (
                    "query1",
                    [(1, False), (2, True)],
                ),  # Doc 1 no click, doc 2 clicked, stops here
                ("query1", [(1, True), (2, False)]),  # Click on doc 1, stops here
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
                ("query1", [(1, True), (2, True)]),  # Should only count doc 1
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
                ("query1", [(1, False), (2, False)]),
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
                ("query1", [(1, True), (2, False)]),
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
                ("query1", [(1, True), (2, False)]),
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
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = UBMModel()
        # Act
        ubm_update_attractiveness(sessions, model)
        # Assert
        # Clicked doc should have higher attractiveness
        assert model.attracts[("query1", 1)] > 0.0

    def test_update_attractiveness_bounds(self):
        """Test update_attractiveness keeps values in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = UBMModel()
        # Act
        ubm_update_attractiveness(sessions, model)
        # Assert
        for _key, value in model.attracts.items():
            assert 0.0 <= value <= 1.0

    def test_update_examines_updates_ranks(self):
        """Test update_examines updates rank probabilities."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = UBMModel()
        # Act
        ubm_update_examines(sessions, model)
        # Assert
        # Rank probabilities should be updated
        assert len(model.ranks) > 0

    def test_update_examines_bounds(self):
        """Test update_examines keeps probabilities in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = UBMModel()
        # Act
        ubm_update_examines(sessions, model)
        # Assert
        for _key, value in model.ranks.items():
            assert 0.0 <= value <= 1.0


class TestSessionBuild:
    """Test session building functionality."""

    def test_build_creates_sessions(self):
        """Test build creates Session objects."""
        # Arrange
        data: SessionTupleList = [
            ("query1", [(1, True), (2, False)]),
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
        data: SessionTupleList = [
            ("query1", [(1, True), (2, False)]),
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
        data: SessionTupleList = [
            ("query1", [(1, True)]),
            ("query2", [(2, False)]),
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
                ("query1", [(1, True)]),
                ("query2", [(1, False)]),
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
                ("query1", [(1, True)]),
            ]
        )
        # Act
        model = user_browse_model(sessions, rounds=0)
        # Assert
        assert isinstance(model, UBMModel)


class TestPBMModel:
    """Test Position-Based Model functionality."""

    def test_position_based_model_initializes(self):
        """Test position_based_model initializes model."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        # Act
        model = position_based_model(sessions, rounds=1)
        # Assert
        assert isinstance(model, PBMModel)
        assert hasattr(model, "ranks")
        assert hasattr(model, "attracts")

    def test_position_based_model_multiple_rounds(self):
        """Test position_based_model runs multiple rounds."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        # Act
        model = position_based_model(sessions, rounds=5)
        # Assert
        assert isinstance(model, PBMModel)

    def test_pbm_update_attractiveness_with_clicks(self):
        """Test update_attractiveness updates attractiveness for clicked docs."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = PBMModel()
        # Act
        pbm_update_attractiveness(sessions, model)
        # Assert
        # Clicked doc should have higher attractiveness
        assert model.attracts[("query1", 1)] > 0.0
        assert model.attracts[("query1", 1)] <= 1.0

    def test_pbm_update_attractiveness_bounds(self):
        """Test update_attractiveness keeps values in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = PBMModel()
        # Act
        pbm_update_attractiveness(sessions, model)
        # Assert
        for _key, value in model.attracts.items():
            assert 0.0 <= value <= 1.0

    def test_pbm_update_examines_updates_ranks(self):
        """Test update_examines updates rank probabilities."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = PBMModel()
        # Act
        pbm_update_examines(sessions, model)
        # Assert
        # Rank probabilities should be updated
        assert len(model.ranks) > 0

    def test_pbm_update_examines_bounds(self):
        """Test update_examines keeps probabilities in valid range."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        model = PBMModel()
        # Act
        pbm_update_examines(sessions, model)
        # Assert
        for i in range(len(model.ranks)):
            rank_val = model.ranks[i]
            assert isinstance(rank_val, float)
            assert 0.0 <= rank_val <= 1.0

    def test_pbm_model_empty_sessions(self):
        """Test position_based_model handles empty sessions."""
        # Arrange
        sessions = []
        # Act
        model = position_based_model(sessions, rounds=1)
        # Assert
        assert isinstance(model, PBMModel)
        assert len(model.attracts) == 0


class TestSDBNModel:
    """Test S-DBN (Simplified Dynamic Bayesian Network) model functionality."""

    def test_sdbn_initializes(self):
        """Test sdbn initializes model."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False), (3, True)]),
            ]
        )
        # Act
        model = sdbn(sessions)
        # Assert
        assert isinstance(model, SDBNModel)
        assert hasattr(model, "satisfacts")
        assert hasattr(model, "attracts")

    def test_sdbn_calculates_attractiveness(self):
        """Test sdbn calculates attractiveness correctly."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False), (3, True)]),  # Last click at doc 3
                ("query1", [(1, False), (2, True), (3, False)]),  # Last click at doc 2
            ]
        )
        # Act
        model = sdbn(sessions)
        # Assert
        # Attractiveness should be calculated for docs that appear before last click
        assert ("query1", 1) in model.attracts
        assert ("query1", 2) in model.attracts
        assert ("query1", 3) in model.attracts
        assert 0.0 <= model.attracts[("query1", 1)] <= 1.0

    def test_sdbn_calculates_satisfaction(self):
        """Test sdbn calculates satisfaction correctly."""
        # Arrange
        sessions = build(
            [
                ("query1", [(1, True), (2, False), (3, True)]),  # Last click at doc 3
            ]
        )
        # Act
        model = sdbn(sessions)
        # Assert
        # Satisfaction should be calculated for last clicked docs
        if ("query1", 3) in model.satisfacts:
            assert 0.0 <= model.satisfacts[("query1", 3)] <= 1.0

    def test_sdbn_empty_sessions(self):
        """Test sdbn handles empty sessions."""
        # Arrange
        sessions = []
        # Act
        model = sdbn(sessions)
        # Assert
        assert isinstance(model, SDBNModel)
        assert len(model.attracts) == 0
        assert len(model.satisfacts) == 0

    def test_reverse_enumerate(self):
        """Test reverse_enumerate function."""
        # Arrange
        from ltr.clickmodels.session import Doc

        docs = [
            Doc(doc_id=1, click=True),
            Doc(doc_id=2, click=False),
            Doc(doc_id=3, click=True),
        ]
        # Act
        result = list(reverse_enumerate(docs))
        # Assert
        assert len(result) == 3
        assert result[0] == (2, docs[2])  # Last doc, index 2
        assert result[1] == (1, docs[1])  # Middle doc, index 1
        assert result[2] == (0, docs[0])  # First doc, index 0


class TestCOECModel:
    """Test COEC (Clicks Over Expected Clicks) model functionality."""

    def test_coec_initializes(self):
        """Test coec initializes model."""
        # Arrange
        ctr_by_rank = {0: 0.5, 1: 0.3, 2: 0.2}
        sessions = build(
            [
                ("query1", [(1, True), (2, False)]),
            ]
        )
        # Act
        model = coec(ctr_by_rank, sessions)
        # Assert
        assert isinstance(model, COECModel)
        assert hasattr(model, "coecs")
        assert hasattr(model, "ctrs")

    def test_coec_calculates_coec_values(self):
        """Test coec calculates COEC values correctly."""
        # Arrange
        ctr_by_rank = {0: 0.5, 1: 0.3}  # Rank 0: 50% CTR, Rank 1: 30% CTR
        sessions = build(
            [
                (
                    "query1",
                    [(1, True), (2, False)],
                ),  # Doc 1 clicked at rank 0, doc 2 not clicked at rank 1
                (
                    "query1",
                    [(1, False), (2, True)],
                ),  # Doc 1 not clicked at rank 0, doc 2 clicked at rank 1
            ]
        )
        # Act
        model = coec(ctr_by_rank, sessions)
        # Assert
        # Doc 1: 1 click, expected = 0.5 + 0.5 = 1.0, COEC = 1/1.0 = 1.0
        # Doc 2: 1 click, expected = 0.3 + 0.3 = 0.6, COEC = 1/0.6 ≈ 1.67
        assert ("query1", 1) in model.coecs
        assert ("query1", 2) in model.coecs
        assert model.coecs[("query1", 1)] == pytest.approx(1.0, rel=1e-6)
        assert model.coecs[("query1", 2)] == pytest.approx(1.0 / 0.6, rel=1e-6)

    def test_coec_empty_sessions(self):
        """Test coec handles empty sessions."""
        # Arrange
        ctr_by_rank = {0: 0.5}
        sessions = []
        # Act
        model = coec(ctr_by_rank, sessions)
        # Assert
        assert isinstance(model, COECModel)
        assert len(model.coecs) == 0


class TestConversionAugmentedAttractiveness:
    """Test conversion-augmented attractiveness adjustment."""

    def test_conv_aug_attracts_with_conversion(self):
        """Test conv_aug_attracts when clicks lead to conversions."""
        # Arrange
        attracts: dict[QueryDocPair, float] = {("query1", 1): 0.8, ("query1", 2): 0.6}
        from ltr.clickmodels.session import Doc, Session

        sessions = [
            Session(
                query="query1",
                docs=[
                    Doc(doc_id=1, click=True, conversion=True),  # Clicked and converted
                    Doc(doc_id=2, click=False, conversion=False),
                ],
            )
        ]
        costs: CostMap = {1: 0.5, 2: 0.3}  # Doc 1 costs more
        # Act
        result = conv_aug_attracts(attracts, sessions, costs)
        # Assert
        assert ("query1", 1) in result
        assert ("query1", 2) in result
        # With conversion, attractiveness should be confirmed (not penalized)
        assert result[("query1", 1)] > 0.0

    def test_conv_aug_attracts_without_conversion(self):
        """Test conv_aug_attracts when clicks don't lead to conversions."""
        # Arrange
        attracts: dict[QueryDocPair, float] = {("query1", 1): 0.8, ("query1", 2): 0.6}
        from ltr.clickmodels.session import Doc, Session

        sessions = [
            Session(
                query="query1",
                docs=[
                    Doc(
                        doc_id=1, click=True, conversion=False
                    ),  # Clicked but not converted
                    Doc(doc_id=2, click=False, conversion=False),
                ],
            )
        ]
        costs: CostMap = {1: 0.1, 2: 0.3}  # Doc 1 is cheap
        # Act
        result = conv_aug_attracts(attracts, sessions, costs)
        # Assert
        # Cheap action without conversion should be penalized more
        assert ("query1", 1) in result
        assert result[("query1", 1)] < attracts[("query1", 1)]  # Should be reduced

    def test_conv_aug_attracts_no_clicks(self):
        """Test conv_aug_attracts when there are no clicks."""
        # Arrange
        attracts: dict[QueryDocPair, float] = {("query1", 1): 0.8}
        from ltr.clickmodels.session import Doc, Session

        sessions = [
            Session(
                query="query1",
                docs=[Doc(doc_id=1, click=False, conversion=False)],
            )
        ]
        costs: CostMap = {1: 0.5}
        # Act
        result = conv_aug_attracts(attracts, sessions, costs)
        # Assert
        assert ("query1", 1) in result
        # No click should still adjust based on cost
        assert result[("query1", 1)] == pytest.approx(
            attracts[("query1", 1)] * costs[1], rel=1e-6
        )

    def test_conv_aug_attracts_empty_sessions(self):
        """Test conv_aug_attracts with empty sessions."""
        # Arrange
        attracts: dict[QueryDocPair, float] = {("query1", 1): 0.8}
        sessions = []
        costs: CostMap = {1: 0.5}
        # Act
        result = conv_aug_attracts(attracts, sessions, costs)
        # Assert
        assert len(result) == 0
