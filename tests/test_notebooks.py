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
    pytest tests/test_notebooks.py
    
    # Re-run only failed notebooks from last run
    pytest --lf tests/test_notebooks.py
    
    # Run only opensearch notebooks
    pytest -k opensearch tests/test_notebooks.py
    
    # Run specific notebook
    pytest tests/test_notebooks.py::test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb]
    
    # Parallel execution (4x faster)
    pytest -n auto tests/test_notebooks.py
"""
import pytest
from datetime import datetime

# Import test configuration
from test_config import TEST_PATHS, IGNORED_NOTEBOOKS
from nb_test_config import NotebookTestConfig


def collect_notebooks():
    """
    Collect all notebooks to test.
    
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
        engine = 'general'
        if 'solr' in test_path:
            engine = 'solr'
        elif 'elasticsearch' in test_path:
            engine = 'elasticsearch'
        elif 'opensearch' in test_path:
            engine = 'opensearch'
        
        # Add setup notebook if exists
        if config.setup:
            notebooks.append((config.setup, 'setup', engine))
        
        # Add test notebooks (excluding ignored)
        for nb in config.notebooks:
            if nb not in IGNORED_NOTEBOOKS:
                notebooks.append((nb, 'test', engine))
    
    return notebooks


# For parametrization, we need the list at module level, but we'll handle errors gracefully
try:
    NOTEBOOK_LIST = collect_notebooks()
    if not NOTEBOOK_LIST:
        import warnings
        warnings.warn(
            "No notebooks collected for testing. Check TEST_PATHS in test_config.py",
            UserWarning
        )
except Exception as e:
    # If collection fails at import time, pytest will handle it during collection
    import warnings
    warnings.warn(
        f"Failed to collect notebooks: {e}. Tests may not run correctly.",
        UserWarning
    )
    NOTEBOOK_LIST = []


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
    
    lines = [f"\n{'='*60}"]
    lines.append(f"Errors in {notebook_path}: {len(errors)} error(s)")
    
    for i, error in enumerate(errors, 1):
        lines.append(f"\nError {i}:")
        
        # Show cell index if available
        cell_index = error.get('cell_index')
        if cell_index is not None:
            lines.append(f"  Cell {cell_index}:")
        
        # Show cell source (first 3 lines) if available
        cell_source = error.get('cell_source')
        if cell_source:
            source_lines = cell_source.strip().split('\n')[:3]
            lines.append("  Cell source:")
            for line in source_lines:
                lines.append(f"    {line}")
            
            source_line_count = len(cell_source.strip().split('\n'))
            if source_line_count > 3:
                remaining = source_line_count - 3
                lines.append(f"    ... ({remaining} more lines)")
        
        # Show error details
        ename = error.get('ename', 'Unknown')
        evalue = error.get('evalue', 'No message')
        lines.append(f"  {ename}: {evalue}")
        
        # Show traceback if available
        if 'traceback' in error:
            lines.append("  Traceback:")
            for tb_line in error['traceback']:
                lines.append(f"    {tb_line}")
    
    lines.append(f"{'='*60}\n")
    return "\n".join(lines)


@pytest.mark.parametrize("notebook_path,notebook_type,engine", NOTEBOOK_LIST)
def test_notebook_executes_without_errors(notebook_path, notebook_type, engine, notebook_runner):
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
    """
    # Log execution start (matches existing test output style)
    log(f"\n{'='*60}")
    log(f"Running: {notebook_path}")
    log(f"{'='*60}")
    
    # Execute notebook using the runner fixture
    result = notebook_runner(notebook_path)
    
    # Check for errors and format output
    if result['errors']:
        error_msg = format_error_output(notebook_path, result['errors'])
        pytest.fail(error_msg, pytrace=False)
    else:
        log(f"✓ Completed successfully ({result['execution_time']:.1f}s)\n")



