# Hello-LTR Test Suite

This directory contains the test infrastructure for the hello-ltr project, focusing on automated notebook testing using pytest.

## Overview

The test suite validates that all Jupyter notebooks execute successfully without errors. It covers:
- 36+ notebooks across Solr, Elasticsearch, and OpenSearch
- Per-worker Docker container isolation (default)
- Automated setup and teardown
- Parallel execution support with isolated containers

## Quick Start

The test suite can be run in several ways depending on your needs. For a full test run that automatically handles dependencies and containers, use the test wrapper script. For more control, use pytest directly.

### Run All Tests
```bash
# Recommended: Use test.sh wrapper (handles environment setup)
./tests/test.sh

# Direct pytest (per-worker containers enabled by default)
pytest tests/notebooks/test_notebooks.py

# Parallel execution with isolated containers per worker
pytest -n auto tests/notebooks/test_notebooks.py
# or
PYTEST_ARGS="-n auto" ./tests/test.sh
```

### Run Specific Tests
```bash
# Re-run only failed tests from last run
pytest --lf tests/notebooks/test_notebooks.py

# Run only Solr notebooks
pytest -k solr tests/notebooks/test_notebooks.py

# Run in parallel (4x faster)
pytest -n auto tests/notebooks/test_notebooks.py

# Retry flaky tests (retry failed tests 3 times with 2 second delay)
pytest --reruns 3 --reruns-delay 2 tests/notebooks/test_notebooks.py
```

### Code Quality Checks
```bash
# Run all quality checks (linting, formatting, notebook outputs)
./tests/check_quality.sh

# Auto-fix issues where possible
./tests/check_quality.sh --fix

# Check only notebooks
./tests/check_quality.sh --notebooks-only

# Check only Python code
./tests/check_quality.sh --code-only
```

The quality check script uses `ruff` for linting and formatting (supports both Python code and Jupyter notebooks) and `nbstripout` to verify notebook outputs are stripped.

## Test Environment Setup

This section covers how to set up your environment to run the test suite.

### Prerequisites

**Required Software:**
- **Python 3.9+** - Check with `python3 --version`
- **Docker & Docker Compose** - Required for running search engine containers
  - Check Docker: `docker --version`
  - Check Docker Compose: `docker compose version`
- **Git** - For cloning the repository

**System Requirements:**
- **Disk Space**: At least 5GB free (for Docker images and test data)
- **Memory**: 8GB+ RAM recommended (4GB minimum)
- **Network**: Internet connection for downloading Docker images and test data

**macOS Specific:**
- Increase file descriptor limit (required for parallel execution):
  ```bash
  ulimit -n 4096
  ```
- Add to `~/.zshrc` or `~/.bash_profile` to make permanent:
  ```bash
  ulimit -n 4096
  ```

### Installation Steps

**1. Clone the Repository**
```bash
git clone <repository-url>
cd hello-ltr
```

**2. Set Up Python Virtual Environment**

Using `uv` (recommended, as per project standards):
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**3. Install Dependencies**

Using `uv sync` (recommended):
```bash
uv sync
```

This will automatically:
- Create a virtual environment (`.venv`) if it doesn't exist
- Install Python if needed
- Install all dependencies from `pyproject.toml`

After running `uv sync`, activate the virtual environment:
```bash
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows
```

**Note:** `uv sync` handles virtual environment creation automatically, so you don't need to run `uv venv` separately.

**4. Verify Installation**

Check that pytest and dependencies are installed:
```bash
pytest --version
python -c "import pytest, pytest_xdist, pytest_timeout; print('All test dependencies installed')"
```

**5. Verify Docker**

Ensure Docker is running and accessible:
```bash
docker ps
docker compose version
```

### Test Environment Validation

Before running tests, validate your environment:

**Check Python Environment:**
```bash
python --version  # Should be 3.9+
which python       # Should point to venv Python
```

**Check Docker Services:**
```bash
docker ps          # Should show running containers (if any)
docker info        # Should show Docker system information
```

**Check Port Availability:**
```bash
# Check if test ports are available (should show "not listening")
netstat -an | grep 18983  # Solr test port
netstat -an | grep 19200  # Elasticsearch test port
netstat -an | grep 19201  # OpenSearch test port
```

**Run Quick Validation Test:**
```bash
# Run a single fast test to verify setup
pytest -k "sandbox" tests/notebooks/test_notebooks.py -v
```

### Common Setup Issues

**Issue: Python version too old**
```bash
# Error: "requires-python = '>=3.9'"
# Solution: Install Python 3.9+ and recreate venv
python3.9 -m venv venv
```

**Issue: Docker not running**
```bash
# Error: "Cannot connect to Docker daemon"
# Solution: Start Docker Desktop or Docker service
sudo systemctl start docker  # Linux
# Or start Docker Desktop application (Mac/Windows)
```

**Issue: Port conflicts**

With per-worker containers (default), port conflicts are automatically handled:
- Each worker gets unique ports (base_port + worker_id * 1000)
- Containers are isolated per worker
- No manual port management needed

If you see port conflicts:
```bash
# Error: "Port already in use" or "Ports not available"
# Solution 1: Clean up leftover containers
docker ps -a | grep hello-ltr
docker stop <container-id>
docker rm <container-id>

# Solution 2: Use legacy mode with custom ports
USE_WORKER_CONTAINERS=false \
SOLR_PORT=28983 \
ELASTICSEARCH_PORT=29200 \
OPENSEARCH_PORT=29201 \
./tests/test.sh
```

**Issue: Permission denied (Docker)**
```bash
# Error: "permission denied while trying to connect to Docker"
# Solution: Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

**Issue: Virtual environment not activated**
```bash
# Error: "ModuleNotFoundError" or wrong Python path
# Solution: Ensure venv is activated
source venv/bin/activate  # Check prompt shows (venv)
which python              # Should show venv path
```

### CI/CD Environment Setup

For CI/CD environments (GitHub Actions, Jenkins, etc.):

**Required Environment Variables:**
```bash
AUTO_CLEANUP_CONFLICTS=true      # Auto-cleanup without prompts
SERVICE_WAIT_TIMEOUT=600         # Longer timeout for CI
NOTEBOOK_TIMEOUT_MINUTES=10      # Extended timeout for CI (default: 5 minutes)
```

**CI Setup Script:**
```bash
#!/bin/bash
set -e

# Install dependencies
uv sync

# Verify Docker
docker compose version

# Run tests (containers are managed automatically by fixtures)
./tests/test.sh
```

## Pytest Command Reference

### Re-run Failed Tests
```bash
# Run only tests that failed in the last run
pytest --lf tests/notebooks/test_notebooks.py

# Run failed tests first, then continue with the rest
pytest --ff tests/notebooks/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="--lf" ./tests/test.sh
```

### Resume After Failure
```bash
# Stepwise: stop at first failure, resume from there on next run
pytest --sw tests/notebooks/test_notebooks.py

# Stop at first failure (useful for debugging)
pytest -x tests/notebooks/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="--sw" ./tests/test.sh
```

### Filter Tests by Pattern
```bash
# Run tests matching a pattern (by path, engine, etc.)
pytest -k "opensearch" tests/notebooks/test_notebooks.py
pytest -k "solr or elasticsearch" tests/notebooks/test_notebooks.py
pytest -k "not evaluation" tests/notebooks/test_notebooks.py

