# Hello-LTR Test Suite

This directory contains the test infrastructure for the hello-ltr project, focusing on automated notebook testing using pytest.

## Overview

The test suite validates that all Jupyter notebooks execute successfully without errors. It covers:
- 36+ notebooks across Solr, Elasticsearch, and OpenSearch
- Integration testing with Docker containers
- Automated setup and teardown
- Parallel execution support

## Quick Start

### Run All Tests
```bash
# With Docker orchestration (recommended)
./tests/test.sh

# Direct pytest (requires services already running)
pytest tests/test_notebooks.py
```

### Run Specific Tests
```bash
# Re-run only failed tests from last run
pytest --lf tests/test_notebooks.py

# Run only Solr notebooks
pytest -k solr tests/test_notebooks.py

# Run in parallel (4x faster)
pytest -n auto tests/test_notebooks.py

# Retry flaky tests (retry failed tests 3 times with 2 second delay)
pytest --reruns 3 --reruns-delay 2 tests/test_notebooks.py
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

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows
```

Using standard Python venv:
```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows
```

**3. Install Dependencies**

Using `uv` (recommended):
```bash
uv pip install -e .
```

Using pip:
```bash
pip install --upgrade pip wheel setuptools
pip install -e .
```

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
pytest -k "sandbox" tests/test_notebooks.py -v
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
```bash
# Error: "Port already in use"
# Solution: Stop conflicting services or use different ports
export SOLR_PORT=28983
export ELASTICSEARCH_PORT=29200
export OPENSEARCH_PORT=29201
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
NOTEBOOK_TIMEOUT_HOURS=12        # Extended timeout for CI
```

**CI Setup Script:**
```bash
#!/bin/bash
set -e

# Install dependencies
uv pip install -e .

# Verify Docker
docker compose version

# Run tests non-interactively
AUTO_CLEANUP_CONFLICTS=true ./tests/test.sh --non-interactive
```

## Pytest Command Reference

### Re-run Failed Tests
```bash
# Run only tests that failed in the last run
pytest --lf tests/test_notebooks.py

# Run failed tests first, then continue with the rest
pytest --ff tests/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="--lf" ./tests/test.sh
```

### Resume After Failure
```bash
# Stepwise: stop at first failure, resume from there on next run
pytest --sw tests/test_notebooks.py

# Stop at first failure (useful for debugging)
pytest -x tests/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="--sw" ./tests/test.sh
```

### Filter Tests by Pattern
```bash
# Run tests matching a pattern (by path, engine, etc.)
pytest -k "opensearch" tests/test_notebooks.py
pytest -k "solr or elasticsearch" tests/test_notebooks.py
pytest -k "not evaluation" tests/test_notebooks.py

# Run only Solr notebooks
pytest -k "solr" tests/test_notebooks.py

# Run only notebooks with "lambda-mart" in the name
pytest -k "lambda-mart" tests/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="-k opensearch" ./tests/test.sh
```

### Run Specific Notebook
```bash
# Run a specific notebook test
pytest "tests/test_notebooks.py::test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb-test-solr]"

# Easier: use -k with a unique part of the path
pytest -k "sandbox" tests/test_notebooks.py
```

### Run by Test Markers
```bash
# Run only Solr tests (using markers)
pytest -m solr tests/test_notebooks.py

# Run only setup notebooks
pytest -m setup tests/test_notebooks.py

# Skip slow tests
pytest -m "not slow" tests/test_notebooks.py

# Combine markers
pytest -m "opensearch and not slow" tests/test_notebooks.py
```

### Parallel Execution (Faster Tests)
```bash
# Run on all available CPU cores
pytest -n auto tests/test_notebooks.py

# Run on specific number of workers
pytest -n 4 tests/test_notebooks.py

# With Docker wrapper
PYTEST_ARGS="-n auto" ./tests/test.sh

# Group tests by engine (recommended for Docker)
# Each engine gets its own worker, avoiding port conflicts
pytest -n auto --dist loadgroup tests/test_notebooks.py
```

**Port Conflict Handling:**
- When running in parallel, each worker automatically gets unique ports
- Port offset: base_port + (worker_id * 1000)
- Example: Worker 0 uses ports 18983, 19200, 19201; Worker 1 uses 19983, 20200, 20201
- Ports are logged at worker startup for debugging

**Note**: When using `test.sh` with Docker, containers are started once before pytest runs. For best results with parallel execution:
- Use `--dist loadgroup` to group by engine (recommended)
- Or run sequential tests if you need all engines available to all workers

