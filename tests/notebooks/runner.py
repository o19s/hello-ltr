"""
Notebook test runner for executing Jupyter notebooks in tests.

This module provides functionality to execute Jupyter notebooks programmatically,
capture errors, and inject port patching code to redirect connections to test ports.

Adapted from: https://www.blog.pythonlibrary.org/2018/10/16/testing-jupyter-notebooks/

Environment Variables:
    NOTEBOOK_TIMEOUT_MINUTES: Minutes to allow per notebook execution (default: 5)

Key Functions:
    run_notebook: Execute a notebook and return results with error details
    PatchedExecutePreprocessor: Custom preprocessor with progress logging
"""

import os

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor


def hours(hours):
    """Convert hours to seconds.

    Args:
        hours: Number of hours

    Returns:
        int: Number of seconds
    """
    return hours * 60 * 60


class PatchedExecutePreprocessor(ExecutePreprocessor):
    """Custom preprocessor with progress logging for long-running notebooks.

    Extends ExecutePreprocessor to add cell-by-cell progress logging,
    making it easier to track execution progress for long-running notebooks.
    """

    def __init__(self, *args, **kwargs):
        """Initialize preprocessor with cell tracking counters.

        Args:
            *args: Positional arguments passed to parent ExecutePreprocessor
            **kwargs: Keyword arguments passed to parent ExecutePreprocessor
        """
        super().__init__(*args, **kwargs)
        self.cell_count = 0
        self.total_cells = 0

    def preprocess(self, nb, resources=None, km=None):
        """Preprocess notebook and track total cell count.

        Args:
            nb: Notebook node
            resources: Resources dictionary (optional, defaults to None)
            km: Optional kernel manager

        Returns:
            Tuple of (notebook, resources) after preprocessing
        """
        self.total_cells = len(nb.cells)
        return super().preprocess(nb, resources, km)

    def preprocess_cell(self, cell, resources, index):
        """Preprocess a single cell with progress logging.

        Logs progress for code cells to help track execution progress
        in long-running notebooks.

        Args:
            cell: Cell to preprocess
            resources: Resources dictionary
            index: Index of the cell in the notebook

        Returns:
            Tuple of (cell, resources) after preprocessing
        """
        from datetime import datetime

        # Log progress for code cells
        if cell.cell_type == "code" and cell.source.strip():
            self.cell_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            # Show first line of cell for context
            first_line = cell.source.split("\n")[0][:60]
            if len(cell.source.split("\n")[0]) > 60:
                first_line += "..."
            print(
                f"[{timestamp}]   Cell {index}/{self.total_cells}: {first_line}",
                flush=True,
            )

        return super().preprocess_cell(cell, resources, index)


