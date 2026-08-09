"""
Unit tests for judgment list parsing and I/O operations.

Tests cover:
- Judgment list parsing from StringIO
- File I/O operations for judgments
- Validation of judgment list format (sorted by qid)
- Reading and writing judgment files
"""

import logging
import unittest

logger = logging.getLogger(__name__)


def clean_jl(judg_list_str):
    """
    Clean and dedent a judgment list string for testing.

    Args:
        judg_list_str: Multi-line string containing judgment list

    Returns:
        str: Dedented string with first character removed
    """
    import textwrap

    dedented = textwrap.dedent(judg_list_str)[1:]
    return dedented


class JudgmentsTestCase(unittest.TestCase):
    """Test cases for judgment list parsing and I/O operations."""

    def test_string_io_unsorted_throws(self):
        """Test that reading unsorted judgments raises ValueError.

        Verifies that judgments_reader correctly validates that judgments
        are sorted by qid (query ID). When judgments are not sorted,
        a ValueError should be raised.
        """
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      1	qid:2	 # 9876	rocky ii
                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo""")

        from io import StringIO

        from ltr.judgments import judgments_reader

        judg_string_io = StringIO(judgment_list)

        # Act & Assert
        with (
            self.assertRaises(ValueError),
            judgments_reader(judg_string_io) as judg_list,
        ):
            for j in judg_list:
                logger.debug("Processing judgment: %s", j)

    def _read_judgments_from_string(self, judgment_list):
        """Helper method to read judgments from a string and group by qid.

        Args:
            judgment_list: String containing judgment list data

        Returns:
            dict: Dictionary mapping qid to list of judgments
        """
        from io import StringIO

        from ltr.judgments import judgments_reader

        judg_string_io = StringIO(judgment_list)
        judgments_by_qid = {}
        with judgments_reader(judg_string_io) as judg_list:
            from itertools import groupby

            for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                judgments_by_qid[qid] = list(query_judgments)
        return judgments_by_qid

    def test_string_io_read_number_of_queries(self):
        """Test that reading judgments groups them by the correct number of queries."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        self.assertEqual(
            len(judgments_by_qid), 2, "Should have judgments for 2 queries"
        )

    def test_string_io_read_total_judgments(self):
        """Test that reading judgments returns the correct total number of judgments."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        total_judgments = sum(len(judgments) for judgments in judgments_by_qid.values())
        self.assertEqual(total_judgments, 3, "Should have 3 total judgments")

    def test_string_io_read_qid1_judgment_count(self):
        """Test that qid:1 has the correct number of judgments."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        self.assertEqual(len(qid1_judgments), 2, "qid:1 should have 2 judgments")

    def test_string_io_read_qid1_doc_ids(self):
        """Test that qid:1 judgments have the correct document IDs."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        qid1_doc_ids = {j.docId for j in qid1_judgments}
        self.assertEqual(
            qid1_doc_ids, {"1234", "5670"}, "qid:1 should have correct doc IDs"
        )

    def test_string_io_read_qid1_keywords(self):
        """Test that qid:1 judgments have the correct keywords."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            self.assertEqual(
                j.keywords,
                "rambo",
                f"qid:1 judgment {j.docId} should have 'rambo' keywords",
            )

    def test_string_io_read_qid1_qid_values(self):
        """Test that qid:1 judgments have the correct qid value."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            self.assertEqual(j.qid, 1, f"qid:1 judgment {j.docId} should have qid=1")

    def test_string_io_read_qid1_grades(self):
        """Test that qid:1 judgments have the correct grades."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            if j.docId == "1234":
                self.assertEqual(j.grade, 4, "docId 1234 should have grade 4")
            elif j.docId == "5670":
                self.assertEqual(j.grade, 3, "docId 5670 should have grade 3")

    def test_string_io_read_qid2_judgment_count(self):
        """Test that qid:2 has the correct number of judgments."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        self.assertEqual(len(qid2_judgments), 1, "qid:2 should have 1 judgment")

    def test_string_io_read_qid2_doc_ids(self):
        """Test that qid:2 judgments have the correct document IDs."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        qid2_doc_ids = {j.docId for j in qid2_judgments}
        self.assertEqual(qid2_doc_ids, {"9876"}, "qid:2 should have correct doc ID")

    def test_string_io_read_qid2_keywords(self):
        """Test that qid:2 judgments have the correct keywords."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(
                j.keywords,
                "rocky ii",
                f"qid:2 judgment {j.docId} should have 'rocky ii' keywords",
            )

    def test_string_io_read_qid2_qid_value(self):
        """Test that qid:2 judgments have the correct qid value."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.qid, 2, f"qid:2 judgment {j.docId} should have qid=2")

    def test_string_io_read_qid2_doc_id(self):
        """Test that qid:2 judgment has the correct document ID."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.docId, "9876", "qid:2 should have docId 9876")

    def test_string_io_read_qid2_grade(self):
        """Test that qid:2 judgment has the correct grade."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments_by_qid = self._read_judgments_from_string(judgment_list)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.grade, 1, "docId 9876 should have grade 1")

    def _write_read_judgments(self, expected_judgments):
        """Helper method to write judgments to a temporary file and read them back.

        Args:
            expected_judgments: List of Judgment objects to write

        Returns:
            dict: Dictionary mapping qid to list of judgments read from file
        """
        import os
        import tempfile

        from ltr.judgments import judgments_open

        fd, judgment_file = tempfile.mkstemp(suffix=".txt", prefix="test_judgments_")
        os.close(fd)  # Close the file descriptor, we'll use the path

        try:
            # Act - Write judgments
            with judgments_open(judgment_file, "w") as judg_list:
                for judgment in expected_judgments:
                    judg_list.write(judgment=judgment)

            # Act - Read judgments back
            judgments_by_qid = {}
            with judgments_open(judgment_file, "r") as judg_list:
                from itertools import groupby

                for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                    judgments_by_qid[qid] = list(query_judgments)

            return judgments_by_qid
        finally:
            # Clean up temporary file
            if os.path.exists(judgment_file):
                os.unlink(judgment_file)

    def test_write_read_total_judgments(self):
        """Test that writing and reading judgments preserves the total number of judgments."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        total_read = sum(len(judgments) for judgments in judgments_by_qid.values())
        self.assertEqual(total_read, 3, "Should have read 3 judgments")

    def test_write_read_number_of_queries(self):
        """Test that writing and reading judgments preserves the number of queries."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        self.assertEqual(
            len(judgments_by_qid), 2, "Should have judgments for 2 queries"
        )

    def test_write_read_qid1_judgment_count(self):
        """Test that writing and reading preserves qid:1 judgment count."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        self.assertEqual(len(qid1_judgments), 2, "qid:1 should have 2 judgments")

    def test_write_read_qid1_doc_ids(self):
        """Test that writing and reading preserves qid:1 document IDs."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        qid1_doc_ids = {j.docId for j in qid1_judgments}
        self.assertEqual(
            qid1_doc_ids, {"1234", "5670"}, "qid:1 should have correct doc IDs"
        )

    def test_write_read_qid1_keywords(self):
        """Test that writing and reading preserves qid:1 keywords."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            self.assertEqual(
                j.keywords,
                "rambo",
                f"qid:1 judgment {j.docId} should have 'rambo' keywords",
            )

    def test_write_read_qid1_qid_values(self):
        """Test that writing and reading preserves qid:1 qid values."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            self.assertEqual(j.qid, 1, f"qid:1 judgment {j.docId} should have qid=1")

    def test_write_read_qid1_grades(self):
        """Test that writing and reading preserves qid:1 grades."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid1_judgments = judgments_by_qid[1]
        for j in qid1_judgments:
            if j.docId == "1234":
                self.assertEqual(j.grade, 4, "docId 1234 should have grade 4")
            elif j.docId == "5670":
                self.assertEqual(j.grade, 3, "docId 5670 should have grade 3")

    def test_write_read_qid2_judgment_count(self):
        """Test that writing and reading preserves qid:2 judgment count."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        self.assertEqual(len(qid2_judgments), 1, "qid:2 should have 1 judgment")

    def test_write_read_qid2_doc_ids(self):
        """Test that writing and reading preserves qid:2 document IDs."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        qid2_doc_ids = {j.docId for j in qid2_judgments}
        self.assertEqual(qid2_doc_ids, {"9876"}, "qid:2 should have correct doc ID")

    def test_write_read_qid2_keywords(self):
        """Test that writing and reading preserves qid:2 keywords."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(
                j.keywords,
                "rocky ii",
                f"qid:2 judgment {j.docId} should have 'rocky ii' keywords",
            )

    def test_write_read_qid2_qid_value(self):
        """Test that writing and reading preserves qid:2 qid value."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.qid, 2, f"qid:2 judgment {j.docId} should have qid=2")

    def test_write_read_qid2_doc_id(self):
        """Test that writing and reading preserves qid:2 document ID."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.docId, "9876", "qid:2 should have docId 9876")

    def test_write_read_qid2_grade(self):
        """Test that writing and reading preserves qid:2 grade."""
        # Arrange
        from ltr.judgments import Judgment

        expected_judgments = [
            Judgment(keywords="rambo", qid=1, grade=4, doc_id="1234"),
            Judgment(keywords="rambo", qid=1, grade=3, doc_id="5670"),
            Judgment(keywords="rocky ii", qid=2, grade=1, doc_id="9876"),
        ]

        # Act
        judgments_by_qid = self._write_read_judgments(expected_judgments)

        # Assert
        qid2_judgments = judgments_by_qid[2]
        for j in qid2_judgments:
            self.assertEqual(j.grade, 1, "docId 9876 should have grade 1")