### Verbose Output
```bash
# Verbose output (show test names)
pytest -v tests/test_notebooks.py

# Very verbose (show more details)
pytest -vv tests/test_notebooks.py

# Show print statements (useful for debugging)
pytest -s tests/test_notebooks.py

# Show local variables on failure
pytest -l tests/test_notebooks.py
```

### Generate Reports
```bash
# Generate HTML report
pytest --html=report.html --self-contained-html tests/test_notebooks.py

# Generate JUnit XML (for CI/CD)
pytest --junitxml=results.xml tests/test_notebooks.py

# Show slowest 10 tests
pytest --durations=10 tests/test_notebooks.py
```

### Tips & Tricks
```bash
# List all tests without running
pytest --collect-only tests/test_notebooks.py

# Count tests matching a pattern
pytest --collect-only -q -k "opensearch" tests/test_notebooks.py

# Clear pytest cache (including last-failed data)
pytest --cache-clear

# Show cache contents
pytest --cache-show

# Combining options: Run failed tests first, then only opensearch tests, in parallel
pytest --ff -k opensearch -n 4 tests/test_notebooks.py

# Verbose, show prints, stop at first failure
pytest -vv -s -x tests/test_notebooks.py
```

## Test Infrastructure

### Architecture

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_notebooks.py        # Main test suite (parametrized)
├── runner.py                # Notebook execution engine
├── nb_test_config.py        # Test path configuration
├── patch_clients_for_tests.py  # Port patching for isolation
├── test.sh                  # Docker orchestration script
└── README.md               # This file
```

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

**4. Docker Orchestration ([test.sh](test.sh))**
- Starts required Docker containers
- Port conflict detection and resolution
- Service health checking
- Automatic cleanup on exit/interrupt

## Test Configuration

### Pytest Settings ([pytest.ini](../pytest.ini))

```ini
[pytest]
# Timeout: 6 hours per test (matches notebook execution needs)
timeout = 21600

# Markers for test categorization
markers =
    solr: Solr-specific tests
    elasticsearch: Elasticsearch tests
    opensearch: OpenSearch tests
    slow: Slow-running tests
    setup: Setup notebooks
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
- `NOTEBOOK_TIMEOUT_HOURS`: Timeout per notebook (default: 6)
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

Add it to `IGNORED_NOTEBOOKS` in [conftest.py](conftest.py):

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
   NOTEBOOK_TIMEOUT_HOURS=12 ./tests/test.sh
   ```

2. **Check for infinite loops** in notebook:
   - Review `tests/last_run.ipynb` to see where it stopped
   - Look for cells that might be hanging

3. **Run specific slow notebook with extended timeout**:
   ```bash
   NOTEBOOK_TIMEOUT_HOURS=24 pytest -k "specific-notebook" tests/test_notebooks.py
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
   pytest -n 2 tests/test_notebooks.py  # Limit to 2 workers
   pytest -n 1 tests/test_notebooks.py  # Single worker
   ```

2. **Run sequentially** (no parallel execution):
   ```bash
   pytest tests/test_notebooks.py  # No -n flag
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
   ./tests/test.sh --engines=solr
   ./tests/test.sh --engines=elasticsearch
   ./tests/test.sh --engines=opensearch
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
   pytest -n auto --dist loadgroup tests/test_notebooks.py
   ```
   This groups tests by engine, reducing port conflicts.

3. **Run sequential tests** (if parallel causes issues):
   ```bash
   pytest tests/test_notebooks.py  # No -n flag
   ```

4. **Check worker port assignments**:
   - Look for `[Worker gw0] Using ports:` messages in test output
   - Verify each worker has unique ports

**Note**: When using `test.sh` with Docker, containers are started once before pytest runs. For true parallel execution with isolated containers per worker, consider:
- Using `--dist loadgroup` to group tests by engine
- Starting containers manually per worker (advanced)
- Running sequential tests: `pytest tests/test_notebooks.py` (no `-n` flag)

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
   pytest --cache-clear tests/test_notebooks.py
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

2. **Rebuild containers**:
   ```bash
   ./tests/test.sh --rebuild-containers
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
   pip list | grep -E "(elasticsearch|opensearch|pysolr)"
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
   pip install -e .
   # or
   uv pip install -e .
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
   pip install --force-reinstall -e .
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
   pytest tests/test_notebooks.py -v
   ```

2. **Manual validation**:
   ```bash
   python -c "from tests.test_env_validation import check_test_environment; check_test_environment(verbose=True)"
   ```

3. **Fix missing dependencies**:
   ```bash
   # Install missing packages
   uv pip install -e .
   # Or specific packages
   uv pip install pytest pytest-xdist pytest-timeout pytest-html pytest-cov
   ```

4. **Skip specific checks** (if handled elsewhere):
   ```bash
   # Skip Docker check (if test.sh handles it)
   SKIP_DOCKER_CHECK=true pytest tests/test_notebooks.py
   
   # Skip port check (if test.sh handles conflicts)
   SKIP_PORT_CHECK=true pytest tests/test_notebooks.py
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

