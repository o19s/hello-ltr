"""
Pytest configuration and fixtures for hello-ltr test suite.

This module provides:
- Fixtures for notebook execution
- Custom pytest hooks for test reporting and collection
- Port conflict handling for parallel execution
- Slow test detection and ordering
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Known slow notebook patterns (notebooks that typically take > 60 seconds)
SLOW_PATTERNS = [
    'netfix',
    'bayesian-optimization',
    'bigger bot',
    'lambda-mart',
    'feature_search',
    'evaluation'
]

# Threshold for marking tests as slow based on execution time (seconds)
SLOW_TEST_THRESHOLD = 60.0


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


@pytest.fixture(autouse=True)
def add_error_context(request):
    """
    Automatically add context to test failures for better debugging.

    This fixture runs for every test and adds context information to failures,
    such as test name, parameters, and local variables.
    """
    # Store test context for use in error reporting
    request.node.user_properties.append(('test_name', request.node.name))
    if hasattr(request.node, 'callspec') and request.node.callspec:
        request.node.user_properties.append(('test_params', dict(request.node.callspec.params)))

    yield

    # After test, we could add cleanup or logging here if needed


def pytest_runtest_makereport(item, call):
    """
    Hook to enhance test reports with additional context.

    This adds debugging information to test failure reports.
    """
    if call.when == "call" and call.excinfo is not None:
        # Add context to failure reports
        excinfo = call.excinfo
        if excinfo.typename == "AssertionError":
            # For assertion errors, try to add more context
            # The actual error message enhancement is done in the assertion itself
            pass


def pytest_runtest_logfinish(nodeid, location):
    """
    Hook called when a test finishes execution.

    Records test execution time in pytest cache for future slow test detection.
    """
    # This hook is called after test execution, but we need the actual duration
    # We'll record it in pytest_runtest_logreport instead
    pass


def pytest_runtest_logreport(report):
    """
    Hook called for each test reporting event.

    Records execution time when test completes successfully.
    """
    if report.when == "call" and report.outcome == "passed":
        # Record execution time for successful tests
        duration = getattr(report, 'duration', None)
        if duration is not None and duration > 0:
            # Store in cache for future runs
            config = getattr(report, 'config', None)
            if config is not None:
                cache = getattr(config, 'cache', None)
                if cache is not None:
                    execution_times = cache.get('test_execution_times', {})
                    if not isinstance(execution_times, dict):
                        execution_times = {}
                    execution_times[report.nodeid] = duration
                    cache.set('test_execution_times', execution_times)
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

def _load_test_execution_times(config):
    """
    Load test execution times from pytest cache.

    Returns:
        dict: Mapping of test nodeid to execution time in seconds
    """
    cache = getattr(config, 'cache', None)
    if cache is None:
        return {}

    # Get execution times from cache
    execution_times = cache.get('test_execution_times', {})
    return execution_times if isinstance(execution_times, dict) else {}


def _is_slow_test(notebook_path, execution_times, nodeid):
    """
    Determine if a test should be marked as slow.

    Checks both pattern-based detection and execution time from previous runs.

    Args:
        notebook_path: Path to the notebook file
        execution_times: Dict mapping nodeid to execution time
        nodeid: Test nodeid for looking up execution time

    Returns:
        bool: True if test should be marked as slow
    """
    if not notebook_path:
        return False

    notebook_path_lower = notebook_path.lower()

    # Check against known slow patterns
    for pattern in SLOW_PATTERNS:
        if pattern.lower() in notebook_path_lower:
            return True

    # Check execution time from previous runs
    if nodeid in execution_times:
        exec_time = execution_times[nodeid]
        if isinstance(exec_time, (int, float)) and exec_time >= SLOW_TEST_THRESHOLD:
            return True

    return False


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to modify test items after collection.

    Applies markers dynamically based on test parameters and reorders tests
    so slow tests run last.
    """
    # Load execution times from cache
    execution_times = _load_test_execution_times(config)

    # First pass: apply markers
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

        # Mark slow tests based on patterns and execution history
        if _is_slow_test(notebook_path, execution_times, item.nodeid):
            item.add_marker(pytest.mark.slow)

    # Second pass: reorder tests - fast tests first, slow tests last
    # Maintain relative order within each group
    fast_tests = []
    slow_tests = []

    for item in items:
        # Check if test has slow marker
        has_slow_marker = any(marker.name == 'slow' for marker in item.iter_markers())

        if has_slow_marker:
            slow_tests.append(item)
        else:
            fast_tests.append(item)

    # Reorder: fast tests first, slow tests last
    items[:] = fast_tests + slow_tests

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

    Provides detailed summary report with passed/failed/skipped counts and
    slow test statistics.
    """
    # Collect test results (these are TestReport objects, not test items)
    passed_reports = terminalreporter.stats.get('passed', [])
    failed_reports = terminalreporter.stats.get('failed', [])
    skipped_reports = terminalreporter.stats.get('skipped', [])

    # Get session to access actual test items
    session = getattr(terminalreporter, '_session', None)
    if session:
        # Build a mapping of nodeid to test item for marker checking
        nodeid_to_item = {item.nodeid: item for item in session.items}

        # Separate slow tests from fast tests by checking markers on actual items
        slow_passed = [
            report for report in passed_reports
            if report.nodeid in nodeid_to_item and
            any(m.name == 'slow' for m in nodeid_to_item[report.nodeid].iter_markers())
        ]
        slow_failed = [
            report for report in failed_reports
            if report.nodeid in nodeid_to_item and
            any(m.name == 'slow' for m in nodeid_to_item[report.nodeid].iter_markers())
        ]
    else:
        # Fallback: can't check markers without session
        slow_passed = []
        slow_failed = []

    slow_total = len(slow_passed) + len(slow_failed)

    passed = len(passed_reports)
    failed = len(failed_reports)
    skipped = len(skipped_reports)
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

    # Show slow test statistics
    if slow_total > 0:
        print(f"\nSlow tests: {slow_total} ({len(slow_passed)} passed, {len(slow_failed)} failed)", file=sys.stderr)
        print("  Tip: Skip slow tests with: pytest -m 'not slow'", file=sys.stderr)
        print("  Tip: Run only slow tests with: pytest -m slow", file=sys.stderr)
        print("  Tip: See slowest tests with: pytest --durations=10", file=sys.stderr)

    # Note: For slowest tests, use pytest --durations=10
    # Pytest's built-in duration reporting is more reliable than trying to extract
    # durations from internal structures which vary by pytest version

    # Show failed notebooks
    if failed > 0:
        print("\nFailed notebooks:", file=sys.stderr)
        for report in failed_reports:
            name = _extract_notebook_name_from_report(report, session)
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


def _extract_notebook_name_from_report(report, session):
    """
    Extract notebook path from test report.

    First tries to get the actual test item from session, then falls back
    to parsing the nodeid.
    """
    # Try to get the actual test item from session
    if session:
        for item in session.items:
            if item.nodeid == report.nodeid:
                return _extract_notebook_name(item)

    # Fallback: parse from nodeid
    nodeid = getattr(report, 'nodeid', '')
    if '[' in nodeid and ']' in nodeid:
        # Parametrized test name format: test_name[param1-param2-param3]
        notebook_part = nodeid.split('[')[1].split(']')[0]
        parts = notebook_part.split('-')
        if parts:
            return parts[0]

    return nodeid
