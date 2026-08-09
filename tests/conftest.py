"""
Pytest configuration and fixtures for hello-ltr test suite.

This module provides:
- Fixtures for notebook execution
- Container fixtures for search engines
- Utility fixtures (temp_file, temp_dir)
- Error context fixture

All pytest hooks and container management logic have been moved to separate modules
in tests/fixtures/ for better organization and maintainability.
"""

import pytest

# Import pytest hooks from fixtures module
# This ensures hooks are registered with pytest
# Pytest automatically discovers hooks (functions starting with pytest_)
# in imported modules, so we just need to import the module
# The import appears unused but is required for pytest hook discovery
from tests.fixtures import (
    pytest_hooks,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)

# Import container fixture management
from tests.fixtures.container_fixtures import _manage_container_fixture
from tests.port_management import get_engine_port_config


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
    from .notebooks.runner import run_notebook

    def runner(
        notebook_path, timeout=None, save_nb_path="tests/last_run.ipynb", fail_fast=None
    ):
        """
        Run a notebook and return results.

        Args:
            notebook_path: Path to the notebook to execute
            timeout: Optional timeout in seconds (default: 5 minutes from env)
            save_nb_path: Where to save the executed notebook
            fail_fast: If True, stop execution on first error (default: from env or False)

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
            save_nb_path=save_nb_path,
            fail_fast=fail_fast,
        )
        return {
            "notebook": nb,
            "errors": errors,
            "execution_time": exec_time,
            "path": notebook_path,
        }

    return runner


# Per-worker Docker container fixtures
# These fixtures provide isolated containers for each pytest-xdist worker
# when running tests in parallel. When not in parallel mode, they can be
# skipped if containers are already running (via test.sh).


@pytest.fixture(scope="session")
def solr_container(request):
    """
    Start Solr container for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.

    Usage:
        def test_something(solr_container):
            # solr_container is True if container is ready
            # Port is available via SOLR_PORT environment variable
            pass
    """
    from tests.fixtures.container_fixtures import EngineConfig

    port_config = get_engine_port_config("solr")
    engine_config: EngineConfig = {
        "engine": "solr",
        "display_name": "Solr",
        "port_config": port_config["port_config"],
        "health_checks": port_config["health_checks"],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(scope="session")
def elasticsearch_container(request):
    """
    Start Elasticsearch and Kibana containers for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.
    """
    from tests.fixtures.container_fixtures import EngineConfig

    port_config = get_engine_port_config("elasticsearch")
    engine_config: EngineConfig = {
        "engine": "elasticsearch",
        "display_name": "Elasticsearch",
        "port_config": port_config["port_config"],
        "health_checks": port_config["health_checks"],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(scope="session")
def opensearch_container(request):
    """
    Start OpenSearch and OpenSearch Dashboards containers for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.
    """
    from tests.fixtures.container_fixtures import EngineConfig

    port_config = get_engine_port_config("opensearch")
    engine_config: EngineConfig = {
        "engine": "opensearch",
        "display_name": "OpenSearch",
        "port_config": port_config["port_config"],
        "health_checks": port_config["health_checks"],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(autouse=True)
def add_error_context(request):
    """
    Automatically add context to test failures for better debugging.

    This fixture runs for every test and adds context information to failures,
    such as test name, parameters, and local variables.
    """
    # Store test context for use in error reporting
    request.node.user_properties.append(("test_name", request.node.name))
    # callspec is a pytest internal attribute that may not be in type stubs
    callspec = getattr(request.node, "callspec", None)
    if callspec:
        request.node.user_properties.append(("test_params", dict(callspec.params)))

    yield

    # After test, we could add cleanup or logging here if needed


@pytest.fixture
def temp_file(tmp_path):
    """
    Create a temporary file that is automatically cleaned up after the test.

    This fixture provides a temporary file path. Cleanup is handled automatically
    by pytest's tmp_path fixture, which cleans up the entire temporary directory
    after the test completes.

    Usage:
        def test_something(temp_file):
            # temp_file is a Path object pointing to a temporary file
            temp_file.write_text("test content")
            # File is automatically deleted after test (via tmp_path cleanup)

    Returns:
        pathlib.Path: Path to a temporary file
    """
    temp_file_path = tmp_path / "test_file"
    temp_file_path.touch()
    return temp_file_path


@pytest.fixture
def temp_dir(tmp_path):
    """
    Create a temporary directory that is automatically cleaned up after the test.

    This fixture provides a temporary directory path. Cleanup is handled automatically
    by pytest's tmp_path fixture, which cleans up the entire temporary directory
    after the test completes.

    Usage:
        def test_something(temp_dir):
            # temp_dir is a Path object pointing to a temporary directory
            (temp_dir / "subdir").mkdir()
            (temp_dir / "file.txt").write_text("content")
            # Directory and contents are automatically deleted after test (via tmp_path cleanup)

    Returns:
        pathlib.Path: Path to a temporary directory
    """
    temp_dir_path = tmp_path / "test_dir"
    temp_dir_path.mkdir()
    return temp_dir_path