# Run only Solr notebooks
pytest -k "solr" tests/notebooks/test_notebooks.py

# Run only notebooks with "lambda-mart" in the name
pytest -k "lambda-mart" tests/notebooks/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="-k opensearch" ./tests/test.sh
```

### Run Specific Notebook
```bash
# Run a specific notebook test
pytest "tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb-test-solr]"

# Easier: use -k with a unique part of the path
pytest -k "sandbox" tests/notebooks/test_notebooks.py
```

### Run by Test Markers
```bash
# Run only Solr tests (using markers)
pytest -m solr tests/notebooks/test_notebooks.py

# Run only setup notebooks
pytest -m setup tests/notebooks/test_notebooks.py

# Skip slow tests (recommended for development)
pytest -m "not slow" tests/notebooks/test_notebooks.py

# Run only slow tests (for validation)
pytest -m slow tests/notebooks/test_notebooks.py

# Combine markers
pytest -m "opensearch and not slow" tests/notebooks/test_notebooks.py
```

### Parallel Execution (Faster Tests)
```bash
# Run on all available CPU cores
pytest -n auto tests/notebooks/test_notebooks.py

# Run on specific number of workers
pytest -n 4 tests/notebooks/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="-n auto" ./tests/test.sh

# Group tests by engine (recommended for Docker)
# Each engine gets its own worker, avoiding port conflicts
pytest -n auto --dist loadgroup tests/notebooks/test_notebooks.py
```

**Port Conflict Handling:**
- When running in parallel, each worker automatically gets unique ports
- Port offset: base_port + (worker_id * 1000)
- Example: Worker 0 uses ports 18983, 19200, 19201; Worker 1 uses 19983, 20200, 20201
- Ports are logged at worker startup for debugging
- Each worker gets its own isolated containers (per-worker containers are default)

**Per-Worker Containers (Default):**
- Containers are automatically started per worker
- No port conflicts between workers
- Automatic cleanup after tests complete
- Use `--dist loadgroup` to group by engine for better resource usage

### Verbose Output
```bash
# Verbose output (show test names)
pytest -v tests/notebooks/test_notebooks.py

# Very verbose (show more details)
pytest -vv tests/notebooks/test_notebooks.py

# Show print statements (useful for debugging)
pytest -s tests/notebooks/test_notebooks.py

# Show local variables on failure
pytest -l tests/notebooks/test_notebooks.py
```

### Generate Reports
```bash
# Generate HTML report
pytest --html=report.html --self-contained-html tests/notebooks/test_notebooks.py

# Generate JUnit XML (for CI/CD)
pytest --junitxml=results.xml tests/notebooks/test_notebooks.py

# Show slowest 10 tests
pytest --durations=10 tests/notebooks/test_notebooks.py
```

### Tips & Tricks
```bash
# List all tests without running
pytest --collect-only tests/notebooks/test_notebooks.py

# Count tests matching a pattern
pytest --collect-only -q -k "opensearch" tests/notebooks/test_notebooks.py

# Clear pytest cache (including last-failed data)
pytest --cache-clear

# Show cache contents
pytest --cache-show

# Combining options: Run failed tests first, then only opensearch tests, in parallel
pytest --ff -k opensearch -n 4 tests/notebooks/test_notebooks.py

# Verbose, show prints, stop at first failure
pytest -vv -s -x tests/notebooks/test_notebooks.py
```

## Test Infrastructure

### Architecture

```
tests/
├── conftest.py              # Pytest fixtures and configuration
│                            # - Per-worker container fixtures (default)
│                            # - Port management and isolation
│                            # - Health checks and timing
├── test_notebooks.py        # Main test suite (parametrized)
├── runner.py                # Notebook execution engine
├── nb_test_config.py        # NotebookTestConfig class for discovering notebooks
├── test_config.py           # Test configuration (paths and ignored notebooks)
├── patch_clients_for_tests.py  # Port patching for isolation
├── test.sh                  # Test runner wrapper (simplified)
└── README.md               # This file
```

### Container Management

**Per-Worker Containers (Default):**
- Each pytest worker gets its own isolated containers
- Containers automatically start before tests and clean up after
- Unique ports per worker prevent conflicts
- Enabled by default (`USE_WORKER_CONTAINERS=true`)

**Legacy Mode (Externally Managed):**
- Set `USE_WORKER_CONTAINERS=false` to use externally managed containers
- Useful if you want to manage containers manually or reuse existing ones

### Key Components

**1. Test Parametrization ([test_notebooks.py](test_notebooks.py))**
- Each notebook is a separate pytest test
- Enables individual test results, timing, and filtering
- Automatic marking by engine (solr, elasticsearch, opensearch)

**2. Notebook Runner ([runner.py](runner.py))**
- Executes notebooks with 6-hour timeout
- Cell-by-cell progress logging
- Captures errors with context (cell index, source)
- Automatic port patching injection

**3. Port Patching ([patch_clients_for_tests.py](patch_clients_for_tests.py))**
- Redirects client connections to test ports
- Prevents conflicts with production services
- Patches: Solr (8983→18983), ES (9200→19200), OpenSearch (9201→19201)

**4. Container Fixtures ([conftest.py](conftest.py))**
- Per-worker container isolation (default)
- Automatic container startup and cleanup
- Health checks with timing logs
- Port management and conflict prevention
- File locking for parallel execution safety

**5. Test Runner ([test.sh](test.sh))**
- Simplified wrapper for pytest
- Environment setup and dependency management
- Per-worker containers enabled by default
- Legacy mode support for externally managed containers

## Test Documentation

This section provides comprehensive documentation of the test suite, including test organization, fixtures, and examples.

### Test Organization

The test suite is organized into three main categories:

#### 1. Notebook Tests (`tests/notebooks/`)

**Purpose:** End-to-end validation of Jupyter notebooks executing successfully.

**Test Files:**
- `test_notebooks.py` - Parametrized test suite that executes all notebooks
- `runner.py` - Notebook execution engine with error capture and port patching
- `nb_test_config.py` - NotebookTestConfig class for discovering notebooks in directories
- `test_config.py` - Configuration constants (TEST_PATHS and IGNORED_NOTEBOOKS)

**Coverage:**
- 36+ notebooks across Solr, Elasticsearch, and OpenSearch
- Setup notebooks (index creation, data preparation)
- Training notebooks (feature engineering, model training)
- Evaluation notebooks (performance metrics, analysis)

**Example:**
```python
# Each notebook becomes a parametrized test
@pytest.mark.parametrize("notebook_path,notebook_type,engine", NOTEBOOK_LIST)
def test_notebook_executes_without_errors(notebook_path, notebook_type, engine, notebook_runner, request):
    """Test that a notebook executes without errors."""
    # Request container fixtures based on engine
    if engine == 'solr':
        request.getfixturevalue('solr_container')
    # ... execute notebook and check for errors