### Slow Test Execution

**Problem**: Tests run very slowly

**Symptoms:**
- Tests take hours to complete
- Individual notebooks take 30+ minutes
- System is unresponsive during tests

**Solutions:**

1. **Use parallel execution**:
   ```bash
   pytest -n auto tests/test_notebooks.py  # 4x faster
   ```

2. **Run only fast tests**:
   ```bash
   pytest -m "not slow" tests/test_notebooks.py
   ```

3. **Run specific engines**:
   ```bash
   ./tests/test.sh --engines=solr  # Test only Solr
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
pytest --sw tests/test_notebooks.py

# After fixing, re-run only the failed test
pytest --lf tests/test_notebooks.py
```

### Development Cycle
```bash
# 1. Make changes to a notebook
# 2. Run just that notebook
pytest -k "my-notebook" tests/test_notebooks.py

# 3. If it fails, fix and re-run
pytest --lf tests/test_notebooks.py
```

### Pre-Commit Testing
```bash
# Run fast tests only (skip slow evaluation notebooks)
pytest -m "not slow" tests/test_notebooks.py
```

### CI/CD: Full Test Suite
```bash
# Run all tests in parallel with JUnit report
pytest -n auto --junitxml=results.xml tests/test_notebooks.py

# Or with HTML report
pytest -n auto --html=report.html --self-contained-html tests/test_notebooks.py
```

### Debugging: Single Notebook
```bash
# Run one notebook with full output
pytest -s -vv -k "sandbox" tests/test_notebooks.py

# Run with full output and stop at first failure
pytest -s -vv -x -k "failing-notebook" tests/test_notebooks.py

# Check the last executed notebook
cat tests/last_run.ipynb
```

### Performance: Find Slow Tests
```bash
# Show 10 slowest tests
pytest --durations=10 tests/test_notebooks.py
```

## Test Results

### Understanding Output

**Successful test:**
```
tests/test_notebooks.py::test_notebook[./notebooks/solr/tmdb/sandbox.ipynb] PASSED [10%]
```

**Failed test:**
```
tests/test_notebooks.py::test_notebook[./notebooks/solr/tmdb/sandbox.ipynb] FAILED [10%]
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
pytest --html=report.html --self-contained-html tests/test_notebooks.py
```

## Performance

### Test Execution Time

- **Sequential**: ~20 minutes for all 36 notebooks
- **Parallel (-n auto)**: ~5-7 minutes (4x faster)

### Per-Notebook Timing

See slowest tests:
```bash
pytest --durations=10 tests/test_notebooks.py
```

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    ./tests/test.sh --non-interactive
  env:
    AUTO_CLEANUP_CONFLICTS: true
    NOTEBOOK_TIMEOUT_HOURS: 12
```

### Jenkins Example
```groovy
stage('Test') {
    steps {
        sh '''
            export AUTO_CLEANUP_CONFLICTS=true
            ./tests/test.sh --non-interactive
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
   pytest -k "your-notebook-name" tests/test_notebooks.py -v
   ```

5. **Verify it's discovered**:
   ```bash
   # List all collected tests
   pytest --collect-only tests/test_notebooks.py | grep your-notebook
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
   pytest tests/test_notebooks.py -vv > test_output.txt
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
   - `tests/test_notebooks.py` - Example integration test
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

| Old Command | New Pytest Command |
|-------------|-------------------|
| `python tests/run_most_nbs.py` | `pytest tests/test_notebooks.py` |
| `SKIP_TO_NB=24 python tests/run_most_nbs.py` | `pytest --lf tests/test_notebooks.py` |
| `--skip-to-path opensearch/tmdb` | `pytest -k "opensearch/tmdb" tests/test_notebooks.py` |
| `--only-path solr` | `pytest -k solr tests/test_notebooks.py` |
| `ONLY_PATH="elasticsearch" python tests/run_most_nbs.py` | `PYTEST_ARGS="-k elasticsearch" ./tests/test.sh` |

## Further Reading

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest.ini](../pytest.ini) - Pytest configuration
- [TEST_INFRASTRUCTURE_REVIEW.md](../TEST_INFRASTRUCTURE_REVIEW.md) - Infrastructure review
- [PYTEST_EVALUATION.md](PYTEST_EVALUATION.md) - Migration evaluation

