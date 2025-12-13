"""
Unit tests for judgment list parsing and I/O operations.

Tests cover:
- Judgment list parsing from StringIO
- File I/O operations for judgments
- Validation of judgment list format (sorted by qid)
- Reading and writing judgment files
"""

import unittest


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
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      1	qid:2	 # 9876	rocky ii
                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo""")

        from io import StringIO

        from ltr.judgments import judgments_reader

        judg_string_io = StringIO(judgment_list)

        with (
            self.assertRaises(ValueError),
            judgments_reader(judg_string_io) as judg_list,
        ):
            for j in judg_list:
                print(j)

    def test_string_io_read(self):
        """Test reading and parsing sorted judgments from StringIO.

        Verifies that judgments_reader correctly:
        - Parses judgments from a StringIO stream
        - Groups judgments by qid
        - Validates judgment properties (keywords, qid, docId, grade)
        - Handles multiple queries correctly
        """
        judgment_list = clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        from io import StringIO

        from ltr.judgments import judgments_reader

        judg_string_io = StringIO(judgment_list)
        read_judgments = 0
        with judgments_reader(judg_string_io) as judg_list:
            from itertools import groupby

            for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                query_judgments = list(query_judgments)
                read_judgments += len(query_judgments)
                if qid == 1:
                    self.assertEqual(len(query_judgments), 2)
                    for j in query_judgments:
                        self.assertEqual(j.keywords, "rambo")
                        self.assertEqual(j.qid, qid)
                        if j.docId == "1234":
                            self.assertEqual(j.grade, 4)
                        elif j.docId == "5670":
                            self.assertEqual(j.grade, 3)
                        else:
                            print(f"DocID:{j.docId} should not be present in qid:{qid}")
                            raise AssertionError()
                if qid == 2:
                    self.assertEqual(len(query_judgments), 1)
                    for j in query_judgments:
                        self.assertEqual(j.keywords, "rocky ii")
                        self.assertEqual(j.qid, qid)
                        if j.docId == "9876":
                            self.assertEqual(j.grade, 1)
                        else:
                            self.fail(
                                f"DocID:{j.docId} should not be present in qid:{qid}"
                            )
        self.assertEqual(read_judgments, 3)

    def test_write_read(self):
        """Test writing judgments to file and reading them back.

        Verifies the complete write-read cycle:
        - Writing judgments to a temporary file
        - Reading judgments back from the file
        - Validating that all judgments are correctly preserved
        - Ensuring judgment properties match original values

        Note: Uses Python's tempfile module for temporary file creation.
        """
        import os
        import tempfile

        from ltr.judgments import Judgment, judgments_open

        # Create a temporary file
        fd, judgment_file = tempfile.mkstemp(suffix=".txt", prefix="test_judgments_")
        os.close(fd)  # Close the file descriptor, we'll use the path

        try:
            with judgments_open(judgment_file, "w") as judg_list:
                judg_list.write(
                    judgment=Judgment(keywords="rambo", qid=1, grade=4, docId=1234)
                )
                judg_list.write(
                    judgment=Judgment(keywords="rambo", qid=1, grade=3, docId=5670)
                )
                judg_list.write(
                    judgment=Judgment(keywords="rocky ii", qid=2, grade=1, docId=9876)
                )

            read_judgments = 0
            with judgments_open(judgment_file, "r") as judg_list:
                from itertools import groupby

                for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                    query_judgments = list(query_judgments)
                    read_judgments += len(query_judgments)
                    if qid == 1:
                        self.assertEqual(len(query_judgments), 2)
                        for j in query_judgments:
                            self.assertEqual(j.keywords, "rambo")
                            self.assertEqual(j.qid, qid)
                            if j.docId == "1234":
                                self.assertEqual(j.grade, 4)
                            elif j.docId == "5670":
                                self.assertEqual(j.grade, 3)
                            else:
                                print(
                                    f"DocID:{j.docId} should not be present in qid:{qid}"
                                )
                                raise AssertionError()
                    if qid == 2:
                        self.assertEqual(len(query_judgments), 1)
                        for j in query_judgments:
                            self.assertEqual(j.keywords, "rocky ii")
                            self.assertEqual(j.qid, qid)
                            if j.docId == "9876":
                                self.assertEqual(j.grade, 1)
                            else:
                                self.fail(
                                    f"DocID:{j.docId} should not be present in qid:{qid}"
                                )
            self.assertEqual(read_judgments, 3)
        finally:
            # Clean up temporary file
            if os.path.exists(judgment_file):
                os.unlink(judgment_file)
