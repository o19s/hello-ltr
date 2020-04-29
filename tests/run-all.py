import unittest
import runner
import os
from collections import defaultdict

class TestAllNbs(unittest.TestCase):

    def get_nb_dirs(path='./notebooks', skip=['.ipynb_checkpoints',
                                              'solr/msmarco', 'evaluation (Solr).ipynb']):
        nb_paths = defaultdict(lambda: {'setup': None, 'notebooks': []})
        for subdir, dirs, files in os.walk(path):
            for fname in files:
                full_path = os.path.join(subdir, fname)
                should_skip = False
                for skipPath in skip:
                    if skipPath in fname:
                        should_skip = True
                    if skipPath in subdir:
                        should_skip = True

                if should_skip:
                    print("Skipping %s" % full_path)
                    continue

                if fname.endswith('.ipynb'):
                    if fname == 'setup.ipynb':
                        nb_paths[subdir]['setup'] = full_path
                    else:
                        nb_paths[subdir]['notebooks'].append(full_path)
        return nb_paths
        print(os.path.join(subdir, fname))

    def test_all_no_errors(self):
        """ Run every notebook under notebooks, confirm there are no errors"""
        nb_paths = TestAllNbs.get_nb_dirs()
        print(nb_paths)

        for subdir, nbs in nb_paths.items():
            print("EXECUTING NBS IN DIRECTORY: " + subdir)
            if nbs['setup']:
                print("Setting up ... " + subdir)
                nb, errors = runner.run_notebook(nbs['setup'])
                print(errors)
                assert len(errors) == 0
            for nb in nbs['notebooks']:
                print("Running... " + nb)
                nb, errors = runner.run_notebook(nb)
                print(errors)
                assert len(errors) == 0

if __name__ == "__main__":
    unittest.main()
