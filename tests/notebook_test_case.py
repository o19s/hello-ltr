import unittest
from nb_test_config import NotebookTestConfig
import runner

class NotebooksTestCase(unittest.TestCase):

    SAVE_NB_PATH='tests/last_run.ipynb'

    def test_paths(self):
        return []

    def ignored_nbs(self):
        return []

    def nbs_to_run(self):
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
        import sys
        from datetime import datetime
        
        def log(msg):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {msg}", flush=True)
        
        total_notebooks = 0
        completed_notebooks = 0
        
        # First pass: count notebooks
        for nb_path in self.test_paths():
            nb_cfg = NotebookTestConfig(path=nb_path)
            if nb_cfg.setup:
                total_notebooks += 1
            for nb in nb_cfg.notebooks:
                if nb in self.nbs_to_run() and nb not in self.ignored_nbs():
                    total_notebooks += 1
        
        log(f"Found {total_notebooks} notebook(s) to execute")
        log(f"{'='*60}\n")
        
        for nb_path in self.test_paths():
            nb_cfg = NotebookTestConfig(path=nb_path)
            log(f"\n{'#'*60}")
            log(f"# EXECUTING NBS IN DIRECTORY: {nb_path}")
            log(f"{'#'*60}")
            if nb_cfg.setup:
                completed_notebooks += 1
                log(f"\n{'='*60}")
                log(f"[{completed_notebooks}/{total_notebooks}] Setting up: {nb_cfg.setup}")
                log(f"{'='*60}")
                nb, errors = runner.run_notebook(nb_cfg.setup, save_nb_path=NotebooksTestCase.SAVE_NB_PATH)
                if errors:
                    print(f"Errors in setup notebook: {errors}", file=sys.stderr)
                assert len(errors) == 0
                log("✓ Setup completed successfully\n")
            for nb in nb_cfg.notebooks:
                if nb in self.nbs_to_run():
                    if nb in self.ignored_nbs():
                        log(f"Ignored: {nb}")
                    else:
                        completed_notebooks += 1
                        log(f"\n{'='*60}")
                        log(f"[{completed_notebooks}/{total_notebooks}] Running: {nb}")
                        log(f"{'='*60}")
                        nb_result, errors = runner.run_notebook(nb, save_nb_path=NotebooksTestCase.SAVE_NB_PATH)
                        if errors:
                            print(f"\n{'='*60}", file=sys.stderr)
                            print(f"Errors in {nb}: {len(errors)} error(s)", file=sys.stderr)
                            for i, error in enumerate(errors, 1):
                                print(f"\nError {i}:", file=sys.stderr)
                                print(f"  {error.get('ename', 'Unknown')}: {error.get('evalue', 'No message')}", file=sys.stderr)
                                if 'traceback' in error:
                                    print("  Traceback:", file=sys.stderr)
                                    for line in error['traceback']:
                                        print(f"    {line}", file=sys.stderr)
                            print(f"{'='*60}\n", file=sys.stderr)
                        else:
                            log("✓ Notebook completed successfully\n")
                        assert len(errors) == 0
        
        log(f"All {completed_notebooks} notebook(s) completed successfully")

