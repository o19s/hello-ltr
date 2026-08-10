"""
Unit tests for typo injection module.

Tests cover:
- typo_it function (typo injection into judgment files)
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ltr.inject_typos import typo_it
from ltr.judgments import judgments_from_file

# ---------------------------------------------------------------------------
# Judgment-file fixtures
#
# These used to reserve a throwaway qid:0 row because _queries_from_header()
# consumed the first non-comment line without passing it on, so short fixtures
# lost every judgment they contained. That was issue #106; the parser now hands
# the line back and no filler is needed.
# ---------------------------------------------------------------------------


def write_judgment_file(path, headers, rows):
    """Write a judgment file with the given header comments and judgment rows."""
    with open(path, "w", encoding="utf-8") as f:
        for header in headers:
            f.write(header)
        for row in rows:
            f.write(row)


def read_judgment_file(path):
    """Read every judgment from a judgment file."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    headers = [ln for ln in lines if ln.startswith("#")]
    rows = [ln for ln in lines if not ln.startswith("#") and ln.strip()]
    stream = io.StringIO("".join([*headers, *rows]))
    return list(judgments_from_file(stream))


class TestTypoIt:
    """Test typo_it function."""

    def test_typo_it_creates_output_file(self):
        """Test that typo_it creates output file."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with one judgment (needs header)
            # Use spaces instead of tabs to match the expected format
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1 qid:1 # doc1 test query\n",
                ],
            )

            # Mock butterfingers to return a typo
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"  # Typo variant

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

            # Assert
            assert output_file.exists()

    def test_typo_it_preserves_original_judgments(self):
        """Test that typo_it preserves original judgments."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with judgments (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                    "2\tqid:1\t# doc2\ttest query\n",
                ],
            )

            # Mock butterfingers to return a typo
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"  # Typo variant

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

                # Assert - original judgments should be in output
                judgments = read_judgment_file(output_file)
            assert len(judgments) >= 2  # At least original judgments
            # Find original judgments
            original_judgments = [j for j in judgments if j.qid == 1]
            assert len(original_judgments) == 2

    def test_typo_it_creates_typo_judgments(self):
        """Test that typo_it creates new judgments with typos."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with one judgment (needs header)
            # Use spaces instead of tabs to match the expected format
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1 qid:1 # doc1 test query\n",
                ],
            )

            # Mock butterfingers to return a typo
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"  # Typo variant

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

                # Assert - should have original + typo judgments
                judgments = read_judgment_file(output_file)
            assert len(judgments) >= 2  # Original + at least one typo
            # Find typo judgments (qid > 1)
            typo_judgments = [j for j in judgments if j.qid > 1]
            assert len(typo_judgments) >= 1
            assert typo_judgments[0].keywords == "test quary"

    def test_typo_it_assigns_new_qid_for_typos(self):
        """Test that typo_it assigns new qid for each typo variant."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with judgments ending at qid 1 (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                ],
            )

            # Mock butterfingers to return different typos
            typo_variants = ["test quary", "test querry"]
            mock_butterfingers = Mock(side_effect=typo_variants)

            with patch("ltr.inject_typos.butterfingers", mock_butterfingers):
                # Act
                typo_it(str(input_file), str(output_file), rounds=2)

                # Assert - should have different qids for different typos
                judgments = read_judgment_file(output_file)
            qids = {j.qid for j in judgments}
            assert 1 in qids  # Original qid
            assert len(qids) > 1  # At least one new qid

    def test_typo_it_skips_duplicate_typos(self):
        """Test that typo_it skips duplicate typos."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                ],
            )

            # Mock butterfingers to return same typo multiple times
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"  # Same typo

                # Act
                typo_it(str(input_file), str(output_file), rounds=5)

                # Assert - should only have one typo variant (not 5)
                judgments = read_judgment_file(output_file)
            typo_keywords = {j.keywords for j in judgments if j.qid > 1}
            assert len(typo_keywords) == 1  # Only one unique typo

    def test_typo_it_skips_typos_matching_original(self):
        """Test that typo_it skips typos that match original keywords."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                ],
            )

            # Mock butterfingers to return original (no typo)
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test query"  # Same as original

                # Act
                typo_it(str(input_file), str(output_file), rounds=5)

                # Assert - should only have original judgments
                judgments = read_judgment_file(output_file)
            assert len(judgments) == 1  # Only original
            assert all(j.qid == 1 for j in judgments)

    def test_typo_it_creates_judgments_for_all_docs_in_query(self):
        """Test that typo_it creates typo judgments for all docs in original query."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with multiple judgments for same query (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                    "2\tqid:1\t# doc2\ttest query\n",
                    "3\tqid:1\t# doc3\ttest query\n",
                ],
            )

            # Mock butterfingers to return a typo
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

                # Assert - typo qid should have same number of judgments as original
                judgments = read_judgment_file(output_file)
            original_count = len([j for j in judgments if j.qid == 1])
            typo_qids = {j.qid for j in judgments if j.qid > 1}
            if typo_qids:
                typo_qid = list(typo_qids)[0]
                typo_count = len([j for j in judgments if j.qid == typo_qid])
                assert typo_count == original_count

    def test_typo_it_handles_multiple_queries(self):
        """Test that typo_it handles multiple queries correctly."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with multiple queries (needs headers)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: query one\n",
                    "# qid:2: query two\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\tquery one\n",
                    "2\tqid:2\t# doc2\tquery two\n",
                ],
            )

            # Mock butterfingers to return typos
            def butterfingers_side_effect(keywords):
                if keywords == "query one":
                    return "query on"
                elif keywords == "query two":
                    return "query tw"
                return keywords

            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.side_effect = butterfingers_side_effect

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

                # Assert - should have typos for both queries
                judgments = read_judgment_file(output_file)
            keywords_set = {j.keywords for j in judgments}
            assert "query one" in keywords_set  # Original
            assert "query two" in keywords_set  # Original
            assert "query on" in keywords_set  # Typo
            assert "query tw" in keywords_set  # Typo

    def test_typo_it_rounds_parameter(self):
        """Test that typo_it respects rounds parameter."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "1\tqid:1\t# doc1\ttest query\n",
                ],
            )

            # Mock butterfingers to return different typos
            typo_variants = ["test quary", "test querry", "test queri"]
            mock_butterfingers = Mock(
                side_effect=typo_variants * 10
            )  # More than rounds

            with patch("ltr.inject_typos.butterfingers", mock_butterfingers):
                # Act - only 2 rounds
                typo_it(str(input_file), str(output_file), rounds=2)

            # Assert - butterfingers should be called rounds * num_queries times
            assert mock_butterfingers.call_count == 2  # 2 rounds * 1 query

    def test_typo_it_preserves_judgment_attributes(self):
        """Test that typo_it preserves judgment attributes (grade, doc_id) for typo judgments."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file with judgment (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:1: test query\n",
                ],
                rows=[
                    "3\tqid:1\t# doc123\ttest query\n",
                ],
            )

            # Mock butterfingers to return a typo
            with patch("ltr.inject_typos.butterfingers") as mock_butterfingers:
                mock_butterfingers.return_value = "test quary"

                # Act
                typo_it(str(input_file), str(output_file), rounds=1)

                # Assert - typo judgment should have same grade and doc_id
                judgments = read_judgment_file(output_file)
            original = next(j for j in judgments if j.qid == 1)
            typo = next(j for j in judgments if j.qid > 1)
            assert typo.grade == original.grade
            assert typo.docId == original.docId
            assert typo.keywords == "test quary"

    def test_typo_it_empty_input_file(self):
        """Test that typo_it handles empty input file."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create empty input file (no judgments)
            input_file.touch()

            # Act & Assert - should raise ValueError when no judgments exist
            with pytest.raises(ValueError, match="No judgments found"):
                typo_it(str(input_file), str(output_file), rounds=1)

    def test_typo_it_increments_qid_sequentially(self):
        """Test that typo_it increments qid sequentially for multiple typos."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "input.txt"
            output_file = Path(tmpdir) / "output.txt"

            # Create input file ending at qid 5 (needs header)
            write_judgment_file(
                input_file,
                headers=[
                    "# qid:5: test query\n",
                ],
                rows=[
                    "1\tqid:5\t# doc1\ttest query\n",
                ],
            )

            # Mock butterfingers to return different typos
            typo_variants = ["test quary", "test querry"]
            mock_butterfingers = Mock(side_effect=typo_variants)

            with patch("ltr.inject_typos.butterfingers", mock_butterfingers):
                # Act
                typo_it(str(input_file), str(output_file), rounds=2)

                # Assert - qids should be sequential
                judgments = read_judgment_file(output_file)
            qids = sorted({j.qid for j in judgments})
            # Should have original qid 5, then 6, 7, etc.
            assert 5 in qids
            if len(qids) > 1:
                # Check sequential increment
                for i in range(len(qids) - 1):
                    assert qids[i + 1] == qids[i] + 1
