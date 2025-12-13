"""
Pytest configuration and fixtures for hello-ltr test suite.

This module provides:
- Fixtures for notebook execution
- Custom pytest hooks for test reporting and collection
- Port conflict handling for parallel execution
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest


def get_worker_ports():
    """
    Get worker-specific ports for parallel execution.

    When running with pytest-xdist in parallel, each worker needs unique ports
    to avoid conflicts. This function calculates port offsets based on worker ID.

    Returns:
        dict: Port values for SOLR_PORT, ELASTICSEARCH_PORT, OPENSEARCH_PORT, etc.
              If not running in parallel, returns None (use defaults from test.sh)

    Port allocation strategy:
    - Base ports: Solr=18983, ES=19200, OpenSearch=19201
    - Worker offset: worker_id * 1000 (e.g., gw0=+0, gw1=+1000, gw2=+2000)
    - This gives each worker a range of 1000 ports to avoid conflicts

    Note: This is primarily useful when each worker has its own Docker containers.
    When using test.sh, containers are started once before pytest runs. For best
    results with Docker, use --dist loadgroup to group tests by engine, ensuring
    each worker only needs one engine's containers.
    """
    worker = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker:
        # Not running in parallel, return None to use defaults
        return None

    # Extract worker number from worker ID (e.g., "gw0" -> 0, "gw1" -> 1)
    try:
        worker_num = int(worker.replace('gw', ''))
    except (ValueError, AttributeError):
        # If we can't parse worker ID, default to 0
        worker_num = 0

    # Calculate port offset (1000 ports per worker should be plenty)
    port_offset = worker_num * 1000

    # Base ports from test.sh defaults
    base_ports = {
        'SOLR_PORT': 18983,
        'ELASTICSEARCH_PORT': 19200,
        'OPENSEARCH_PORT': 19201,
        'KIBANA_PORT': 15601,
        'OPENSEARCH_PA_PORT': 19600,
        'OPENSEARCH_DASHBOARDS_PORT': 15602,
    }

    # Apply offset to each port
    worker_ports = {}
    for port_name, base_port in base_ports.items():
        worker_ports[port_name] = base_port + port_offset

    return worker_ports

@pytest.fixture
def notebook_runner():
    """
    Fixture providing the notebook execution function.

    Returns a callable that executes a notebook and returns structured results.

    Usage:
        def test_my_notebook(notebook_runner):
            result = notebook_runner('path/to/notebook.ipynb')
            assert result['errors'] == []
    """
    from runner import run_notebook

    def runner(notebook_path, timeout=None, save_nb_path='tests/last_run.ipynb'):
        """
        Run a notebook and return results.

        Args:
            notebook_path: Path to the notebook to execute
            timeout: Optional timeout in seconds (default: 6 hours from env)
            save_nb_path: Where to save the executed notebook

        Returns:
            dict with keys:
                - 'notebook': The executed notebook object
                - 'errors': List of errors encountered
                - 'execution_time': Time taken in seconds
                - 'path': Path to the notebook
        """
        nb, errors, exec_time = run_notebook(
            notebook_path,
            timeout=timeout,
            save_nb_path=save_nb_path
        )
        return {
            'notebook': nb,
            'errors': errors,
            'execution_time': exec_time,
            'path': notebook_path
        }

    return runner

def pytest_configure(config):
    """
    Pytest hook to configure custom markers and settings.

    This is called once at the start of the test session.
    Also sets up worker-specific ports for parallel execution.
    Validates test environment before running tests.
    """
    # Only run environment validation on the main process (not workers)
    # Workers will inherit the validated environment
    is_worker = os.environ.get('PYTEST_XDIST_WORKER') is not None

    if not is_worker:
        # Validate test environment
        from test_env_validation import check_test_environment

        # Skip port checks if running in parallel (ports will be assigned per worker)
        # Skip Docker check if test.sh is handling it (can be disabled via env var)
        skip_port_check = os.environ.get('SKIP_PORT_CHECK', 'false').lower() == 'true'
        skip_docker_check = os.environ.get('SKIP_DOCKER_CHECK', 'false').lower() == 'true'

        verbose = config.option.verbose > 0
        all_ok, issues = check_test_environment(
            check_docker=not skip_docker_check,
            check_ports=not skip_port_check,
            check_packages=True,
            check_disk=True,
            verbose=verbose
        )

        if not all_ok:
            # Separate errors from warnings
            errors = [issue for issue in issues if not issue.startswith('Port:')]
            warnings = [issue for issue in issues if issue.startswith('Port:')]

            if errors:
                print("\n" + "="*80, file=sys.stderr)
                print("TEST ENVIRONMENT VALIDATION FAILED", file=sys.stderr)
                print("="*80, file=sys.stderr)
                for error in errors:
                    print(f"  ✗ {error}", file=sys.stderr)
                if warnings:
                    print("\nWarnings (non-fatal):", file=sys.stderr)
                    for warning in warnings:
                        print(f"  ⚠ {warning}", file=sys.stderr)
                print("="*80 + "\n", file=sys.stderr)
                # Don't exit - let pytest handle it, but warn the user
                print("WARNING: Some environment checks failed. Tests may not run correctly.", file=sys.stderr)
            elif warnings:
                # Only warnings, not errors
                if verbose:
                    print("\nEnvironment validation warnings:", file=sys.stderr)
                    for warning in warnings:
                        print(f"  ⚠ {warning}", file=sys.stderr)
                    print("(These are non-fatal - test.sh will handle port conflicts)\n", file=sys.stderr)

    # Set up worker-specific ports if running in parallel
    worker_ports = get_worker_ports()
    if worker_ports:
        # Update environment variables for this worker
        for port_name, port_value in worker_ports.items():
            # Only set if not already set (allow manual override)
            if port_name not in os.environ:
                os.environ[port_name] = str(port_value)

        # Log port assignment for debugging
        worker = os.environ.get('PYTEST_XDIST_WORKER', 'unknown')
        print(f"\n[Worker {worker}] Using ports:", file=sys.stderr)
        for port_name, port_value in worker_ports.items():
            print(f"  {port_name}={port_value}", file=sys.stderr)
        print("", file=sys.stderr, flush=True)

    # Register custom markers (also defined in pytest.ini for documentation)
    config.addinivalue_line(
        "markers",
        "solr: Solr-specific tests"
    )
    config.addinivalue_line(
        "markers",
        "elasticsearch: Elasticsearch-specific tests"
    )
    config.addinivalue_line(
        "markers",
        "opensearch: OpenSearch-specific tests"
    )
    config.addinivalue_line(
        "markers",
        "slow: Slow-running tests (> 5 minutes)"
    )
    config.addinivalue_line(
        "markers",
        "setup: Setup notebooks that prepare test environments"
    )
    config.addinivalue_line(
        "markers",
        "fast: Fast-running tests (< 1 minute)"
    )

def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to modify test items after collection.

    Applies markers dynamically based on test parameters.
    """
    for item in items:
        # Only process parametrized tests (from test_notebooks.py)
        if not hasattr(item, 'callspec') or not item.callspec:
            continue

        # Check if this is a parametrized test with our expected parameters
        params = item.callspec.params
        if 'engine' not in params or 'notebook_path' not in params:
            continue

        engine = params.get('engine', 'general')
        notebook_type = params.get('notebook_type', 'test')
        notebook_path = params.get('notebook_path', '')

        # Apply engine markers
        if engine == 'solr':
            item.add_marker(pytest.mark.solr)
        elif engine == 'elasticsearch':
            item.add_marker(pytest.mark.elasticsearch)
        elif engine == 'opensearch':
            item.add_marker(pytest.mark.opensearch)

        # Apply type markers
        if notebook_type == 'setup':
            item.add_marker(pytest.mark.setup)

        # Mark slow tests
        if notebook_path and 'evaluation' in notebook_path.lower():
            item.add_marker(pytest.mark.slow)