```

#### 2. Unit Tests (`tests/unit/`)

**Purpose:** Test individual functions and classes in isolation.

**Test Files and Coverage:**

| Test File                       | What It Tests                     | Key Test Cases                                                              |
|---------------------------------|-----------------------------------|-----------------------------------------------------------------------------|
| `test_client_solr.py`           | SolrClient class                  | Initialization, index operations, LTR features, queries, document retrieval |
| `test_client_elastic.py`        | ElasticClient class               | Initialization, index operations, LTR features, queries, model submission   |
| `client_test_helpers.py`        | All client classes (parametrized) | Shared tests for Solr, OpenSearch, and Elastic clients                      |
| `test_search.py`                | Search query generation           | esLtrQuery, solrLtrQuery, search function with all engines                  |
| `test_index.py`                 | Index rebuild functionality       | Force rebuild, create new index, method ordering                            |
| `test_evaluate.py`              | Evaluation functions              | evaluate() with all engines, rre_table() data loading                       |
| `test_ranklib.py`               | RankLib integration               | Training, feature search, model saving, KCV support                         |
| `test_clickmodels.py`           | Click model algorithms            | Cascade model, User Browse Model, session building                          |
| `test_judg_list.py`             | Judgment list parsing             | StringIO reading, file I/O, unsorted detection                              |
| `test_utils.py`                 | Utility functions                 | Helper functions used across the codebase                                   |
| `test_notebook_patterns.py`     | Notebook code patterns            | Common patterns and anti-patterns in notebooks                              |
| `test_package_compatibility.py` | Package compatibility             | NumPy, SciPy, scikit-learn, pandas, matplotlib operations                   |

**Total:** 13 test files, 200+ individual test cases

**Example:**
```python
def test_solr_client_initializes_with_localhost():
    """Test client initializes with localhost when not in Docker."""
    client = SolrClient()
    assert client.get_host() == 'localhost'
    assert client.port == 8983
```

#### 3. Integration Tests (`tests/integration/`)

**Purpose:** Test interactions between components and external services.

**Test Files:**
- `test_container_fixtures.py` - Verifies container fixtures work correctly
- `test_env_validation.py` - Validates test environment setup

**Coverage:**
- Container fixture initialization and cleanup
- Port management and conflict resolution
- Environment validation (Docker, ports, packages, disk space)
- Health check functionality

### Test Fixtures

Fixtures are defined in `tests/conftest.py` and provide reusable test setup and teardown.

#### Container Fixtures (Session Scope)

**Purpose:** Start and manage Docker containers for search engines.

**Available Fixtures:**

1. **`solr_container`** - Solr container
   - **Scope:** Session (shared across all tests in a worker)
   - **Port:** `SOLR_PORT` environment variable (default: 18983)
   - **Health Check:** `/solr/admin/info/system`
   - **Usage:**
     ```python
     def test_something(solr_container):
         # Container is ready, SOLR_PORT is set
         client = SolrClient()
         # Use client...
     ```

2. **`elasticsearch_container`** - Elasticsearch + Kibana containers
   - **Scope:** Session
   - **Ports:** `ELASTICSEARCH_PORT` (default: 19200), `KIBANA_PORT` (default: 15601)
   - **Health Checks:** `/_cluster/health`, `/api/status`
   - **Usage:**
     ```python
     def test_something(elasticsearch_container):
         # Containers are ready
         client = ElasticClient()
         # Use client...
     ```

3. **`opensearch_container`** - OpenSearch + OpenSearch Dashboards containers
   - **Scope:** Session
   - **Ports:** `OPENSEARCH_PORT` (default: 19201), `OPENSEARCH_DASHBOARDS_PORT` (default: 15602)
   - **Health Checks:** `/_cluster/health`, `/api/status`
   - **Usage:**
     ```python
     def test_something(opensearch_container):
         # Containers are ready
         client = OpenSearchClient()
         # Use client...
     ```

**Features:**
- Per-worker isolation (each pytest-xdist worker gets its own containers)
- Automatic cleanup after session ends
- Port conflict prevention via file locking
- Health checks with exponential backoff retry logic
- Startup timing logs for performance debugging

**Configuration:**
- Set `USE_WORKER_CONTAINERS=false` to disable per-worker containers (legacy mode)
- Containers are skipped if already running externally

#### Notebook Runner Fixture

**`notebook_runner`** - Function fixture for executing notebooks

**Purpose:** Execute notebooks and return structured results.

**Usage:**
```python
def test_my_notebook(notebook_runner):
    """Test a specific notebook."""
    result = notebook_runner('path/to/notebook.ipynb')
    
    # Check results
    assert result['errors'] == []
    assert result['execution_time'] < 3600  # Less than 1 hour
    assert result['notebook'] is not None
```

**Returns:**
```python
{
    'notebook': nbformat.NotebookNode,  # Executed notebook object
    'errors': List[Dict],                # List of errors encountered
    'execution_time': float,            # Time taken in seconds
    'path': str                         # Path to the notebook
}
```

**Features:**
- Automatic port patching injection
- Cell-by-cell progress logging
- Error capture with context (cell index, source code)
- Configurable timeout (default: 5 minutes from `NOTEBOOK_TIMEOUT_MINUTES`)

### Running Specific Test Scenarios

#### Run Tests by Category

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only notebook tests
pytest tests/notebooks/test_notebooks.py

# Run tests for a specific engine
pytest -k solr tests/
pytest -k elasticsearch tests/
pytest -k opensearch tests/
```

#### Run Tests by Module

```bash
# Test Solr client functionality
pytest tests/unit/test_client_solr.py

# Test search query generation
pytest tests/unit/test_search.py

# Test click models
pytest tests/unit/test_clickmodels.py

# Test RankLib integration
pytest tests/unit/test_ranklib.py
```

#### Run Specific Test Cases

```bash
# Run a specific test function
pytest tests/unit/test_client_solr.py::test_solr_client_initializes_with_localhost

# Run tests matching a pattern
pytest -k "initialization" tests/unit/

# Run tests in a specific class
pytest tests/unit/test_clickmodels.py::TestCascadeModel
```

#### Run with Different Options

```bash
# Verbose output with print statements
pytest -vv -s tests/unit/test_client_solr.py

# Stop at first failure
pytest -x tests/

# Show slowest tests
pytest --durations=10 tests/

# Run in parallel (4 workers)
pytest -n 4 tests/unit/

# Retry flaky tests
pytest --reruns 3 --reruns-delay 2 tests/
```

### Test Data Sources

#### Notebook Test Data

**Source:** External URLs and local files
- TMDB dataset: `http://es-learn-to-rank.labs.o19s.com/tmdb.json`
- Local copies: `data/tmdb.json` (when available)

**Setup Requirements:**
- Internet connection for downloading test data (first run)
- Docker containers running for search engines
- Sufficient disk space for indices (~2GB per engine)

#### Unit Test Data

**Source:** Inline test data and mocks
- Test data created inline in test functions
- Mock objects for external dependencies
- Temporary files for file I/O tests

**Example:**
```python
def test_judgment_parsing():
    """Test parsing judgment lists."""
    # Inline test data
    judgment_list = """
    4	qid:1	 # 1234	rambo
    3	qid:1	 # 5670	rambo
    """
    # Test parsing...
```

### Test Docstring Standards

All tests should have descriptive docstrings explaining their purpose.

**Format:**
```python
def test_feature_name():
    """Test description of what is being tested.
    
    Optionally include:
    - What the test verifies
    - Expected behavior
    - Edge cases covered
    """
    # Test implementation...
```

