"""
Pytest hooks for hello-ltr test suite.

This module provides:
- pytest_configure: Configuration and environment validation
- pytest_collection_modifyitems: Test marking and ordering
- pytest_collection_finish: Collection summary
- pytest_terminal_summary: Custom summary report
- pytest_sessionfinish: Session cleanup
- pytest_runtest_*: Test execution hooks
"""

from __future__ import annotations

import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import pytest

from ltr.logger import get_logger
from tests.fixtures.container_management import cleanup_all_test_containers
from tests.port_management import get_worker_ports
from tests.test_config import SLOW_PATTERNS

logger = get_logger(__name__)

# Threshold for marking tests as slow based on execution time (seconds)
SLOW_TEST_THRESHOLD = 60.0


def _setup_signal_handlers() -> None:
    """
    Set up signal handlers for SIGINT (Ctrl+C) and SIGTERM to ensure cleanup.

    This ensures containers are cleaned up even if pytest is interrupted.
    """

    def signal_handler(signum, frame):
        """Handle interrupt signals by cleaning up containers."""
        signal_name = signal.Signals(signum).name
        print(
            f"\n\nReceived {signal_name}, cleaning up test containers...",
            file=sys.stderr,
            flush=True,
        )
        cleanup_all_test_containers()
        # Re-raise the signal to allow pytest to handle it normally
        # Use default handler to avoid recursion
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    # Only set up signal handlers on main process (not workers)
    # Workers will be cleaned up by the main process
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None
    if not is_worker:
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError):
            # Signal handling may not be available on all platforms
            # (e.g., Windows has limited signal support)
            pass


def _load_test_execution_times(config: pytest.Config) -> dict[str, float]:
    """
    Load test execution times from pytest cache.

    Returns:
        dict: Mapping of test nodeid to execution time in seconds
    """
    cache = getattr(config, "cache", None)
    if cache is None:
        return {}

    # Get execution times from cache
    execution_times = cache.get("test_execution_times", {})
    return execution_times if isinstance(execution_times, dict) else {}


def _is_slow_test(
    notebook_path: str, execution_times: dict[str, float], nodeid: str
) -> bool:
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


def _extract_notebook_name(item: pytest.Item) -> str:
    """
    Extract notebook path from test item name.

    Handles parametrized test names like:
    test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb-test-solr]
    """
    # Try to get name from item
    name = getattr(item, "name", None)
    if not name:
        name = str(item)

    # For parametrized tests, extract notebook path from parameter
    # callspec is a pytest internal attribute that may not be in type stubs
    callspec = getattr(item, "callspec", None)
    if callspec:
        params = callspec.params
        notebook_path = params.get("notebook_path", "")
        if notebook_path:
            return notebook_path

    # Fallback: try to parse from test name
    if "[" in name and "]" in name:
        # Parametrized test name format: test_name[param1-param2-param3]
        # We want the first param (notebook_path)
        notebook_part = name.split("[")[1].split("]")[0]
        # Split by '-' and take first part (notebook path)
        parts = notebook_part.split("-")
        if parts:
            return parts[0]

    return name


def _extract_notebook_name_from_report(
    report: pytest.TestReport, session: pytest.Session | None
) -> str:
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
    nodeid = getattr(report, "nodeid", "")
    if "[" in nodeid and "]" in nodeid:
        # Parametrized test name format: test_name[param1-param2-param3]
        notebook_part = nodeid.split("[")[1].split("]")[0]
        parts = notebook_part.split("-")
        if parts:
            return parts[0]

    return nodeid


