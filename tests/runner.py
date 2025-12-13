# Notebook test runner, adapted from
# https://www.blog.pythonlibrary.org/2018/10/16/testing-jupyter-notebooks/
#
# Environment Variables:
#   NOTEBOOK_TIMEOUT_HOURS    Hours to allow per notebook execution (default: 6)
#
import nbformat
import os

from nbconvert.preprocessors import ExecutePreprocessor

def hours(hours):
    """ Hours as seconds """
    return hours * 60 * 60

class PatchedExecutePreprocessor(ExecutePreprocessor):
    """Custom preprocessor with progress logging for long-running notebooks."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cell_count = 0
        self.total_cells = 0
    
    def preprocess(self, nb, resources, km=None):
        self.total_cells = len(nb.cells)
        return super().preprocess(nb, resources, km)
    
    def preprocess_cell(self, cell, resources, cell_index):
        from datetime import datetime
        
        # Log progress for code cells
        if cell.cell_type == 'code' and cell.source.strip():
            self.cell_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            # Show first line of cell for context
            first_line = cell.source.split('\n')[0][:60]
            if len(cell.source.split('\n')[0]) > 60:
                first_line += "..."
            print(f"[{timestamp}]   Cell {cell_index}/{self.total_cells}: {first_line}", flush=True)
        
        return super().preprocess_cell(cell, resources, cell_index)

def run_notebook(notebook_path, timeout=None, save_nb_path=None):
    import sys
    import time
    from datetime import datetime
    
    # Get timeout from environment variable or use default of 6 hours
    if timeout is None:
        timeout_hours = float(os.environ.get('NOTEBOOK_TIMEOUT_HOURS', '6'))
        timeout = int(hours(timeout_hours))
    
    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)
    
    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", file=sys.stderr, flush=True)

    log(f"Loading notebook: {notebook_path}")
    start_time = time.time()
    
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    # Inject patch code as first cell to ensure it runs before any notebook code.
    # This is the SINGLE point where port patching happens - no redundant patches elsewhere.
    # The patch modifies client classes to use test ports (18983, 19200, 19201)
    # instead of default ports (8983, 9200, 9201) to avoid conflicts with production services.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    patch_cell = nbformat.v4.new_code_cell(
        source=f"import sys; import os; sys.path.insert(0, r'{project_root}'); "
               "from tests.patch_clients_for_tests import patch_clients_for_test_ports, patch_requests_for_test_ports; "
               "patch_clients_for_test_ports(); patch_requests_for_test_ports()"
    )
    nb.cells.insert(0, patch_cell)

    # Execute notebook with patched clients
    log(f"Executing {nb_name} ({len(nb.cells)} cells)...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting cell-by-cell execution:", flush=True)
    # Use custom preprocessor for progress logging
    proc = PatchedExecutePreprocessor(timeout=timeout, kernel_name='python3')
    proc.allow_errors = True

    proc.preprocess(nb, {'metadata': {'path': dirname}})
    
    execution_time = time.time() - start_time
    log(f"✓ Completed execution of {nb_name} (took {execution_time:.1f}s)")

    if save_nb_path:
        with open(save_nb_path, mode='wt') as f:
            nbformat.write(nb, f)

    errors = []
    for cell_index, cell in enumerate(nb.cells):
        if 'outputs' in cell:
            for output in cell['outputs']:
                if output.output_type == 'error':
                    # Enhance error with cell context
                    error_with_context = dict(output)
                    error_with_context['cell_index'] = cell_index
                    error_with_context['cell_source'] = cell.get('source', '')
                    # Truncate cell source if too long (first 500 chars)
                    if len(error_with_context['cell_source']) > 500:
                        error_with_context['cell_source'] = error_with_context['cell_source'][:500] + '...'
                    errors.append(error_with_context)

    return nb, errors, execution_time

if __name__ == '__main__':
    nb, errors, exec_time = run_notebook('Testing.ipynb')
    print(f"Errors: {errors}")
    print(f"Execution time: {exec_time:.1f}s")
