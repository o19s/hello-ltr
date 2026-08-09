#!/usr/bin/env python3
"""
Compare test performance before and after Docker resource limits.

Usage:
    python tests/compare_performance.py
"""

from __future__ import annotations

import json
from pathlib import Path


def load_report(filepath: Path) -> dict | None:
    """Load a performance report JSON file."""
    if not filepath.exists():
        return None
    with open(filepath) as f:
        return json.load(f)


def compare_reports(
    before: dict, after: dict, test_type: str = "notebook_tests"
) -> None:
    """Compare two performance reports and show differences."""
    before_data = before.get(test_type, {})
    after_data = after.get(test_type, {})

    before_total = before_data.get("total_time", 0)
    after_total = after_data.get("total_time", 0)
    before_count = before_data.get("count", 0)
    after_count = after_data.get("count", 0)

    print(f"\n{'=' * 80}")
    print(f"Performance Comparison: {test_type.replace('_', ' ').title()}")
    print(f"{'=' * 80}")
    print("\nBefore Resource Limits:")
    print(f"  Total tests: {before_count}")
    print(f"  Total time: {before_total:.2f} seconds ({before_total / 60:.2f} minutes)")
    if before_count > 0:
        print(f"  Average time: {before_total / before_count:.2f} seconds")

    print("\nAfter Resource Limits:")
    print(f"  Total tests: {after_count}")
    print(f"  Total time: {after_total:.2f} seconds ({after_total / 60:.2f} minutes)")
    if after_count > 0:
        print(f"  Average time: {after_total / after_count:.2f} seconds")

    if before_total > 0 and after_total > 0:
        change = ((after_total - before_total) / before_total) * 100
        change_abs = after_total - before_total
        print("\nChange:")
        print(f"  Absolute: {change_abs:+.2f} seconds ({change_abs / 60:+.2f} minutes)")
        print(f"  Percentage: {change:+.1f}%")

        if abs(change) > 10:
            if change > 0:
                print(f"  ⚠️  SIGNIFICANT SLOWDOWN: Tests are {abs(change):.1f}% slower")
            else:
                print(f"  ✅ SPEEDUP: Tests are {abs(change):.1f}% faster")
        else:
            print("  ✓ Minimal change (<10%)")

    # Compare individual test times
    before_times = before_data.get("test_times", {})
    after_times = after_data.get("test_times", {})

    if before_times and after_times:
        print(f"\n{'=' * 80}")
        print("Individual Test Comparisons (showing tests present in both):")
        print(f"{'=' * 80}")

        common_tests = set(before_times.keys()) & set(after_times.keys())
        if common_tests:
            changes = []
            for test_name in common_tests:
                before_time = before_times[test_name]
                after_time = after_times[test_name]
                if before_time > 0:
                    change_pct = ((after_time - before_time) / before_time) * 100
                    changes.append((test_name, before_time, after_time, change_pct))

            # Sort by absolute change
            changes.sort(key=lambda x: abs(x[3]), reverse=True)

            print("\nTop 10 tests with largest changes:")
            print(f"{'Test Name':<60} {'Before':>10} {'After':>10} {'Change':>10}")
            print("-" * 100)
            for test_name, before_t, after_t, change_pct in changes[:10]:
                test_short = (
                    test_name.split("[")[-1].replace("]", "")
                    if "[" in test_name
                    else test_name[-50:]
                )
                print(
                    f"{test_short:<60} {before_t:>10.2f}s {after_t:>10.2f}s {change_pct:>+9.1f}%"
                )
        else:
            print("\n⚠️  No common tests found - test sets may differ significantly")


def main():
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    perf_dir = project_root / "tests" / "performance"

    # Load reports
    before_notebooks = load_report(
        perf_dir / "performance_report_notebooks_complete.json"
    )
    after_notebooks = load_report(
        perf_dir / "performance_report_notebooks_with_limits_parallel.json"
    )

    before_integration = load_report(perf_dir / "performance_report_integration.json")
    after_integration = load_report(
        perf_dir / "performance_report_integration_with_limits.json"
    )

    print("=" * 80)
    print("Docker Resource Limits Impact Analysis")
    print("=" * 80)
    print("\nComparing test performance before and after adding Docker resource limits")
    print("in docker-compose.test.yml files.")

    if before_notebooks and after_notebooks:
        compare_reports(before_notebooks, after_notebooks, "notebook_tests")
    else:
        print("\n⚠️  Missing notebook test reports:")
        if not before_notebooks:
            print("  - Before: performance_report_notebooks_complete.json")
        if not after_notebooks:
            print("  - After: performance_report_notebooks_with_limits_parallel.json")

    if before_integration and after_integration:
        compare_reports(before_integration, after_integration, "integration_tests")
    else:
        print("\n⚠️  Missing integration test reports:")
        if not before_integration:
            print("  - Before: performance_report_integration.json")
        if not after_integration:
            print("  - After: performance_report_integration_with_limits.json")

    print(f"\n{'=' * 80}")
    print("Summary")
    print(f"{'=' * 80}")
    print("\nTo get accurate comparison, ensure:")
    print("1. Tests are run with --cache-clear to avoid cached results")
    print("2. Tests are run with same parallelization settings")
    print("3. System load is similar between runs")
    print("\nResource limits configured in:")
    print("  - notebooks/solr/docker-compose.test.yml")
    print("  - notebooks/elasticsearch/docker-compose.test.yml")
    print("  - notebooks/opensearch/docker-compose.test.yml")


if __name__ == "__main__":
    main()