def pytest_collection_finish(session):
    """
    Hook called after test collection is complete.

    Prints summary of collected tests.
    """
    if session.config.option.collectonly:
        return

    # Count tests from test_notebooks.py
    num_tests = len([
        item for item in session.items
        if hasattr(item, 'path') and Path(item.path).name == 'test_notebooks.py'
    ])

    if num_tests > 0:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Found {num_tests} notebook(s) to execute", flush=True)
        print(f"[{timestamp}] {'='*60}\n", flush=True)

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Hook called at the end of test session to generate custom summary report.

    Provides detailed summary report with passed/failed/skipped counts.
    """
    # Collect test results
    passed_items = terminalreporter.stats.get('passed', [])
    failed_items = terminalreporter.stats.get('failed', [])
    skipped_items = terminalreporter.stats.get('skipped', [])

    passed = len(passed_items)
    failed = len(failed_items)
    skipped = len(skipped_items)
    total = passed + failed + skipped

    # Get total execution time from session
    session = getattr(terminalreporter, '_session', None)
    total_time = getattr(session, 'duration', 0) if session else 0

    # Print summary report
    print(f"\n{'='*80}", file=sys.stderr)
    print("TEST SUMMARY REPORT", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Total notebooks in test set: {total}", file=sys.stderr)
    print(f"  ✓ Passed: {passed}", file=sys.stderr)
    print(f"  ✗ Failed: {failed}", file=sys.stderr)
    if skipped > 0:
        print(f"  ⊳ Skipped: {skipped}", file=sys.stderr)

    if total_time > 0:
        print(f"\nTotal execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)", file=sys.stderr)

    # Note: For slowest tests, use pytest --durations=10
    # Pytest's built-in duration reporting is more reliable than trying to extract
    # durations from internal structures which vary by pytest version

    # Show failed notebooks
    if failed > 0:
        print("\nFailed notebooks:", file=sys.stderr)
        for item in failed_items:
            name = _extract_notebook_name(item)
            print(f"  ✗ {name}", file=sys.stderr)

    print(f"{'='*80}\n", file=sys.stderr)


def _extract_notebook_name(item):
    """
    Extract notebook path from test item name.

    Handles parametrized test names like:
    test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb-test-solr]
    """
    # Try to get name from item
    name = getattr(item, 'name', None)
    if not name:
        name = str(item)

    # For parametrized tests, extract notebook path from parameter
    if hasattr(item, 'callspec') and item.callspec:
        params = item.callspec.params
        notebook_path = params.get('notebook_path', '')
        if notebook_path:
            return notebook_path

    # Fallback: try to parse from test name
    if '[' in name and ']' in name:
        # Parametrized test name format: test_name[param1-param2-param3]
        # We want the first param (notebook_path)
        notebook_part = name.split('[')[1].split(']')[0]
        # Split by '-' and take first part (notebook path)
        parts = notebook_part.split('-')
        if parts:
            return parts[0]

    return name
