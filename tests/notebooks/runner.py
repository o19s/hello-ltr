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

    Logs each code cell with:
    - Cell index and total cell count
    - Timestamp
    - Cell source code (first 5 lines or up to 300 characters)
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
        in long-running notebooks. For each code cell, logs:
        - Cell number (index/total)
        - Timestamp
        - Cell source code (first 5 lines or up to 300 characters)

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

            # Show cell code (first 5 lines, truncated to 300 chars if longer)
            source_lines = cell.source.split("\n")
            if len(source_lines) <= 5:
                # Show all lines if 5 or fewer
                code_preview = cell.source.rstrip()
            else:
                # Show first 5 lines, then truncate if over 300 chars
                code_preview = "\n".join(source_lines[:5]).rstrip()
                if len(code_preview) > 300:
                    code_preview = code_preview[:300] + "..."
                # Add truncation indicator since we have more than 5 lines
                code_preview += "\n    ..."

            # Indent code preview for readability
            indented_code = "\n".join(
                f"    {line}" for line in code_preview.split("\n")
            )

            print(
                f"[{timestamp}]   Cell {index}/{self.total_cells}:\n{indented_code}",
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
        source=f"import sys; "
        f"sys.path.insert(0, r'{project_root}'); "
        "from tests.patch_clients_for_tests import patch_clients_for_test_ports, patch_requests_for_test_ports; "
        "patch_clients_for_test_ports(); patch_requests_for_test_ports()"
    )
    nb.cells.insert(0, patch_cell)

    # Patch configs_dir for Elasticsearch/OpenSearch notebooks
    # This ensures clients can find settings files when running from project root during tests
    notebook_dir = os.path.dirname(notebook_path)
    is_es_notebook = (
        "elasticsearch" in notebook_path.lower()
        or "opensearch" in notebook_path.lower()
    ) and ("tmdb" in notebook_path.lower() or "osc-blog" in notebook_path.lower())

    if is_es_notebook:
        # Determine relative path from project root to notebook directory
        notebook_dir_rel = os.path.relpath(notebook_dir, project_root)

        # Set environment variable for the notebook's config directory
        # This is used by the OpenSearchClient and ElasticClient when configs_dir is not specified
        # The clients will check this env var and use it as the default configs_dir
        os.environ["NOTEBOOK_CONFIGS_DIR"] = notebook_dir_rel
        insert_index = 1
    else:
        insert_index = 1

    # Check if notebook needs index setup (uses reset_ltr, create_featureset, or sltr queries)
    # This ensures notebooks that depend on the index have it created if needed
    # Note: We check for sltr even if rebuild is present, because rebuild might fail
    # or the notebook's rebuild code might not execute properly in test environment.
    # The injected code checks if index exists before creating, so it's safe to run.
    notebook_source = " ".join(
        [cell.get("source", "") for cell in nb.cells if cell.get("cell_type") == "code"]
    )
    # Notebooks that use sltr queries always need the index, even if they have rebuild
    # because sltr queries will fail if the index doesn't exist
    needs_index = (
        "reset_ltr" in notebook_source
        or "create_featureset" in notebook_source
        or "sltr" in notebook_source
    )
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
            # Check if notebook will rebuild the index itself
            # If it does, we only create the index if it doesn't exist (don't force rebuild)
            # This avoids conflicts where we create it, then notebook deletes and fails to recreate
            notebook_will_rebuild = (
                "rebuild" in notebook_source and "force=True" in notebook_source
            )

            # Inject index setup code after patch cell
            # This ensures the index exists before notebooks try to use it
            if notebook_will_rebuild:
                # Notebook will rebuild, so only create if missing (don't force)
                # This avoids the scenario where we create it, notebook deletes it, then fails to recreate
                rebuild_strategy = (
                    "if not _test_client.check_index_exists('tmdb'):\n"
                    "            movies = indexable_movies(movies_path=data_file)\n"
                    "            rebuild(_test_client, index='tmdb', doc_src=movies, force=False)\n"
                    "            print('[TEST] Created tmdb index (notebook will rebuild it)')\n"
                    "        else:\n"
                    "            print('[TEST] Index exists, notebook will rebuild it')"
                )
            else:
                # Notebook won't rebuild, so ensure index exists (force rebuild for clean state)
                rebuild_strategy = (
                    "movies = indexable_movies(movies_path=data_file)\n"
                    "        rebuild(_test_client, index='tmdb', doc_src=movies, force=True)\n"
                    "        print('[TEST] Successfully created/rebuilt tmdb index')"
                )

            index_setup_cell = nbformat.v4.new_code_cell(
                source=f"{client_import}\n"
                "import os\n"
                "from ltr import download\n"
                "from ltr.helpers.movies import indexable_movies\n"
                "from ltr.index import rebuild\n"
                "\n"
                "# Ensure tmdb index exists for notebooks that need it\n"
                "# This runs before the notebook's own rebuild code to ensure the index exists\n"
                "_test_client = Client()\n"
                "# Download data if it doesn't exist\n"
                "data_file = 'data/tmdb.json'\n"
                "if not os.path.exists(data_file):\n"
                "    try:\n"
                "        corpus = 'http://es-learn-to-rank.labs.o19s.com/tmdb.json'\n"
                "        download([corpus], dest='data/')\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not download data: {{e}}')\n"
                "        print('[TEST] Index creation skipped - notebook may fail if data is required')\n"
                "# Create index if data file exists\n"
                "if os.path.exists(data_file):\n"
                "    try:\n"
                f"        {rebuild_strategy}\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not create index: {{e}}')\n"
                "        print('[TEST] Notebook may fail if index is required')\n"
                "del _test_client"
            )
            nb.cells.insert(insert_index, index_setup_cell)
            insert_index += 1

    # Check if notebook uses train() or feature_search() and reduce expensive parameters for testing
    # This reduces kcv, trees, bag, and leafs to speed up tests while still validating functionality
    uses_train = "train(" in notebook_source
    uses_feature_search = "feature_search(" in notebook_source

    # Check if notebook builds training sets (uses FeatureLogger.log_for_qid with groupby)
    # This can be expensive if there are many queries/judgments
    uses_feature_logging = (
        "log_for_qid" in notebook_source
        and "groupby" in notebook_source
        and "judgments_open" in notebook_source
    )

    if uses_train or uses_feature_search:
        # Get test mode limits from environment or use defaults
        max_test_folds = int(os.environ.get("NOTEBOOK_MAX_KCV_FOLDS", "1"))
        max_test_trees = int(os.environ.get("NOTEBOOK_MAX_TREES", "1"))
        max_test_bag = int(os.environ.get("NOTEBOOK_MAX_BAG", "1"))
        max_test_leafs = int(os.environ.get("NOTEBOOK_MAX_LEAFS", "1"))
        max_test_features = int(
            os.environ.get("NOTEBOOK_MAX_FEATURES", "2")
        )  # Limit features for feature_search to reduce exponential combinations

        # Build comprehensive patch code for train() and feature_search()
        patch_source = "# Reduce expensive parameters for faster testing\n"
        patch_source += "from ltr.ranklib import train as _original_train, feature_search as _original_feature_search\n"
        patch_source += "\n"

        # Patch train() function
        if uses_train:
            patch_source += "def train(*args, kcv=None, trees=None, bag=None, leafs=None, features=None, **kwargs):\n"
            patch_source += '    """Wrapped train() function that reduces expensive parameters for testing."""\n'
            patch_source += "    print('[TEST MODE] Wrapper train() called')\n"
            patch_source += "    # Get parameter values (from kwargs if not provided as named parameters)\n"
            patch_source += (
                "    kcv_val = kcv if kcv is not None else kwargs.get('kcv', None)\n"
            )
            patch_source += "    trees_val = trees if trees is not None else kwargs.get('trees', None)\n"
            patch_source += (
                "    bag_val = bag if bag is not None else kwargs.get('bag', None)\n"
            )
            patch_source += "    leafs_val = leafs if leafs is not None else kwargs.get('leafs', None)\n"
            patch_source += "    features_val = features if features is not None else kwargs.get('features', None)\n"
            patch_source += "    # Reduce expensive parameters\n"
            patch_source += (
                f"    if kcv_val is not None and kcv_val > {max_test_folds}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing kcv from {{kcv_val}} to {max_test_folds} for faster testing')\n"
            patch_source += f"        kcv = {max_test_folds}\n"
            patch_source += (
                "        kwargs.pop('kcv', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if trees_val is not None and trees_val > {max_test_trees}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing trees from {{trees_val}} to {max_test_trees} for faster testing')\n"
            patch_source += f"        trees = {max_test_trees}\n"
            patch_source += (
                "        kwargs.pop('trees', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if bag_val is not None and bag_val > {max_test_bag}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing bag from {{bag_val}} to {max_test_bag} for faster testing')\n"
            patch_source += f"        bag = {max_test_bag}\n"
            patch_source += (
                "        kwargs.pop('bag', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if leafs_val is not None and leafs_val > {max_test_leafs}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing leafs from {{leafs_val}} to {max_test_leafs} for faster testing')\n"
            patch_source += f"        leafs = {max_test_leafs}\n"
            patch_source += (
                "        kwargs.pop('leafs', None)  # Remove from kwargs if present\n"
            )
            patch_source += "    # Limit features list to reduce training complexity\n"
            patch_source += f"    if features_val is not None and len(features_val) > {max_test_features}:\n"
            patch_source += f"        print(f'[TEST MODE] Reducing train() features from {{len(features_val)}} to {max_test_features} ({{features_val[:{max_test_features}]}}) for faster testing')\n"
            patch_source += f"        features = features_val[:{max_test_features}]\n"
            patch_source += "        if 'features' in kwargs:\n"
            patch_source += "            kwargs['features'] = features\n"
            patch_source += "    elif features_val is not None:\n"
            patch_source += "        features = features_val\n"
            patch_source += "    else:\n"
            patch_source += "        features = None\n"
            patch_source += "    return _original_train(*args, kcv=kcv, trees=trees, bag=bag, leafs=leafs, features=features, **kwargs)\n"
            patch_source += "\n"
            patch_source += "# Monkey-patch the train function in ltr.ranklib module\n"
            patch_source += "import ltr.ranklib\n"
            patch_source += "ltr.ranklib.train = train\n"
            patch_source += (
                "print('[TEST MODE] Successfully patched ltr.ranklib.train')\n"
            )
            patch_source += "\n"

        # Patch feature_search() function
        if uses_feature_search:
            patch_source += "def feature_search(*args, kcv=None, trees=None, bag=None, leafs=None, features=None, **kwargs):\n"
            patch_source += '    """Wrapped feature_search() function that reduces expensive parameters for testing."""\n'
            patch_source += "    print('[TEST MODE] Wrapper feature_search() called')\n"
            patch_source += "    # Get parameter values (from kwargs if not provided as named parameters)\n"
            patch_source += (
                "    kcv_val = kcv if kcv is not None else kwargs.get('kcv', None)\n"
            )
            patch_source += "    trees_val = trees if trees is not None else kwargs.get('trees', None)\n"
            patch_source += (
                "    bag_val = bag if bag is not None else kwargs.get('bag', None)\n"
            )
            patch_source += "    leafs_val = leafs if leafs is not None else kwargs.get('leafs', None)\n"
            patch_source += "    features_val = features if features is not None else kwargs.get('features', None)\n"
            patch_source += "    # Reduce expensive parameters\n"
            patch_source += (
                f"    if kcv_val is not None and kcv_val > {max_test_folds}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing kcv from {{kcv_val}} to {max_test_folds} for faster testing')\n"
            patch_source += f"        kcv = {max_test_folds}\n"
            patch_source += (
                "        kwargs.pop('kcv', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if trees_val is not None and trees_val > {max_test_trees}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing trees from {{trees_val}} to {max_test_trees} for faster testing')\n"
            patch_source += f"        trees = {max_test_trees}\n"
            patch_source += (
                "        kwargs.pop('trees', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if bag_val is not None and bag_val > {max_test_bag}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing bag from {{bag_val}} to {max_test_bag} for faster testing')\n"
            patch_source += f"        bag = {max_test_bag}\n"
            patch_source += (
                "        kwargs.pop('bag', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if leafs_val is not None and leafs_val > {max_test_leafs}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing leafs from {{leafs_val}} to {max_test_leafs} for faster testing')\n"
            patch_source += f"        leafs = {max_test_leafs}\n"
            patch_source += (
                "        kwargs.pop('leafs', None)  # Remove from kwargs if present\n"
            )
            patch_source += "    # Limit features list to reduce exponential combinations (2^n - 1 combinations)\n"
            patch_source += "    # Reducing from 9 features (511 combos) to 2 features (3 combos) = 170x speedup!\n"
            patch_source += (
                "    # Always set features to ensure it's passed correctly\n"
            )
            patch_source += "    if features_val is not None:\n"
            patch_source += f"        if len(features_val) > {max_test_features}:\n"
            patch_source += f"            print(f'[TEST MODE] Reducing features from {{len(features_val)}} to {max_test_features} ({{features_val[:{max_test_features}]}}) for faster testing')\n"
            patch_source += (
                f"            features = features_val[:{max_test_features}]\n"
            )
            patch_source += "        else:\n"
            patch_source += "            features = features_val\n"
            patch_source += (
                "        # Update kwargs if features was passed via kwargs\n"
            )
            patch_source += "        if 'features' in kwargs:\n"
            patch_source += "            kwargs['features'] = features\n"
            patch_source += "    else:\n"
            patch_source += "        features = None\n"
            patch_source += "    return _original_feature_search(*args, kcv=kcv, trees=trees, bag=bag, leafs=leafs, features=features, **kwargs)\n"
            patch_source += "\n"
            patch_source += (
                "# Monkey-patch the feature_search function in ltr.ranklib module\n"
            )
            patch_source += "ltr.ranklib.feature_search = feature_search\n"
            patch_source += (
                "print('[TEST MODE] Successfully patched ltr.ranklib.feature_search')\n"
            )

        patch_cell = nbformat.v4.new_code_cell(source=patch_source)
        nb.cells.insert(insert_index, patch_cell)
        insert_index += 1

    # Limit training set size by reducing number of queries processed
    if uses_feature_logging:
        max_test_queries = int(
            os.environ.get("NOTEBOOK_MAX_QUERIES", "2")
        )  # Limit to 2 queries for faster testing
        max_test_judgments_per_query = int(
            os.environ.get("NOTEBOOK_MAX_JUDGMENTS_PER_QUERY", "2")
        )  # Limit judgments per query

        training_set_patch = "# Limit training set size for faster testing\n"
        training_set_patch += "from itertools import groupby\n"
        training_set_patch += "\n"
        training_set_patch += (
            "# Wrap FeatureLogger to limit queries and judgments per query\n"
        )
        training_set_patch += "# Use module-level counter so limit applies across all FeatureLogger instances\n"
        training_set_patch += "import ltr.log\n"
        training_set_patch += "ltr.log._test_query_count = 0\n"
        training_set_patch += f"ltr.log._test_max_queries = {max_test_queries}\n"
        training_set_patch += (
            f"ltr.log._test_max_judgments_per_query = {max_test_judgments_per_query}\n"
        )
        training_set_patch += (
            "from ltr.log import FeatureLogger as _OriginalFeatureLogger\n"
        )
        training_set_patch += "class LimitedFeatureLogger(_OriginalFeatureLogger):\n"
        training_set_patch += "    def log_for_qid(self, qid, judgments, keywords):\n"
        training_set_patch += "        # Limit number of queries processed (shared across all instances)\n"
        training_set_patch += "        import ltr.log\n"
        training_set_patch += (
            "        if ltr.log._test_query_count >= ltr.log._test_max_queries:\n"
        )
        training_set_patch += "            print(f'[TEST MODE] Skipping query {qid} - already processed {ltr.log._test_max_queries} queries for faster testing')\n"
        training_set_patch += "            return [], list(judgments)  # Return empty training set, all judgments discarded\n"
        training_set_patch += "        ltr.log._test_query_count += 1\n"
        training_set_patch += "        # Limit judgments per query\n"
        training_set_patch += "        judgments_list = list(judgments)\n"
        training_set_patch += (
            "        if len(judgments_list) > ltr.log._test_max_judgments_per_query:\n"
        )
        training_set_patch += "            print(f'[TEST MODE] Limiting query {qid} to {ltr.log._test_max_judgments_per_query} judgments (from {len(judgments_list)}) for faster testing')\n"
        training_set_patch += "            judgments_list = judgments_list[:ltr.log._test_max_judgments_per_query]\n"
        training_set_patch += (
            "        return super().log_for_qid(qid, judgments_list, keywords)\n"
        )
        training_set_patch += "\n"
        training_set_patch += "# Monkey-patch FeatureLogger\n"
        training_set_patch += "ltr.log.FeatureLogger = LimitedFeatureLogger\n"
        training_set_patch += f"print(f'[TEST MODE] Successfully patched FeatureLogger to limit to {max_test_queries} queries and {max_test_judgments_per_query} judgments per query')\n"

        training_set_cell = nbformat.v4.new_code_cell(source=training_set_patch)
        nb.cells.insert(insert_index, training_set_cell)
        insert_index += 1

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
