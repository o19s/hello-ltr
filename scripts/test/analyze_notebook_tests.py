#!/usr/bin/env python3
"""
Script to run all notebook tests, track failures, and analyze cell-level errors.
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import (  # type: ignore  # noqa: E402, I001
    FAILING_NOTEBOOKS_BY_ENGINE_EXTENDED,
    extract_errors,
    get_test_name,
    print_test_summary,
    save_test_results,
)
from tests.test_config import collect_notebooks  # noqa: E402


FAILING_NOTEBOOKS = FAILING_NOTEBOOKS_BY_ENGINE_EXTENDED


def collect_all_notebooks():
    """
    Collect all notebooks to test.

    This function delegates to the consolidated collect_notebooks() function
    from tests.test_config to avoid code duplication.

    Notebooks are ordered to optimize test execution:
    1. Setup notebooks run first
    2. hello-ltr notebooks run before dependent notebooks
    3. Fast notebooks run before slow notebooks (slow notebooks run last)

    Slow notebooks are identified by matching patterns in SLOW_PATTERNS
    (e.g., "lambda-mart", "bigger bot", "netfix", "bayesian-optimization").
    """
    return collect_notebooks()


def collect_failing_notebooks(engine_filter=None):
    """Collect only failing notebooks, optionally filtered by engine."""
    notebooks = []

    for engine, notebook_list in FAILING_NOTEBOOKS.items():
        if engine_filter and engine != engine_filter:
            continue

        for notebook_path in notebook_list:
            # Determine notebook type (usually "test")
            notebook_type = "test"
            notebooks.append((notebook_path, notebook_type, engine))

    return notebooks


def run_test(notebook_path, notebook_type, engine):
    """Run a single notebook test and return detailed results."""
    test_name = get_test_name(notebook_path, notebook_type, engine)

    print(f"\n{'=' * 80}")
    print(f"Running: {notebook_path}")
    print(f"{'=' * 80}")
    sys.stdout.flush()

    # When running sequential tests, disable per-worker containers
    # This allows reuse of existing containers or external container management
    env = os.environ.copy()
    env["USE_WORKER_CONTAINERS"] = "false"

    cmd = [
        "uv",
        "run",
        "pytest",
        test_name,
        "-v",
        "--no-cov",
        "--tb=short",
        "-s",  # Don't capture output so we see progress
        "-n",
        "0",  # Disable parallel execution for individual test runs
    ]

    process: Union[subprocess.Popen[str], None] = None
    output_lines: list[str] = []
    try:
        # Use Popen to stream output in real-time while capturing it
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            env=env,  # Pass environment variables
        )

        # Stream output in real-time
        for line in process.stdout:
            print(line, end="")  # Print immediately
            sys.stdout.flush()
            output_lines.append(line)

        process.wait(timeout=600)  # Wait with timeout

        output = "".join(output_lines)
        passed = process.returncode == 0

        # Extract error information using shared utility
        errors = extract_errors(output, notebook_path, max_cell_source=500)

        return {
            "notebook": notebook_path,
            "notebook_type": notebook_type,
            "engine": engine,
            "passed": passed,
            "returncode": process.returncode,
            "stdout": output,
            "stderr": "",
            "errors": errors,
            "error_count": len(errors),
        }
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
        print("\n⚠️  Test timed out after 10 minutes")
        return {
            "notebook": notebook_path,
            "notebook_type": notebook_type,
            "engine": engine,
            "passed": False,
            "returncode": -1,
            "stdout": "".join(output_lines),
            "stderr": "Test timed out after 10 minutes",
            "errors": [],
            "error_count": 0,
        }
    except Exception as e:
        return {
            "notebook": notebook_path,
            "notebook_type": notebook_type,
            "engine": engine,
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "errors": [],
            "error_count": 0,
        }


def analyze_failure(notebook_path, errors):
    """Analyze why a notebook failed based on cell errors."""
    if not errors:
        return {
            "likely_cause": "Test execution failed",
            "analysis": "No specific notebook errors reported. May be a test infrastructure issue or timeout.",
            "recommendations": [
                "Check if containers are running",
                "Verify notebook file is valid JSON",
                "Check for timeout issues",
            ],
        }

    # Group errors by type
    error_types = {}
    for error in errors:
        error_type = error["error_type"]
        if error_type not in error_types:
            error_types[error_type] = []
        error_types[error_type].append(error)

    # Analyze based on error patterns
    analysis = {
        "likely_cause": "Unknown",
        "analysis": "",
        "recommendations": [],
        "error_summary": {
            error_type: len(errors) for error_type, errors in error_types.items()
        },
    }

    # Check for common patterns
    if "RequestError" in error_types:
        analysis["likely_cause"] = "Feature set or model not found"
        analysis["analysis"] = (
            "Feature sets or models are being queried but don't exist. This often happens when feature set creation fails or model creation fails earlier in the notebook."
        )
        analysis["recommendations"] = [
            "Check if feature sets are created before being used",
            "Verify model creation succeeds before querying",
            "Check for index existence before creating feature sets",
        ]

    elif "RuntimeError" in error_types:
        runtime_errors = error_types["RuntimeError"]
        # Check error messages
        if any(
            "index" in err["error_message"].lower()
            and "does not exist" in err["error_message"].lower()
            for err in runtime_errors
        ):
            analysis["likely_cause"] = "Index does not exist"
            analysis["analysis"] = (
                "Notebook is trying to create feature sets or query an index that doesn't exist."
            )
            analysis["recommendations"] = [
                "Ensure index is created before feature set creation",
                "Check if index setup cell runs before feature set creation",
                "Verify index name matches between creation and usage",
            ]
        else:
            analysis["likely_cause"] = "Runtime error in notebook execution"
            analysis["analysis"] = (
                f"Runtime errors occurred in cells: {[e['cell_index'] for e in runtime_errors]}"
            )
            analysis["recommendations"] = [
                "Review the cell source code for the failing cells",
                "Check for missing dependencies or configuration",
            ]

    elif "NameError" in error_types:
        analysis["likely_cause"] = "Cascading errors from previous failures"
        analysis["analysis"] = (
            "Variables are undefined because previous cells failed. This is a cascading error - fix the root cause first."
        )
        analysis["recommendations"] = [
            "Find the first failing cell (lowest cell index)",
            "Fix the root cause error",
            "Cascading NameErrors will resolve once root cause is fixed",
        ]

    elif "TransportError" in error_types:
        analysis["likely_cause"] = "Model not found"
        analysis["analysis"] = (
            "Models are being queried but don't exist. This usually means model creation failed earlier."
        )
        analysis["recommendations"] = [
            "Check if model creation succeeds before querying",
            "Verify model name matches between creation and usage",
            "Check for feature set issues that prevent model creation",
        ]

    elif "KeyError" in error_types:
        analysis["likely_cause"] = "Response structure mismatch"
        analysis["analysis"] = (
            "Code is accessing dictionary keys that don't exist in the response. This often happens when queries fail but error handling is missing."
        )
        analysis["recommendations"] = [
            "Add error checking before accessing nested response keys",
            "Validate response structure before accessing data",
            "Handle error responses gracefully",
        ]

    # Add first failing cell info
    if errors:
        first_error = min(errors, key=lambda e: e["cell_index"])
        analysis["first_failing_cell"] = first_error["cell_index"]
        analysis["first_error_type"] = first_error["error_type"]
        analysis["first_error_message"] = first_error["error_message"]

    return analysis


def main():
    """Run all notebook tests and analyze failures."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run notebook tests and analyze failures"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of tests to run (for testing)"
    )
    parser.add_argument(
        "--start", type=int, default=0, help="Start index (for batch processing)"
    )
    parser.add_argument("--end", type=int, help="End index (for batch processing)")
    parser.add_argument(
        "--failing-only", action="store_true", help="Run only failing notebooks"
    )
    parser.add_argument(
        "--engine",
        choices=["opensearch", "elasticsearch", "solr"],
        help="Filter by engine type",
    )
    parser.add_argument(
        "--batch-size", type=int, help="Process notebooks in batches of this size"
    )
    args = parser.parse_args()

    print("Collecting notebooks to test...")

    # Collect notebooks based on filters
    if args.failing_only:
        notebooks = collect_failing_notebooks(engine_filter=args.engine)
        print("Running FAILING notebooks only")
        if args.engine:
            print(f"Filtered by engine: {args.engine}")
    else:
        notebooks = collect_all_notebooks()
        if args.engine:
            notebooks = [nb for nb in notebooks if nb[2] == args.engine]
            print(f"Filtered by engine: {args.engine}")

    # Apply batch limits if specified
    if args.end:
        notebooks = notebooks[args.start : args.end]
        print(f"Batch: {args.start} to {args.end}")
    elif args.start:
        notebooks = notebooks[args.start :]
        print(f"Starting from index: {args.start}")
    if args.limit:
        notebooks = notebooks[: args.limit]
        print(f"Limited to: {args.limit} notebooks")

    # Process in batches if batch-size specified
    if args.batch_size:
        total_batches = (len(notebooks) + args.batch_size - 1) // args.batch_size
        print(
            f"Processing in {total_batches} batches of {args.batch_size} notebooks each"
        )
        sys.stdout.flush()

        all_results = []
        all_passed = []
        all_failed = []

        for batch_num in range(total_batches):
            batch_start = batch_num * args.batch_size
            batch_end = min(batch_start + args.batch_size, len(notebooks))
            batch_notebooks = notebooks[batch_start:batch_end]

            print(f"\n{'=' * 80}")
            print(
                f"BATCH {batch_num + 1}/{total_batches} (notebooks {batch_start}-{batch_end - 1})"
            )
            print(f"{'=' * 80}")
            sys.stdout.flush()

            batch_results, batch_passed, batch_failed = run_notebook_batch(
                batch_notebooks, batch_start
            )
            all_results.extend(batch_results)
            all_passed.extend(batch_passed)
            all_failed.extend(batch_failed)

            # Save intermediate results
            output_file = save_test_results(
                batch_results,
                f"notebook_test_analysis_batch_{batch_num + 1}.json",
                metadata={
                    "batch": f"{batch_num + 1}/{total_batches}",
                },
            )
            print(f"\nBatch {batch_num + 1} results saved to: {output_file}")

        # Final summary
        print_final_summary(all_results, all_passed, all_failed)
        return 0 if len(all_failed) == 0 else 1

    print(f"Found {len(notebooks)} notebooks to test")
    print("Note: This may take a while. Each test can take up to 10 minutes.\n")
    sys.stdout.flush()

    results, passed_tests, failed_tests = run_notebook_batch(notebooks, 0)
    print_final_summary(results, passed_tests, failed_tests)
    return 0 if len(failed_tests) == 0 else 1


