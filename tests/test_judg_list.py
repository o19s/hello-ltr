import unittest

def clean_jl(judg_list_str):
    import textwrap
    dedented=textwrap.dedent(judg_list_str)[1:]
    return dedented

class JudgmentsTestCase(unittest.TestCase):

    def test_string_io_unsorted_throws(self):
        judgment_list=clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      1	qid:2	 # 9876	rocky ii
                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo""")

        from ltr.judgments import judgments_reader
        from io import StringIO

        judg_string_io=StringIO(judgment_list)

        with self.assertRaises(ValueError):
            with judgments_reader(judg_string_io) as judg_list:
                for j in judg_list:
                    print(j)


    def test_string_io_read(self):
        judgment_list=clean_jl("""
                      # qid:1: rambo*1
                      # qid:2: rocky ii*1

                      4	qid:1	 # 1234	rambo
                      3	qid:1	 # 5670	rambo
                      1	qid:2	 # 9876	rocky ii""")

        from ltr.judgments import judgments_reader
        from io import StringIO

        judg_string_io=StringIO(judgment_list)
        read_judgments=0
        with judgments_reader(judg_string_io) as judg_list:
            from itertools import groupby
            for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                query_judgments = [j for j in query_judgments]
                read_judgments += len(query_judgments)
                if qid == 1:
                    self.assertEqual(len(query_judgments),2)
                    for j in query_judgments:
                        self.assertEqual(j.keywords,'rambo')
                        self.assertEqual(j.qid,qid)
                        if j.docId == '1234':
                            self.assertEqual(j.grade, 4)
                        elif j.docId == '5670':
                            self.assertEqual(j.grade, 3)
                        else:
                            print("DocID:{} should not be present in qid:{}".format(j.docId, qid))
                            assert False
                if qid == 2:
                    self.assertEqual(len(query_judgments),1)
                    for j in query_judgments:
                        self.assertEqual(j.keywords,'rocky ii')
                        self.assertEqual(j.qid, qid)
                        if j.docId == '9876':
                            self.assertEqual(j.grade,1)
                        else:
                            self.fail("DocID:{} should not be present in qid:{}".format(j.docId, qid))
        self.assertEqual(read_judgments,3)

    def test_write_read(self):
        from ltr.judgments import judgments_open, Judgment
        import tempfile
        import os
        temp_path=tempfile.gettempdir()
        judgment_file=os.path.join(temp_path, 'judgments.txt')

        print(judgment_file)

        with judgments_open(judgment_file, 'w') as judg_list:
            judg_list.write(judgment=Judgment(keywords='rambo', qid=1, grade=4, docId=1234))
            judg_list.write(judgment=Judgment(keywords='rambo', qid=1, grade=3, docId=5670))
            judg_list.write(judgment=Judgment(keywords='rocky ii', qid=2, grade=1, docId=9876))

        read_judgments=0
        with judgments_open(judgment_file, 'r') as judg_list:
            from itertools import groupby
            for qid, query_judgments in groupby(judg_list, key=lambda j: j.qid):
                query_judgments = [j for j in query_judgments]
                read_judgments += len(query_judgments)
                if qid == 1:
                    self.assertEqual(len(query_judgments),2)
                    for j in query_judgments:
                        self.assertEqual(j.keywords,'rambo')
                        self.assertEqual(j.qid,qid)
                        if j.docId == '1234':
                            self.assertEqual(j.grade, 4)
                        elif j.docId == '5670':
                            self.assertEqual(j.grade, 3)
                        else:
                            print("DocID:{} should not be present in qid:{}".format(j.docId, qid))
                            assert False
                if qid == 2:
                    self.assertEqual(len(query_judgments),1)
                    for j in query_judgments:
                        self.assertEqual(j.keywords,'rocky ii')
                        self.assertEqual(j.qid, qid)
                        if j.docId == '9876':
                            self.assertEqual(j.grade,1)
                        else:
                            self.fail("DocID:{} should not be present in qid:{}".format(j.docId, qid))
        self.assertEqual(read_judgments,3)


if __name__ == "__main__":
    unittest.main()
