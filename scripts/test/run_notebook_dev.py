#!/usr/bin/env python3
r"""
Development script for fast notebook iteration with real-time streaming output.

This script provides a faster feedback loop for notebook development by:
- Streaming output in real-time (no buffering)
- Stopping on first error (fail-fast)
- Showing immediate error visibility
- Allowing interactive interruption (Ctrl+C)
- Bypassing pytest overhead for single notebook testing

Usage:
    # Run a single notebook with streaming output
    python scripts/test/run_notebook_dev.py notebooks/opensearch/tmdb/hello-ltr\ \(OpenSearch\).ipynb

    # Run with custom timeout
    NOTEBOOK_TIMEOUT_MINUTES=2 python scripts/test/run_notebook_dev.py notebooks/solr/tmdb/sandbox.ipynb

    # Run with fail-fast disabled (collect all errors)
    NOTEBOOK_FAIL_FAST=false python scripts/test/run_notebook_dev.py notebooks/elasticsearch/tmdb/hello-ltr\ \(ES\).ipynb

Environment Variables:
    NOTEBOOK_TIMEOUT_MINUTES: Timeout in minutes (default: 5)
    NOTEBOOK_FAIL_FAST: Enable fail-fast mode (default: true)
    NOTEBOOK_MAX_KCV_FOLDS: Max kcv folds for testing (default: 1)
    NOTEBOOK_MAX_TREES: Max trees for testing (default: 1)
    NOTEBOOK_MAX_BAG: Max bag for testing (default: 1)
    NOTEBOOK_MAX_LEAFS: Max leafs for testing (default: 1)
    NOTEBOOK_MAX_FEATURES: Max features for testing (default: 2)
    NOTEBOOK_MAX_QUERIES: Max queries for testing (default: 2)
    NOTEBOOK_MAX_JUDGMENTS_PER_QUERY: Max judgments per query (default: 2)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after sys.path setup - type checker shows false positive
from tests.notebooks.runner import run_notebook  # noqa: E402


def main():
    """Run a notebook with development-friendly settings."""
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/test/run_notebook_dev.py <notebook_path>",
            file=sys.stderr,
        )
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    notebook_path = sys.argv[1]

    # Check if notebook exists
    if not os.path.exists(notebook_path):
        print(f"Error: Notebook not found: {notebook_path}", file=sys.stderr)
        sys.exit(1)

    # Get configuration from environment
    fail_fast = os.environ.get("NOTEBOOK_FAIL_FAST", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    timeout_minutes = float(os.environ.get("NOTEBOOK_TIMEOUT_MINUTES", "5"))
    timeout = int(timeout_minutes * 60)

    print("=" * 80)
    print(f"Running notebook: {notebook_path}")
    print(f"Fail-fast mode: {'enabled' if fail_fast else 'disabled'}")
    print(f"Timeout: {timeout_minutes} minutes")
    print("=" * 80)
    print()

    try:
        # Run notebook with fail-fast enabled by default for development
        _nb, errors, exec_time = run_notebook(
            notebook_path=notebook_path,
            timeout=timeout,
            save_nb_path="tests/last_run.ipynb",
            fail_fast=fail_fast,
        )

        print()
        print("=" * 80)
        if errors:
            print(f"FAILED: {len(errors)} error(s) found")
            print("=" * 80)
            for i, error in enumerate(errors, 1):
                print(f"\nError {i}/{len(errors)}:")
                print(f"  Cell: {error.get('cell_index', 'unknown')}")
                print(f"  Type: {error.get('ename', 'Unknown')}")
                print(f"  Message: {error.get('evalue', 'No message')}")
                if error.get("traceback"):
                    print("  Traceback:")
                    for tb_line in error["traceback"][:10]:
                        print(f"    {tb_line}")
            print("=" * 80)
            sys.exit(1)
        else:
            print("SUCCESS: Notebook executed without errors")
            print(f"Execution time: {exec_time:.1f}s")
            print("=" * 80)
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
