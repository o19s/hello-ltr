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


class HeaderBoundaryTestCase(unittest.TestCase):
    """Tests for the header/body boundary (issue #106).

    Detecting the end of the header block requires reading one line past it.
    That line used to be discarded, so any file without a blank separator line
    silently lost its first judgment - no warning, no error, just one fewer row
    than the file contained.
    """

    def _read(self, judgment_list):
        """Parse a judgment-list string and return the Judgment objects."""
        from io import StringIO

        from ltr.judgments import judgments_from_file

        return list(judgments_from_file(StringIO(judgment_list)))

    def test_no_blank_line_after_header_keeps_first_judgment(self):
        """The reported repro: a single judgment with no separator line."""
        # Arrange
        judgment_list = "# qid:1: test query\n1 qid:1 # doc1 test query\n"

        # Act
        judgments = self._read(judgment_list)

        # Assert
        self.assertEqual(len(judgments), 1, "The only judgment must survive parsing")
        self.assertEqual(judgments[0].docId, "doc1")
        self.assertEqual(judgments[0].qid, 1)
        self.assertEqual(judgments[0].grade, 1)

    def test_blank_line_after_header_still_parses(self):
        """The shipped convention must be unaffected by the fix."""
        # Arrange
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        # Act
        judgments = self._read(judgment_list)

        # Assert
        self.assertEqual(len(judgments), 3)
        self.assertEqual([j.docId for j in judgments], ["1234", "5670", "9876"])

    def test_with_and_without_separator_agree(self):
        """The separator line must make no difference to the parsed result."""
        # Arrange
        rows = "4\tqid:1\t # 1234\trambo\n3\tqid:1\t # 5670\trambo\n"
        header = "# qid:1: rambo*1\n"

        # Act
        without_separator = self._read(header + rows)
        with_separator = self._read(header + "\n" + rows)

        # Assert
        self.assertEqual(
            [(j.qid, j.docId, j.grade) for j in without_separator],
            [(j.qid, j.docId, j.grade) for j in with_separator],
            "The blank separator line must be optional, not load-bearing",
        )

    def test_header_only_file_yields_nothing(self):
        """A file with no body must parse to an empty list, not raise."""
        # Arrange / Act
        judgments = self._read("# qid:1: rambo*1\n")

        # Assert
        self.assertEqual(judgments, [])

    def test_empty_file_yields_nothing(self):
        """An empty file must parse to an empty list, not raise."""
        # Arrange / Act / Assert
        self.assertEqual(self._read(""), [])

    def test_body_only_file_raises_on_unknown_qid(self):
        """A row now reaches the parser even with no header, and has no keywords.

        Previously the lone row was swallowed as the header terminator and the
        caller got a silent empty list. Surfacing a KeyError is the better of
        the two - it names a real problem with the file.
        """
        # Arrange / Act / Assert
        with self.assertRaises(KeyError):
            self._read("4\tqid:1\t # 1234\trambo\n")

    def test_features_survive_missing_separator(self):
        """A feature-bearing first row must keep its features, not just its ids."""
        # Arrange
        judgment_list = "# qid:1: rambo*1\n4\tqid:1\t1:9.5\t2:3.0\t # 1234\trambo\n"

        # Act
        judgments = self._read(judgment_list)

        # Assert
        self.assertEqual(len(judgments), 1)
        self.assertEqual(judgments[0].features, [9.5, 3.0])

    def test_reader_also_keeps_first_judgment(self):
        """JudgmentsReader shares the parsing path and must behave identically."""
        # Arrange
        from io import StringIO

        from ltr.judgments import judgments_reader

        judgment_list = "# qid:1: test query\n1 qid:1 # doc1 test query\n"

        # Act
        with judgments_reader(StringIO(judgment_list)) as reader:
            judgments = list(reader)

        # Assert
        self.assertEqual(len(judgments), 1, "JudgmentsReader must not drop the row")
        self.assertEqual(judgments[0].docId, "doc1")