**Good Examples:**
```python
def test_solr_client_initializes_with_localhost():
    """Test client initializes with localhost when not in Docker."""
    # Clear, concise, explains the scenario

def test_cascade_model_stops_counting_at_first_click():
    """Test cascade_model stops counting attractiveness at first click.
    
    Verifies that the cascade model correctly implements the assumption
    that users stop examining results after the first click.
    """
    # More detailed explanation for complex tests
```

**Bad Examples:**
```python
def test_client():
    """Test client."""  # Too vague

def test_1():
    """Test."""  # No information
```

### Test Execution Examples

#### Example 1: Run All Unit Tests for a Specific Module

```bash
# Test all Solr client functionality
pytest tests/unit/test_client_solr.py -v

# Expected output:
# test_client_solr.py::test_solr_client_initializes_with_localhost PASSED
# test_client_solr.py::test_solr_client_initializes_with_docker_host PASSED
# ... (25 tests total)
```

#### Example 2: Run Notebook Tests for One Engine

```bash
# Test only Solr notebooks
pytest -k solr tests/notebooks/test_notebooks.py -v

# Expected: All Solr notebook tests run with solr_container fixture
```

#### Example 3: Debug a Failing Test

```bash
# Run with verbose output and stop at first failure
pytest -vv -s -x tests/unit/test_client_solr.py::test_solr_client_query

# Shows:
# - Detailed test output
# - Print statements
# - Stops immediately on failure
```

#### Example 4: Run Tests in Parallel

```bash
# Run unit tests with 4 parallel workers
pytest -n 4 tests/unit/

# Each worker gets isolated containers (if needed)
# Ports automatically assigned: worker 0 (18983), worker 1 (19983), etc.
```

## Test Configuration

### Pytest Settings ([pytest.ini](../pytest.ini))

```ini
[pytest]
# Timeout: 5 minutes per test (fail fast if notebooks hang)
timeout = 300

# Markers for test categorization
markers =
    solr: Solr-specific tests
    elasticsearch: Elasticsearch tests
    opensearch: OpenSearch tests
    slow: Slow-running tests (detected by patterns or execution time > 60s)
    setup: Setup notebooks
    fast: Fast-running tests (< 1 minute)
```

### Test Paths ([conftest.py](conftest.py))

Tests are collected from these directories:
- `./notebooks/` (general notebooks)
- `./notebooks/solr/tmdb`
- `./notebooks/elasticsearch/tmdb`
- `./notebooks/elasticsearch/osc-blog`
- `./notebooks/opensearch/tmdb`
- `./notebooks/opensearch/osc-blog`

### Ignored Notebooks

These notebooks are excluded from automated testing:
- **Evaluation notebooks**: Slow and resource-intensive (30+ minutes each)
- **XGBoost notebooks**: Complex dependencies and platform-specific requirements

For detailed explanations of why each notebook is ignored, when to un-ignore them, and what needs to be fixed, see the comments in [test_config.py](test_config.py).

**Current ignored notebooks:**
- `./notebooks/solr/tmdb/evaluation (Solr).ipynb`
- `./notebooks/elasticsearch/tmdb/evaluation.ipynb`
- `./notebooks/opensearch/tmdb/evaluation.ipynb`
- `./notebooks/elasticsearch/tmdb/XGBoost.ipynb`
- `./notebooks/opensearch/tmdb/XGBoost.ipynb`

See `IGNORED_NOTEBOOKS` in [test_config.py](test_config.py) for the full list with detailed documentation.

## Environment Variables

### Test Execution
- `NOTEBOOK_TIMEOUT_MINUTES`: Timeout per notebook in minutes (default: 5)
- `PYTEST_ARGS`: Additional pytest arguments for test.sh

### Service Ports
- `SOLR_PORT`: Test port for Solr (default: 18983)
- `ELASTICSEARCH_PORT`: Test port for Elasticsearch (default: 19200)
- `OPENSEARCH_PORT`: Test port for OpenSearch (default: 19201)
- `KIBANA_PORT`: Test port for Kibana (default: 15601)
- `OPENSEARCH_DASHBOARDS_PORT`: Test port for OpenSearch Dashboards (default: 15602)

### Docker Settings
- `AUTO_CLEANUP_CONFLICTS`: Auto-cleanup conflicting containers (default: false)
- `SERVICE_WAIT_TIMEOUT`: Service startup timeout in seconds (default: 300)

### Test Environment Validation
- `SKIP_DOCKER_CHECK`: Skip Docker validation (default: false)
- `SKIP_PORT_CHECK`: Skip port availability checks (default: false)

**Note:** Test environment validation runs automatically before tests. It checks:
- Docker installation and daemon status
- Docker Compose availability
- Test port availability
- Required Python packages
- Disk space availability

See [test_env_validation.py](test_env_validation.py) for details.

## Writing New Tests

### Adding a New Notebook Test

Notebooks are automatically discovered if they're in a configured test path. Just add your notebook to one of these directories:
- `notebooks/solr/tmdb/`
- `notebooks/elasticsearch/tmdb/`
- `notebooks/opensearch/tmdb/`

The test suite will automatically pick it up.

### Excluding a Notebook

Add it to `IGNORED_NOTEBOOKS` in [test_config.py](test_config.py):

```python
IGNORED_NOTEBOOKS = [
    './notebooks/solr/tmdb/my-slow-notebook.ipynb',
]
```

### Adding Test Markers

Markers are automatically applied based on the notebook path, but you can add custom logic in [test_notebooks.py](test_notebooks.py):

```python
# Mark evaluation notebooks as slow
if 'evaluation' in notebook_path.lower():
    request.node.add_marker(pytest.mark.slow)
```

### Writing Unit Tests

Unit tests for core modules should go in:
```
tests/unit/
├── test_judgments.py
├── test_clients.py
├── test_clickmodels.py
└── test_helpers.py
```

Use standard pytest conventions:
```python
def test_my_feature():
    result = my_function()
    assert result == expected_value
```

## Troubleshooting

This section covers common issues and their solutions.

### Tests Fail Immediately

**Problem**: Tests fail with connection errors or "service not available"

**Symptoms:**
- `ConnectionRefusedError` or `ConnectionError`
- "Service not ready" errors
- Tests fail within seconds of starting

**Solutions:**
1. **Use Docker orchestration script** (recommended):
   ```bash
   ./tests/test.sh
   ```
   This automatically starts required Docker containers.

2. **Check Docker is running**:
   ```bash
   docker ps
   # If empty, start Docker Desktop or Docker service
   ```

3. **Verify services are accessible**:
   ```bash
   curl http://localhost:18983/solr/admin/info/system  # Solr
   curl http://localhost:19200/_cluster/health         # Elasticsearch
   curl http://localhost:19201/_cluster/health         # OpenSearch
   ```

4. **Check service logs**:
   ```bash
   cd notebooks/solr && docker compose logs
   cd notebooks/elasticsearch && docker compose logs
   cd notebooks/opensearch && docker compose logs
   ```

### Port Conflicts

**Problem**: Ports already in use

**Symptoms:**
- `Address already in use` errors
- `Port conflict detected` messages
- Services fail to start

**Solutions:**

1. **Automatic cleanup** (test.sh handles this):
   ```bash
   AUTO_CLEANUP_CONFLICTS=true ./tests/test.sh
   ```

