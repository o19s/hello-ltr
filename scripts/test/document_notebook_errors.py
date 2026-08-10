#!/usr/bin/env python3
"""
Script to run failing notebook tests one by one and extract exact error details
for documentation in CODEBASE_REVIEW.md.
"""

import json
import sys
from pathlib import Path

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import (  # type: ignore  # noqa: E402
    FAILING_NOTEBOOKS_BY_ENGINE_MINIMAL,
    extract_errors,
    run_notebook_test,
)

# List of failing notebooks from CODEBASE_REVIEW.md
FAILING_NOTEBOOKS = FAILING_NOTEBOOKS_BY_ENGINE_MINIMAL


def run_test(notebook_path: str) -> dict:
    """Run a single notebook test and return detailed error information."""
    print(f"\n{'=' * 80}")
    print(f"Running: {notebook_path}")
    print(f"{'=' * 80}")
    sys.stdout.flush()

    # Run test with custom settings for error documentation
    # stream_output=True shows real-time progress while still capturing output
    result = run_notebook_test(
        notebook_path,
        timeout=300,  # 5 minute timeout (reduced from 10)
        use_worker_containers=False,  # Disable per-worker containers for sequential runs
        pytest_args=["-v", "--no-cov", "--tb=short", "-s", "-n", "0"],
        add_test_run_markers=False,
        stream_output=True,  # Stream output to terminal in real-time
    )

    # Extract errors from output
    output = result.get("stdout", "") + result.get("stderr", "")
    errors = extract_errors(output, notebook_path, max_cell_source=300)

    # Convert to format expected by this script
    return {
        "notebook": notebook_path,
        "passed": result.get("passed", False),
        "returncode": result.get("returncode", -1),
        "errors": errors,
        "error_count": len(errors),
        "output": output,
        "timeout": result.get("timeout", False),
    }


def format_errors_for_markdown(errors: list[dict]) -> str:
    """Format errors for markdown documentation."""
    if not errors:
        return "No errors extracted from test output."

    lines = []
    for i, error in enumerate(errors, 1):
        lines.append(
            f"  {i}. **Cell {error['cell_index']}** - `{error['error_type']}`:"
        )
        # Truncate long messages
        msg = error["error_message"]
        if len(msg) > 200:
            msg = msg[:200] + "..."
        lines.append(f"     - {msg}")

    return "\n".join(lines)


def group_errors_by_type(all_results: list[dict]) -> dict[str, list[str]]:
    """Group notebooks by error types they share."""
    error_type_to_notebooks: dict[str, list[str]] = {}

    for result in all_results:
        if result.get("timeout"):
            error_type = "TIMEOUT"
            if error_type not in error_type_to_notebooks:
                error_type_to_notebooks[error_type] = []
            error_type_to_notebooks[error_type].append(result["notebook"])
        elif not result.get("errors"):
            error_type = "NO_ERRORS_EXTRACTED"
            if error_type not in error_type_to_notebooks:
                error_type_to_notebooks[error_type] = []
            error_type_to_notebooks[error_type].append(result["notebook"])
        else:
            # Get unique error types for this notebook
            error_types = {e["error_type"] for e in result["errors"]}
            for et in error_types:
                if et not in error_type_to_notebooks:
                    error_type_to_notebooks[et] = []
                error_type_to_notebooks[et].append(result["notebook"])

    return error_type_to_notebooks


def display_error_details(result: dict):
    """Display detailed error information and stop execution."""
    notebook_path = result["notebook"]

    print("\n" + "=" * 80)
    print("❌ ERROR DETECTED - STOPPING FOR FIX")
    print("=" * 80)
    print(f"\nNotebook: {notebook_path}")

    if result.get("timeout"):
        print("\n⏱️  TIMEOUT: Test timed out after 5 minutes")
        print("\nThis notebook took too long to execute.")
        return

    if result["passed"]:
        print("\n✅ PASSED (unexpected - was in failing list)")
        return

    print(f"\n❌ FAILED with {result['error_count']} error(s)\n")

    if result["errors"]:
        print("DETAILED ERROR INFORMATION:")
        print("-" * 80)
        for i, error in enumerate(result["errors"], 1):
            print(f"\nError {i}:")
            print(f"  Cell Index: {error['cell_index']}")
            print(f"  Error Type: {error['error_type']}")
            print(f"  Error Message: {error['error_message']}")
            if error.get("cell_source"):
                print("  Cell Source (first 300 chars):")
                print(f"    {error['cell_source'][:300]}")
    else:
        print("⚠️  No errors extracted from test output.")
        print("\nFull output saved. Check test output for details.")

    print("\n" + "=" * 80)
    print("STOPPED: Fix the error above before continuing")
    print("=" * 80)


def main():
    """Run failing notebooks one by one, stopping on first error."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run failing notebook tests one by one, stopping on first error"
    )
    parser.add_argument(
        "--notebook",
        type=str,
        help="Run a specific notebook (path relative to repo root)",
    )
    parser.add_argument(
        "--continue",
        action="store_true",
        dest="continue_mode",
        help="Continue from where we left off (skip already processed notebooks)",
    )
    args = parser.parse_args()

    # Collect all failing notebooks
    all_notebooks = []
    for engine, notebooks in FAILING_NOTEBOOKS.items():
        for notebook in notebooks:
            all_notebooks.append((notebook, engine))

    # If specific notebook requested, run only that one
    if args.notebook:
        matching = [(nb, eng) for nb, eng in all_notebooks if args.notebook in nb]
        if not matching:
            print(f"Error: Notebook '{args.notebook}' not found in failing list")
            return 1
        all_notebooks = matching

    print(f"Found {len(all_notebooks)} notebook(s) to test")
    print("Running one at a time - will stop on first error\n")

    # Run each notebook
    for i, (notebook_path, _engine) in enumerate(all_notebooks, 1):
        print(f"\n[{i}/{len(all_notebooks)}] Testing {notebook_path}")
        sys.stdout.flush()

        result = run_test(notebook_path)

        if result.get("timeout"):
            display_error_details(result)
            return 1
        elif result["passed"]:
            print("  ✅ PASSED (unexpected - was in failing list)")
            continue
        else:
            # Found errors - stop and display details
            display_error_details(result)

            # Save current result for documentation
            logs_dir = Path("tests/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            result_file = (
                logs_dir
                / f"current_error_{notebook_path.replace('/', '_').replace(' ', '_')}.json"
            )
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"\nError details saved to: {result_file}")

            return 1  # Exit with error code to stop execution

    # If we get here, all notebooks passed (unlikely)
    print("\n✅ All notebooks passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
