#!/usr/bin/env python3
"""
Format test_results.json into human-readable text output.

This script processes test_results.json and converts it to a readable text format:
- Strips ANSI color codes
- Converts \\n to actual line breaks
- Can resume processing from where it left off (appends rather than overwrites)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Set up path first, then import from _setup
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import from shared setup module (re-exports from constants and utils)
# Type checker shows false positive - imports work at runtime due to sys.path setup above
from scripts.test._setup import strip_ansi_codes  # type: ignore  # noqa: E402


def convert_newlines(text: str) -> str:
    """Convert \\n escape sequences to actual newlines."""
    if not text:
        return ""
    return text.replace("\\n", "\n")


def format_text(text: str) -> str:
    """Strip ANSI codes and convert newlines."""
    return convert_newlines(strip_ansi_codes(text))


def format_result(result: dict[str, Any], index: int, total: int) -> str:
    """Format a single test result into readable text."""
    lines = []
    notebook = result.get("notebook", "unknown")
    passed = result.get("passed", False)
    returncode = result.get("returncode", -1)
    error_count = result.get("error_count", 0)

    # Header
    status_icon = "✅" if passed else "❌"
    status_text = "PASSED" if passed else "FAILED"
    lines.append(f"\n{'=' * 80}")
    lines.append(f"[{index}/{total}] {status_icon} {status_text}: {notebook}")
    lines.append(f"{'=' * 80}")
    lines.append(f"Return code: {returncode}")
    lines.append(f"Error count: {error_count}")

    # Summary
    summary = result.get("summary", {})
    if summary:
        lines.append("\nSummary:")
        lines.append(f"  Status: {summary.get('status', 'unknown')}")
        error_msg = summary.get("error_message")
        if error_msg:
            lines.append(f"  Error message: {format_text(error_msg)}")
        key_lines = summary.get("key_lines", [])
        if key_lines:
            lines.append("  Key lines:")
            for line in key_lines:
                lines.append(f"    {format_text(str(line))}")

    # Stdout
    stdout = result.get("stdout", "")
    if stdout:
        lines.append(f"\n{'─' * 80}")
        lines.append("STDOUT:")
        lines.append(f"{'─' * 80}")
        lines.append(format_text(stdout))

    # Stderr
    stderr = result.get("stderr", "")
    if stderr:
        lines.append(f"\n{'─' * 80}")
        lines.append("STDERR:")
        lines.append(f"{'─' * 80}")
        lines.append(format_text(stderr))

    return "\n".join(lines) + "\n"


def get_processed_info(output_file: Path) -> tuple[set[str], int]:
    """
    Extract notebook paths and highest index that have already been processed.

    Returns:
        Tuple of (set of processed notebook paths, highest processed index)
    """
    processed = set()
    highest_index = 0
    if not output_file.exists():
        return processed, highest_index

    try:
        with open(output_file, encoding="utf-8") as f:
            content = f.read()
            # Look for notebook paths and indices in the formatted output
            # Pattern: [index/total] ✅/❌ PASSED/FAILED: <notebook_path>
            pattern = r"\[(\d+)/\d+\]\s+[✅❌]\s+(?:PASSED|FAILED):\s+(.+?)(?:\n|$)"
            matches = re.findall(pattern, content)
            for index_str, notebook_path in matches:
                processed.add(notebook_path)
                index = int(index_str)
                if index > highest_index:
                    highest_index = index
    except Exception as e:
        print(f"Warning: Could not read existing output file: {e}", flush=True)

    return processed, highest_index


def format_test_results(
    json_file: Path, output_file: Path, resume: bool = True
) -> None:
    """Format test results from JSON to human-readable text."""
    if not json_file.exists():
        print(f"Error: JSON file not found: {json_file}", flush=True)
        return

    # Load JSON data
    print(f"Loading test results from: {json_file}", flush=True)
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    timestamp = data.get("timestamp", "unknown")
    total = data.get("total", 0)
    passed = data.get("passed", 0)
    failed = data.get("failed", 0)
    results = data.get("results", [])

    print(f"Found {len(results)} test results", flush=True)
    print(f"  Total: {total}, Passed: {passed}, Failed: {failed}", flush=True)

    # Determine which results to process
    start_index = 1
    if resume and output_file.exists():
        processed_notebooks, highest_index = get_processed_info(output_file)
        print(
            f"Found {len(processed_notebooks)} already processed notebooks", flush=True
        )
        print(f"Highest processed index: {highest_index}", flush=True)
        results_to_process = [
            r for r in results if r.get("notebook") not in processed_notebooks
        ]
        if results_to_process:
            # Start from the next index after the highest processed one
            start_index = highest_index + 1
            print(f"Processing {len(results_to_process)} remaining results", flush=True)
        else:
            print("All results already processed!", flush=True)
            return
    else:
        results_to_process = results
        # If not resuming, create new file
        if output_file.exists():
            output_file.unlink()

    # Format and write results
    mode = "a" if resume and output_file.exists() else "w"
    with open(output_file, mode, encoding="utf-8") as f:
        # Write header if starting new file
        if mode == "w":
            f.write(f"{'=' * 80}\n")
            f.write("TEST RESULTS SUMMARY\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"Generated from: {json_file}\n")
            f.write(f"Source timestamp: {timestamp}\n")
            f.write(f"Total tests: {total}\n")
            f.write(f"Passed: {passed}\n")
            f.write(f"Failed: {failed}\n")
            f.write(f"{'=' * 80}\n")

        # Write each result
        for i, result in enumerate(results_to_process, start=start_index):
            notebook = result.get("notebook", "unknown")
            print(f"Processing [{i}/{len(results)}]: {notebook}", flush=True)
            formatted = format_result(result, i, len(results))
            f.write(formatted)
            f.flush()  # Ensure data is written immediately

    print(f"\n✅ Formatted results written to: {output_file}", flush=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Format test_results.json into human-readable text"
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("tests/logs/test_results.json"),
        help="Path to test_results.json file (default: tests/logs/test_results.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/logs/test_results.txt"),
        help="Path to output text file (default: tests/logs/test_results.txt)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume from existing output (overwrite instead)",
    )

    args = parser.parse_args()

    format_test_results(args.json, args.output, resume=not args.no_resume)


if __name__ == "__main__":
    main()
