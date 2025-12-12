# Notebook test runner, adapted from
# https://www.blog.pythonlibrary.org/2018/10/16/testing-jupyter-notebooks/
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

def run_notebook(notebook_path, timeout=hours(6), save_nb_path=None):
    import sys
    from datetime import datetime
    
    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)
    
    def log(msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", file=sys.stderr, flush=True)

    log(f"Loading notebook: {notebook_path}")
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    # Inject patch code as first cell to ensure it runs before any notebook code
    # Use absolute path to project root to find tests module
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    patch_cell = nbformat.v4.new_code_cell(
        source=f"import sys; import os; sys.path.insert(0, r'{project_root}'); "
               "from tests.patch_clients_for_tests import patch_clients_for_test_ports, patch_requests_for_test_ports; "
               "patch_clients_for_test_ports(); patch_requests_for_test_ports()"
    )
    nb.cells.insert(0, patch_cell)

    # Patching is handled by the injected cell above
    log(f"Executing {nb_name} ({len(nb.cells)} cells)...")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting cell-by-cell execution:", flush=True)
    # Use custom preprocessor for progress logging
    proc = PatchedExecutePreprocessor(timeout=timeout, kernel_name='python3')
    proc.allow_errors = True

    proc.preprocess(nb, {'metadata': {'path': dirname}})
    log(f"✓ Completed execution of {nb_name}")

    if save_nb_path:
        with open(save_nb_path, mode='wt') as f:
            nbformat.write(nb, f)

    errors = []
    for cell in nb.cells:
        if 'outputs' in cell:
            for output in cell['outputs']:
                if output.output_type == 'error':
                    errors.append(output)

    return nb, errors

if __name__ == '__main__':
    nb, errors = run_notebook('Testing.ipynb')
    print(errors)
