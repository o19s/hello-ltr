"""Shared utilities for notebook test scripts."""

import json  # noqa: I001
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from scripts.test.constants import DEFAULT_TIMEOUT, SLOW_PATTERNS  # pyright: ignore[reportMissingImports]


def get_test_name(
    notebook_path: str,
    notebook_type: Optional[str] = None,
    engine: Optional[str] = None,
) -> str:
    """Convert notebook path to pytest test name format.

    Args:
        notebook_path: Path to the notebook file (relative to repo root)
        notebook_type: Type of notebook ("test", "setup", etc.). Defaults to "test" if not provided.
        engine: Search engine type ("opensearch", "elasticsearch", "solr", "general").
                Auto-detected from path if not provided.

    Returns:
        Pytest test name in format: tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[path-type-engine]
    """
    # Auto-detect engine from path if not provided
    if engine is None:
        if "opensearch" in notebook_path:
            engine = "opensearch"
        elif "elasticsearch" in notebook_path:
            engine = "elasticsearch"
        elif "solr" in notebook_path:
            engine = "solr"
        else:
            engine = "general"

    # Default notebook type to "test" if not provided
    if notebook_type is None:
        notebook_type = "test"

    return f"tests/notebooks/test_notebooks.py::test_notebook_executes_without_errors[{notebook_path}-{notebook_type}-{engine}]"


