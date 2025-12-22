"""
Parametrized notebook tests for hello-ltr notebooks.

This module uses pytest parametrization to turn each notebook into an individual test,
enabling powerful features:

- pytest --lf: Re-run only last failed tests
- pytest --sw: Stepwise execution (stop at first failure, resume from there)
- pytest -k "opensearch": Run tests matching pattern
- pytest -n auto: Parallel execution
- Individual test results and timing per notebook

Usage:
    # Run all notebooks
    pytest tests/notebooks/test_notebooks.py

    # Re-run only failed notebooks from last run
    pytest --lf tests/notebooks/test_notebooks.py

    # Run only opensearch notebooks
    pytest -k opensearch tests/notebooks/test_notebooks.py

    # Run specific notebook
    pytest tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb]

    # Parallel execution (4x faster)
    pytest -n auto tests/notebooks/test_notebooks.py
"""

import sys
from datetime import datetime

import pytest

from ..nb_test_config import NotebookTestConfig
from ..test_config import IGNORED_NOTEBOOKS, TEST_PATHS

# Known slow notebook patterns (notebooks that typically take > 60 seconds)
# These match the patterns defined in tests/conftest.py
SLOW_PATTERNS = [
    "netfix",
    "bayesian-optimization",
    "bigger bot",
    "lambda-mart",
    "feature_search",
    "evaluation",
]


def _is_slow_notebook(notebook_path: str) -> bool:
    """
    Check if a notebook matches known slow patterns.

    Args:
        notebook_path: Path to the notebook file

    Returns:
        bool: True if notebook matches slow patterns
    """
    if not notebook_path:
        return False
    notebook_path_lower = notebook_path.lower()
    return any(pattern.lower() in notebook_path_lower for pattern in SLOW_PATTERNS)


def collect_notebooks():
    """
    Collect all notebooks to test.

    Notebooks are ordered to optimize test execution:
    1. Setup notebooks run first
    2. hello-ltr notebooks run before dependent notebooks
    3. Fast notebooks run before slow notebooks (slow notebooks run last)

    Slow notebooks are identified by matching patterns in SLOW_PATTERNS
    (e.g., "lambda-mart", "bigger bot", "netfix", "bayesian-optimization").

    Returns:
        List of tuples: (notebook_path, notebook_type, engine)

        notebook_type: 'setup' or 'test'
        engine: 'solr', 'elasticsearch', 'opensearch', or 'general'
    """
    import os

    notebooks = []

    for test_path in TEST_PATHS:
        # Skip if path doesn't exist
        if not os.path.exists(test_path):
            continue

        try:
            config = NotebookTestConfig(path=test_path)
        except Exception:
            # Skip paths that fail to load
            continue

        # Determine engine from path for automatic marking
        engine = "general"
        if "solr" in test_path:
            engine = "solr"
        elif "elasticsearch" in test_path:
            engine = "elasticsearch"
        elif "opensearch" in test_path:
            engine = "opensearch"

        # Add setup notebook if exists
        if config.setup:
            notebooks.append((config.setup, "setup", engine))

        # Add test notebooks (excluding ignored)
        # Sort: hello-ltr notebooks first, then fast notebooks, then slow notebooks last
        test_notebooks = [nb for nb in config.notebooks if nb not in IGNORED_NOTEBOOKS]
        test_notebooks.sort(
            key=lambda x: (
                0 if "hello-ltr" in x.lower() else 1,  # hello-ltr first
                1 if _is_slow_notebook(x) else 0,  # slow notebooks last
                x,  # then alphabetical
            )
        )
        for nb in test_notebooks:
            notebooks.append((nb, "test", engine))

    return notebooks


# For parametrization, we need the list at module level, but we'll handle errors gracefully
_notebook_list: list[tuple[str, str, str]] = []
try:
    _notebook_list = collect_notebooks()
    if not _notebook_list:
        import warnings

        warnings.warn(
            "No notebooks collected for testing. Check TEST_PATHS in test_config.py",
            UserWarning,
            stacklevel=2,
        )
except Exception as e:
    # If collection fails at import time, pytest will handle it during collection
    import warnings

    warnings.warn(
        f"Failed to collect notebooks: {e}. Tests may not run correctly.",
        UserWarning,
        stacklevel=2,
    )
NOTEBOOK_LIST = _notebook_list


