#!/usr/bin/env python3
"""
Script to run all failing notebook tests one by one and collect results.
"""

import argparse
import sys
from pathlib import Path

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import (  # type: ignore  # noqa: E402, I001
    FAILING_TESTS_FLAT,
    is_slow_notebook,
    print_test_summary,
    run_notebook_test,
    save_test_results,
)


# List of failing tests from CODEBASE_REVIEW.md section 5.3
# Ordered: fast tests first, slow tests last (will timeout after 5 minutes)
# Slow patterns: "netfix", "bayesian-optimization", "bigger bot", "lambda-mart"
FAILING_TESTS = FAILING_TESTS_FLAT


def run_test(notebook_path):
    """Run a single notebook test and return results."""
    print(f"\n{'=' * 80}", flush=True)
    print(f"Running: {notebook_path}", flush=True)
    print(f"{'=' * 80}", flush=True)

    return run_notebook_test(
        notebook_path,
        timeout=300,  # 5 minute timeout per test (stop slow tests)
        use_worker_containers=True,
    )


def main():
    """Run all failing tests and collect results."""
    import sys

    # Ensure output is unbuffered for real-time logging
    # Use flush=True on all print statements instead of reconfigure
    parser = argparse.ArgumentParser(
        description="Run failing notebook tests with optional filtering"
    )
    parser.add_argument(
        "--no-slow",
        action="store_true",
        help="Skip slow tests (lambda-mart, bigger bot, netfix, bayesian-optimization, etc.)",
    )
    parser.add_argument(
        "--only-slow",
        action="store_true",
        help="Run only slow tests",
    )
    args = parser.parse_args()

    # Filter tests based on flags
    tests_to_run = FAILING_TESTS.copy()

    if args.no_slow and args.only_slow:
        print(
            "Error: --no-slow and --only-slow cannot be used together", file=sys.stderr
        )
        return 1

    if args.no_slow:
        tests_to_run = [t for t in tests_to_run if not is_slow_notebook(t)]
        print(
            f"Filtered: Running {len(tests_to_run)} fast tests (skipping {len(FAILING_TESTS) - len(tests_to_run)} slow tests)",
            flush=True,
        )
    elif args.only_slow:
        tests_to_run = [t for t in tests_to_run if is_slow_notebook(t)]
        print(
            f"Filtered: Running {len(tests_to_run)} slow tests (skipping {len(FAILING_TESTS) - len(tests_to_run)} fast tests)",
            flush=True,
        )

    results = []
    passed_tests = []
    failed_tests = []

    for i, notebook_path in enumerate(tests_to_run, 1):
        print(f"\n[{i}/{len(tests_to_run)}] Processing {notebook_path}", flush=True)

        result = run_test(notebook_path)
        results.append(result)

        if result["passed"]:
            passed_tests.append(notebook_path)
            print(f"✅ PASSED: {notebook_path}", flush=True)
        else:
            failed_tests.append(notebook_path)
            print(
                f"❌ FAILED: {notebook_path} (errors: {result['error_count']})",
                flush=True,
            )

    # Save results to JSON
    output_file = save_test_results(
        results,
        "test_results.json",
        metadata={
            "filtered": {
                "no_slow": args.no_slow,
                "only_slow": args.only_slow,
            },
        },
    )

    # Print summary
    print_test_summary(results, passed_tests, failed_tests)
    print(f"\nResults saved to: {output_file}", flush=True)

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