def is_slow_notebook(notebook_path: str) -> bool:
    """Check if a notebook matches known slow patterns.

    Args:
        notebook_path: Path to the notebook file

    Returns:
        bool: True if notebook matches slow patterns
    """
    if not notebook_path:
        return False
    notebook_path_lower = notebook_path.lower()
    return any(pattern.lower() in notebook_path_lower for pattern in SLOW_PATTERNS)


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text.

    Args:
        text: Text that may contain ANSI escape codes

    Returns:
        Text with ANSI codes removed
    """
    if not text:
        return ""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def extract_error_count(output: str) -> int:
    """Extract error count from test output.

    Args:
        output: Combined stdout/stderr from test execution

    Returns:
        Total number of errors found
    """
    matches = re.findall(r"Errors in .*?: (\d+) error", output)
    if matches:
        return sum(int(m) for m in matches)
    return 0


def extract_summary(stdout: str, stderr: str) -> dict[str, Any]:
    """Extract a readable summary from test output.

    Args:
        stdout: Standard output from test execution
        stderr: Standard error from test execution

    Returns:
        Dictionary with status, error_message, and key_lines
    """
    summary: dict[str, Any] = {
        "status": "unknown",
        "error_message": None,
        "key_lines": [],
    }

    combined = (stdout or "") + (stderr or "")

    # Extract key error messages
    if "FAILED" in combined:
        summary["status"] = "failed"
        error_match = re.search(r"FAILED.*?\n(.*?)(?:\n\n|\n===)", combined, re.DOTALL)
        if error_match:
            error_line = error_match.group(1).strip()
            if len(error_line) < 200:
                summary["error_message"] = error_line
    elif "PASSED" in combined or "passed" in combined.lower():
        summary["status"] = "passed"

    # Extract key lines
    lines = combined.split("\n")
    non_empty = [line.strip() for line in lines if line.strip()][:5]
    if len(non_empty) > 0:
        summary["key_lines"] = non_empty[:3]

    return summary


def extract_errors(
    output: str, notebook_path: str, max_cell_source: int = 500
) -> list[dict[str, Any]]:
    """Extract detailed error information from test output.

    Args:
        output: Combined stdout/stderr from test execution
        notebook_path: Path to the notebook file (for context)
        max_cell_source: Maximum length for cell source in error details

    Returns:
        List of error dictionaries with cell_index, cell_source, error_type, error_message
    """
    errors: list[dict[str, Any]] = []

    # Pattern to match error sections from test output
    # Format: "Error N:\n  Cell X:\n    Cell source:\n      ...\n    ErrorType: message"
    error_pattern = (
        r"Error \d+:\s*\n\s*Cell (\d+):\s*\n\s*Cell source:\s*\n"
        r"((?:\s{4}.*\n?)*)\s*(\w+Error):\s*(.*?)"
        r"(?=\n\s*\w+Error:|\n\s*Traceback:|\n={60}|$)"
    )

    matches = re.finditer(error_pattern, output, re.MULTILINE | re.DOTALL)

    for match in matches:
        cell_index = int(match.group(1))
        cell_source_lines = match.group(2).strip().split("\n")
        cell_source = "\n".join(
            line.strip() for line in cell_source_lines if line.strip()
        )
        error_type = match.group(3)
        error_message = match.group(4).strip()

        # Clean up error message (remove extra whitespace)
        error_message = re.sub(r"\s+", " ", error_message)

        errors.append(
            {
                "cell_index": cell_index,
                "cell_source": cell_source[:max_cell_source],
                "error_type": error_type,
                "error_message": error_message[:500],  # Limit message length
            }
        )

    # Also try to extract from "Errors in" format
    if not errors:
        error_section_pattern = r"Errors in .*?: (\d+) error\(s\)(.*?)(?=\n={60}|\Z)"
        section_match = re.search(error_section_pattern, output, re.DOTALL)
        if section_match:
            error_text = section_match.group(2)
            cell_error_pattern = (
                r"Cell (\d+):\s*\n\s*Cell source:\s*\n"
                r"((?:\s{4}.*\n?)*)\s*(\w+Error):\s*(.*?)(?=\n\s*Cell \d+:|$)"
            )
            cell_matches = re.finditer(
                cell_error_pattern, error_text, re.MULTILINE | re.DOTALL
            )
            for cell_match in cell_matches:
                cell_index = int(cell_match.group(1))
                cell_source_lines = cell_match.group(2).strip().split("\n")
                cell_source = "\n".join(
                    line.strip() for line in cell_source_lines if line.strip()
                )
                error_type = cell_match.group(3)
                error_message = cell_match.group(4).strip()
                error_message = re.sub(r"\s+", " ", error_message)

                errors.append(
                    {
                        "cell_index": cell_index,
                        "cell_source": cell_source[:max_cell_source],
                        "error_type": error_type,
                        "error_message": error_message[:500],
                    }
                )

    # If still no errors, try to extract from traceback
    if not errors and "FAILED" in output:
        # Try to find the first error type mentioned
        error_type_match = re.search(r"(\w+Error):\s*(.*?)(?=\n|$)", output)
        if error_type_match:
            errors.append(
                {
                    "cell_index": 0,
                    "cell_source": "",
                    "error_type": error_type_match.group(1),
                    "error_message": error_type_match.group(2)[:500],
                }
            )

    return errors


def _run_with_streaming(
    cmd: list[str],
    notebook_path: str,
    timeout: int,
    env: dict[str, str],
    test_run_start: str,
    add_test_run_markers: bool,
) -> dict[str, Any]:
    """Run test with streaming output (both displayed and captured).

    Args:
        cmd: Command to run
        notebook_path: Path to notebook (for context)
        timeout: Timeout in seconds
        env: Environment variables
        test_run_start: Test run start marker
        add_test_run_markers: Whether to add markers

    Returns:
        Dictionary with test results
    """
    from typing import Union

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
            env=env,
        )

        # Stream output in real-time
        if process.stdout:
            for line in process.stdout:
                print(line, end="", flush=True)  # Print immediately
                output_lines.append(line)  # Also capture for later

        process.wait(timeout=timeout)

        output = "".join(output_lines)
        passed = process.returncode == 0
        error_count = extract_error_count(output)
        summary = extract_summary(output, "")

        # Strip ANSI codes for cleaner JSON logs
        formatted_stdout = strip_ansi_codes(output)
        formatted_stderr = ""

        # Determine result status
        result_status = "SUCCESS" if passed else "FAILURE"

        # Add TEST RUN messages before and after test output
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: {result_status}\n"
            formatted_stdout = (
                test_run_start + formatted_stdout + test_run_end + test_run_result
            )

        return {
            "notebook": notebook_path,
            "passed": passed,
            "returncode": process.returncode,
            "error_count": error_count,
            "summary": summary,
            "stdout": formatted_stdout,
            "stderr": formatted_stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
        timeout_msg = f"Test timed out after {timeout} seconds"
        print(f"\n⚠️  {timeout_msg}")
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: TIMEOUT\n"
            timeout_output = (
                test_run_start
                + "".join(output_lines)
                + timeout_msg
                + test_run_end
                + test_run_result
            )
        else:
            timeout_output = "".join(output_lines) + timeout_msg

        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "error_count": 0,
            "summary": {"status": "timeout", "error_message": timeout_msg},
            "stdout": timeout_output,
            "stderr": timeout_msg,
            "timeout": True,
        }
    except Exception as e:
        error_msg = str(e)
        print(f"\n⚠️  Error running test: {error_msg}")
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: ERROR\n"
            error_output = (
                test_run_start
                + "".join(output_lines)
                + error_msg
                + test_run_end
                + test_run_result
            )
        else:
            error_output = "".join(output_lines) + error_msg

        return {
            "notebook": notebook_path,
            "passed": False,
            "returncode": -1,
            "error_count": 0,
            "summary": {"status": "error", "error_message": error_msg},
            "stdout": error_output,
            "stderr": error_msg,
            "timeout": False,
        }


def run_notebook_test(
    notebook_path: str,
    timeout: int = DEFAULT_TIMEOUT,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = True,
    stream_output: bool = False,
    use_worker_containers: Optional[bool] = None,
    pytest_args: Optional[list[str]] = None,
    add_test_run_markers: bool = True,
) -> dict[str, Any]:
    """Run a single notebook test and return results.

    Args:
        notebook_path: Path to the notebook file (relative to repo root)
        timeout: Timeout in seconds (default: 300)
        env: Environment variables to set (default: None, uses os.environ.copy())
        capture_output: Whether to capture stdout/stderr (default: True)
        stream_output: Whether to stream output to terminal in real-time (default: False)
                      When True, output is both streamed and captured
        use_worker_containers: Whether to use worker containers (default: None, auto-detect)
        pytest_args: Additional pytest arguments (default: None, uses defaults)
        add_test_run_markers: Whether to add TEST RUN markers to output (default: True)

    Returns:
        Dictionary with notebook, passed, returncode, error_count, summary, stdout, stderr, timeout
    """
    test_name = get_test_name(notebook_path)

    # Build pytest command
    cmd = ["uv", "run", "pytest", test_name]
    if pytest_args:
        cmd.extend(pytest_args)
    else:
        cmd.extend(["-n", "1", "-v", "--no-cov", "--tb=short"])

    # Set up environment
    if env is None:
        env = os.environ.copy()

    # Handle USE_WORKER_CONTAINERS
    if use_worker_containers is not None:
        env["USE_WORKER_CONTAINERS"] = "true" if use_worker_containers else "false"
    elif "USE_WORKER_CONTAINERS" not in env:
        # Default behavior: use worker containers for isolated tests
        env["USE_WORKER_CONTAINERS"] = "true"

    # Add TEST RUN message before test
    test_run_start = f"TEST RUN: {notebook_path}\n" if add_test_run_markers else ""

    # If streaming output, use Popen to stream while capturing
    if stream_output:
        return _run_with_streaming(
            cmd, notebook_path, timeout, env, test_run_start, add_test_run_markers
        )

    # Otherwise use standard subprocess.run
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            env=env,
        )

        passed = result.returncode == 0
        output = (result.stdout or "") + (result.stderr or "")
        error_count = extract_error_count(output)
        summary = extract_summary(result.stdout or "", result.stderr or "")

        # Strip ANSI codes for cleaner JSON logs
        formatted_stdout = strip_ansi_codes(result.stdout) if result.stdout else ""
        formatted_stderr = strip_ansi_codes(result.stderr) if result.stderr else ""

        # Determine result status
        result_status = "SUCCESS" if passed else "FAILURE"

        # Add TEST RUN messages before and after test output
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: {result_status}\n"
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
            "timeout": False,
        }
    except subprocess.TimeoutExpired:
        timeout_msg = f"Test timed out after {timeout} seconds"
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: TIMEOUT\n"
            timeout_output = (
                test_run_start + timeout_msg + test_run_end + test_run_result
            )
        else:
            timeout_output = timeout_msg

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
            "timeout": True,
        }
    except Exception as e:
        error_msg = str(e)
        if add_test_run_markers:
            test_run_end = f"\nTEST RUN: {notebook_path}\n"
            test_run_result = f"TEST RUN: {notebook_path}: FAILURE\n"
            error_output = test_run_start + error_msg + test_run_end + test_run_result
        else:
            error_output = error_msg

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
            "timeout": False,
        }


def print_test_summary(
    results: list[dict[str, Any]],
    passed_tests: list[str],
    failed_tests: list[str],
    timeout_tests: Optional[list[str]] = None,
) -> None:
    """Print a formatted test summary.

    Args:
        results: List of test result dictionaries
        passed_tests: List of notebook paths that passed
        failed_tests: List of notebook paths that failed
        timeout_tests: Optional list of notebook paths that timed out
    """
    timeout_tests = timeout_tests or []
    total = len(results)

    print(f"\n{'=' * 80}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'=' * 80}", flush=True)
    print(f"Total tests run: {total}", flush=True)
    print(f"✅ Passed: {len(passed_tests)}", flush=True)
    print(f"❌ Failed: {len(failed_tests)}", flush=True)
    if timeout_tests:
        print(f"⏱️  Timeout: {len(timeout_tests)}", flush=True)

    if passed_tests:
        print("\n✅ Passing:", flush=True)
        for test in passed_tests:
            print(f"  - {test}", flush=True)

    if failed_tests:
        print("\n❌ Failing:", flush=True)
        for test in failed_tests:
            result = next((r for r in results if r["notebook"] == test), None)
            if result:
                error_count = result.get("error_count", 0)
                print(f"  - {test} ({error_count} errors)", flush=True)
            else:
                print(f"  - {test}", flush=True)

    if timeout_tests:
        print("\n⏱️  Timeout (stopped after timeout):", flush=True)
        for test in timeout_tests:
            print(f"  - {test}", flush=True)


def save_test_results(
    results: list[dict[str, Any]],
    filename: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Path:
    """Save test results to JSON file.

    Args:
        results: List of test result dictionaries
        passed_tests: List of notebook paths that passed
        failed_tests: List of notebook paths that failed
        filename: Output filename (will be saved in tests/logs/)
        metadata: Optional metadata dictionary to include in output

    Returns:
        Path to the saved file
    """
    logs_dir = Path("tests/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    output_file = logs_dir / filename

    # Count passed/failed/timeout
    passed = sum(1 for r in results if r.get("passed", False))
    failed = sum(
        1 for r in results if not r.get("passed", False) and not r.get("timeout", False)
    )
    timeout = sum(1 for r in results if r.get("timeout", False))

    output_data: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "timeout": timeout,
    }

    if metadata:
        output_data.update(metadata)

    output_data["results"] = results

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return output_file