def log(msg):
    """Timestamped logging that matches existing test output style."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def format_error_output(notebook_path, errors):
    """
    Format errors with context for detailed error reporting.

    Provides cell index, source code, and traceback information.
    """
    if not errors:
        return ""

    lines = [f"\n{'=' * 60}"]
    lines.append(f"Errors in {notebook_path}: {len(errors)} error(s)")

    for i, error in enumerate(errors, 1):
        lines.append(f"\nError {i}:")

        # Show cell index if available
        cell_index = error.get("cell_index")
        if cell_index is not None:
            lines.append(f"  Cell {cell_index}:")

        # Show cell source (first 3 lines) if available
        cell_source = error.get("cell_source")
        if cell_source:
            source_lines = cell_source.strip().split("\n")[:3]
            lines.append("  Cell source:")
            for line in source_lines:
                lines.append(f"    {line}")

            source_line_count = len(cell_source.strip().split("\n"))
            if source_line_count > 3:
                remaining = source_line_count - 3
                lines.append(f"    ... ({remaining} more lines)")

        # Show error details
        ename = error.get("ename", "Unknown")
        evalue = error.get("evalue", "No message")
        lines.append(f"  {ename}: {evalue}")

        # Show traceback if available
        if "traceback" in error:
            lines.append("  Traceback:")
            for tb_line in error["traceback"]:
                lines.append(f"    {tb_line}")

    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


@pytest.mark.parametrize("notebook_path,notebook_type,engine", NOTEBOOK_LIST)
def test_notebook_executes_without_errors(
    notebook_path, notebook_type, engine, notebook_runner, request
):
    """
    Test that a notebook executes without errors.

    Each notebook is a separate test, enabling:
    - Individual test results and timing
    - pytest --lf to re-run only failed notebooks
    - pytest -k to filter by notebook path or engine
    - Better failure isolation and reporting

    Markers are automatically applied in conftest.py:pytest_collection_modifyitems
    based on engine and notebook_type parameters.

    Args:
        notebook_path: Path to the notebook file
        notebook_type: 'setup' or 'test'
        engine: 'solr', 'elasticsearch', 'opensearch', or 'general'
        notebook_runner: Fixture providing notebook execution function
        request: Pytest request object for accessing fixtures dynamically
    """
    # Arrange: Request container fixtures based on engine (for per-worker containers)
    # This ensures containers are started when USE_WORKER_CONTAINERS=true
    try:
        if engine == "solr":
            request.getfixturevalue("solr_container")
        elif engine == "elasticsearch":
            request.getfixturevalue("elasticsearch_container")
        elif engine == "opensearch":
            request.getfixturevalue("opensearch_container")
    except Exception:
        raise

    # Arrange: Log execution start (matches existing test output style)
    log(f"\n{'=' * 60}")
    log(f"Running: {notebook_path}")
    log(f"{'=' * 60}")

    # Act: Execute notebook using the runner fixture
    result = notebook_runner(notebook_path)

    # Assert: Check for errors and format output
    if result["errors"]:
        print(f"\n{'=' * 80}", file=sys.stderr, flush=True)
        print(
            f"Found {len(result['errors'])} error(s) in notebook: {notebook_path}",
            file=sys.stderr,
            flush=True,
        )
        print(f"{'=' * 80}", file=sys.stderr, flush=True)

        for i, error in enumerate(result["errors"], 1):
            ename = error.get("ename", "Unknown")
            evalue = error.get("evalue", "No message")
            cell_index = error.get("cell_index", "unknown")
            traceback_lines = error.get("traceback", [])

            # Print detailed error info to stderr (will show in pytest output)
            print(
                f"\nError {i}/{len(result['errors'])}:",
                file=sys.stderr,
                flush=True,
            )
            print(f"  Cell Index: {cell_index}", file=sys.stderr, flush=True)
            print(f"  Error Type: {ename}", file=sys.stderr, flush=True)
            print(f"  Error Message: {evalue}", file=sys.stderr, flush=True)
            if traceback_lines:
                print("  Traceback:", file=sys.stderr, flush=True)
                for tb_line in traceback_lines[:15]:  # First 15 lines
                    print(f"    {tb_line}", file=sys.stderr, flush=True)

        error_msg = format_error_output(notebook_path, result["errors"])
        pytest.fail(error_msg, pytrace=False)
    else:
        log(f"✓ Completed successfully ({result['execution_time']:.1f}s)\n")
