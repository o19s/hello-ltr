#!/usr/bin/env python3
"""
Investigate Fast-Failing Tests

Identifies tests that complete in ~0.001s and determines if they're:
1. Legitimately fast tests (expected)
2. Failing quickly due to import/module errors
3. Cached results from previous runs
4. Actual failures that need fixing

Usage:
    python tests/investigate_fast_failures.py                    # Investigate all tests
    python tests/investigate_fast_failures.py --unit              # Unit tests only
    python tests/investigate_fast_failures.py --integration      # Integration tests only
    python tests/investigate_fast_failures.py --notebooks        # Notebook tests only
    python tests/investigate_fast_failures.py --threshold 0.005  # Custom threshold (default 0.005s)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def run_pytest_with_detailed_output(
    test_path: str, parallel: bool = False
) -> tuple[dict[str, dict], float]:
    """
    Run pytest and collect detailed test results including failures and errors.

    Returns:
        Tuple of (test_results dict, total_time)
        test_results format: {nodeid: {'duration': float, 'status': str, 'error': str}}
    """
    project_root = Path(__file__).parent.parent

    # Create temporary files for reports
    with tempfile.NamedTemporaryFile(
        encoding="utf-8", suffix=".xml", delete=False, mode="w"
    ) as f:
        xml_report_path = f.name

    # Build pytest command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "-v",
        "--tb=short",
        f"--junitxml={xml_report_path}",
    ]

    if parallel:
        cmd.extend(["-n", "auto"])

    # Run pytest
    subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False,
    )
    total_time = 0.0  # We'll calculate from XML

    # Parse JUnit XML report
    test_results = {}
    try:
        if Path(xml_report_path).exists():
            tree = ET.parse(xml_report_path)
            root = tree.getroot()

            for testcase in root.findall(".//testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_attr = testcase.get("time", "0")

                # Construct nodeid
                nodeid = f"{classname}::{name}" if classname else name

                try:
                    duration = float(time_attr)
                except ValueError:
                    duration = 0.0

                # Check for failures or errors
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")

                status = "passed"
                error_msg = ""

                if skipped is not None:
                    status = "skipped"
                    error_msg = skipped.get("message", "")
                elif failure is not None:
                    status = "failed"
                    error_msg = failure.get("message", "") or failure.text or ""
                elif error is not None:
                    status = "error"
                    error_msg = error.get("message", "") or error.text or ""

                test_results[nodeid] = {
                    "duration": duration,
                    "status": status,
                    "error": error_msg[:500]
                    if error_msg
                    else "",  # Truncate long errors
                }

            # Clean up temp files
            Path(xml_report_path).unlink(missing_ok=True)
    except (ET.ParseError, FileNotFoundError) as e:
        print(f"Warning: Could not parse XML report: {e}", file=sys.stderr)

    return test_results, total_time


def categorize_fast_tests(
    test_results: dict[str, dict], threshold: float = 0.005
) -> dict[str, list[dict]]:
    """
    Categorize tests that complete quickly.

    Returns:
        Dict with keys: 'legitimate', 'import_errors', 'other_failures', 'cached'
    """
    categories = {
        "legitimate": [],  # Fast tests that pass
        "import_errors": [],  # Tests failing due to import/module errors
        "other_failures": [],  # Tests failing for other reasons
        "skipped": [],  # Tests that are skipped
    }

    import_error_keywords = [
        "ModuleNotFoundError",
        "ImportError",
        "cannot import",
        "No module named",
        "Module not found",
        "Import failed",
    ]

    for nodeid, result in test_results.items():
        duration = result["duration"]
        status = result["status"]
        error = result["error"]

        # Only consider tests that complete very quickly
        if duration > threshold:
            continue

        test_info = {
            "nodeid": nodeid,
            "duration": duration,
            "status": status,
            "error": error,
        }

        if status == "skipped":
            categories["skipped"].append(test_info)
        elif status == "passed":
            # Legitimately fast test
            categories["legitimate"].append(test_info)
        elif status in ("failed", "error"):
            # Check if it's an import error
            error_lower = error.lower()
            is_import_error = any(
                keyword.lower() in error_lower for keyword in import_error_keywords
            )

            if is_import_error:
                categories["import_errors"].append(test_info)
            else:
                categories["other_failures"].append(test_info)

    return categories


def check_pytest_cache() -> dict[str, float]:
    """Check pytest cache for cached execution times."""
    cache_dir = Path(__file__).parent.parent / ".pytest_cache" / "v" / "cache"
    cache_file = cache_dir / "test_execution_times"

    cached_times = {}
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cached_times = data
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return cached_times


def print_report(
    categories: dict[str, list[dict]], cached_times: dict[str, float], threshold: float
):
    """Print investigation report."""
    print("=" * 80)
    print("Fast-Failing Tests Investigation Report")
    print("=" * 80)
    print(f"\nThreshold: {threshold}s (tests completing faster than this are analyzed)")
    print(f"\nTotal fast tests found: {sum(len(v) for v in categories.values())}")
    print()

    # Legitimate fast tests
    if categories["legitimate"]:
        print(f"✅ Legitimately Fast Tests ({len(categories['legitimate'])}):")
        print(
            "   These tests pass and are simply very fast (<0.01s is normal for unit tests)"
        )
        for test in sorted(categories["legitimate"], key=lambda x: x["duration"])[:10]:
            cached = " (cached)" if test["nodeid"] in cached_times else ""
            print(f"   - {test['nodeid']}: {test['duration']:.4f}s{cached}")
        if len(categories["legitimate"]) > 10:
            print(f"   ... and {len(categories['legitimate']) - 10} more")
        print()

    # Import errors
    if categories["import_errors"]:
        print(f"⚠️  Import/Module Errors ({len(categories['import_errors'])}):")
        print("   These tests fail quickly due to import or module errors")
        for test in categories["import_errors"]:
            cached = " (cached)" if test["nodeid"] in cached_times else ""
            print(f"   - {test['nodeid']}: {test['duration']:.4f}s{cached}")
            if test["error"]:
                error_preview = test["error"].split("\n")[0][:100]
                print(f"     Error: {error_preview}...")
        print()

    # Other failures
    if categories["other_failures"]:
        print(f"❌ Other Fast Failures ({len(categories['other_failures'])}):")
        print("   These tests fail quickly for reasons other than import errors")
        for test in categories["other_failures"]:
            cached = " (cached)" if test["nodeid"] in cached_times else ""
            print(f"   - {test['nodeid']}: {test['duration']:.4f}s{cached}")
            if test["error"]:
                error_preview = test["error"].split("\n")[0][:100]
                print(f"     Error: {error_preview}...")
        print()

    # Skipped tests
    if categories["skipped"]:
        print(f"⏭️  Skipped Tests ({len(categories['skipped'])}):")
        print("   These tests are intentionally skipped")
        for test in categories["skipped"][:10]:
            cached = " (cached)" if test["nodeid"] in cached_times else ""
            print(f"   - {test['nodeid']}: {test['duration']:.4f}s{cached}")
        if len(categories["skipped"]) > 10:
            print(f"   ... and {len(categories['skipped']) - 10} more")
        print()

    # Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Legitimate fast tests: {len(categories['legitimate'])} ✅")
    print(f"Import/module errors: {len(categories['import_errors'])} ⚠️")
    print(f"Other failures: {len(categories['other_failures'])} ❌")
    print(f"Skipped tests: {len(categories['skipped'])} ⏭️")
    print()

    # Recommendations
    if categories["import_errors"] or categories["other_failures"]:
        print("Recommendations:")
        if categories["import_errors"]:
            print("  1. Fix import/module errors in the failing tests")
            print("  2. Ensure all dependencies are installed: uv sync")
            print("  3. Check PYTHONPATH and module paths")
        if categories["other_failures"]:
            print("  4. Investigate other fast failures - they may indicate:")
            print("     - Missing test fixtures or setup")
            print("     - Incorrect test configuration")
            print("     - Environment-specific issues")
        print()

    # Cache note
    cached_count = sum(
        1
        for cat in categories.values()
        for test in cat
        if test["nodeid"] in cached_times
    )
    if cached_count > 0:
        print(f"Note: {cached_count} tests have cached execution times")
        print("      Clear cache with: rm -rf .pytest_cache")
        print()


def main():
    """Main entry point for investigating fast-failing tests.

    Parses command-line arguments and analyzes test execution times to identify
    tests that complete suspiciously quickly, which may indicate they're not
    actually running or are being skipped.
    """
    parser = argparse.ArgumentParser(
        description="Investigate tests that complete very quickly (<0.005s)"
    )
    parser.add_argument(
        "--unit", action="store_true", help="Investigate unit tests only"
    )
    parser.add_argument(
        "--integration", action="store_true", help="Investigate integration tests only"
    )
    parser.add_argument(
        "--notebooks", action="store_true", help="Investigate notebook tests only"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.005,
        help="Time threshold in seconds (default: 0.005)",
    )
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")

    args = parser.parse_args()

    # Determine test path
    if args.unit:
        test_path = "tests/unit"
    elif args.integration:
        test_path = "tests/integration"
    elif args.notebooks:
        test_path = "tests/test_notebooks.py"
    else:
        test_path = "tests"

    print(f"Investigating fast-failing tests in: {test_path}")
    print(f"Threshold: {args.threshold}s")
    print("Running tests...\n")

    # Run tests and collect results
    test_results, _ = run_pytest_with_detailed_output(test_path, parallel=args.parallel)

    # Check cache
    cached_times = check_pytest_cache()

    # Categorize fast tests
    categories = categorize_fast_tests(test_results, threshold=args.threshold)

    # Print report
    print_report(categories, cached_times, args.threshold)

    # Exit code based on findings
    if categories["import_errors"] or categories["other_failures"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