def run_notebook(notebook_path, timeout=None, save_nb_path=None):
    """
    Execute a Jupyter notebook and return results with error details.

    This function:
    - Loads a notebook from the specified path
    - Injects port patching code as the first cell (to redirect to test ports)
    - Executes all cells using PatchedExecutePreprocessor
    - Captures errors with context (cell index, source code, traceback)
    - Optionally saves the executed notebook to a file
    - Returns structured results including errors and execution time

    Args:
        notebook_path: Path to the notebook file to execute
        timeout: Optional timeout in seconds (defaults to NOTEBOOK_TIMEOUT_MINUTES env var or 5 minutes)
        save_nb_path: Optional path to save executed notebook (default: 'tests/last_run.ipynb')

    Returns:
        tuple: (notebook, errors, execution_time)
            - notebook: Executed notebook object (nbformat.NotebookNode)
            - errors: List of error dictionaries, each containing:
                - 'ename': Exception name
                - 'evalue': Exception message
                - 'traceback': List of traceback lines
                - 'cell_index': Index of cell where error occurred
                - 'cell_source': Source code of the cell
            - execution_time: Time taken in seconds (float)
    """
    import sys
    import time
    from datetime import datetime

    # Get timeout from environment variable or use default of 5 minutes
    if timeout is None:
        timeout_minutes = float(os.environ.get("NOTEBOOK_TIMEOUT_MINUTES", "5"))
        timeout = int(timeout_minutes * 60)

    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)

    def log(msg):
        """Log a message with timestamp to stderr.

        Args:
            msg: Message to log
        """
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
    # project_root should be the parent of 'tests' directory, not the tests directory itself
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    patch_cell = nbformat.v4.new_code_cell(
        source=f"import sys; import os; sys.path.insert(0, r'{project_root}'); "
        "from tests.patch_clients_for_tests import patch_clients_for_test_ports, patch_requests_for_test_ports; "
        "patch_clients_for_test_ports(); patch_requests_for_test_ports()"
    )
    nb.cells.insert(0, patch_cell)

    # Check if notebook needs index setup (uses reset_ltr or create_featureset but not rebuild)
    # This ensures notebooks that depend on the index have it created if needed
    notebook_source = " ".join(
        [cell.get("source", "") for cell in nb.cells if cell.get("cell_type") == "code"]
    )
    needs_index = (
        "reset_ltr" in notebook_source or "create_featureset" in notebook_source
    ) and "rebuild" not in notebook_source
    is_tmdb_notebook = "tmdb" in notebook_path.lower()

    if needs_index and is_tmdb_notebook:
        # Determine client type from notebook path
        if "solr" in notebook_path.lower():
            client_import = "from ltr.client import SolrClient as Client"
        elif "opensearch" in notebook_path.lower():
            client_import = "from ltr.client import OpenSearchClient as Client"
        elif (
            "elasticsearch" in notebook_path.lower()
            or "elastic" in notebook_path.lower()
        ):
            client_import = "from ltr.client import ElasticClient as Client"
        else:
            client_import = None

        if client_import:
            # Inject index setup code after patch cell
            # This ensures the index exists before notebooks try to use it
            index_setup_cell = nbformat.v4.new_code_cell(
                source=f"{client_import}\n"
                "import os\n"
                "from ltr import download\n"
                "from ltr.helpers.movies import indexable_movies\n"
                "from ltr.index import rebuild\n"
                "\n"
                "# Ensure tmdb index exists for notebooks that need it\n"
                "_test_client = Client()\n"
                "if not _test_client.check_index_exists('tmdb'):\n"
                "    # Download data if it doesn't exist\n"
                "    data_file = 'data/tmdb.json'\n"
                "    if not os.path.exists(data_file):\n"
                "        try:\n"
                "            corpus = 'http://es-learn-to-rank.labs.o19s.com/tmdb.json'\n"
                "            download([corpus], dest='data/')\n"
                "        except Exception as e:\n"
                "            print(f'Warning: Could not download data: {{e}}')\n"
                "            print('Index creation skipped - notebook may fail if data is required')\n"
                "    # Create index if data file exists\n"
                "    if os.path.exists(data_file):\n"
                "        movies = indexable_movies(movies=data_file)\n"
                "        rebuild(_test_client, index='tmdb', doc_src=movies)\n"
                "del _test_client"
            )
            nb.cells.insert(1, index_setup_cell)

    # Execute notebook with patched clients
    log(f"Executing {nb_name} ({len(nb.cells)} cells)...")
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Starting cell-by-cell execution:",
        flush=True,
    )
    # Use custom preprocessor for progress logging
    proc = PatchedExecutePreprocessor(timeout=timeout, kernel_name="python3")
    proc.allow_errors = True

    proc.preprocess(nb, {"metadata": {"path": dirname}})

    execution_time = time.time() - start_time
    log(f"✓ Completed execution of {nb_name} (took {execution_time:.1f}s)")

    if save_nb_path:
        with open(save_nb_path, mode="w") as f:
            nbformat.write(nb, f)

    errors = []
    for cell_index, cell in enumerate(nb.cells):
        if "outputs" in cell:
            for output in cell["outputs"]:
                if output.output_type == "error":
                    # Enhance error with cell context
                    error_with_context = dict(output)
                    error_with_context["cell_index"] = cell_index
                    error_with_context["cell_source"] = cell.get("source", "")
                    # Truncate cell source if too long (first 500 chars)
                    if len(error_with_context["cell_source"]) > 500:
                        error_with_context["cell_source"] = (
                            error_with_context["cell_source"][:500] + "..."
                        )
                    errors.append(error_with_context)

    return nb, errors, execution_time