def run_notebook_batch(notebooks, start_index):
    """Run a batch of notebooks and return results."""
    results = []
    passed_tests = []
    failed_tests = []

    start_time = datetime.now()

    for i, (notebook_path, notebook_type, engine) in enumerate(notebooks, 1):
        elapsed = (datetime.now() - start_time).total_seconds()
        avg_time = elapsed / i if i > 0 else 0
        remaining = avg_time * (len(notebooks) - i)

        print(f"\n[{i}/{len(notebooks)}] Processing {notebook_path}")
        print(
            f"   Elapsed: {elapsed / 60:.1f}min | Est. remaining: {remaining / 60:.1f}min"
        )
        sys.stdout.flush()

        result = run_test(notebook_path, notebook_type, engine)
        results.append(result)

        if result["passed"]:
            passed_tests.append(notebook_path)
            print(f"\n✅ PASSED: {notebook_path}")
        else:
            failed_tests.append(notebook_path)
            print(f"\n❌ FAILED: {notebook_path} ({result['error_count']} errors)")

            # Analyze failure
            analysis = analyze_failure(notebook_path, result["errors"])
            result["failure_analysis"] = analysis

        sys.stdout.flush()

    return results, passed_tests, failed_tests


def print_final_summary(results, passed_tests, failed_tests):
    """Print final summary of test results."""
    # Save detailed results
    output_file = save_test_results(
        results,
        "notebook_test_analysis.json",
    )

    # Print summary
    print(f"\n{'=' * 80}")
    print("TEST EXECUTION SUMMARY")
    print(f"{'=' * 80}")
    print_test_summary(results, passed_tests, failed_tests)
    print(f"\nDetailed results saved to: {output_file}")

    # Print failure analysis
    if failed_tests:
        print(f"\n{'=' * 80}")
        print("FAILURE ANALYSIS")
        print(f"{'=' * 80}")

        for notebook_path in failed_tests:
            result = next(r for r in results if r["notebook"] == notebook_path)
            analysis = result.get("failure_analysis", {})

            print(f"\n❌ {notebook_path}")
            print(f"   Likely Cause: {analysis.get('likely_cause', 'Unknown')}")
            if analysis.get("first_failing_cell"):
                print(f"   First Failing Cell: {analysis['first_failing_cell']}")
                print(
                    f"   First Error Type: {analysis.get('first_error_type', 'Unknown')}"
                )
            if analysis.get("error_summary"):
                print(f"   Error Summary: {analysis['error_summary']}")
            if analysis.get("recommendations"):
                print("   Recommendations:")
                for rec in analysis["recommendations"]:
                    print(f"     - {rec}")

            # Show first few errors
            if result["errors"]:
                print(f"   Errors ({len(result['errors'])} total):")
                for error in result["errors"][:3]:  # Show first 3
                    print(
                        f"     Cell {error['cell_index']}: {error['error_type']}: {error['error_message'][:100]}"
                    )
                if len(result["errors"]) > 3:
                    print(f"     ... and {len(result['errors']) - 3} more errors")


if __name__ == "__main__":
    sys.exit(main())
