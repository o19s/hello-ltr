#!/usr/bin/env python3
"""
Script to run a batch of failing notebook tests and collect results.
Usage: python run_test_batch.py <start_index> <end_index>
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# List of failing tests from CODEBASE_REVIEW.md section 5.3
FAILING_TESTS = [
    # OpenSearch Notebooks (13 failures)
    "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/Dataframes.ipynb",
    "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
    "./notebooks/opensearch/tmdb/raw-opensearch-commands.ipynb",
    "./notebooks/opensearch/tmdb/sandbox.ipynb",
    "./notebooks/opensearch/tmdb/tale-of-two-queries (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/opensearch/tmdb/gonna need a bigger bot (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies.ipynb",
    "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
    "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
    # Elasticsearch Notebooks (10 failures)
    "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
    "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # Solr Notebooks (4 failures)
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
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

    print(f"\n{'=' * 80}")
    print(f"Running: {notebook_path}")
    print(f"{'=' * 80}")

    cmd = ["uv", "run", "pytest", test_name, "-n", "1", "-v", "--no-cov", "--tb=short"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout per test
        )

        passed = result.returncode == 0

        return {
            "notebook": notebook_path,
            "passed": passed,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error_count": extract_error_count(result.stdout + result.stderr),
        }
    except subprocess.TimeoutExpired:
        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Test timed out after 10 minutes",
            "error_count": 0,
        }
    except Exception as e:
        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "error_count": 0,
        }


def extract_error_count(output):
    """Extract error count from test output."""
    # Look for "Errors in" pattern
    import re

    matches = re.findall(r"Errors in .*?: (\d+) error", output)
    if matches:
        return sum(int(m) for m in matches)
    return 0


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
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    output_file = logs_dir / f"test_results_batch_{start_idx}_{end_idx}.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "batch": f"{start_idx}-{end_idx}",
                "total": len(batch_tests),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "results": results,
            },
            f,
            indent=2,
        )

    # Print summary
    print(f"\n{'=' * 80}")
    print(f"BATCH SUMMARY ({start_idx}-{end_idx})")
    print(f"{'=' * 80}")
    print(f"Total tests run: {len(batch_tests)}")
    print(f"✅ Passed: {len(passed_tests)}")
    print(f"❌ Failed: {len(failed_tests)}")
    print(f"\nResults saved to: {output_file}")

    if passed_tests:
        print("\n✅ Now passing:")
        for test in passed_tests:
            print(f"  - {test}")

    if failed_tests:
        print("\n❌ Still failing:")
        for test in failed_tests:
            result = next(r for r in results if r["notebook"] == test)
            print(f"  - {test} ({result['error_count']} errors)")

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
