# Development Scripts

This directory contains utility scripts for development, testing, and code analysis. Scripts are organized by purpose:

## Directory Structure

### `test/` - Test-Related Scripts

Scripts for running and analyzing notebook tests:

- **`run_all_notebook_tests.py`** - Run all notebook tests one by one with timeout
- **`run_failing_tests.py`** - Run only failing notebook tests
- **`run_test_batch.py`** - Run a batch of failing notebook tests
- **`format_test_results.py`** - Format test_results.json into human-readable output
- **`document_notebook_errors.py`** - Extract and document notebook test errors
- **`analyze_notebook_tests.py`** - Analyze notebook tests and track failures

**Shared Utilities:**

- **`_setup.py`** - Centralized import setup module:
  - Handles `sys.path` setup for all scripts
  - Re-exports all constants and utilities
  - Scripts should import from `_setup` instead of directly from `constants`/`utils`

- **`utils.py`** - Shared utility functions for test scripts:
  - `get_test_name()` - Convert notebook path to pytest test name
  - `run_notebook_test()` - Run a single notebook test with configurable options
  - `extract_error_count()` - Extract error count from test output
  - `extract_summary()` - Extract readable summary from test output
  - `extract_errors()` - Extract detailed error information
  - `strip_ansi_codes()` - Remove ANSI escape sequences
  - `is_slow_notebook()` - Check if notebook matches slow patterns
  - `print_test_summary()` - Print formatted test summary
  - `save_test_results()` - Save test results to JSON

- **`constants.py`** - Shared constants for test scripts:
  - `SLOW_PATTERNS` - List of patterns identifying slow notebooks
  - `DEFAULT_TIMEOUT`, `LONG_TIMEOUT` - Timeout values
  - `FAILING_TESTS_FLAT` - Flat list of failing tests (ordered)
  - `FAILING_NOTEBOOKS_BY_ENGINE_*` - Engine-organized failing notebook lists

### `analysis/` - Code Analysis Scripts

Scripts for analyzing code quality and dependencies:

- **`analyze_dependencies.py`** - Analyze which dependencies are actually used in the codebase
- **`find_undocumented.py`** - Find functions, classes, and methods without docstrings

### `dev/` - Development Metrics

Scripts for measuring development metrics:

- **`measure_dev_metrics.py`** - Measure CI/CD build time, PR merge time, and bug escape rate

## Usage

All scripts should be run from the project root directory. They use relative paths that assume execution from the root:

```bash
# From project root
python scripts/test/run_all_notebook_tests.py
python scripts/analysis/analyze_dependencies.py
python scripts/dev/measure_dev_metrics.py
```

## Notes

- Scripts use relative paths (e.g., `./notebooks`, `tests/logs`) that assume execution from the project root
- Some scripts reference files in the root directory (e.g., `CODEBASE_REVIEW.md`, `requirements.txt`) using relative paths
- Test scripts may write output to `tests/logs/` directory

