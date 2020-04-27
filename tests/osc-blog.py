import unittest
import runner
import os
from collections import defaultdict

class TestAllNbs(unittest.TestCase):

    def get_nb_dirs(path='./notebooks'):
        nb_paths = defaultdict(lambda: {'setup': None, 'notebooks': []})
        for subdir, dirs, files in os.walk(path):
            for fname in files:
                if fname.endswith('.ipynb'):
                    if fname == 'setup.ipynb':
                        nb_paths[subdir]['setup'] = os.path.join(subdir, fname)
                    else:
                        nb_paths[subdir]['notebooks'].append(os.path.join(subdir, fname))
        return nb_paths
        print(os.path.join(subdir, fname))

    def test_all_no_errors(self):
        """ Run every notebook under notebooks, confirm there are no errors"""
        nb_paths = TestAllNbs.get_nb_dirs()
        print(nb_paths)

        for subdir, nbs in nb_paths.items():
            print("EXECUTING NBS IN DIRECTORY: " + subdir)
            if nbs['setup']:
                nb, errors = runner.run_notebook(nbs['setup'])
                print(errors)
                assert len(errors) == 0
            for nb in nbs['notebooks']:
                nb, errors = runner.run_notebook(nb)
                print(errors)
                assert len(errors) == 0

if __name__ == "__main__":
    unittest.main()
