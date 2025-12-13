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

    def _print_errors_with_context(self, notebook_path, errors):
        """Print errors with cell context (index and source) for better debugging."""
        import sys
        
        if not errors:
            return
        
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"Errors in {notebook_path}: {len(errors)} error(s)", file=sys.stderr)
        for i, error in enumerate(errors, 1):
            print(f"\nError {i}:", file=sys.stderr)
            # Show cell index if available
            cell_index = error.get('cell_index')
            if cell_index is not None:
                print(f"  Cell {cell_index}:", file=sys.stderr)
            # Show cell source if available
            cell_source = error.get('cell_source')
            if cell_source:
                # Show first few lines of cell source
                source_lines = cell_source.strip().split('\n')[:3]
                print("  Cell source:", file=sys.stderr)
                for line in source_lines:
                    print(f"    {line}", file=sys.stderr)
                source_line_count = len(cell_source.strip().split('\n'))
                if source_line_count > 3:
                    remaining_lines = source_line_count - 3
                    print(f"    ... ({remaining_lines} more lines)", file=sys.stderr)
            # Show error details
            print(f"  {error.get('ename', 'Unknown')}: {error.get('evalue', 'No message')}", file=sys.stderr)
            if 'traceback' in error:
                print("  Traceback:", file=sys.stderr)
                for line in error['traceback']:
                    print(f"    {line}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)

    def test_for_no_errors(self):
        """ Run all nbs in directories at test_paths()
            also included in nbs_to_run(),
            excepting those in ignored_nbs()
            - assert there are no errors
            - generate summary report
            """
        import time
        from datetime import datetime
        
        def log(msg):
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {msg}", flush=True)
        
        # Track results for summary report
        test_results = []
        total_start_time = time.time()
        
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
                nb, errors, exec_time = runner.run_notebook(nb_cfg.setup, save_nb_path=NotebooksTestCase.SAVE_NB_PATH)
                test_results.append({
                    'name': nb_cfg.setup,
                    'type': 'setup',
                    'status': 'PASS' if len(errors) == 0 else 'FAIL',
                    'execution_time': exec_time,
                    'error_count': len(errors),
                    'errors': errors
                })
                if errors:
                    self._print_errors_with_context(nb_cfg.setup, errors)
                assert len(errors) == 0
                log("✓ Setup completed successfully\n")
            for nb in nb_cfg.notebooks:
                if nb in self.nbs_to_run():
                    if nb in self.ignored_nbs():
                        log(f"Ignored: {nb}")
                        test_results.append({
                            'name': nb,
                            'type': 'notebook',
                            'status': 'IGNORED',
                            'execution_time': 0,
                            'error_count': 0,
                            'errors': []
                        })
                    else:
                        completed_notebooks += 1
                        log(f"\n{'='*60}")
                        log(f"[{completed_notebooks}/{total_notebooks}] Running: {nb}")
                        log(f"{'='*60}")
                        nb_result, errors, exec_time = runner.run_notebook(nb, save_nb_path=NotebooksTestCase.SAVE_NB_PATH)
                        test_results.append({
                            'name': nb,
                            'type': 'notebook',
                            'status': 'PASS' if len(errors) == 0 else 'FAIL',
                            'execution_time': exec_time,
                            'error_count': len(errors),
                            'errors': errors
                        })
                        if errors:
                            self._print_errors_with_context(nb, errors)
                        else:
                            log("✓ Notebook completed successfully\n")
                        assert len(errors) == 0
        
        total_execution_time = time.time() - total_start_time
        
        # Generate and print summary report
        self._generate_test_report(test_results, total_execution_time)
        
        log(f"All {completed_notebooks} notebook(s) completed successfully")
    
    def _generate_test_report(self, results, total_time):
        """Generate and print a summary test report."""
        import sys
        
        # Calculate statistics
        total_tests = len(results)
        passed = sum(1 for r in results if r['status'] == 'PASS')
        failed = sum(1 for r in results if r['status'] == 'FAIL')
        ignored = sum(1 for r in results if r['status'] == 'IGNORED')
        total_exec_time = sum(r['execution_time'] for r in results)
        
        # Sort by execution time (slowest first)
        sorted_by_time = sorted(
            [r for r in results if r['status'] != 'IGNORED'],
            key=lambda x: x['execution_time'],
            reverse=True
        )
        
        # Print summary report
        print(f"\n{'='*80}", file=sys.stderr)
        print("TEST SUMMARY REPORT", file=sys.stderr)
        print(f"{'='*80}", file=sys.stderr)
        print(f"Total notebooks tested: {total_tests}", file=sys.stderr)
        print(f"  ✓ Passed: {passed}", file=sys.stderr)
        print(f"  ✗ Failed: {failed}", file=sys.stderr)
        print(f"  ⊘ Ignored: {ignored}", file=sys.stderr)
        print(f"\nTotal execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)", file=sys.stderr)
        print(f"Notebook execution time: {total_exec_time:.1f}s ({total_exec_time/60:.1f} minutes)", file=sys.stderr)
        
        if sorted_by_time:
            print("\nSlowest notebooks (top 10):", file=sys.stderr)
            for i, result in enumerate(sorted_by_time[:10], 1):
                status_symbol = "✓" if result['status'] == 'PASS' else "✗"
                print(f"  {i:2d}. {status_symbol} {result['execution_time']:6.1f}s - {result['name']}", file=sys.stderr)
        
        if failed > 0:
            print("\nFailed notebooks:", file=sys.stderr)
            for result in results:
                if result['status'] == 'FAIL':
                    print(f"  ✗ {result['name']} ({result['error_count']} error(s))", file=sys.stderr)
        
        print(f"{'='*80}\n", file=sys.stderr)

