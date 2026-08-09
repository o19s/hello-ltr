"""
Unit tests for MART model analysis.

Tests cover:
- fold_whoopsies function
- dedup_whoopsies function
- MARTModel class (basic initialization and parsing)
"""

import pytest

from ltr.mart_model import MARTModel, Whoopsie, dedup_whoopsies, fold_whoopsies


class TestFoldWhoopsies:
    """Test fold_whoopsies function."""

    def test_fold_whoopsies_merges_lists(self):
        """Test that fold_whoopsies merges two lists."""
        # Arrange
        whoopsie1 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="doc1",
            max_grade_doc_id="doc2",
            output=0.5,
        )
        whoopsie2 = Whoopsie(
            qid=2,
            judg_list=[],
            min_grade=2,
            max_grade=3,
            min_grade_doc_id="doc3",
            max_grade_doc_id="doc4",
            output=0.6,
        )
        whoopsies1 = [whoopsie1]
        whoopsies2 = [whoopsie2]

        # Act
        result = fold_whoopsies(whoopsies1, whoopsies2)

        # Assert
        assert len(result) == 2
        assert result is whoopsies1  # Should return same reference
        assert whoopsie1 in result
        assert whoopsie2 in result

    def test_fold_whoopsies_sorts_by_qid_then_magnitude(self):
        """Test that fold_whoopsies sorts by qid then descending magnitude."""
        # Arrange
        # Create whoopsies with different qids and magnitudes
        whoopsie1 = Whoopsie(
            qid=2,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )  # qid=2, magnitude=1
        whoopsie2 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=4,
            min_grade_doc_id="d3",
            max_grade_doc_id="d4",
            output=0.6,
        )  # qid=1, magnitude=3
        whoopsie3 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=2,
            max_grade=3,
            min_grade_doc_id="d5",
            max_grade_doc_id="d6",
            output=0.7,
        )  # qid=1, magnitude=1
        whoopsies1 = [whoopsie1]
        whoopsies2 = [whoopsie2, whoopsie3]

        # Act
        result = fold_whoopsies(whoopsies1, whoopsies2)

        # Assert
        # Should be sorted: qid=1 (magnitude=3), qid=1 (magnitude=1), qid=2 (magnitude=1)
        assert len(result) == 3
        assert result[0].qid == 1
        assert result[0].magnitude() == 3  # Highest magnitude for qid=1
        assert result[1].qid == 1
        assert result[1].magnitude() == 1  # Lower magnitude for qid=1
        assert result[2].qid == 2

    def test_fold_whoopsies_empty_second_list(self):
        """Test fold_whoopsies with empty second list."""
        # Arrange
        whoopsie = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )
        whoopsies1 = [whoopsie]
        whoopsies2 = []

        # Act
        result = fold_whoopsies(whoopsies1, whoopsies2)

        # Assert
        assert len(result) == 1
        assert result[0] == whoopsie

    def test_fold_whoopsies_empty_first_list(self):
        """Test fold_whoopsies with empty first list."""
        # Arrange
        whoopsie = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )
        whoopsies1 = []
        whoopsies2 = [whoopsie]

        # Act
        result = fold_whoopsies(whoopsies1, whoopsies2)

        # Assert
        assert len(result) == 1
        assert result[0] == whoopsie