2. **Use different ports**:
   ```bash
   SOLR_PORT=28983 ELASTICSEARCH_PORT=29200 OPENSEARCH_PORT=29201 ./tests/test.sh
   ```

3. **Manually stop conflicting containers**:
   ```bash
   docker ps | grep solr
   docker stop <container-id>
   docker rm <container-id>
   ```

4. **Find and stop processes using ports**:
   ```bash
   # Linux/Mac
   lsof -i :18983
   kill -9 <PID>
   
   # Or use netstat
   netstat -tulpn | grep 18983
   ```

### Timeout Errors

**Problem**: Notebook execution times out

**Symptoms:**
- `TimeoutError` after 6 hours (default)
- Tests hang indefinitely
- "Test execution exceeded timeout" messages

**Solutions:**

1. **Increase timeout**:
   ```bash
   NOTEBOOK_TIMEOUT_MINUTES=10 ./tests/test.sh
   ```

2. **Check for infinite loops** in notebook:
   - Review `tests/last_run.ipynb` to see where it stopped
   - Look for cells that might be hanging

3. **Run specific slow notebook with extended timeout**:
   ```bash
   NOTEBOOK_TIMEOUT_MINUTES=15 pytest -k "specific-notebook" tests/notebooks/test_notebooks.py
   ```

4. **Check system resources**:
   ```bash
   # Monitor CPU/memory usage
   top
   # Or
   htop
   ```

### Memory Issues

**Problem**: Out of memory errors

**Symptoms:**
- `MemoryError` exceptions
- `Killed` processes (OOM killer)
- System becomes unresponsive
- Docker containers crash

**Solutions:**

1. **Reduce parallel workers**:
   ```bash
   pytest -n 2 tests/notebooks/test_notebooks.py  # Limit to 2 workers
   pytest -n 1 tests/notebooks/test_notebooks.py  # Single worker
   ```

2. **Run sequentially** (no parallel execution):
   ```bash
   pytest tests/notebooks/test_notebooks.py  # No -n flag
   ```

3. **Increase Docker memory limits**:
   - Docker Desktop: Settings → Resources → Memory (increase to 8GB+)
   - Docker daemon: Edit `/etc/docker/daemon.json`:
     ```json
     {
       "default-ulimits": {
         "memlock": {
           "Hard": -1,
           "Name": "memlock",
           "Soft": -1
         }
       }
     }
     ```

4. **Run tests by engine** (reduces memory usage):
   ```bash
   pytest -k solr tests/notebooks/test_notebooks.py
   pytest -k elasticsearch tests/notebooks/test_notebooks.py
   pytest -k opensearch tests/notebooks/test_notebooks.py
   ```

### Parallel Execution Port Conflicts

**Problem**: Port conflicts when running tests in parallel

**Symptoms:**
- Multiple workers try to use same ports
- Connection errors in parallel execution
- Tests pass sequentially but fail in parallel

**Solutions:**

1. **Automatic port handling** (already implemented):
   - Each worker gets unique ports (base_port + worker_id * 1000)
   - Ports are automatically assigned in `conftest.py`
   - Workers log their assigned ports at startup

2. **Use loadgroup distribution** (recommended for Docker):
   ```bash
   pytest -n auto --dist loadgroup tests/notebooks/test_notebooks.py
   ```
   This groups tests by engine, reducing port conflicts.

3. **Run sequential tests** (if parallel causes issues):
   ```bash
   pytest tests/notebooks/test_notebooks.py  # No -n flag
   ```

4. **Check worker port assignments**:
   - Look for `[Worker gw0] Using ports:` messages in test output
   - Verify each worker has unique ports

**Note**: Containers are automatically managed by pytest fixtures (per-worker isolation is the default). Each worker gets its own isolated containers with unique ports. For optimal parallel execution:
- Use `--dist loadgroup` to group tests by engine (reduces resource usage)
- Containers are automatically cleaned up after tests complete
- Cleanup also runs on interruption (Ctrl+C) via signal handlers and `pytest_sessionfinish` hook
- If containers are left running after interruption, use `python tests/cleanup_test_containers.py` to clean them up
- To disable per-worker containers, set `USE_WORKER_CONTAINERS=false` (legacy mode)

### Test Cache Issues

**Problem**: `--lf` re-runs wrong tests or cache is stale

**Symptoms:**
- `--lf` doesn't re-run expected tests
- Tests marked as "failed" but actually pass
- Cache shows incorrect test states

**Solutions:**

1. **Clear pytest cache**:
   ```bash
   pytest --cache-clear
   ```

2. **View cache contents**:
   ```bash
   pytest --cache-show
   ```

3. **Force re-run all tests**:
   ```bash
   pytest --cache-clear tests/notebooks/test_notebooks.py
   ```

4. **Check cache location**:
   ```bash
   # Cache is in .pytest_cache/ directory
   rm -rf .pytest_cache/
   ```

### Docker Container Issues

**Problem**: Containers fail to start or crash

**Symptoms:**
- `docker compose up` fails
- Containers exit immediately
- "Health check failed" errors

**Solutions:**

1. **Check Docker logs**:
   ```bash
   cd notebooks/solr
   docker compose logs --tail=100
   ```

2. **Rebuild containers** (containers are managed per-worker by fixtures):
   ```bash
   # Containers are automatically rebuilt when started by fixtures
   # To force rebuild, stop containers manually first:
   docker ps -a | grep hello-ltr
   docker stop <container-id>
   docker rm <container-id>
   # Then run tests - fixtures will rebuild containers
   ./tests/test.sh
   ```

3. **Check disk space**:
   ```bash
   df -h
   docker system df  # Check Docker disk usage
   ```

4. **Clean up Docker resources**:
   ```bash
   docker system prune -a  # Remove unused images/containers
   docker volume prune     # Remove unused volumes
   ```

5. **Verify Docker Compose files**:
   ```bash
   cd notebooks/solr
   docker compose config  # Validate configuration
   ```

### Leftover Test Containers

**Problem**: Test containers remain running after tests are interrupted or canceled

**Symptoms:**
- Containers with names like `test-unit-solr-gw0-*`, `test-integration-opensearch-gw0-*`, or `test-notebooks-elasticsearch-gw0-*` still running after tests
- Port conflicts when running tests again
- `docker ps` shows test containers from previous runs

**Solutions:**

1. **Automatic cleanup** (already implemented):
   - Containers are automatically cleaned up when tests complete normally
   - Cleanup also runs on interruption (Ctrl+C) via signal handlers
   - `pytest_sessionfinish` hook ensures cleanup even if pytest is killed

2. **Manual cleanup with utility script**:
   ```bash
   # Clean up all leftover test containers
   python tests/cleanup_test_containers.py
   
   # Dry run to see what would be cleaned up
   python tests/cleanup_test_containers.py --dry-run
   
   # Verbose output
   python tests/cleanup_test_containers.py --verbose
   ```

3. **Manual cleanup with Docker commands**:
   ```bash
   # List test containers
   docker ps -a --filter "name=test-"
   
   # Stop and remove specific containers
   docker stop <container-name>
   docker rm <container-name>
   
   # Or clean up by project name (for a specific worker)
   cd notebooks/solr
   docker compose -p test-unit-solr-gw0 down -v
   ```

