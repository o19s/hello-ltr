#!/usr/bin/env python3
"""
Script to run remaining notebook tests with real-time streaming output.
Uses 2-3 minute timeout per test to prevent tests from running forever.
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
    FAILING_TESTS_FLAT,
    extract_errors,
    is_slow_notebook,
    print_test_summary,
    run_notebook_test,
)


# Timeout: 2-3 minutes (180 seconds) - enough for most tests, stops hanging tests quickly
STREAMING_TIMEOUT = 180


def run_test(notebook_path):
    """Run a single notebook test with streaming output and return results."""
    print(f"\n{'=' * 80}", flush=True)
    print(f"Running: {notebook_path}", flush=True)
    print(f"{'=' * 80}", flush=True)

    return run_notebook_test(
        notebook_path,
        timeout=STREAMING_TIMEOUT,  # 2-3 minute timeout per test
        use_worker_containers=True,
        stream_output=True,  # Enable real-time streaming
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
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": start_timestamp,
                "last_updated": datetime.now().isoformat(),
                "total": len(tests_to_run),
                "completed": len(results),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "timeout": len(timeout_tests),
                "timeout_seconds": STREAMING_TIMEOUT,
                "streaming_enabled": True,
                "filtered": {
                    "no_slow": getattr(args, "no_slow", False),
                    "only_slow": getattr(args, "only_slow", False),
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def main():
    """Run remaining notebook tests with streaming and collect results."""
    parser = argparse.ArgumentParser(
        description="Run remaining notebook tests with real-time streaming output (2-3 min timeout)"
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
    tests_to_run = FAILING_TESTS_FLAT.copy()

    if args.no_slow and args.only_slow:
        print(
            "Error: --no-slow and --only-slow cannot be used together", file=sys.stderr
        )
        return 1

    if args.no_slow:
        tests_to_run = [t for t in tests_to_run if not is_slow_notebook(t)]
        print(
            f"Filtered: Running {len(tests_to_run)} fast tests (skipping {len(FAILING_TESTS_FLAT) - len(tests_to_run)} slow tests)",
            flush=True,
        )
    elif args.only_slow:
        tests_to_run = [t for t in tests_to_run if is_slow_notebook(t)]
        print(
            f"Filtered: Running {len(tests_to_run)} slow tests (skipping {len(FAILING_TESTS_FLAT) - len(tests_to_run)} fast tests)",
            flush=True,
        )

    print(
        f"\nRunning {len(tests_to_run)} notebook tests with streaming output",
        flush=True,
    )
    print(
        f"Timeout: {STREAMING_TIMEOUT} seconds ({STREAMING_TIMEOUT // 60} minutes) per test",
        flush=True,
    )
    print("Output will be streamed in real-time\n", flush=True)

    # Create output file at the start
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = logs_dir / f"streaming_tests_{timestamp_str}.json"
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

        # Extract errors for better reporting
        if not result.get("passed") and not result.get("timeout"):
            output = result.get("stdout", "") + result.get("stderr", "")
            errors = extract_errors(output, notebook_path, max_cell_source=500)
            result["errors"] = errors
            result["error_count"] = len(errors)

        if result.get("timeout"):
            timeout_tests.append(notebook_path)
            print(
                f"⏱️  TIMEOUT: {notebook_path} (stopped after {STREAMING_TIMEOUT} seconds)",
                flush=True,
            )
        elif result.get("passed"):
            passed_tests.append(notebook_path)
            print(f"✅ PASSED: {notebook_path}", flush=True)
        else:
            failed_tests.append(notebook_path)
            error_count = result.get("error_count", 0)
            print(f"❌ FAILED: {notebook_path} ({error_count} errors)", flush=True)

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
