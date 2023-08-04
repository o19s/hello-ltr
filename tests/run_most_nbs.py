from notebook_test_case import NotebooksTestCase
import unittest

class RunMostNotebooksTestCase(NotebooksTestCase):

    TEST_PATHS = ['./notebooks/',
                  './notebooks/solr/tmdb',
                  './notebooks/elasticsearch/tmdb',
                  './notebooks/elasticsearch/osc-blog',
                  './notebooks/opensearch/tmdb',
                  './notebooks/opensearch/osc-blog']

    IGNORED_NBS = ['./notebooks/solr/tmdb/evaluation (Solr).ipynb',
                   './notebooks/elasticsearch/tmdb/XGBoost.ipynb',
                   './notebooks/elasticsearch/tmdb/evaluation.ipynb',
                   './notebooks/opensearch/tmdb/XGBoost.ipynb',
                   './notebooks/opensearch/tmdb/evaluation.ipynb']


    def test_paths(self):
        return RunMostNotebooksTestCase.TEST_PATHS

    def ignored_nbs(self):
        return RunMostNotebooksTestCase.IGNORED_NBS



if __name__ == "__main__":
    unittest.main()