4. **Clean up all test containers**:
   ```bash
   # Stop all test containers
   docker ps -a --filter "name=test-" --format "{{.Names}}" | \
     grep -E "test-(unit|integration|notebooks)-(solr|elasticsearch|opensearch)-gw" | \
     xargs -r docker stop
   
   # Remove all test containers
   docker ps -a --filter "name=test-" --format "{{.Names}}" | \
     grep -E "test-(unit|integration|notebooks)-(solr|elasticsearch|opensearch)-gw" | \
     xargs -r docker rm
   ```

**Note**: The cleanup script and automatic cleanup only affect containers with test project names (starting with `test-{test_type}-{engine}-gw`, e.g., `test-unit-solr-gw0`, `test-integration-opensearch-gw0`, `test-notebooks-elasticsearch-gw0`). Manually started containers (like `hello-ltr-notebook` or containers from root `docker-compose.yml`) are never touched by automatic cleanup.

### Notebook Execution Errors

**Problem**: Notebooks fail with Python errors

**Symptoms:**
- `NameError`, `ImportError`, `AttributeError` in notebooks
- Cell execution fails
- Error messages in test output

**Solutions:**

1. **Check last executed notebook**:
   ```bash
   # Review the failing notebook
   cat tests/last_run.ipynb
   # Or open in Jupyter
   jupyter notebook tests/last_run.ipynb
   ```

2. **Run notebook manually**:
   ```bash
   # Execute notebook directly to see full error
   jupyter nbconvert --to notebook --execute notebooks/solr/tmdb/sandbox.ipynb
   ```

3. **Check for missing dependencies**:
   ```bash
   # Verify all packages are installed
   uv pip list | grep -E "(elasticsearch|opensearch|pysolr)"
   ```

4. **Verify port patching**:
   - Check that `patch_clients_for_tests.py` is being injected
   - Verify test ports match environment variables

### Import Errors

**Problem**: Module import failures

**Symptoms:**
- `ModuleNotFoundError: No module named 'ltr'`
- `ImportError: cannot import name 'X'`
- Package not found errors

**Solutions:**

1. **Install package in development mode**:
   ```bash
   uv sync
   ```

2. **Verify virtual environment is activated**:
   ```bash
   which python  # Should show venv path
   echo $VIRTUAL_ENV  # Should show venv directory
   ```

3. **Check PYTHONPATH**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

4. **Reinstall dependencies**:
   ```bash
   uv sync --reinstall
   ```

### Environment Validation Errors

**Problem**: Test environment validation fails

**Symptoms:**
- "TEST ENVIRONMENT VALIDATION FAILED" message
- Missing Docker or Python packages
- Port conflicts detected

**Solutions:**

1. **Check validation output**:
   ```bash
   # Run with verbose output to see details
   pytest tests/notebooks/test_notebooks.py -v
   ```

2. **Manual validation**:
   ```bash
   python -c "from tests.test_env_validation import check_test_environment; check_test_environment(verbose=True)"
   ```

3. **Fix missing dependencies**:
   ```bash
   # Install all dependencies (recommended)
   uv sync
   # Or install specific packages if needed
   uv pip install pytest pytest-xdist pytest-timeout pytest-html pytest-cov
   ```

4. **Skip specific checks** (if handled elsewhere):
   ```bash
   # Skip Docker check (if test.sh handles it)
   SKIP_DOCKER_CHECK=true pytest tests/notebooks/test_notebooks.py
   
   # Skip port check (if test.sh handles conflicts)
   SKIP_PORT_CHECK=true pytest tests/notebooks/test_notebooks.py
   ```

5. **Fix Docker issues**:
   ```bash
   # Check Docker is running
   docker ps
   
   # Start Docker service (Linux)
   sudo systemctl start docker
   
   # Or start Docker Desktop (Mac/Windows)
   ```

**Note**: Environment validation runs automatically before tests. Warnings about port conflicts are non-fatal (test.sh handles them automatically).

### Fast-Failing Tests (0.001s)

**Problem**: Tests complete in ~0.001 seconds and fail immediately

**Symptoms:**
- Tests show 0.001s execution time
- Tests fail before actually executing
- Docker Compose errors in test output

**Common Causes:**

1. **Docker Compose Configuration Conflict** (Most Common):
   - Old-style resource limits (`mem_limit`, `mem_reservation`) conflict with new-style `deploy.resources`
   - **Error**: `can't set distinct values on 'mem_reservation' and 'deploy.resources.reservations.memory'`
   - **Fix**: Remove old-style limits from base `docker-compose.yml` files
   - Resource limits should be managed only through `docker-compose.test.yml` override files

2. **Import/Module Errors**:
   - Tests fail immediately due to import failures
   - **Investigation**: Use `tests/investigate_fast_failures.py` to identify
   - **Fix**: Ensure all dependencies installed (`uv sync`)

3. **Legitimately Fast Tests**:
   - Most unit tests complete in <0.01 seconds (this is normal!)
   - These are **not failures** - they're working as designed
   - Use investigation tool to verify: `python tests/investigate_fast_failures.py --unit`

**Solutions:**

1. **Investigate fast-failing tests**:
   ```bash
   # Identify which tests are failing quickly
   python tests/investigate_fast_failures.py --unit
   
   # Check for import errors specifically
   python tests/investigate_fast_failures.py --unit --threshold 0.01
   ```

2. **Fix Docker Compose conflicts**:
   ```bash
   # Verify Docker Compose config is valid
   docker compose -f notebooks/solr/docker-compose.yml -f notebooks/solr/docker-compose.test.yml config --services
   
   # If errors, check for old-style resource limits in base docker-compose.yml files
   # Remove mem_limit and mem_reservation from base files
   ```

3. **Clear pytest cache** (if cached failures):
   ```bash
   rm -rf .pytest_cache
   ```

**Note**: Most 0.001s tests are **legitimately fast** unit tests. Only investigate if they're actually failing.

### Slow Test Execution

**Problem**: Tests run very slowly

**Symptoms:**
- Tests take hours to complete
- Individual notebooks take 30+ minutes
- System is unresponsive during tests

**Solutions:**

1. **Use parallel execution**:
   ```bash
   pytest -n auto tests/notebooks/test_notebooks.py  # 4x faster
   ```

2. **Run only fast tests**:
   ```bash
   pytest -m "not slow" tests/notebooks/test_notebooks.py
   ```

3. **Run specific engines**:
   ```bash
   pytest -k solr tests/notebooks/test_notebooks.py  # Test only Solr
   pytest -k elasticsearch tests/notebooks/test_notebooks.py  # Test only Elasticsearch
   pytest -k opensearch tests/notebooks/test_notebooks.py  # Test only OpenSearch
   ```

4. **Check system resources**:
   - Ensure adequate CPU/RAM
   - Close other resource-intensive applications
   - Check for background processes consuming resources

5. **Optimize Docker resources**:
   - Increase Docker CPU/memory limits
   - Use SSD storage for Docker volumes
   - Enable Docker BuildKit for faster builds

## Common Workflows

### Development: Quick Iteration
```bash
# Run tests, stop at first failure, easily re-run failed tests
pytest --sw tests/notebooks/test_notebooks.py

# After fixing, re-run only the failed test
pytest --lf tests/notebooks/test_notebooks.py
```

