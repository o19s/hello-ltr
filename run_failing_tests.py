#!/usr/bin/env python3
"""
Script to run all failing notebook tests one by one and collect results.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Slow notebook patterns (matches tests/notebooks/test_notebooks.py)
SLOW_PATTERNS = [
    "netfix",
    "bayesian-optimization",
    "bigger bot",
    "lambda-mart",
    "feature_search",
    "evaluation",
    "ai-powered-search",  # Also slow
]


def _is_slow_notebook(notebook_path: str) -> bool:
    """Check if a notebook matches known slow patterns."""
    if not notebook_path:
        return False
    notebook_path_lower = notebook_path.lower()
    return any(pattern.lower() in notebook_path_lower for pattern in SLOW_PATTERNS)


# List of failing tests from NOTEBOOK_TEST_RESULTS.md
# Ordered: fast tests first, slow tests last (will timeout after 5 minutes)
# Slow patterns: "netfix", "bayesian-optimization", "bigger bot", "lambda-mart"
FAILING_TESTS = [
    # Fast tests first (OpenSearch)
    "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
    "./notebooks/opensearch/tmdb/raw-opensearch-commands.ipynb",
    "./notebooks/opensearch/tmdb/sandbox.ipynb",
    "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
    "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
    # Fast tests first (Elasticsearch)
    "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
    "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # Fast tests first (Solr)
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
    # Slow tests last (will timeout after 5 minutes)
    "./notebooks/opensearch/tmdb/gonna need a bigger bot (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies.ipynb",
    "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
]


def get_test_name(notebook_path):
    """Convert notebook path to pytest test name format."""
    # Determine engine from path
    if "opensearch" in notebook_path:
        engine = "opensearch"
    elif "elasticsearch" in notebook_path:
        engine = "elasticsearch"
    elif "solr" in notebook_path:
        engine = "solr"
    else:
        engine = "general"

    # Determine notebook type (usually "test" for these)
    notebook_type = "test"

    return f"tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[{notebook_path}-{notebook_type}-{engine}]"


def run_test(notebook_path):
    """Run a single notebook test and return results."""
    test_name = get_test_name(notebook_path)

    print(f"\n{'=' * 80}", flush=True)
    print(f"Running: {notebook_path}", flush=True)
    print(f"{'=' * 80}", flush=True)

    cmd = ["uv", "run", "pytest", test_name, "-n", "1", "-v", "--no-cov", "--tb=short"]

    # Set USE_WORKER_CONTAINERS=true as default to ensure tests use isolated test containers
    # Only set if not already specified (allows override if needed)
    env = os.environ.copy()
    if "USE_WORKER_CONTAINERS" not in env:
        env["USE_WORKER_CONTAINERS"] = "true"

    # Add TEST RUN message before test
    test_run_start = f"TEST RUN: {notebook_path}\n"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per test (stop slow tests)
            env=env,
        )

        passed = result.returncode == 0
        error_count = extract_error_count(result.stdout + result.stderr)
        summary = extract_summary(result.stdout, result.stderr)

        # Strip ANSI codes for cleaner JSON logs (colors are for terminal display only)
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")

        formatted_stdout = ansi_escape.sub("", result.stdout) if result.stdout else ""
        formatted_stderr = ansi_escape.sub("", result.stderr) if result.stderr else ""

        # Determine result status
        result_status = "SUCCESS" if passed else "FAILURE"

        # Add TEST RUN messages before and after test output
        test_run_end = f"\nTEST RUN: {notebook_path}\n"
        test_run_result = f"TEST RUN: {notebook_path}: {result_status}\n"

        # Prepend start message and append end messages to stdout
        formatted_stdout = (
            test_run_start + formatted_stdout + test_run_end + test_run_result
        )

        return {
            "notebook": notebook_path,
            "passed": passed,
            "returncode": result.returncode,
            "error_count": error_count,
            "summary": summary,
            "stdout": formatted_stdout,
            "stderr": formatted_stderr,
        }
    except subprocess.TimeoutExpired:
        timeout_msg = "Test timed out after 5 minutes (slow test stopped)"
        test_run_end = f"\nTEST RUN: {notebook_path}\n"
        test_run_result = f"TEST RUN: {notebook_path}: TIMEOUT\n"
        timeout_output = test_run_start + timeout_msg + test_run_end + test_run_result
        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "error_count": 0,
            "summary": {
                "status": "timeout",
                "error_message": timeout_msg,
                "key_lines": [timeout_msg],
            },
            "stdout": timeout_output,
            "stderr": timeout_msg,
        }
    except Exception as e:
        error_msg = str(e)
        test_run_end = f"\nTEST RUN: {notebook_path}\n"
        test_run_result = f"TEST RUN: {notebook_path}: FAILURE\n"
        error_output = test_run_start + error_msg + test_run_end + test_run_result
        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "error_count": 0,
            "summary": {
                "status": "error",
                "error_message": error_msg,
                "key_lines": [error_msg],
            },
            "stdout": error_output,
            "stderr": error_msg,
        }


def extract_error_count(output):
    """Extract error count from test output."""
    # Look for "Errors in" pattern
    import re

    matches = re.findall(r"Errors in .*?: (\d+) error", output)
    if matches:
        return sum(int(m) for m in matches)
    return 0


def extract_summary(stdout, stderr):
    """Extract a readable summary from test output."""
    import re

    summary = {
        "status": "unknown",
        "error_message": None,
        "key_lines": [],
    }

    combined = (stdout or "") + (stderr or "")

    # Extract key error messages
    if "FAILED" in combined:
        summary["status"] = "failed"
        # Try to extract the main error message
        error_match = re.search(r"FAILED.*?\n(.*?)(?:\n\n|\n===)", combined, re.DOTALL)
        if error_match:
            error_line = error_match.group(1).strip()
            if len(error_line) < 200:  # Only if reasonable length
                summary["error_message"] = error_line
    elif "PASSED" in combined or "passed" in combined.lower():
        summary["status"] = "passed"

    # Extract key lines (first few non-empty lines, last few lines)
    lines = combined.split("\n")
    non_empty = [line.strip() for line in lines if line.strip()][
        :5
    ]  # First 5 non-empty
    if len(non_empty) > 0:
        summary["key_lines"] = non_empty[:3]  # First 3 key lines

    return summary


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
        tests_to_run = [t for t in tests_to_run if not _is_slow_notebook(t)]
        print(
            f"Filtered: Running {len(tests_to_run)} fast tests (skipping {len(FAILING_TESTS) - len(tests_to_run)} slow tests)",
            flush=True,
        )
    elif args.only_slow:
        tests_to_run = [t for t in tests_to_run if _is_slow_notebook(t)]
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

    # Save results to JSON with pretty formatting
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    output_file = logs_dir / "test_results.json"

    # Prepare results with formatted output
    formatted_results = []
    for result in results:
        formatted_result = result.copy()
        # Keep stdout/stderr as-is (JSON will handle newlines properly)
        # The indent=2 will make the JSON readable, and newlines in strings are preserved
        formatted_results.append(formatted_result)

    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "total": len(tests_to_run),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "filtered": {
                    "no_slow": args.no_slow,
                    "only_slow": args.only_slow,
                },
                "results": formatted_results,
            },
            f,
            indent=2,
            ensure_ascii=False,  # Preserve unicode characters properly
        )

    # Print summary
    print(f"\n{'=' * 80}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'=' * 80}", flush=True)
    print(f"Total tests run: {len(tests_to_run)}", flush=True)
    print(f"✅ Passed: {len(passed_tests)}", flush=True)
    print(f"❌ Failed: {len(failed_tests)}", flush=True)
    print(f"\nResults saved to: {output_file}", flush=True)

    if passed_tests:
        print("\n✅ Now passing:", flush=True)
        for test in passed_tests:
            print(f"  - {test}", flush=True)

    if failed_tests:
        print("\n❌ Still failing:", flush=True)
        for test in failed_tests:
            result = next(r for r in results if r["notebook"] == test)
            print(f"  - {test} ({result['error_count']} errors)", flush=True)

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
