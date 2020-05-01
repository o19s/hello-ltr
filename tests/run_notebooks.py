import unittest
from nb_test_config import NotebookTestConfig
import runner

class RunNbsTestCase(unittest.TestCase):

    SAVE_NB_PATH='tests/last_run.ipynb'

    TEST_PATHS = ['./notebooks/',
                  './notebooks/solr/tmdb',
                  './notebooks/elasticsearch/tmdb',
                  './notebooks/elasticsearch/osc-blog']

    IGNORED_NBS = ['/notebooks/solr/tmdb/evaluation (Solr).ipynb',
                   '/notebooks/elasticsearch/tmdb/evaluation.ipynb']

    def test_paths():
        return []

    def ignored_nbs():
        return []

    def nbs_to_run():
        class IncludeAll:
            def __contains__(self, _):
                return True
        return IncludeAll()

    def test_for_no_errors(self):
        """ Run all nbs in directories at test_paths()
            also included in nbs_to_run(),
            excepting those in ignored_nbs()
            - assert there are no errors
            """
        for nb_path in self.test_paths():

            nb_cfg = NotebookTestConfig(path=nb_path)
            print("EXECUTING NBS IN DIRECTORY: " + nb_path)
            if nb_cfg.setup:
                print("Setting up ... " + nb_path)
                nb, errors = runner.run_notebook(nb_cfg.setup, save_nb_path=RunNbsTestCase.SAVE_NB_PATH)
                print(errors)
                assert len(errors) == 0
            for nb in nb_cfg.notebooks:
                if nb in self.nbs_to_run():
                    if nb in RunNbsTestCase.IGNORED_NBS:
                        print("Ignored " + nb)
                        continue
                    else:
                        print("Running... " + nb)
                        nb, errors = runner.run_notebook(nb)
                        print(errors)
                        assert len(errors) == 0

if __name__ == "__main__":
    unittest.main()