### Development Cycle
```bash
# 1. Make changes to a notebook
# 2. Run just that notebook
pytest -k "my-notebook" tests/notebooks/test_notebooks.py

# 3. If it fails, fix and re-run
pytest --lf tests/notebooks/test_notebooks.py
```

### Pre-Commit Testing
```bash
# Run fast tests only (skip slow evaluation notebooks)
pytest -m "not slow" tests/notebooks/test_notebooks.py
```

### CI/CD: Full Test Suite
```bash
# Run all tests in parallel with JUnit report
pytest -n auto --junitxml=results.xml tests/notebooks/test_notebooks.py

# Or with HTML report
pytest -n auto --html=report.html --self-contained-html tests/notebooks/test_notebooks.py
```

### Debugging: Single Notebook
```bash
# Run one notebook with full output
pytest -s -vv -k "sandbox" tests/notebooks/test_notebooks.py

# Run with full output and stop at first failure
pytest -s -vv -x -k "failing-notebook" tests/notebooks/test_notebooks.py

# Check the last executed notebook
cat tests/last_run.ipynb
```

### Performance: Find Slow Tests
```bash
# Show 10 slowest tests
pytest --durations=10 tests/notebooks/test_notebooks.py
```

### Managing Slow Tests

Slow tests are automatically identified and marked based on:
- **Pattern matching**: Notebooks matching known slow patterns (netfix, bayesian-optimization, bigger bot, lambda-mart, feature_search, evaluation)
- **Execution history**: Tests that took > 60 seconds in previous runs (tracked in pytest cache)

Slow tests are automatically reordered to run **after** fast tests, providing quicker feedback during development.

**Skip slow tests during development:**
```bash
# Run only fast tests (skip slow ones)
pytest -m "not slow" tests/notebooks/test_notebooks.py
```

**Run only slow tests:**
```bash
# Run only slow tests (for validation)
pytest -m slow tests/notebooks/test_notebooks.py
```

**Identify slow tests:**
```bash
# See which tests are marked as slow
pytest --collect-only -m slow tests/notebooks/test_notebooks.py

# See slowest tests by execution time
pytest --durations=10 tests/notebooks/test_notebooks.py
```

**Note**: After running tests, execution times are cached. Tests that exceed 60 seconds will be automatically marked as slow in future runs.

## Test Results

### Understanding Output

**Successful test:**
```
tests/notebooks/test_notebooks.py::test_notebook[./notebooks/solr/tmdb/sandbox.ipynb] PASSED [10%]
```

**Failed test:**
```
tests/notebooks/test_notebooks.py::test_notebook[./notebooks/solr/tmdb/sandbox.ipynb] FAILED [10%]
...
============================== ERRORS ==============================
Errors in ./notebooks/solr/tmdb/sandbox.ipynb: 1 error(s)

Error 1:
  Cell 5:
  Cell source:
    result = client.query("test")
    ... (2 more lines)
  NameError: name 'client' is not defined
================================================================
```

### Last Executed Notebook

The last executed notebook is saved to `tests/last_run.ipynb` for debugging.

### Test Reports

Generate HTML report for easier viewing:
```bash
pytest --html=report.html --self-contained-html tests/notebooks/test_notebooks.py
```

## Performance

### Test Execution Time

**Notebook Tests:**
- **Sequential**: ~20 minutes for all 36 notebooks
- **Parallel (-n auto)**: ~5-7 minutes (4x faster)

**Unit Tests:**
- **Sequential**: ~1-2 minutes (13 test files, 200+ tests)
- **Parallel**: ~30 seconds (minimal benefit due to low overhead)

**Integration Tests:**
- **Sequential**: ~1-2 minutes (container-dependent)

### Investigating Fast-Failing Tests

If tests complete very quickly (<0.01s) and you suspect they're failing:

```bash
# Investigate all fast tests
python tests/investigate_fast_failures.py

# Investigate unit tests only
python tests/investigate_fast_failures.py --unit

# Custom threshold (default 0.005s)
python tests/investigate_fast_failures.py --threshold 0.01
```

The investigation tool categorizes tests into:
- ✅ Legitimately fast tests (passing, just very fast)
- ⚠️ Import/module errors (failing due to import issues)
- ❌ Other failures (failing for other reasons)
- ⏭️ Skipped tests (intentionally skipped)

**Note**: Most unit tests legitimately complete in <0.01 seconds. Only investigate if tests are actually failing.

### Measuring Test Performance

Use the performance measurement script to get detailed timing information:

```bash
# Measure all tests (unit + integration)
python tests/measure_performance.py

# Measure unit tests only
python tests/measure_performance.py --unit

# Measure integration tests only
python tests/measure_performance.py --integration

# Measure with parallel execution for comparison
python tests/measure_performance.py --parallel

# Generate JSON report for CI/CD
python tests/measure_performance.py --output performance.json
```

The script generates a detailed report including:
- Total execution time per test category
- Average, fastest, and slowest test times
- List of slow tests (configurable thresholds)
- JSON output for programmatic analysis

### Per-Notebook Timing

See slowest notebook tests:
```bash
pytest --durations=10 tests/notebooks/test_notebooks.py
```

See slowest unit/integration tests:
```bash
pytest --durations=10 tests/unit tests/integration
```

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    ./tests/test.sh
  env:
    NOTEBOOK_TIMEOUT_MINUTES: 10
