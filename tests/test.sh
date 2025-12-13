#!/bin/bash
#
# Test runner wrapper for hello-ltr
#
# Syncs dependencies with uv and runs pytest. Environment validation is handled by
# conftest.py. All options passed via PYTEST_ARGS environment variable.
#
# Usage:
#   ./tests/test.sh                                    # Run all tests (parallel by default)
#   PYTEST_ARGS="--lf" ./tests/test.sh                # Re-run failed tests
#   PYTEST_ARGS="-n 1" ./tests/test.sh                # Run sequentially (disable parallel)
#   PYTEST_ARGS="-k opensearch" ./tests/test.sh       # Filter tests
#
# Environment Variables:
#   PYTEST_ARGS          Pytest arguments (e.g., "--lf", "-k opensearch", "-n 1" to disable parallel)
#   USE_WORKER_CONTAINERS Use per-worker containers (default: true)
#
# Alternative: uv run pytest tests/notebooks/test_notebooks.py
#

# Change to project root (allows running from any directory)
cd "$(dirname "$0")/.."

# Ensure dependencies are installed and synchronized
echo "[$(date +%H:%M:%S)] Syncing dependencies with uv..."
uv sync

# Run pytest (environment validation happens in conftest.py)
# USE_WORKER_CONTAINERS defaults to true in conftest.py if not set
uv run pytest tests/notebooks/test_notebooks.py $PYTEST_ARGS
exit $?
