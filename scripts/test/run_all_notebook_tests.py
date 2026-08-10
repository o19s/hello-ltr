#!/usr/bin/env python3
"""
Script to run all notebook tests one by one with 5-minute timeout per test.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import (  # type: ignore  # noqa: E402, I001
    print_test_summary,
    run_notebook_test,
)


# List of untested notebooks from CODEBASE_REVIEW.md section 5.3
ALL_UNTESTED_NOTEBOOKS = [
    # Elasticsearch (7 untested)
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # Solr (4 untested)
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
]

# From the log, these failed or didn't complete:
# Failed: raw-es-commands, sandbox, gonna need a bigger bot, lambda-mart-in-python
# Interrupted: netfix movies-random-forests
# Not started: osc-blog, all 4 Solr notebooks
# Passed: bayesian-optimization (skip this one)
UNTESTED_NOTEBOOKS = [
    # Failed Elasticsearch notebooks
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    # Interrupted or not started
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # All Solr notebooks (not started)
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
]


def run_test(notebook_path):
    """Run a single notebook test and return results."""
    print(f"\n{'=' * 80}", flush=True)
    print(f"Running: {notebook_path}", flush=True)
    print(f"{'=' * 80}", flush=True)

    return run_notebook_test(
        notebook_path,
        timeout=300,  # 5 minute timeout per test
        use_worker_containers=True,
    )


def save_results_incremental(
    output_file: Path,
    results: list,
    passed_tests: list,
    failed_tests: list,
    timeout_tests: list,
    tests_to_run: list,
    args: argparse.Namespace,
    start_timestamp: str,
):
    """Save test results to JSON file incrementally."""
    # Use save_test_results but override the file path
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": start_timestamp,
                "last_updated": datetime.now().isoformat(),
                "total": len(tests_to_run),
                "completed": len(results),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "timeout": len(timeout_tests),
                "filtered": {
                    "no_slow": getattr(args, "no_slow", False),
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def main():
    """Run untested notebook tests and collect results."""
    parser = argparse.ArgumentParser(
        description="Run untested notebook tests one by one with 5-minute timeout"
    )
    args = parser.parse_args()

    # Use the untested notebooks list
    tests_to_run = UNTESTED_NOTEBOOKS.copy()

    print(f"Running {len(tests_to_run)} untested notebooks", flush=True)
    print("Note: Tests will timeout after 5 minutes if not completed", flush=True)

    # Create output file at the start
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = logs_dir / f"all_tests_run_{timestamp_str}.json"
    start_timestamp = datetime.now().isoformat()

    results = []
    passed_tests = []
    failed_tests = []
    timeout_tests = []

    # Initialize the JSON file with empty results
    save_results_incremental(
        output_file,
        results,
        passed_tests,
        failed_tests,
        timeout_tests,
        tests_to_run,
        args,
        start_timestamp,
    )
    print(f"Results will be saved incrementally to: {output_file}", flush=True)

    for i, notebook_path in enumerate(tests_to_run, 1):
        print(f"\n[{i}/{len(tests_to_run)}] Processing {notebook_path}", flush=True)

        result = run_test(notebook_path)
        results.append(result)

        if result["timeout"]:
            timeout_tests.append(notebook_path)
            print(f"⏱️  TIMEOUT: {notebook_path} (stopped after 5 minutes)", flush=True)
        elif result["passed"]:
            passed_tests.append(notebook_path)
            print(f"✅ PASSED: {notebook_path}", flush=True)
        else:
            failed_tests.append(notebook_path)
            print(
                f"❌ FAILED: {notebook_path} (errors: {result['error_count']})",
                flush=True,
            )

        # Update JSON file after each test completes
        save_results_incremental(
            output_file,
            results,
            passed_tests,
            failed_tests,
            timeout_tests,
            tests_to_run,
            args,
            start_timestamp,
        )

    # Print summary
    print_test_summary(results, passed_tests, failed_tests, timeout_tests)
    print(f"\nResults saved to: {output_file}", flush=True)

    return 0 if len(failed_tests) == 0 and len(timeout_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