class TestDedupWhoopsies:
    """Test dedup_whoopsies function."""

    def test_dedup_whoopsies_keeps_worst_per_query(self):
        """Test that dedup_whoopsies keeps only worst whoopsie per query."""
        # Arrange
        # Create whoopsies for same query with different magnitudes
        whoopsie1 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )  # magnitude=1
        whoopsie2 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=4,
            min_grade_doc_id="d3",
            max_grade_doc_id="d4",
            output=0.6,
        )  # magnitude=3 (worst)
        whoopsie3 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=2,
            max_grade=3,
            min_grade_doc_id="d5",
            max_grade_doc_id="d6",
            output=0.7,
        )  # magnitude=1
        whoopsie4 = Whoopsie(
            qid=2,
            judg_list=[],
            min_grade=1,
            max_grade=3,
            min_grade_doc_id="d7",
            max_grade_doc_id="d8",
            output=0.8,
        )  # magnitude=2
        sorted_whoopsies = [
            whoopsie2,
            whoopsie1,
            whoopsie3,
            whoopsie4,
        ]  # Sorted by qid then magnitude

        # Act
        result = dedup_whoopsies(sorted_whoopsies)

        # Assert
        assert len(result) == 2  # One per query
        assert result[0] == whoopsie2  # Worst for qid=1 (magnitude=3)
        assert result[1] == whoopsie4  # Only one for qid=2

    def test_dedup_whoopsies_single_query(self):
        """Test dedup_whoopsies with single query."""
        # Arrange
        whoopsie = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )
        sorted_whoopsies = [whoopsie]

        # Act
        result = dedup_whoopsies(sorted_whoopsies)

        # Assert
        assert len(result) == 1
        assert result[0] == whoopsie

    def test_dedup_whoopsies_empty_list(self):
        """Test dedup_whoopsies with empty list."""
        # Arrange
        sorted_whoopsies = []

        # Act
        result = dedup_whoopsies(sorted_whoopsies)

        # Assert
        assert len(result) == 0

    def test_dedup_whoopsies_multiple_queries(self):
        """Test dedup_whoopsies with multiple queries."""
        # Arrange
        whoopsie1 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=4,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )  # qid=1, magnitude=3
        whoopsie2 = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=2,
            min_grade_doc_id="d3",
            max_grade_doc_id="d4",
            output=0.6,
        )  # qid=1, magnitude=1
        whoopsie3 = Whoopsie(
            qid=2,
            judg_list=[],
            min_grade=1,
            max_grade=3,
            min_grade_doc_id="d5",
            max_grade_doc_id="d6",
            output=0.7,
        )  # qid=2, magnitude=2
        whoopsie4 = Whoopsie(
            qid=2,
            judg_list=[],
            min_grade=2,
            max_grade=3,
            min_grade_doc_id="d7",
            max_grade_doc_id="d8",
            output=0.8,
        )  # qid=2, magnitude=1
        sorted_whoopsies = [whoopsie1, whoopsie2, whoopsie3, whoopsie4]

        # Act
        result = dedup_whoopsies(sorted_whoopsies)

        # Assert
        assert len(result) == 2
        assert result[0] == whoopsie1  # Worst for qid=1
        assert result[1] == whoopsie3  # Worst for qid=2


class TestWhoopsie:
    """Test Whoopsie class."""

    def test_whoopsie_magnitude(self):
        """Test whoopsie magnitude calculation."""
        # Arrange
        whoopsie = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=1,
            max_grade=4,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )

        # Act
        magnitude = whoopsie.magnitude()

        # Assert
        assert magnitude == 3  # max_grade - min_grade = 4 - 1

    def test_whoopsie_magnitude_zero(self):
        """Test whoopsie magnitude when min equals max."""
        # Arrange
        whoopsie = Whoopsie(
            qid=1,
            judg_list=[],
            min_grade=2,
            max_grade=2,
            min_grade_doc_id="d1",
            max_grade_doc_id="d2",
            output=0.5,
        )

        # Act
        magnitude = whoopsie.magnitude()

        # Assert
        assert magnitude == 0


class TestMARTModel:
    """Test MARTModel class."""

    def test_mart_model_init_lambdamart(self):
        """Test MARTModel initialization with LambdaMART XML."""
        # Arrange
        ranklib_xml = """## LambdaMART
<ensemble>
    <tree weight="0.5">
        <split pos="left">
            <feature>1</feature>
            <threshold>0.5</threshold>
            <split pos="left">
                <output>0.1</output>
            </split>
            <split pos="right">
                <output>0.9</output>
            </split>
        </split>
        <split pos="right">
            <output>0.5</output>
        </split>
    </tree>
</ensemble>"""
        features = [{"name": "feature1"}, {"name": "feature2"}]

        # Act
        model = MARTModel(ranklib_xml, features)

        # Assert
        assert len(model.trees) == 1
        assert model.trees[0][0] == 0.5  # weight

    def test_mart_model_init_random_forest(self):
        """Test MARTModel initialization with Random Forest XML."""
        # Arrange
        ranklib_xml = """## Random Forests
## No. of bags = 1
<ensemble>
    <tree weight="0.5">
        <output>0.3</output>
    </tree>
</ensemble>"""
        features = [{"name": "feature1"}]

        # Act
        model = MARTModel(ranklib_xml, features)

        # Assert
        assert len(model.trees) == 1

    def test_mart_model_init_invalid_header(self):
        """Test MARTModel initialization with invalid header raises ValueError."""
        # Arrange
        ranklib_xml = """## Invalid Header
<ensemble>
    <tree weight="0.5">
        <output>0.3</output>
    </tree>
</ensemble>"""
        features = [{"name": "feature1"}]

        # Act & Assert
        with pytest.raises(ValueError, match="Whoopsies only support"):
            MARTModel(ranklib_xml, features)

    def test_mart_model_str(self):
        """Test MARTModel string representation."""
        # Arrange
        ranklib_xml = """## LambdaMART
<ensemble>
    <tree weight="0.5">
        <split feature="0" pos="left" threshold="10.0">
            <output>0.3</output>
        </split>
    </tree>
</ensemble>"""
        features = [{"name": "feature1"}]
        model = MARTModel(ranklib_xml, features)

        # Act
        result = str(model)

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0  # Should have some content
