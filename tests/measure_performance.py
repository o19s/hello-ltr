#!/usr/bin/env python3
"""
Test Performance Measurement Script

Measures and reports execution times for unit and integration tests.
Generates performance reports and identifies slow tests.
Optionally monitors Docker container resource usage during test execution.

Usage:
    python tests/measure_performance.py                    # Measure all tests
    python tests/measure_performance.py --unit              # Unit tests only
    python tests/measure_performance.py --integration       # Integration tests only
    python tests/measure_performance.py --notebooks        # Notebook tests only
    python tests/measure_performance.py --profile           # Profile slow tests
    python tests/measure_performance.py --parallel          # Run with parallel execution
    python tests/measure_performance.py --docker-monitor    # Monitor Docker resources
"""

import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def run_pytest_with_timing(
    test_path: str, parallel: bool = False
) -> tuple[dict[str, float], float]:
    """
    Run pytest and collect execution times using JUnit XML report.

    Args:
        test_path: Path to test directory or file (relative to project root)
        parallel: Whether to run tests in parallel

    Returns:
        Tuple of (test_times dict, total_time)
    """
    import tempfile

    # Create temporary file for JUnit XML report
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        xml_report_path = f.name

    # Use 'uv run pytest' to ensure proper environment setup (like test.sh does)
    # This ensures pytest runs with the correct Python environment and can resolve imports
    project_root = Path(__file__).parent.parent

    # Check if uv is available, otherwise fall back to python -m pytest
    import shutil

    uv_cmd = shutil.which("uv")

    if uv_cmd:
        cmd = [
            uv_cmd,
            "run",
            "pytest",
            test_path,
            "-v",
            "--tb=no",  # No traceback for cleaner output
            f"--junitxml={xml_report_path}",
        ]
    else:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "-v",
            "--tb=no",  # No traceback for cleaner output
            f"--junitxml={xml_report_path}",
        ]

    # Add environment variables for integration/notebook tests
    env = os.environ.copy()
    # Add project root to PYTHONPATH to ensure imports work
    pythonpath = str(project_root)
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{pythonpath}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = pythonpath

    if "integration" in test_path:
        env["SKIP_DOCKER_CHECK"] = "true"
        env["SKIP_PORT_CHECK"] = "true"

    if parallel:
        cmd.extend(["-n", "auto"])

    start_time = time.time()
    subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        check=False,
        env=env,
    )
    total_time = time.time() - start_time

    # Parse JUnit XML report
    test_times = {}
    try:
        if Path(xml_report_path).exists():
            tree = ET.parse(xml_report_path)
            root = tree.getroot()

            # Extract test durations from XML
            for testcase in root.findall(".//testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_attr = testcase.get("time", "0")

                # Construct nodeid: classname::name or just name
                nodeid = f"{classname}::{name}" if classname else name

                try:
                    duration = float(time_attr)
                    if duration > 0:
                        test_times[nodeid] = duration
                except ValueError:
                    pass

            # Clean up temp file
            Path(xml_report_path).unlink(missing_ok=True)
    except (ET.ParseError, FileNotFoundError):
        # Fallback: use pytest cache if available
        cache_dir = Path(__file__).parent.parent / ".pytest_cache" / "v" / "cache"
        cache_file = cache_dir / "test_execution_times"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cache_data = json.load(f)
                    if isinstance(cache_data, dict):
                        test_times = cache_data
            except (json.JSONDecodeError, FileNotFoundError):
                pass

    return test_times, total_time


def get_slow_tests(
    test_times: dict[str, float], threshold: float = 1.0
) -> list[tuple[str, float]]:
    """
    Identify slow tests above threshold.

    Args:
        test_times: Dictionary mapping test names to execution times
        threshold: Minimum time in seconds to be considered slow

    Returns:
        List of (test_name, duration) tuples sorted by duration (slowest first)
    """
    slow = [
        (name, duration)
        for name, duration in test_times.items()
        if duration >= threshold
    ]
    return sorted(slow, key=lambda x: x[1], reverse=True)


def generate_report(
    unit_times: dict[str, float],
    integration_times: dict[str, float],
    notebook_times: dict[str, float],
    unit_total: float,
    integration_total: float,
    notebook_total: float,
    output_file: str = None,
) -> str:
    """
    Generate a formatted performance report.

    Args:
        unit_times: Unit test execution times
        integration_times: Integration test execution times
        unit_total: Total time for unit tests
        integration_total: Total time for integration tests
        output_file: Optional file path to save JSON report

    Returns:
        Formatted report string
    """
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("Test Performance Report")
    report_lines.append("=" * 80)
    report_lines.append("")

    # Unit tests summary
    report_lines.append("Unit Tests")
    report_lines.append("-" * 80)
    report_lines.append(f"Total tests: {len(unit_times)}")
    report_lines.append(
        f"Total execution time: {unit_total:.2f} seconds ({unit_total/60:.2f} minutes)"
    )
    if unit_times:
        avg_time = sum(unit_times.values()) / len(unit_times)
        max_time = max(unit_times.values())
        min_time = min(unit_times.values())
        report_lines.append(f"Average test time: {avg_time:.3f} seconds")
        report_lines.append(f"Fastest test: {min_time:.3f} seconds")
        report_lines.append(f"Slowest test: {max_time:.3f} seconds")
    report_lines.append("")

    # Integration tests summary
    report_lines.append("Integration Tests")
    report_lines.append("-" * 80)
    report_lines.append(f"Total tests: {len(integration_times)}")
    report_lines.append(
        f"Total execution time: {integration_total:.2f} seconds ({integration_total/60:.2f} minutes)"
    )
    if integration_times:
        avg_time = sum(integration_times.values()) / len(integration_times)
        max_time = max(integration_times.values())
        min_time = min(integration_times.values())
        report_lines.append(f"Average test time: {avg_time:.3f} seconds")
        report_lines.append(f"Fastest test: {min_time:.3f} seconds")
        report_lines.append(f"Slowest test: {max_time:.3f} seconds")
    report_lines.append("")

    # Notebook tests summary
    report_lines.append("Notebook Tests")
    report_lines.append("-" * 80)
    report_lines.append(f"Total tests: {len(notebook_times)}")
    report_lines.append(
        f"Total execution time: {notebook_total:.2f} seconds ({notebook_total/60:.2f} minutes)"
    )
    if notebook_times:
        avg_time = sum(notebook_times.values()) / len(notebook_times)
        max_time = max(notebook_times.values())
        min_time = min(notebook_times.values())
        report_lines.append(
            f"Average test time: {avg_time:.3f} seconds ({avg_time/60:.2f} minutes)"
        )
        report_lines.append(
            f"Fastest test: {min_time:.3f} seconds ({min_time/60:.2f} minutes)"
        )
        report_lines.append(
            f"Slowest test: {max_time:.3f} seconds ({max_time/60:.2f} minutes)"
        )
    report_lines.append("")

    # Slow tests
    slow_unit = get_slow_tests(unit_times, threshold=0.5)
    slow_integration = get_slow_tests(integration_times, threshold=1.0)
    slow_notebooks = get_slow_tests(notebook_times, threshold=60.0)  # >1 minute

    if slow_unit:
        report_lines.append("Slow Unit Tests (>0.5s)")
        report_lines.append("-" * 80)
        for test_name, duration in slow_unit[:10]:  # Top 10
            report_lines.append(f"  {duration:6.3f}s  {test_name}")
        report_lines.append("")

    if slow_integration:
        report_lines.append("Slow Integration Tests (>1.0s)")
        report_lines.append("-" * 80)
        for test_name, duration in slow_integration[:10]:  # Top 10
            report_lines.append(f"  {duration:6.3f}s  {test_name}")
        report_lines.append("")

    if slow_notebooks:
        report_lines.append("Slow Notebook Tests (>1 minute)")
        report_lines.append("-" * 80)
        for test_name, duration in slow_notebooks[:20]:  # Top 20
            minutes = duration / 60
            report_lines.append(f"  {minutes:6.2f}m  {test_name}")
        report_lines.append("")

    # Overall summary
    report_lines.append("Overall Summary")
    report_lines.append("-" * 80)
    total_tests = len(unit_times) + len(integration_times) + len(notebook_times)
    total_time = unit_total + integration_total + notebook_total
    report_lines.append(f"Total tests: {total_tests}")
    report_lines.append(
        f"Total execution time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)"
    )
    report_lines.append("=" * 80)

    report = "\n".join(report_lines)

    # Save JSON report if requested
    if output_file:
        # Get slow tests for JSON report
        slow_unit_json = get_slow_tests(unit_times, threshold=0.5)
        slow_integration_json = get_slow_tests(integration_times, threshold=1.0)
        slow_notebooks_json = get_slow_tests(notebook_times, threshold=60.0)

        json_data = {
            "unit_tests": {
                "count": len(unit_times),
                "total_time": unit_total,
                "test_times": unit_times,
                "slow_tests": slow_unit_json,
            },
            "integration_tests": {
                "count": len(integration_times),
                "total_time": integration_total,
                "test_times": integration_times,
                "slow_tests": slow_integration_json,
            },
            "notebook_tests": {
                "count": len(notebook_times),
                "total_time": notebook_total,
                "test_times": notebook_times,
                "slow_tests": slow_notebooks_json,
            },
            "summary": {"total_tests": total_tests, "total_time": total_time},
        }
        with open(output_file, "w") as f:
            json.dump(json_data, f, indent=2)
        report_lines.append(f"\nJSON report saved to: {output_file}")

    return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Measure test execution performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--unit", action="store_true", help="Measure unit tests only")
    parser.add_argument(
        "--integration", action="store_true", help="Measure integration tests only"
    )
    parser.add_argument(
        "--notebooks", action="store_true", help="Measure notebook tests only"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Profile slow tests (requires pytest-profiling plugin)",
    )
    parser.add_argument(
        "--parallel", action="store_true", help="Run tests in parallel (pytest-xdist)"
    )
    parser.add_argument("--output", type=str, help="Output file for JSON report")

    args = parser.parse_args()

    # Determine which tests to run
    # If specific flags are set, only run those; otherwise run all except notebooks (they're slow and require containers)
    run_unit = args.unit or (not args.integration and not args.notebooks)
    run_integration = args.integration or (not args.unit and not args.notebooks)
    run_notebooks = args.notebooks

    if run_notebooks:
        print(
            "WARNING: Notebook tests require Docker containers and may take 5-20 minutes."
        )
        print(
            "         They must be run from the project root with proper pytest discovery."
        )
        print("         Consider using: ./tests/test.sh or running from project root.")
        print("")

    unit_times = {}
    integration_times = {}
    notebook_times = {}
    unit_total = 0.0
    integration_total = 0.0
    notebook_total = 0.0

    # Measure unit tests
    if run_unit:
        print("Measuring unit tests...")
        unit_times, unit_total = run_pytest_with_timing(
            "tests/unit", parallel=args.parallel
        )
        print(f"Unit tests completed in {unit_total:.2f} seconds")

    # Measure integration tests
    if run_integration:
        print("Measuring integration tests...")
        integration_times, integration_total = run_pytest_with_timing(
            "tests/integration", parallel=args.parallel
        )
        print(f"Integration tests completed in {integration_total:.2f} seconds")

    # Measure notebook tests
    if run_notebooks:
        print("Measuring notebook tests (this may take 5-20 minutes)...")
        print(
            "Note: Notebook tests require Docker containers and proper pytest discovery."
        )
        # Notebook tests must be run from project root with proper imports
        notebook_times, notebook_total = run_pytest_with_timing(
            "tests/notebooks/test_notebooks.py", parallel=args.parallel
        )
        print(
            f"Notebook tests completed in {notebook_total:.2f} seconds ({notebook_total/60:.2f} minutes)"
        )

    # Generate and print report
    report = generate_report(
        unit_times,
        integration_times,
        notebook_times,
        unit_total,
        integration_total,
        notebook_total,
        output_file=args.output,
    )
    print("\n" + report)

    # Profile slow tests if requested
    if args.profile:
        print("\nProfiling slow tests...")
        slow_unit = get_slow_tests(unit_times, threshold=0.5)
        slow_integration = get_slow_tests(integration_times, threshold=1.0)

        if slow_unit or slow_integration:
            print("Note: Install pytest-profiling for detailed profiling:")
            print("  uv pip install pytest-profiling")
            print("Then run: pytest --profile tests/unit tests/integration")


if __name__ == "__main__":
    main()
