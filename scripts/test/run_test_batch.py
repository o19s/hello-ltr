#!/usr/bin/env python3
"""
Script to run a batch of failing notebook tests and collect results.
Usage: python run_test_batch.py <start_index> <end_index>
"""

import sys
from pathlib import Path

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import (  # type: ignore  # noqa: E402
    FAILING_TESTS_FLAT_EXTENDED,
    print_test_summary,
    run_notebook_test,
    save_test_results,
)

# List of failing tests from CODEBASE_REVIEW.md section 5.3
FAILING_TESTS = FAILING_TESTS_FLAT_EXTENDED


def run_test(notebook_path):
    """Run a single notebook test and return results."""
    print(f"\n{'=' * 80}")
    print(f"Running: {notebook_path}")
    print(f"{'=' * 80}")

    return run_notebook_test(
        notebook_path,
        timeout=600,  # 10 minute timeout per test
        use_worker_containers=None,  # Use default behavior
        add_test_run_markers=False,  # Simpler output for batch runs
    )


def main():
    """Run a batch of failing tests and collect results."""
    if len(sys.argv) < 3:
        print("Usage: python run_test_batch.py <start_index> <end_index>")
        print(f"Total tests: {len(FAILING_TESTS)}")
        sys.exit(1)

    start_idx = int(sys.argv[1])
    end_idx = int(sys.argv[2])

    batch_tests = FAILING_TESTS[start_idx:end_idx]
    results = []
    passed_tests = []
    failed_tests = []

    for i, notebook_path in enumerate(batch_tests, start_idx + 1):
        print(f"\n[{i}/{len(FAILING_TESTS)}] Processing {notebook_path}")

        result = run_test(notebook_path)
        results.append(result)

        if result["passed"]:
            passed_tests.append(notebook_path)
            print(f"✅ PASSED: {notebook_path}")
        else:
            failed_tests.append(notebook_path)
            print(f"❌ FAILED: {notebook_path} (errors: {result['error_count']})")

    # Save results to JSON
    output_file = save_test_results(
        results,
        f"test_results_batch_{start_idx}_{end_idx}.json",
        metadata={
            "batch": f"{start_idx}-{end_idx}",
        },
    )

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"BATCH SUMMARY ({start_idx}-{end_idx})")
    print(f"{'=' * 80}")
    print_test_summary(results, passed_tests, failed_tests)
    print(f"\nResults saved to: {output_file}")

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