def pytest_configure(config: pytest.Config) -> None:
    """
    Pytest hook to configure custom markers and settings.

    This is called once at the start of the test session.
    Also sets up worker-specific ports for parallel execution.
    Validates test environment before running tests.
    Sets up signal handlers for cleanup on interruption.
    Warns when parallel execution is enabled about Docker tests running sequentially.
    """
    # Set up signal handlers for cleanup on interruption (main process only)
    _setup_signal_handlers()

    # Check if parallel execution is enabled
    # If so, configure Docker tests to run sequentially
    try:
        numprocesses = getattr(config.option, "numprocesses", None)
        if numprocesses and numprocesses != "no":
            # Parallel execution is enabled
            # Check if --dist option is set (for loadgroup)
            dist = getattr(config.option, "dist", None)
            if not dist or dist == "no":
                # No distribution mode set - warn user about Docker tests
                logger.warning(
                    "Parallel execution detected. Docker tests will run sequentially "
                    "to prevent system freezing. To group Docker tests, use: "
                    "--dist loadgroup -m docker"
                )
    except AttributeError:
        # pytest-xdist not available or option not set
        pass

    # Only run environment validation on the main process (not workers)
    # Workers will inherit the validated environment
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None

    if not is_worker:
        # Validate test environment
        try:
            from tests.integration.test_env_validation import check_test_environment
        except ImportError:
            # If check function not available (e.g., when running individual test files),
            # skip environment validation
            logger.warning(
                "Could not import check_test_environment from test_env_validation. "
                "Skipping environment validation. This may occur when running individual test files."
            )
        else:
            # Skip port checks if running in parallel (ports will be assigned per worker)
            # Skip Docker check if test.sh is handling it (can be disabled via env var)
            skip_port_check = (
                os.environ.get("SKIP_PORT_CHECK", "false").lower() == "true"
            )
            skip_docker_check = (
                os.environ.get("SKIP_DOCKER_CHECK", "false").lower() == "true"
            )

            verbose = config.option.verbose > 0
            all_ok, issues = check_test_environment(
                check_docker=not skip_docker_check,
                check_ports=not skip_port_check,
                check_packages=True,
                check_disk=True,
                verbose=verbose,
            )

            if not all_ok:
                # Separate errors from warnings
                errors = [issue for issue in issues if not issue.startswith("Port:")]
                warnings = [issue for issue in issues if issue.startswith("Port:")]

                if errors:
                    print("\n" + "=" * 80, file=sys.stderr)
                    print("TEST ENVIRONMENT VALIDATION FAILED", file=sys.stderr)
                    print("=" * 80, file=sys.stderr)
                    for error in errors:
                        print(f"  ✗ {error}", file=sys.stderr)
                    if warnings:
                        print("\nWarnings (non-fatal):", file=sys.stderr)
                        for warning in warnings:
                            print(f"  ⚠ {warning}", file=sys.stderr)
                    print("=" * 80 + "\n", file=sys.stderr)
                    # Don't exit - let pytest handle it, but warn the user
                    print(
                        "WARNING: Some environment checks failed. Tests may not run correctly.",
                        file=sys.stderr,
                    )
                elif warnings:
                    # Only warnings, not errors
                    if verbose:
                        print("\nEnvironment validation warnings:", file=sys.stderr)
                        for warning in warnings:
                            print(f"  ⚠ {warning}", file=sys.stderr)
                        print(
                            "(These are non-fatal - test.sh will handle port conflicts)\n",
                            file=sys.stderr,
                        )

    # Set up worker-specific ports if running in parallel
    worker_ports = get_worker_ports()
    if worker_ports:
        # Update environment variables for this worker
        for port_name, port_value in worker_ports.items():
            # Only set if not already set (allow manual override)
            if port_name not in os.environ:
                os.environ[port_name] = str(port_value)

        # Log port assignment for debugging
        worker = os.environ.get("PYTEST_XDIST_WORKER", "unknown")
        print(f"\n[Worker {worker}] Using ports:", file=sys.stderr)
        for port_name, port_value in worker_ports.items():
            print(f"  {port_name}={port_value}", file=sys.stderr)
        print("", file=sys.stderr, flush=True)

    # Register custom markers (also defined in pytest.ini for documentation)
    config.addinivalue_line("markers", "solr: Solr-specific tests")
    config.addinivalue_line("markers", "elasticsearch: Elasticsearch-specific tests")
    config.addinivalue_line("markers", "opensearch: OpenSearch-specific tests")
    config.addinivalue_line(
        "markers",
        "docker: Tests that use Docker containers (run sequentially by default)",
    )
    config.addinivalue_line("markers", "slow: Slow-running tests (> 5 minutes)")
    config.addinivalue_line(
        "markers", "setup: Setup notebooks that prepare test environments"
    )
    config.addinivalue_line("markers", "fast: Fast-running tests (< 1 minute)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests (notebook tests)")

    # Output capturing for integration and e2e tests is configured in
    # pytest_collection_modifyitems to use tee-sys mode for real-time streaming


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Pytest hook to modify test items after collection.

    Applies markers dynamically based on test parameters, enables tee-sys capture
    mode for e2e/integration tests to show real-time output, and reorders tests
    so slow tests run last. Also marks Docker tests and groups them together
    for sequential execution when parallel mode is enabled.
    """
    # Load execution times from cache
    execution_times = _load_test_execution_times(config)

    # First pass: apply markers
    for item in items:
        # Mark integration tests (tests in tests/integration/)
        test_path = None
        if hasattr(item, "fspath"):
            test_path = str(item.fspath)
        elif hasattr(item, "path"):
            test_path = str(item.path)

        if test_path and "/tests/integration/" in test_path.replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
            # Integration tests typically use Docker containers
            item.add_marker(pytest.mark.docker)

        # Mark E2E tests (notebook tests) - check path first
        is_notebook_test = test_path and "/tests/notebooks/" in test_path.replace(
            "\\", "/"
        )

        # Only process parametrized tests (from notebooks/test_notebooks.py)
        # callspec is a pytest internal attribute that may not be in type stubs
        callspec = getattr(item, "callspec", None)
        if not callspec:
            # If it's a notebook test file but not parametrized, mark as e2e
            if is_notebook_test:
                item.add_marker(pytest.mark.e2e)
            continue

        # Check if this is a parametrized test with our expected parameters
        params = callspec.params
        if "engine" not in params or "notebook_path" not in params:
            # If it's a notebook test file but doesn't match expected params, mark as e2e
            if is_notebook_test:
                item.add_marker(pytest.mark.e2e)
            continue

        engine = params.get("engine", "general")
        notebook_type = params.get("notebook_type", "test")
        notebook_path = params.get("notebook_path", "")

        # Apply engine markers
        if engine == "solr":
            item.add_marker(pytest.mark.solr)
            item.add_marker(pytest.mark.docker)  # Solr tests use Docker
        elif engine == "elasticsearch":
            item.add_marker(pytest.mark.elasticsearch)
            item.add_marker(pytest.mark.docker)  # Elasticsearch tests use Docker
        elif engine == "opensearch":
            item.add_marker(pytest.mark.opensearch)
            item.add_marker(pytest.mark.docker)  # OpenSearch tests use Docker

        # Apply type markers
        if notebook_type == "setup":
            item.add_marker(pytest.mark.setup)

        # Mark notebook tests as e2e (parametrized notebook tests)
        item.add_marker(pytest.mark.e2e)

        # Mark slow tests based on patterns and execution history
        if _is_slow_test(notebook_path, execution_times, item.nodeid):
            item.add_marker(pytest.mark.slow)

    # Check if we have any e2e or integration tests and enable tee-sys capture mode
    # This shows output in real-time while still capturing it for pytest reports
    has_e2e_or_integration = any(
        any(marker.name in ("e2e", "integration") for marker in item.iter_markers())
        for item in items
    )
    if has_e2e_or_integration:
        config.option.capture = "tee-sys"

    # Second pass: reorder tests - separate Docker tests for sequential execution
    # When parallel execution is enabled, Docker tests should run sequentially
    # to prevent system freezing. Group them together so they can be run sequentially.
    docker_tests = []
    fast_tests = []
    slow_tests = []

    # Check if parallel execution is enabled
    try:
        numprocesses = getattr(config.option, "numprocesses", None)
        parallel_enabled = numprocesses and numprocesses != "no"
    except AttributeError:
        parallel_enabled = False

    for item in items:
        # Check if test uses Docker (has docker marker)
        has_docker_marker = any(
            marker.name == "docker" for marker in item.iter_markers()
        )
        # Check if test has slow marker
        has_slow_marker = any(marker.name == "slow" for marker in item.iter_markers())

        if has_docker_marker:
            # Docker tests - group together for sequential execution
            docker_tests.append(item)
        else:
            # Non-Docker tests - can run in parallel
            if has_slow_marker:
                slow_tests.append(item)
            else:
                fast_tests.append(item)

    # Reorder: non-Docker tests first (can run in parallel), Docker tests last (sequential)
    # Within non-Docker tests: fast first, slow last
    # Docker tests are grouped together to enable sequential execution
    if parallel_enabled and docker_tests:
        # When parallel is enabled, put Docker tests at the end so they can be run sequentially
        # Non-Docker tests can run in parallel, Docker tests will be grouped together
        items[:] = fast_tests + slow_tests + docker_tests
    else:
        # Sequential mode: maintain original ordering (fast first, slow last)
        # Docker tests are mixed in with others
        items[:] = fast_tests + slow_tests + docker_tests


def pytest_collection_finish(session: pytest.Session) -> None:
    """
    Hook called after test collection is complete.

    Prints summary of collected tests.
    """
    if session.config.option.collectonly:
        return

    # Count tests from notebooks/test_notebooks.py
    num_tests = len(
        [
            item
            for item in session.items
            if hasattr(item, "path") and Path(item.path).name == "test_notebooks.py"
        ]
    )

    if num_tests > 0:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Found {num_tests} notebook(s) to execute", flush=True)
        print(f"[{timestamp}] {'=' * 60}\n", flush=True)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """
    Hook called at the end of test session to generate custom summary report.

    Provides detailed summary report with passed/failed/skipped counts and
    slow test statistics.
    """
    # Collect test results (these are TestReport objects, not test items)
    passed_reports = terminalreporter.stats.get("passed", [])
    failed_reports = terminalreporter.stats.get("failed", [])
    skipped_reports = terminalreporter.stats.get("skipped", [])

    # Get session to access actual test items
    session = getattr(terminalreporter, "_session", None)
    if session:
        # Build a mapping of nodeid to test item for marker checking
        nodeid_to_item = {item.nodeid: item for item in session.items}

        # Separate slow tests from fast tests by checking markers on actual items
        slow_passed = [
            report
            for report in passed_reports
            if report.nodeid in nodeid_to_item
            and any(
                m.name == "slow" for m in nodeid_to_item[report.nodeid].iter_markers()
            )
        ]
        slow_failed = [
            report
            for report in failed_reports
            if report.nodeid in nodeid_to_item
            and any(
                m.name == "slow" for m in nodeid_to_item[report.nodeid].iter_markers()
            )
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
    session = getattr(terminalreporter, "_session", None)
    total_time = getattr(session, "duration", 0) if session else 0

    # Print summary report
    print(f"\n{'=' * 80}", file=sys.stderr)
    print("TEST SUMMARY REPORT", file=sys.stderr)
    print(f"{'=' * 80}", file=sys.stderr)
    print(f"Total notebooks in test set: {total}", file=sys.stderr)
    print(f"  ✓ Passed: {passed}", file=sys.stderr)
    print(f"  ✗ Failed: {failed}", file=sys.stderr)
    if skipped > 0:
        print(f"  ⊳ Skipped: {skipped}", file=sys.stderr)

    if total_time > 0:
        print(
            f"\nTotal execution time: {total_time:.1f}s ({total_time / 60:.1f} minutes)",
            file=sys.stderr,
        )

    # Show slow test statistics
    if slow_total > 0:
        print(
            f"\nSlow tests: {slow_total} ({len(slow_passed)} passed, {len(slow_failed)} failed)",
            file=sys.stderr,
        )
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

    print(f"{'=' * 80}\n", file=sys.stderr)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """
    Pytest hook called when the test session is finishing.

    This hook is called even if tests are interrupted (Ctrl+C) or pytest is killed.
    It ensures all test containers are cleaned up regardless of how the session ends.

    Args:
        session: The pytest session object
        exitstatus: The exit status code (0=passed, 1=failed, 2=interrupted, etc.)
    """
    # Only run cleanup on main process (not workers)
    # Workers' containers will be cleaned up by their own fixtures or by the main process
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None
    if not is_worker:
        cleanup_all_test_containers()


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
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


def pytest_runtest_logfinish(
    nodeid: str, location: tuple[str, int | None, str]
) -> None:
    """
    Hook called when a test finishes execution.

    Records test execution time in pytest cache for future slow test detection.
    """
    # This hook is called after test execution, but we need the actual duration
    # We'll record it in pytest_runtest_logreport instead
    pass


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """
    Hook called for each test reporting event.

    Records execution time when test completes successfully.
    """
    if report.when == "call" and report.outcome == "passed":
        # Record execution time for successful tests
        duration = getattr(report, "duration", None)
        if duration is not None and duration > 0:
            # Store in cache for future runs
            config = getattr(report, "config", None)
            if config is not None:
                cache = getattr(config, "cache", None)
                if cache is not None:
                    execution_times = cache.get("test_execution_times", {})
                    if not isinstance(execution_times, dict):
                        execution_times = {}
                    execution_times[report.nodeid] = duration
                    cache.set("test_execution_times", execution_times)