```

### Jenkins Example
```groovy
stage('Test') {
    steps {
        sh '''
            ./tests/test.sh
        '''
    }
}
```

## Additional Test Scripts

### Package Compatibility Tests
```bash
# Test that all packages work with current Python version
python tests/test_package_compatibility.py
```

### Notebook Pattern Tests
```bash
# Test specific code patterns from notebooks
python tests/test_notebook_patterns.py
```

### Unit Tests
```bash
# Run unit tests for core modules
pytest tests/test_judg_list.py
```

## Contributing

This section provides guidelines for contributing to the test suite.

### Adding New Notebook Tests

**Process:**
1. **Add notebook to appropriate directory**:
   - Solr notebooks: `notebooks/solr/tmdb/`
   - Elasticsearch notebooks: `notebooks/elasticsearch/tmdb/` or `notebooks/elasticsearch/osc-blog/`
   - OpenSearch notebooks: `notebooks/opensearch/tmdb/` or `notebooks/opensearch/osc-blog/`

2. **Ensure notebook runs without errors**:
   - Test manually in Jupyter first
   - Verify all cells execute successfully
   - Check for hardcoded ports (should use environment variables or patching)

3. **Consider test execution time**:
   - Fast tests (< 1 minute): No special handling needed
   - Medium tests (1-5 minutes): Consider adding to slow marker if needed
   - Slow tests (> 5 minutes): Add `slow` marker or consider if it should be ignored

4. **Test your notebook**:
   ```bash
   # Run just your new notebook
   pytest -k "your-notebook-name" tests/notebooks/test_notebooks.py -v
   ```

5. **Verify it's discovered**:
   ```bash
   # List all collected tests
   pytest --collect-only tests/notebooks/test_notebooks.py | grep your-notebook
   ```

### Excluding Notebooks from Testing

If a notebook should not be tested automatically:

1. **Add to `IGNORED_NOTEBOOKS`** in [test_config.py](test_config.py):
   ```python
   IGNORED_NOTEBOOKS = [
       # Your reason here (be specific!)
       # - Why is it ignored? (e.g., "slow", "requires manual setup", "flaky")
       # - When should it be un-ignored? (e.g., "when dependencies are fixed")
       # - What needs to be fixed? (e.g., "needs dependency validation")
       './notebooks/solr/tmdb/my-notebook.ipynb',
   ]
   ```

2. **Document the reason** (required):
   - Add detailed comments explaining why it's ignored
   - Document when it should be un-ignored
   - List what needs to be fixed to enable testing
   - See existing entries in `test_config.py` for examples

3. **Consider alternatives**:
   - Can it be made faster? (reduce dataset size, add checkpoints)
   - Can dependencies be fixed? (add validation, improve error handling)
   - Can it be split? (separate setup from execution)

### Writing Unit Tests

**Location:**
- Unit tests should go in `tests/unit/` directory (when created)
- Currently, unit tests are in `tests/` root (e.g., `test_judg_list.py`)

**Guidelines:**
1. **Follow pytest conventions**:
   ```python
   def test_feature_name():
       """Test description."""
       # Arrange
       input_data = prepare_test_data()
       
       # Act
       result = function_under_test(input_data)
       
       # Assert
       assert result == expected_value
   ```

2. **Use descriptive test names**:
   - Good: `test_judgment_list_parses_valid_format()`
   - Bad: `test_judg()`

3. **Keep tests isolated**:
   - Each test should be independent
   - Don't rely on test execution order
   - Clean up after tests (use fixtures)

4. **Use fixtures for common setup**:
   ```python
   @pytest.fixture
   def sample_judgments():
       return ["1 qid:1 1:0.5 2:0.3", "0 qid:1 1:0.2 2:0.8"]
   
   def test_parse_judgments(sample_judgments):
       result = parse_judgments(sample_judgments)
       assert len(result) == 2
   ```

5. **Test edge cases**:
   - Empty inputs
   - Invalid inputs
   - Boundary conditions
   - Error handling

### Improving Test Infrastructure

**Guidelines:**

1. **Keep components focused**:
   - `runner.py`: Notebook execution only
   - `conftest.py`: Pytest fixtures and configuration
   - `test_notebooks.py`: Test parametrization and collection
   - `patch_clients_for_tests.py`: Port patching logic

2. **Add fixtures to `conftest.py`**:
   ```python
   @pytest.fixture
   def reusable_test_data():
       """Fixture description."""
       # Setup
       data = create_test_data()
       yield data
       # Teardown (if needed)
       cleanup(data)
   ```

3. **Use pytest markers** for test categorization:
   - Existing markers: `solr`, `elasticsearch`, `opensearch`, `slow`, `setup`, `fast`
   - Add new markers in `pytest.ini` and `conftest.py`

4. **Document new features**:
   - Update this README with new functionality
   - Add examples of how to use new features
   - Document any breaking changes

5. **Follow code style**:
   - Use type hints where appropriate
   - Add docstrings to functions/classes
   - Follow PEP 8 style guide

### Test Code Review Checklist

When reviewing test contributions, check:

- [ ] Tests are properly isolated (no shared state)
- [ ] Test names are descriptive
- [ ] Tests cover happy path and error cases
- [ ] No hardcoded values (use fixtures/constants)
- [ ] Proper cleanup (fixtures handle teardown)
- [ ] Documentation updated (README, docstrings)
- [ ] Ignored notebooks have detailed comments
- [ ] New markers documented in `pytest.ini`
- [ ] No test-specific code in production modules

### Reporting Test Issues

When reporting test failures or issues:

1. **Include test output**:
   ```bash
   pytest tests/notebooks/test_notebooks.py -vv > test_output.txt
   ```

2. **Include environment info**:
   ```bash
   python --version
   pytest --version
   docker --version
   docker compose version
   ```

3. **Include relevant logs**:
   - Docker container logs
   - Last executed notebook (`tests/last_run.ipynb`)
   - Pytest cache (if relevant): `pytest --cache-show`

4. **Describe reproduction steps**:
   - Exact command run
   - Environment variables set
   - Previous successful runs (if any)

5. **Check for known issues**:
   - Review this troubleshooting section
   - Check GitHub issues
   - Review `TEST_INFRASTRUCTURE_REVIEW.md`

### Best Practices

**Do:**
- ✅ Write tests before fixing bugs (TDD when possible)
- ✅ Keep tests fast and focused
- ✅ Use meaningful assertions with clear error messages
- ✅ Document why tests are skipped/ignored
- ✅ Clean up test data and resources
- ✅ Test error conditions, not just happy paths

**Don't:**
- ❌ Write tests that depend on external services (use Docker)
- ❌ Write tests that depend on execution order
- ❌ Ignore notebooks without documenting why
- ❌ Commit test code with `print()` statements (use logging)
- ❌ Write tests that modify production data
- ❌ Skip cleanup in fixtures (use `yield` or `finally`)

### Getting Help

If you need help with tests:

1. **Check documentation**:
   - This README
   - `TEST_INFRASTRUCTURE_REVIEW.md`
   - Pytest documentation: https://docs.pytest.org/

2. **Review existing tests**:
   - `tests/test_judg_list.py` - Example unit test
   - `tests/notebooks/test_notebooks.py` - Example integration test
   - `tests/conftest.py` - Example fixtures

3. **Ask questions**:
   - Open a GitHub issue with `[tests]` tag
   - Check existing issues for similar problems
   - Review test infrastructure review document

## Migration Notes

This test suite was migrated from unittest to pytest in December 2025.

### What Changed
- Replaced `run_most_nbs.py` with `test_notebooks.py`
- Removed ~150 lines of custom skip logic
- Each notebook is now a separate test
- Added pytest fixtures and configuration

### What Stayed the Same
- `runner.py`: Notebook execution engine (unchanged)
- `patch_clients_for_tests.py`: Port patching (unchanged)
- `test.sh`: Docker orchestration (updated to call pytest)
- Error formatting and logging style

### Old Commands → New Commands

If you're used to the old `run_most_nbs.py` commands, here are the pytest equivalents:

| Old Command                                              | New Pytest Command                                              |
|----------------------------------------------------------|-----------------------------------------------------------------|
| `python tests/run_most_nbs.py`                           | `pytest tests/notebooks/test_notebooks.py`                      |
| `SKIP_TO_NB=24 python tests/run_most_nbs.py`             | `pytest --lf tests/notebooks/test_notebooks.py`                 |
| `--skip-to-path opensearch/tmdb`                         | `pytest -k "opensearch/tmdb" tests/notebooks/test_notebooks.py` |
| `--only-path solr`                                       | `pytest -k solr tests/notebooks/test_notebooks.py`              |
| `ONLY_PATH="elasticsearch" python tests/run_most_nbs.py` | `PYTEST_ARGS="-k elasticsearch" ./tests/test.sh`                |

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest.ini](../pytest.ini) - Pytest configuration
- [TEST_INFRASTRUCTURE_REVIEW.md](../TEST_INFRASTRUCTURE_REVIEW.md) - Infrastructure review
- [PYTEST_EVALUATION.md](PYTEST_EVALUATION.md) - Migration evaluation

