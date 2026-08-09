"""
Notebook test runner for executing Jupyter notebooks in tests.

This module provides functionality to execute Jupyter notebooks programmatically,
capture errors, and inject port patching code to redirect connections to test ports.

Features:
    - Real-time output streaming (errors visible immediately)
    - Fail-fast mode (stop on first error)
    - Progress indicators with time estimates
    - Cell-by-cell execution logging
    - Automatic parameter reduction for faster testing
    - Cell dependency validation (checks prerequisites and validates critical operations)

Adapted from: https://www.blog.pythonlibrary.org/2018/10/16/testing-jupyter-notebooks/

Environment Variables:
    NOTEBOOK_TIMEOUT_MINUTES: Minutes to allow per notebook execution (default: 5)
    NOTEBOOK_FAIL_FAST: Enable fail-fast mode - stop on first error (default: false)
    NOTEBOOK_VALIDATION_FAIL_FAST: Enable fail-fast for validation errors (default: true)
    NOTEBOOK_DEBUG_MODE: Enable debug mode - show variable states on error (default: false)

Key Functions:
    run_notebook: Execute a notebook and return results with error details
    PatchedExecutePreprocessor: Custom preprocessor with progress logging and error detection
    NotebookDependencyValidator: Validates cell dependencies and critical operations

Framework Evaluation Note:
    We evaluated pytest-notebook, nbmake, and papermill but chose to enhance our
    custom solution because:
    1. We need custom port patching and parameter reduction for testing
    2. Our solution provides better control over execution flow
    3. Real-time streaming and fail-fast are now implemented
    4. No additional dependencies required
"""

import os
import re
from contextlib import suppress
from typing import Any, Optional

import nbformat
from nbconvert.preprocessors import CellExecutionError, ExecutePreprocessor


def hours(hours):
    """Convert hours to seconds.

    Args:
        hours: Number of hours

    Returns:
        int: Number of seconds
    """
    return hours * 60 * 60


def safe_kcv_folds(requested_folds: int, max_queries: int) -> Optional[int]:
    """Clamp cross-validation folds to a value RankLib can actually train on.

    RankLib cannot build k folds from fewer than k queries, and it fails in the
    worst possible way rather than raising: the empty fold makes
    LambdaMART.sortSamplesByFeature throw ArrayIndexOutOfBoundsException inside a
    thread-pool worker, and because that pool is never shut down the JVM hangs
    instead of exiting. The notebook then sits until an outer timeout kills it,
    with nothing useful in the output.

    Because the test harness shrinks the training set to NOTEBOOK_MAX_QUERIES
    queries, the fold count has to be clamped against that, not just against the
    value the notebook asked for. A fold count of 1 is always invalid.

    Verified directly against RankLib using the training set the harness
    produces: -kcv 1 hangs until killed, -kcv 2 finishes in about a second.

    Args:
        requested_folds: Fold count requested via NOTEBOOK_MAX_KCV_FOLDS
        max_queries: Queries the harness keeps in the training set

    Returns:
        int: A fold count between 2 and max_queries, or None if the training set
        is too small for any valid split, meaning the caller should drop kcv and
        train without cross-validation.
    """
    if max_queries < 2:
        return None
    return max(2, min(requested_folds, max_queries))


def inspect_notebook_variables(kernel_manager) -> dict[str, Any]:
    """Inspect common notebook variables to help with debugging.

    Executes code in the kernel to inspect common objects like:
    - ftr_logger.logged (feature logger data)
    - training_set (training data)
    - lambdas_per_query (query-specific lambdas)
    - Other common variables used in LTR notebooks

    Args:
        kernel_manager: Kernel manager instance from ExecutePreprocessor

    Returns:
        Dictionary mapping variable names to their inspected values (or error messages)
    """
    if not kernel_manager:
        return {"error": "No kernel manager available"}

    import json
    import time

    # Code to execute in kernel to inspect variables
    # We'll capture the result by storing it in a special variable
    inspect_code = """
import json

def _safe_repr(obj, max_len=200):
    \"\"\"Safely represent an object, truncating if too long.\"\"\"
    try:
        if hasattr(obj, '__len__') and len(obj) > 10:
            first_item = obj[0] if len(obj) > 0 else None
            first_repr = _safe_repr(first_item, max_len=50) if first_item is not None else "None"
            return f"{type(obj).__name__}(len={len(obj)}, first_item={first_repr})"
        elif hasattr(obj, 'shape'):  # numpy/pandas objects
            return f"{type(obj).__name__}(shape={obj.shape})"
        else:
            repr_str = repr(obj)
            if len(repr_str) > max_len:
                return repr_str[:max_len] + "..."
            return repr_str
    except Exception as e:
        return f"<Error getting repr: {e}>"

def _inspect_var(name):
    \"\"\"Inspect a variable if it exists.\"\"\"
    try:
        if name in globals():
            value = globals()[name]
            return {
                "exists": True,
                "type": type(value).__name__,
                "repr": _safe_repr(value),
                "len": len(value) if hasattr(value, '__len__') else None,
            }
        else:
            return {"exists": False}
    except Exception as e:
        return {"exists": True, "error": str(e)}

# Inspect common variables
result = {}
for var_name in ['ftr_logger', 'training_set', 'lambdas_per_query', 'lambdas_per_query_prec',
                 'features', 'predictors', 'client', 'judgments', 'judgments_open']:
    result[var_name] = _inspect_var(var_name)

# Special handling for ftr_logger.logged if ftr_logger exists
if 'ftr_logger' in globals():
    try:
        ftr_logger = globals()['ftr_logger']
        if hasattr(ftr_logger, 'logged'):
            logged = ftr_logger.logged
            result['ftr_logger.logged'] = {
                "exists": True,
                "type": type(logged).__name__,
                "len": len(logged) if hasattr(logged, '__len__') else None,
                "repr": _safe_repr(logged),
            }
        else:
            result['ftr_logger.logged'] = {"exists": False, "reason": "ftr_logger has no 'logged' attribute"}
    except Exception as e:
        result['ftr_logger.logged'] = {"exists": True, "error": str(e)}

# Store result in a special variable for retrieval
__notebook_debug_result__ = json.dumps(result)
"""

    try:
        # Execute the inspection code in the kernel using kernel manager's client
        if hasattr(kernel_manager, "client") and kernel_manager.client:
            # Execute code and wait for result
            msg_id = kernel_manager.client.execute(inspect_code)

            # Wait for execution to complete (with timeout)
            timeout = 5.0
            start_time = time.time()
            result_received = False
            result_data = None

            while time.time() - start_time < timeout:
                try:
                    msg = kernel_manager.client.get_iopub_msg(timeout=0.5)
                    if msg.get("parent_header", {}).get("msg_id") == msg_id:
                        if msg["msg_type"] == "execute_result":
                            # Extract the result from text/plain output
                            result_str = msg["content"]["data"].get("text/plain", "")
                            # Remove quotes and unescape if needed
                            if result_str.startswith('"') and result_str.endswith('"'):
                                result_str = result_str[1:-1]
                            if result_str.startswith("'") and result_str.endswith("'"):
                                result_str = result_str[1:-1]
                            # Try to parse JSON
                            try:
                                result_data = json.loads(result_str)
                                result_received = True
                                break
                            except json.JSONDecodeError:
                                # Try to get from execute_reply instead
                                pass
                        elif msg["msg_type"] == "error":
                            return {
                                "error": f"Failed to inspect variables: {msg['content'].get('ename', 'Unknown')}: {msg['content'].get('evalue', 'No message')}"
                            }
                except Exception:
                    # Timeout or other error, continue waiting
                    pass

            # Try to get result from kernel namespace directly
            if not result_received:
                # Execute a simple command to get the result variable
                get_result_code = "__notebook_debug_result__"
                msg_id2 = kernel_manager.client.execute(get_result_code)
                time.sleep(0.5)  # Brief wait
                try:
                    msg = kernel_manager.client.get_iopub_msg(timeout=1.0)
                    parent_msg_id = msg.get("parent_header", {}).get("msg_id")
                    if parent_msg_id == msg_id2 and msg["msg_type"] == "execute_result":
                        result_str = msg["content"]["data"].get("text/plain", "")
                        if result_str.startswith('"') and result_str.endswith('"'):
                            result_str = result_str[1:-1]
                        if result_str.startswith("'") and result_str.endswith("'"):
                            result_str = result_str[1:-1]
                        result_data = json.loads(result_str)
                        result_received = True
                except Exception:
                    pass

            if result_received and result_data:
                return result_data
            else:
                return {"error": "Could not retrieve variable inspection results"}
        else:
            return {"error": "Kernel manager doesn't have a client available"}
    except Exception as e:
        return {"error": f"Exception while inspecting variables: {e}"}


class NotebookDependencyValidator:
    """Validates cell dependencies and critical operations in notebooks.

    Tracks critical operations (create_index, create_featureset, rebuild, etc.)
    and validates that they succeeded before dependent cells execute.

    Attributes:
        completed_operations: Dictionary tracking completed operations by type
        client_instance: Optional client instance for validation checks
    """

    def __init__(self, notebook_path: Optional[str] = None):
        """Initialize dependency validator with empty operation tracking.

        Args:
            notebook_path: Optional path to notebook for client type detection
        """
        self.completed_operations: dict[str, set[str]] = {
            "indices": set(),  # Set of index names that exist
            "feature_sets": set(),  # Set of (index, feature_set) tuples as strings
            "models": set(),  # Set of (index, model) tuples as strings
        }
        self.client_instance = None
        self.notebook_path = notebook_path
        self._initialize_client()

    def _initialize_client(self):
        """Initialize client instance based on notebook path if possible."""
        if not self.notebook_path:
            return

        try:
            notebook_path_lower = self.notebook_path.lower()
            if "solr" in notebook_path_lower:
                from tests.client_factory import create_solr_client

                self.client_instance = create_solr_client()
            elif "opensearch" in notebook_path_lower:
                from tests.client_factory import create_opensearch_client

                self.client_instance = create_opensearch_client()
            elif (
                "elasticsearch" in notebook_path_lower
                or "elastic" in notebook_path_lower
            ):
                from tests.client_factory import create_elastic_client

                self.client_instance = create_elastic_client()
        except Exception:
            # If client creation fails, validation will be skipped
            self.client_instance = None

    def detect_critical_operations(self, cell_source: str) -> list[dict[str, str]]:
        """Detect critical operations in cell source code.

        Args:
            cell_source: Source code of the cell

        Returns:
            List of dictionaries with 'operation' and 'target' keys
        """
        operations = []
        source_lower = cell_source.lower()

        # Detect create_index operations
        if "create_index" in source_lower:
            # Try to extract index name from common patterns
            patterns = [
                r"create_index\(['\"]([^'\"]+)['\"]\)",
                r'create_index\(["\']([^"\']+)["\']\)',
                r"create_index\(([a-zA-Z_][a-zA-Z0-9_]*)\)",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, cell_source)
                for match in matches:
                    operations.append({"operation": "create_index", "target": match})

        # Detect create_featureset operations
        if "create_featureset" in source_lower:
            # Pattern: create_featureset(index='...', name='...', ...)
            pattern = r"create_featureset\s*\([^)]*index\s*=\s*['\"]([^'\"]+)['\"][^)]*name\s*=\s*['\"]([^'\"]+)['\"]"
            matches = re.findall(pattern, cell_source)
            for index, name in matches:
                operations.append(
                    {
                        "operation": "create_featureset",
                        "target": f"{index}:{name}",
                    }
                )

        # Detect rebuild operations
        if "rebuild" in source_lower and "(" in source_lower:
            # Pattern: rebuild(client, index='...', ...)
            pattern = r"rebuild\s*\([^,]+,\s*index\s*=\s*['\"]([^'\"]+)['\"]"
            matches = re.findall(pattern, cell_source)
            for match in matches:
                operations.append({"operation": "rebuild", "target": match})

        # Detect reset_ltr operations
        if "reset_ltr" in source_lower:
            pattern = r"reset_ltr\s*\(['\"]([^'\"]+)['\"]\)"
            matches = re.findall(pattern, cell_source)
            for match in matches:
                operations.append({"operation": "reset_ltr", "target": match})

        return operations

    def detect_dependencies(self, cell_source: str) -> list[dict[str, str]]:
        """Detect dependencies in cell source code.

        Args:
            cell_source: Source code of the cell

        Returns:
            List of dictionaries with 'dependency' and 'target' keys
        """
        dependencies = []
        source_lower = cell_source.lower()

        # Detect feature set dependencies (create_featureset, feature_set calls)
        if "create_featureset" in source_lower or "feature_set" in source_lower:
            # Try to extract index name
            pattern = r"index\s*=\s*['\"]([^'\"]+)['\"]"
            matches = re.findall(pattern, cell_source)
            for match in matches:
                dependencies.append({"dependency": "index", "target": match})

        # Detect model dependencies (train, save_model, sltr queries)
        if (
            "train(" in source_lower
            or "save_model" in source_lower
            or "sltr" in source_lower
            or '"model"' in source_lower
            or "'model'" in source_lower
        ):
            # Try to extract index and feature_set/model names
            index_pattern = r"index\s*=\s*['\"]([^'\"]+)['\"]"
            feature_set_pattern = r"feature_set\s*=\s*['\"]([^'\"]+)['\"]"
            model_pattern = r"model\s*=\s*['\"]([^'\"]+)['\"]"
            indices = re.findall(index_pattern, cell_source)
            feature_sets = re.findall(feature_set_pattern, cell_source)
            models = re.findall(model_pattern, cell_source)
            for idx in indices:
                dependencies.append({"dependency": "index", "target": idx})
            for idx, fs in zip(indices[: len(feature_sets)], feature_sets):
                dependencies.append(
                    {"dependency": "feature_set", "target": f"{idx}:{fs}"}
                )
            for idx, model in zip(indices[: len(models)], models):
                dependencies.append({"dependency": "model", "target": f"{idx}:{model}"})

        return dependencies

    def _record_operation(self, operation: str, target: str) -> None:
        """Record a completed operation so dependent cells see it as satisfied.

        Args:
            operation: Type of operation (create_index, rebuild, create_featureset)
            target: Target of the operation (index name, or "index:feature_set")
        """
        if operation in ("create_index", "rebuild"):
            self.completed_operations["indices"].add(target)
        elif operation == "create_featureset":
            self.completed_operations["feature_sets"].add(target)
            # A feature set implies its index exists, so record that too -- the
            # index-creating cell may not have matched any detection pattern.
            if ":" in target:
                self.completed_operations["indices"].add(target.split(":", 1)[0])

    def validate_operation_succeeded(
        self, operation: str, target: str, cell_index: int
    ) -> tuple[bool, Optional[str]]:
        """Validate that a critical operation succeeded.

        Args:
            operation: Type of operation (create_index, create_featureset, etc.)
            target: Target of the operation (index name, feature set name, etc.)
            cell_index: Index of the cell where operation occurred

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        if not self.client_instance:
            # Can't confirm against a live engine, so trust that the cell did what
            # its source says and record the operation anyway. Skipping the record
            # here while check_prerequisites() still enforces it would fail every
            # dependent cell in the notebook -- passing the operation but failing
            # its dependents is never the useful combination.
            self._record_operation(operation, target)
            return True, None

        try:
            if operation == "create_index" or operation == "rebuild":
                # Validate index exists
                if self.client_instance.check_index_exists(target):
                    self.completed_operations["indices"].add(target)
                    return True, None
                return (
                    False,
                    f"Index '{target}' was not created successfully in cell {cell_index}",
                )

            elif operation == "create_featureset":
                # Parse index:feature_set format
                if target and ":" in target:
                    index, feature_set = target.split(":", 1)
                    # Validate index exists first
                    if not self.client_instance.check_index_exists(index):
                        return (
                            False,
                            f"Index '{index}' does not exist (required for feature set '{feature_set}')",
                        )
                    # Try to retrieve feature set to validate it exists
                    try:
                        self.client_instance.feature_set(index=index, name=feature_set)
                        self.completed_operations["feature_sets"].add(target)
                        return True, None
                    except RuntimeError:
                        return (
                            False,
                            f"Feature set '{feature_set}' was not created successfully in cell {cell_index}",
                        )
                return True, None  # Can't parse, assume success

            elif operation == "reset_ltr":
                # reset_ltr doesn't have a direct validation, but it should succeed if no exception
                return True, None

        except Exception as e:
            return False, f"Error validating {operation} for '{target}': {e}"

        return True, None

    def check_prerequisites(
        self, dependencies: list[dict[str, str]], cell_index: int
    ) -> tuple[bool, Optional[str]]:
        """Check if prerequisites for a cell are met.

        Args:
            dependencies: List of dependency dictionaries
            cell_index: Index of the cell being checked

        Returns:
            Tuple of (prerequisites_met: bool, error_message: str | None)
        """
        for dep in dependencies:
            dep_type = dep.get("dependency")
            target = dep.get("target")

            if dep_type == "index":
                if target not in self.completed_operations["indices"]:
                    return (
                        False,
                        f"Cell {cell_index} requires index '{target}' but it has not been created yet. "
                        f"Ensure a previous cell creates the index using create_index() or rebuild().",
                    )

            elif dep_type == "feature_set":
                if (
                    target
                    and ":" in target
                    and target not in self.completed_operations["feature_sets"]
                ):
                    # Parse index:feature_set
                    index, feature_set = target.split(":", 1)
                    return (
                        False,
                        f"Cell {cell_index} requires feature set '{feature_set}' in index '{index}' "
                        f"but it has not been created yet. Ensure a previous cell creates the feature set "
                        f"using create_featureset().",
                    )

            elif (
                dep_type == "model"
                and target
                and ":" in target
                and target not in self.completed_operations["models"]
            ):
                index, model = target.split(":", 1)
                return (
                    False,
                    f"Cell {cell_index} requires model '{model}' in index '{index}' "
                    f"but it has not been created yet. Ensure a previous cell trains and saves the model.",
                )

        return True, None


class PatchedExecutePreprocessor(ExecutePreprocessor):
    """Custom preprocessor with progress logging and real-time error reporting.

    Extends ExecutePreprocessor to add:
    - Cell-by-cell progress logging with time estimates
    - Real-time error detection and reporting
    - Fail-fast option to stop on first error
    - Validation error handling (fail-fast by default)
    - Immediate error visibility
    - Debug mode for variable state inspection on errors

    Logs each code cell with:
    - Cell index and total cell count
    - Timestamp
    - Cell source code (first 5 lines or up to 300 characters)
    - Progress percentage and estimated time remaining

    Validation errors (from dependency checks and operation validation) will
    stop execution immediately by default unless NOTEBOOK_VALIDATION_FAIL_FAST=false.
    This prevents cascading failures and provides clearer error messages.

    When NOTEBOOK_DEBUG_MODE is enabled, variable states are captured and displayed
    when errors occur, helping debug what data was available at the failure point.
    """

    def __init__(
        self,
        *args,
        fail_fast=False,
        enable_dependency_validation=True,
        validation_fail_fast=None,
        debug_mode=None,
        **kwargs,
    ):
        """Initialize preprocessor with cell tracking counters.

        Args:
            *args: Positional arguments passed to parent ExecutePreprocessor
            fail_fast: If True, raise exception immediately on first error (default: False)
            enable_dependency_validation: If True, validate cell dependencies (default: True)
            validation_fail_fast: If True, raise exception on validation errors (default: from NOTEBOOK_VALIDATION_FAIL_FAST env var or True)
            debug_mode: If True, capture variable states on errors (default: from NOTEBOOK_DEBUG_MODE env var or False)
            **kwargs: Keyword arguments passed to parent ExecutePreprocessor
        """
        super().__init__(*args, **kwargs)
        self.cell_count = 0
        self.total_cells = 0
        self.fail_fast = fail_fast
        self.start_time = None
        self.errors_detected = []
        self.enable_dependency_validation = enable_dependency_validation

        # Get validation_fail_fast from parameter, environment variable, or default to True
        if validation_fail_fast is None:
            validation_fail_fast = os.environ.get(
                "NOTEBOOK_VALIDATION_FAIL_FAST", "true"
            ).lower() in (
                "true",
                "1",
                "yes",
            )
        self.validation_fail_fast = validation_fail_fast

        # Get debug_mode from parameter, environment variable, or default to False
        if debug_mode is None:
            debug_mode = os.environ.get("NOTEBOOK_DEBUG_MODE", "false").lower() in (
                "true",
                "1",
                "yes",
            )
        self.debug_mode = debug_mode

        self.dependency_validator = None  # Will be initialized in preprocess()
        self.kernel_manager = None  # Will be set in preprocess()

    def preprocess(self, nb, resources=None, km=None):
        """Preprocess notebook and track total cell count.

        Args:
            nb: Notebook node
            resources: Resources dictionary (optional, defaults to None)
            km: Optional kernel manager

        Returns:
            Tuple of (notebook, resources) after preprocessing
        """
        import time

        self.total_cells = len(nb.cells)
        self.start_time = time.time()
        self.errors_detected = []
        self.kernel_manager = km  # Store kernel manager for debug mode

        # Initialize dependency validator if enabled
        if self.enable_dependency_validation:
            # Try to get notebook path from resources if available.
            # run_notebook() passes it as a top-level "notebook_path" key while
            # "metadata" carries only "path", so check both rather than using
            # if/elif: "metadata" is always present, which would otherwise make
            # the top-level lookup unreachable and leave the path None.
            notebook_path = None
            if resources:
                metadata = resources.get("metadata") or {}
                notebook_path = metadata.get("notebook_path") or resources.get(
                    "notebook_path"
                )
            self.dependency_validator = NotebookDependencyValidator(
                notebook_path=notebook_path
            )

        return super().preprocess(nb, resources, km)

    def preprocess_cell(self, cell, resources, index):
        """Preprocess a single cell with progress logging and error detection.

        Logs progress for code cells to help track execution progress
        in long-running notebooks. For each code cell, logs:
        - Cell number (index/total)
        - Timestamp
        - Cell source code (first 5 lines or up to 300 characters)
        - Progress percentage and estimated time remaining

        After cell execution, checks for errors and:
        - Prints errors immediately if detected
        - Raises exception if fail_fast=True

        Also validates cell dependencies if dependency validation is enabled:
        - Checks prerequisites before executing cells
        - Validates critical operations after execution
        - Raises CellExecutionError on validation failures if validation_fail_fast=True

        Args:
            cell: Cell to preprocess
            resources: Resources dictionary
            index: Index of the cell in the notebook

        Returns:
            Tuple of (cell, resources) after preprocessing

        Raises:
            CellExecutionError: If fail_fast=True and an error is detected, or if
                validation_fail_fast=True and validation fails
        """
        import sys
        import time
        from datetime import datetime

        # Check prerequisites before executing code cells
        if (
            self.enable_dependency_validation
            and self.dependency_validator
            and cell.cell_type == "code"
            and cell.source.strip()
        ):
            dependencies = self.dependency_validator.detect_dependencies(cell.source)
            if dependencies:
                prerequisites_met, error_msg = (
                    self.dependency_validator.check_prerequisites(dependencies, index)
                )
                if not prerequisites_met:
                    # Log error and fail fast if validation_fail_fast is enabled
                    print(
                        f"\n[ERROR] Cell {index}/{self.total_cells} dependency check failed: {error_msg}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if self.validation_fail_fast:
                        raise CellExecutionError(
                            ename="ValidationError",
                            evalue=f"Dependency check failed: {error_msg}",
                            traceback=[],  # type: ignore[arg-type]
                        )
                    else:
                        # Log warning but don't fail (notebooks may handle dependencies differently)
                        print(
                            "[WARNING] Continuing despite dependency check failure (NOTEBOOK_VALIDATION_FAIL_FAST=false)",
                            file=sys.stderr,
                            flush=True,
                        )

        # Log progress for code cells BEFORE execution
        if cell.cell_type == "code" and cell.source.strip():
            self.cell_count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")

            # Calculate progress percentage
            progress_pct = (
                int((index / self.total_cells) * 100) if self.total_cells > 0 else 0
            )

            # Estimate time remaining based on elapsed time
            elapsed_time = time.time() - self.start_time if self.start_time else 0
            if self.cell_count > 1 and elapsed_time > 0:
                avg_time_per_cell = elapsed_time / self.cell_count
                remaining_cells = self.total_cells - index
                estimated_remaining = avg_time_per_cell * remaining_cells
                time_str = f" (~{int(estimated_remaining)}s remaining)"
            else:
                time_str = ""

            # Show cell code (first 5 lines, truncated to 300 chars if longer)
            source_lines = cell.source.split("\n")
            if len(source_lines) <= 5:
                # Show all lines if 5 or fewer
                code_preview = cell.source.rstrip()
            else:
                # Show first 5 lines, then truncate if over 300 chars
                code_preview = "\n".join(source_lines[:5]).rstrip()
                if len(code_preview) > 300:
                    code_preview = code_preview[:300] + "..."
                # Add truncation indicator since we have more than 5 lines
                code_preview += "\n    ..."

            # Indent code preview for readability
            indented_code = "\n".join(
                f"    {line}" for line in code_preview.split("\n")
            )

            print(
                f"[{timestamp}]   Cell {index}/{self.total_cells} ({progress_pct}%){time_str}:\n{indented_code}",
                flush=True,
            )

        # Execute the cell (modifies cell in place with outputs)
        result_cell, result_resources = super().preprocess_cell(cell, resources, index)

        # Validate critical operations after successful execution
        if (
            self.enable_dependency_validation
            and self.dependency_validator
            and result_cell.cell_type == "code"
            and result_cell.source.strip()
        ):
            # Check if cell executed successfully (no errors)
            has_errors = False
            if "outputs" in result_cell:
                for output in result_cell["outputs"]:
                    if output.output_type == "error":
                        has_errors = True
                        break

            if not has_errors:
                # Try to get client instance from kernel namespace for validation
                # This is a best-effort attempt - validation may not work if client isn't accessible
                try:
                    if not self.dependency_validator.client_instance:
                        # Try to get client from kernel namespace (if available)
                        # Note: This requires the kernel to have executed cells that create a client
                        # We'll attempt this but won't fail if it doesn't work
                        pass  # Client instance will be set up later if possible
                except Exception:
                    pass  # Ignore errors getting client instance

                # Detect and validate critical operations
                operations = self.dependency_validator.detect_critical_operations(
                    result_cell.source
                )
                for op in operations:
                    success, error_msg = (
                        self.dependency_validator.validate_operation_succeeded(
                            op["operation"], op["target"], index
                        )
                    )
                    if not success and error_msg:
                        # Log error and fail fast if validation_fail_fast is enabled
                        print(
                            f"\n[ERROR] Cell {index}/{self.total_cells} operation validation failed: {error_msg}",
                            file=sys.stderr,
                            flush=True,
                        )
                        if self.validation_fail_fast:
                            raise CellExecutionError(
                                ename="ValidationError",
                                evalue=f"Operation validation failed: {error_msg}",
                                traceback=[],  # type: ignore[arg-type]
                            )
                        else:
                            # Log warning but don't fail
                            print(
                                "[WARNING] Continuing despite operation validation failure (NOTEBOOK_VALIDATION_FAIL_FAST=false)",
                                file=sys.stderr,
                                flush=True,
                            )

        # Check for errors AFTER execution (cell is modified in place by ExecutePreprocessor)
        if result_cell.cell_type == "code" and "outputs" in result_cell:
            for output in result_cell["outputs"]:
                if output.output_type == "error":
                    error_info = {
                        "cell_index": index,
                        "cell_source": result_cell.get("source", ""),
                        "ename": output.get("ename", "Unknown"),
                        "evalue": output.get("evalue", "No message"),
                        "traceback": output.get("traceback", []),
                    }
                    self.errors_detected.append(error_info)

                    # Print error immediately for visibility
                    print("\n" + "=" * 80, file=sys.stderr, flush=True)
                    print(
                        f"ERROR in Cell {index}/{self.total_cells}:",
                        file=sys.stderr,
                        flush=True,
                    )
                    print("=" * 80, file=sys.stderr, flush=True)
                    print(
                        f"Error Type: {error_info['ename']}",
                        file=sys.stderr,
                        flush=True,
                    )
                    print(
                        f"Error Message: {error_info['evalue']}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if error_info["traceback"]:
                        print("Traceback:", file=sys.stderr, flush=True)
                        for tb_line in error_info["traceback"][:20]:  # First 20 lines
                            print(f"  {tb_line}", file=sys.stderr, flush=True)

                    # Capture and display variable states if debug mode is enabled
                    if self.debug_mode:
                        print("\n" + "-" * 80, file=sys.stderr, flush=True)
                        print(
                            "DEBUG MODE: Variable States at Error Point",
                            file=sys.stderr,
                            flush=True,
                        )
                        print("-" * 80, file=sys.stderr, flush=True)
                        try:
                            var_states = inspect_notebook_variables(self.kernel_manager)
                            if "error" in var_states:
                                print(
                                    f"  Could not inspect variables: {var_states['error']}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            else:
                                for var_name, var_info in var_states.items():
                                    if isinstance(var_info, dict):
                                        if var_info.get("exists"):
                                            var_type = var_info.get("type", "unknown")
                                            var_len = var_info.get("len")
                                            var_repr = var_info.get("repr", "N/A")
                                            if "error" in var_info:
                                                print(
                                                    f"  {var_name}: <Error: {var_info['error']}>",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                            else:
                                                len_str = (
                                                    f", len={var_len}"
                                                    if var_len is not None
                                                    else ""
                                                )
                                                print(
                                                    f"  {var_name}: {var_type}{len_str} = {var_repr}",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                        else:
                                            print(
                                                f"  {var_name}: <not defined>",
                                                file=sys.stderr,
                                                flush=True,
                                            )
                                    else:
                                        print(
                                            f"  {var_name}: {var_info}",
                                            file=sys.stderr,
                                            flush=True,
                                        )
                        except Exception as e:
                            print(
                                f"  Exception while inspecting variables: {e}",
                                file=sys.stderr,
                                flush=True,
                            )
                        print("-" * 80, file=sys.stderr, flush=True)

                    print("=" * 80 + "\n", file=sys.stderr, flush=True)

                    # Fail fast if requested
                    if self.fail_fast:
                        raise CellExecutionError(
                            ename=error_info["ename"],
                            evalue=error_info["evalue"],
                            traceback=error_info.get("traceback", []),
                        )

        return result_cell, result_resources


def _patch_notebook_cells_for_testing(nb):
    """
    Patch notebook cells to handle known test environment issues.

    This function modifies notebook cells at test time to handle issues that
    don't occur when running notebooks manually but do occur in test environments:
    - Hardcoded query IDs that might not exist in test data
    - Empty training sets causing sklearn errors
    - Empty arrays from pairwise transforms

    Validation errors raised by patched code will stop execution immediately
    (fail-fast) unless NOTEBOOK_VALIDATION_FAIL_FAST=false is set.

    Args:
        nb: Notebook object (nbformat.NotebookNode) to patch in-place
    """
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue

        source = cell.get("source", "")
        if not source:
            continue

        # Patch 1: Replace hardcoded query ID access (e.g., .loc[5, :]) with .iloc[0]
        # This handles cases where query ID 5 doesn't exist in test data
        if ".loc[5, :]" in source and "lambdas_per_query" in source:
            # Replace .loc[5, :] with .iloc[0] if available, else None
            # Use regex to handle variations in whitespace
            pattern = r"lambdas_per_query_prec\.loc\[5,\s*:\]"
            replacement = "lambdas_per_query_prec.iloc[0] if len(lambdas_per_query_prec) > 0 else None"
            source = re.sub(pattern, replacement, source)
            cell["source"] = source

        # Patch 2: Add validation after samples_from_training_data calls
        # This catches empty arrays before sklearn.fit() fails
        if (
            "samples_from_training_data" in source
            and "No valid training pairs" not in source
        ):
            # Add validation after the assignment
            lines = source.split("\n")
            new_lines = []
            for idx, line in enumerate(lines):
                new_lines.append(line)
                # Look for the assignment line (handle variations)
                if "samples_from_training_data" in line and "=" in line:
                    # Add validation after this line
                    indent = len(line) - len(line.lstrip())
                    # Find the next non-empty line to determine if we should add validation
                    # Skip if next line already has validation or is a comment
                    next_line_idx = idx + 1
                    if next_line_idx < len(lines):
                        next_line = lines[next_line_idx].strip()
                        if (
                            next_line
                            and not next_line.startswith("#")
                            and "No valid training pairs" not in next_line
                        ):
                            validation_code = (
                                f"\n{' ' * indent}# Validate that pairwise transform produced valid training pairs\n"
                                f"{' ' * indent}if len(features) == 0 or len(predictors) == 0:\n"
                                f"{' ' * (indent + 4)}raise ValueError(\n"
                                f'{" " * (indent + 8)}"No valid training pairs were generated. This usually means:\\\\n"\n'
                                f'{" " * (indent + 8)}"  1. All judgments for each query have the same grade (no pairs to compare)\\\\n"\n'
                                f'{" " * (indent + 8)}"  2. Features were not logged successfully\\\\n"\n'
                                f'{" " * (indent + 8)}"Please ensure your judgments have varying grades per query and that features were logged."\n'
                                f"{' ' * (indent + 4)})\n"
                            )
                            new_lines.append(validation_code)
            if len(new_lines) > len(lines):
                cell["source"] = "\n".join(new_lines)

        # Patch 3: Add validation for empty ftr_logger.logged before sklearn operations
        # This catches empty training sets early
        if (
            "ftr_logger.logged" in source
            and (
                "samples_from_training_data" in source
                or "model.fit" in source
                or "training_set = ftr_logger.logged" in source
            )
            and "No features were logged" not in source
        ):
            # Add validation before using ftr_logger.logged
            lines = source.split("\n")
            new_lines = []
            for line in lines:
                # Look for lines that use ftr_logger.logged
                if "ftr_logger.logged" in line and (
                    "samples_from_training_data" in line
                    or "training_set = ftr_logger.logged" in line
                ):
                    # Add validation before this line
                    indent = len(line) - len(line.lstrip())
                    validation_code = (
                        f"{' ' * indent}# Validate that features were logged before proceeding\n"
                        f"{' ' * indent}if not ftr_logger.logged:\n"
                        f"{' ' * (indent + 4)}raise ValueError(\n"
                        f'{" " * (indent + 8)}"No features were logged. This may indicate that documents in the judgments "\n'
                        f'{" " * (indent + 8)}"file don\'t exist in the index. Please ensure the index is properly set up."\n'
                        f"{' ' * (indent + 4)})\n"
                    )
                    new_lines.append(validation_code)
                new_lines.append(line)
            if len(new_lines) > len(lines):
                cell["source"] = "\n".join(new_lines)


def run_notebook(notebook_path, timeout=None, save_nb_path=None, fail_fast=None):
    """
    Execute a Jupyter notebook and return results with error details.

    This function:
    - Loads a notebook from the specified path
    - Injects port patching code as the first cell (to redirect to test ports)
    - Executes all cells using PatchedExecutePreprocessor
    - Captures errors with context (cell index, source code, traceback)
    - Optionally saves the executed notebook to a file
    - Returns structured results including errors and execution time

    Args:
        notebook_path: Path to the notebook file to execute
        timeout: Optional timeout in seconds (defaults to NOTEBOOK_TIMEOUT_MINUTES env var or 5 minutes)
        save_nb_path: Optional path to save executed notebook (default: 'tests/last_run.ipynb')
        fail_fast: If True, stop execution on first error (default: from NOTEBOOK_FAIL_FAST env var or False)

    Returns:
        tuple: (notebook, errors, execution_time)
            - notebook: Executed notebook object (nbformat.NotebookNode)
            - errors: List of error dictionaries, each containing:
                - 'ename': Exception name
                - 'evalue': Exception message
                - 'traceback': List of traceback lines
                - 'cell_index': Index of cell where error occurred
                - 'cell_source': Source code of the cell
            - execution_time: Time taken in seconds (float)
    """
    import sys
    import time
    from datetime import datetime

    # Per-CELL timeout, not per-notebook: this is handed to nbclient, which
    # applies it to each cell individually. See NOTEBOOK_TIMEOUT_MINUTES in
    # tests/README.md and the nesting note in pytest.ini.
    if timeout is None:
        timeout_minutes = float(os.environ.get("NOTEBOOK_TIMEOUT_MINUTES", "5"))
        timeout = int(timeout_minutes * 60)

    # Keep RankLib's own timeout just inside the per-cell limit so that a stuck
    # training run reports "RankLib training timed out" -- which names the
    # culprit -- rather than nbclient killing the cell with no explanation.
    # ltr/ranklib.py defaults to 1800s, far outside the cell budget, so without
    # this the useful error could never win the race. Applied in the injected
    # setup cell rather than here: setting it on this process would leak into
    # the rest of the pytest session and change what unrelated tests observe.
    ranklib_timeout = os.environ.get("LTR_RANKLIB_TIMEOUT") or str(
        max(60, int(timeout * 0.8))
    )

    # Get fail_fast from parameter, environment variable, or default to False
    if fail_fast is None:
        fail_fast = os.environ.get("NOTEBOOK_FAIL_FAST", "false").lower() in (
            "true",
            "1",
            "yes",
        )

    # Get validation_fail_fast from environment variable (default: True)
    # This controls whether validation errors from patched cells stop execution
    validation_fail_fast = os.environ.get(
        "NOTEBOOK_VALIDATION_FAIL_FAST", "true"
    ).lower() in (
        "true",
        "1",
        "yes",
    )

    # Get debug_mode from environment variable (default: False)
    # This controls whether variable states are captured and displayed on errors
    debug_mode = os.environ.get("NOTEBOOK_DEBUG_MODE", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)

    def log(msg):
        """Log a message with timestamp to stderr.

        Args:
            msg: Message to log
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", file=sys.stderr, flush=True)

    log(f"Loading notebook: {notebook_path}")
    start_time = time.time()

    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    # Patch notebook cells to handle known test environment issues
    _patch_notebook_cells_for_testing(nb)

    # Inject setup code as first cell to ensure it runs before any notebook code.
    # This uses dependency injection via environment variables instead of monkey patching.
    # Clients now accept port parameters that default to environment variables.
    # project_root should be the parent of 'tests' directory, not the tests directory itself
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # Get test ports from environment (already set by conftest.py)
    # These will be used by clients via dependency injection (port parameters default to env vars)
    from tests.port_management import get_port

    solr_port = get_port("SOLR_PORT")
    elasticsearch_port = get_port("ELASTICSEARCH_PORT")
    opensearch_port = get_port("OPENSEARCH_PORT")

    # Build setup cell - sets environment variables and patches requests library
    # Clients will automatically use these ports via their port parameters
    setup_cell_source = (
        f"import sys\nimport os\nsys.path.insert(0, r'{project_root}')\n"
    )

    # Set port environment variables if they're available (for dependency injection)
    if solr_port:
        setup_cell_source += f"os.environ['SOLR_PORT'] = '{solr_port}'\n"
    if elasticsearch_port:
        setup_cell_source += (
            f"os.environ['ELASTICSEARCH_PORT'] = '{elasticsearch_port}'\n"
        )
    if opensearch_port:
        setup_cell_source += f"os.environ['OPENSEARCH_PORT'] = '{opensearch_port}'\n"

    # Bound RankLib inside the per-cell timeout so its own error wins the race
    setup_cell_source += f"os.environ['LTR_RANKLIB_TIMEOUT'] = '{ranklib_timeout}'\n"

    # Still patch requests library for hardcoded URLs in notebooks
    # Also patch reset_ltr timing for test environments
    setup_cell_source += (
        "from tests.patch_clients_for_tests import patch_requests_for_test_ports, patch_reset_ltr_timing\n"
        "try:\n"
        "    patch_requests_for_test_ports()\n"
        "    patch_reset_ltr_timing()\n"
        "except Exception as e:\n"
        "    import traceback\n"
        "    traceback.print_exc(file=sys.stderr)\n"
        "    raise"
    )

    setup_cell = nbformat.v4.new_code_cell(source=setup_cell_source)
    nb.cells.insert(0, setup_cell)

    # Patch configs_dir for Elasticsearch/OpenSearch notebooks
    # This ensures clients can find settings files when running from project root during tests
    notebook_dir = os.path.dirname(notebook_path)
    is_es_notebook = (
        "elasticsearch" in notebook_path.lower()
        or "opensearch" in notebook_path.lower()
    ) and ("tmdb" in notebook_path.lower() or "osc-blog" in notebook_path.lower())

    if is_es_notebook:
        # Determine relative path from project root to notebook directory
        notebook_dir_rel = os.path.relpath(notebook_dir, project_root)

        # Set environment variable for the notebook's config directory
        # This is used by the OpenSearchClient and ElasticClient when configs_dir is not specified
        # The clients will check this env var and use it as the default configs_dir
        os.environ["NOTEBOOK_CONFIGS_DIR"] = notebook_dir_rel
        insert_index = 1
    else:
        insert_index = 1

    # Check if notebook needs index setup (uses reset_ltr, create_featureset, or sltr queries)
    # This ensures notebooks that depend on the index have it created if needed
    # Note: We check for sltr even if rebuild is present, because rebuild might fail
    # or the notebook's rebuild code might not execute properly in test environment.
    # The injected code checks if index exists before creating, so it's safe to run.
    notebook_source = " ".join(
        [cell.get("source", "") for cell in nb.cells if cell.get("cell_type") == "code"]
    )
    # Notebooks that use sltr queries always need the index, even if they have rebuild
    # because sltr queries will fail if the index doesn't exist
    needs_index = (
        "reset_ltr" in notebook_source
        or "create_featureset" in notebook_source
        or "sltr" in notebook_source
    )
    is_tmdb_notebook = "tmdb" in notebook_path.lower()

    if needs_index and is_tmdb_notebook:
        # Determine client type from notebook path and use factory functions for dependency injection
        factory_import = None
        client_creation = None

        if "solr" in notebook_path.lower():
            factory_import = "from tests.client_factory import create_solr_client"
            client_creation = "_test_client = create_solr_client()"
        elif "opensearch" in notebook_path.lower():
            factory_import = "from tests.client_factory import create_opensearch_client"
            client_creation = "_test_client = create_opensearch_client()"
        elif (
            "elasticsearch" in notebook_path.lower()
            or "elastic" in notebook_path.lower()
        ):
            factory_import = "from tests.client_factory import create_elastic_client"
            client_creation = "_test_client = create_elastic_client()"

        if factory_import and client_creation:
            # Check if notebook will rebuild the index itself
            # If it does, we only create the index if it doesn't exist (don't force rebuild)
            # This avoids conflicts where we create it, then notebook deletes and fails to recreate
            notebook_will_rebuild = (
                "rebuild" in notebook_source and "force=True" in notebook_source
            )

            # Inject index setup code after patch cell
            # This ensures the index exists before notebooks try to use it
            if notebook_will_rebuild:
                # Notebook will rebuild, so only create if missing (don't force)
                # This avoids the scenario where we create it, notebook deletes it, then fails to recreate
                rebuild_strategy = (
                    "if not _test_client.check_index_exists('tmdb'):\n"
                    "            movies = indexable_movies(movies_path=data_file)\n"
                    "            rebuild(_test_client, index='tmdb', doc_src=movies, force=False)\n"
                    "            print('[TEST] Created tmdb index (notebook will rebuild it)')\n"
                    "        else:\n"
                    "            print('[TEST] Index exists, notebook will rebuild it')"
                )
            else:
                # Notebook won't rebuild, so ensure index exists (force rebuild for clean state)
                rebuild_strategy = (
                    "movies = indexable_movies(movies_path=data_file)\n"
                    "        rebuild(_test_client, index='tmdb', doc_src=movies, force=True)\n"
                    "        print('[TEST] Successfully created/rebuilt tmdb index')"
                )

            index_setup_cell = nbformat.v4.new_code_cell(
                source=f"{factory_import}\n"
                "import os\n"
                "from ltr import download\n"
                "from ltr.helpers.movies import indexable_movies\n"
                "from ltr.index import rebuild\n"
                "\n"
                "# Ensure tmdb index exists for notebooks that need it\n"
                "# This runs before the notebook's own rebuild code to ensure the index exists\n"
                f"{client_creation}\n"
                "# Download data if it doesn't exist\n"
                "data_file = 'data/tmdb.json'\n"
                "if not os.path.exists(data_file):\n"
                "    try:\n"
                "        corpus = 'http://es-learn-to-rank.labs.o19s.com/tmdb.json'\n"
                "        download([corpus], dest='data/')\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not download data: {{e}}')\n"
                "        print('[TEST] Index creation skipped - notebook may fail if data is required')\n"
                "# Create index if data file exists\n"
                "if os.path.exists(data_file):\n"
                "    try:\n"
                f"        {rebuild_strategy}\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not create index: {{e}}')\n"
                "        print('[TEST] Notebook may fail if index is required')\n"
                "del _test_client"
            )
            nb.cells.insert(insert_index, index_setup_cell)
            insert_index += 1

    # Handle osc-blog notebooks - they need the blog index
    is_osc_blog_notebook = "osc-blog" in notebook_path.lower()
    if needs_index and is_osc_blog_notebook:
        # Determine client type from notebook path and use factory for dependency injection
        if "solr" in notebook_path.lower():
            factory_import = "from tests.client_factory import create_solr_client"
            client_creation = "_test_client = create_solr_client()"
        elif "opensearch" in notebook_path.lower():
            factory_import = "from tests.client_factory import create_opensearch_client"
            client_creation = "_test_client = create_opensearch_client()"
        elif (
            "elasticsearch" in notebook_path.lower()
            or "elastic" in notebook_path.lower()
        ):
            factory_import = "from tests.client_factory import create_elastic_client"
            client_creation = "_test_client = create_elastic_client()"
        else:
            factory_import = None
            client_creation = None

        if factory_import:
            # Check if notebook will rebuild the index itself
            notebook_will_rebuild = (
                "rebuild" in notebook_source and "force=True" in notebook_source
            )

            # Inject blog index setup code after patch cell
            # Always create the index to ensure it exists, even if notebook's rebuild() fails
            # The notebook's rebuild() with force=True will delete and recreate it, which is fine
            rebuild_strategy = (
                "import json\n"
                "        articles = []\n"
                "        with open(data_file) as f:\n"
                "            for line in f:\n"
                "                blog = json.loads(line)\n"
                "                articles.append(blog)\n"
                "        # Always create index to ensure it exists\n"
                "        # Notebook's rebuild() with force=True will delete and recreate it\n"
                "        rebuild(_test_client, index='blog', doc_src=articles, force=True)\n"
                "        print('[TEST] Successfully created/rebuilt blog index')"
            )

            blog_index_setup_cell = nbformat.v4.new_code_cell(
                source=f"{factory_import}\n"
                "import os\n"
                "from ltr import download\n"
                "from ltr.index import rebuild\n"
                "\n"
                "# Ensure blog index exists for osc-blog notebooks\n"
                "# This runs before the notebook's own rebuild code to ensure the index exists\n"
                f"{client_creation}\n"
                "# Download data if it doesn't exist\n"
                "data_file = 'data/blog.jsonl'\n"
                "if not os.path.exists(data_file):\n"
                "    try:\n"
                "        corpus = 'http://es-learn-to-rank.labs.o19s.com/blog.jsonl'\n"
                "        download([corpus], dest='data/')\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not download data: {{e}}')\n"
                "        print('[TEST] Index creation skipped - notebook may fail if data is required')\n"
                "# Create index if data file exists\n"
                "if os.path.exists(data_file):\n"
                "    try:\n"
                f"        {rebuild_strategy}\n"
                "    except Exception as e:\n"
                "        print(f'[TEST] Warning: Could not create index: {{e}}')\n"
                "        print('[TEST] Notebook may fail if index is required')\n"
                "del _test_client"
            )
            nb.cells.insert(insert_index, blog_index_setup_cell)
            insert_index += 1

    # Check if notebook uses train() or feature_search() and reduce expensive parameters for testing
    # This reduces kcv, trees, bag, and leafs to speed up tests while still validating functionality
    uses_train = "train(" in notebook_source
    uses_feature_search = "feature_search(" in notebook_source

    # Check if notebook builds training sets (uses FeatureLogger.log_for_qid with groupby)
    # This can be expensive if there are many queries/judgments
    uses_feature_logging = (
        "log_for_qid" in notebook_source
        and "groupby" in notebook_source
        and "judgments_open" in notebook_source
    )

    if uses_train or uses_feature_search:
        # Get test mode limits from environment or use defaults
        max_test_folds = safe_kcv_folds(
            int(os.environ.get("NOTEBOOK_MAX_KCV_FOLDS", "2")),
            int(os.environ.get("NOTEBOOK_MAX_QUERIES", "2")),
        )
        max_test_trees = int(os.environ.get("NOTEBOOK_MAX_TREES", "1"))
        max_test_bag = int(os.environ.get("NOTEBOOK_MAX_BAG", "1"))
        max_test_leafs = int(os.environ.get("NOTEBOOK_MAX_LEAFS", "1"))
        max_test_features = int(
            os.environ.get("NOTEBOOK_MAX_FEATURES", "2")
        )  # Limit features for feature_search to reduce exponential combinations

        # Build comprehensive patch code for train() and feature_search()
        patch_source = "# Reduce expensive parameters for faster testing\n"
        patch_source += "from ltr.ranklib import train as _original_train, feature_search as _original_feature_search\n"
        patch_source += "\n"

        # Patch train() function
        if uses_train:
            # Use library defaults (50, 1, 10) instead of None so notebooks that don't specify
            # these parameters get reasonable defaults, which we then cap for testing
            patch_source += "def train(*args, kcv=None, trees=50, bag=1, leafs=10, features=None, **kwargs):\n"
            patch_source += '    """Wrapped train() function that reduces expensive parameters for testing."""\n'
            patch_source += "    print('[TEST MODE] Wrapper train() called')\n"
            patch_source += "    # Get parameter values (from kwargs if not provided as named parameters)\n"
            patch_source += (
                "    kcv_val = kcv if kcv is not None else kwargs.get('kcv', None)\n"
            )
            patch_source += "    trees_val = trees if trees is not None else kwargs.get('trees', 50)\n"
            patch_source += (
                "    bag_val = bag if bag is not None else kwargs.get('bag', 1)\n"
            )
            patch_source += "    leafs_val = leafs if leafs is not None else kwargs.get('leafs', 10)\n"
            patch_source += "    features_val = features if features is not None else kwargs.get('features', None)\n"
            patch_source += "    # Reduce expensive parameters\n"
            if max_test_folds is None:
                # No valid fold count for this training set size -- strip kcv so
                # RankLib trains without cross-validation instead of hanging.
                patch_source += "    if kcv_val is not None:\n"
                patch_source += "        print('[TEST MODE] Dropping kcv: too few queries for cross-validation')\n"
                patch_source += "        kcv = None\n"
                patch_source += "        kwargs.pop('kcv', None)\n"
            else:
                patch_source += (
                    f"    if kcv_val is not None and kcv_val > {max_test_folds}:\n"
                )
                patch_source += f"        print(f'[TEST MODE] Reducing kcv from {{kcv_val}} to {max_test_folds} for faster testing')\n"
                patch_source += f"        kcv = {max_test_folds}\n"
                patch_source += (
                    "        kwargs.pop('kcv', None)  # Remove from kwargs if present\n"
                )
            patch_source += (
                f"    if trees_val is not None and trees_val > {max_test_trees}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing trees from {{trees_val}} to {max_test_trees} for faster testing')\n"
            patch_source += f"        trees = {max_test_trees}\n"
            patch_source += (
                "        kwargs.pop('trees', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if bag_val is not None and bag_val > {max_test_bag}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing bag from {{bag_val}} to {max_test_bag} for faster testing')\n"
            patch_source += f"        bag = {max_test_bag}\n"
            patch_source += (
                "        kwargs.pop('bag', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if leafs_val is not None and leafs_val > {max_test_leafs}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing leafs from {{leafs_val}} to {max_test_leafs} for faster testing')\n"
            patch_source += f"        leafs = {max_test_leafs}\n"
            patch_source += (
                "        kwargs.pop('leafs', None)  # Remove from kwargs if present\n"
            )
            patch_source += "    # Limit features list to reduce training complexity\n"
            patch_source += f"    if features_val is not None and len(features_val) > {max_test_features}:\n"
            patch_source += f"        print(f'[TEST MODE] Reducing train() features from {{len(features_val)}} to {max_test_features} ({{features_val[:{max_test_features}]}}) for faster testing')\n"
            patch_source += f"        features = features_val[:{max_test_features}]\n"
            patch_source += "        if 'features' in kwargs:\n"
            patch_source += "            kwargs['features'] = features\n"
            patch_source += "    elif features_val is not None:\n"
            patch_source += "        features = features_val\n"
            patch_source += "    else:\n"
            patch_source += "        features = None\n"
            patch_source += "    return _original_train(*args, kcv=kcv, trees=trees, bag=bag, leafs=leafs, features=features, **kwargs)\n"
            patch_source += "\n"
            patch_source += "# Monkey-patch the train function in ltr.ranklib module\n"
            patch_source += "import ltr.ranklib\n"
            patch_source += "ltr.ranklib.train = train\n"
            patch_source += (
                "print('[TEST MODE] Successfully patched ltr.ranklib.train')\n"
            )
            patch_source += "\n"

        # Patch feature_search() function
        if uses_feature_search:
            # Use library defaults (5, 10, 1, 10) instead of None so notebooks that don't specify
            # these parameters get reasonable defaults, which we then cap for testing
            patch_source += "def feature_search(*args, kcv=5, trees=10, bag=1, leafs=10, features=None, **kwargs):\n"
            patch_source += '    """Wrapped feature_search() function that reduces expensive parameters for testing."""\n'
            patch_source += "    print('[TEST MODE] Wrapper feature_search() called')\n"
            patch_source += "    # Get parameter values (from kwargs if not provided as named parameters)\n"
            patch_source += (
                "    kcv_val = kcv if kcv is not None else kwargs.get('kcv', 5)\n"
            )
            patch_source += "    trees_val = trees if trees is not None else kwargs.get('trees', 10)\n"
            patch_source += (
                "    bag_val = bag if bag is not None else kwargs.get('bag', 1)\n"
            )
            patch_source += "    leafs_val = leafs if leafs is not None else kwargs.get('leafs', 10)\n"
            patch_source += "    features_val = features if features is not None else kwargs.get('features', None)\n"
            patch_source += "    # Reduce expensive parameters\n"
            if max_test_folds is None:
                # No valid fold count for this training set size -- strip kcv so
                # RankLib trains without cross-validation instead of hanging.
                patch_source += "    if kcv_val is not None:\n"
                patch_source += "        print('[TEST MODE] Dropping kcv: too few queries for cross-validation')\n"
                patch_source += "        kcv = None\n"
                patch_source += "        kwargs.pop('kcv', None)\n"
            else:
                patch_source += (
                    f"    if kcv_val is not None and kcv_val > {max_test_folds}:\n"
                )
                patch_source += f"        print(f'[TEST MODE] Reducing kcv from {{kcv_val}} to {max_test_folds} for faster testing')\n"
                patch_source += f"        kcv = {max_test_folds}\n"
                patch_source += (
                    "        kwargs.pop('kcv', None)  # Remove from kwargs if present\n"
                )
            patch_source += (
                f"    if trees_val is not None and trees_val > {max_test_trees}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing trees from {{trees_val}} to {max_test_trees} for faster testing')\n"
            patch_source += f"        trees = {max_test_trees}\n"
            patch_source += (
                "        kwargs.pop('trees', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if bag_val is not None and bag_val > {max_test_bag}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing bag from {{bag_val}} to {max_test_bag} for faster testing')\n"
            patch_source += f"        bag = {max_test_bag}\n"
            patch_source += (
                "        kwargs.pop('bag', None)  # Remove from kwargs if present\n"
            )
            patch_source += (
                f"    if leafs_val is not None and leafs_val > {max_test_leafs}:\n"
            )
            patch_source += f"        print(f'[TEST MODE] Reducing leafs from {{leafs_val}} to {max_test_leafs} for faster testing')\n"
            patch_source += f"        leafs = {max_test_leafs}\n"
            patch_source += (
                "        kwargs.pop('leafs', None)  # Remove from kwargs if present\n"
            )
            patch_source += "    # Limit features list to reduce exponential combinations (2^n - 1 combinations)\n"
            patch_source += "    # Reducing from 9 features (511 combos) to 2 features (3 combos) = 170x speedup!\n"
            patch_source += (
                "    # Always set features to ensure it's passed correctly\n"
            )
            patch_source += "    if features_val is not None:\n"
            patch_source += f"        if len(features_val) > {max_test_features}:\n"
            patch_source += f"            print(f'[TEST MODE] Reducing features from {{len(features_val)}} to {max_test_features} ({{features_val[:{max_test_features}]}}) for faster testing')\n"
            patch_source += (
                f"            features = features_val[:{max_test_features}]\n"
            )
            patch_source += "        else:\n"
            patch_source += "            features = features_val\n"
            patch_source += (
                "        # Update kwargs if features was passed via kwargs\n"
            )
            patch_source += "        if 'features' in kwargs:\n"
            patch_source += "            kwargs['features'] = features\n"
            patch_source += "    else:\n"
            patch_source += "        features = None\n"
            patch_source += "    return _original_feature_search(*args, kcv=kcv, trees=trees, bag=bag, leafs=leafs, features=features, **kwargs)\n"
            patch_source += "\n"
            patch_source += (
                "# Monkey-patch the feature_search function in ltr.ranklib module\n"
            )
            patch_source += "ltr.ranklib.feature_search = feature_search\n"
            patch_source += (
                "print('[TEST MODE] Successfully patched ltr.ranklib.feature_search')\n"
            )

        patch_cell = nbformat.v4.new_code_cell(source=patch_source)
        nb.cells.insert(insert_index, patch_cell)
        insert_index += 1

    # Limit training set size by reducing number of queries processed
    if uses_feature_logging:
        max_test_queries = int(
            os.environ.get("NOTEBOOK_MAX_QUERIES", "2")
        )  # Limit to 2 queries for faster testing
        max_test_judgments_per_query = int(
            os.environ.get("NOTEBOOK_MAX_JUDGMENTS_PER_QUERY", "2")
        )  # Limit judgments per query

        training_set_patch = "# Limit training set size for faster testing\n"
        training_set_patch += "from itertools import groupby\n"
        training_set_patch += "\n"
        training_set_patch += (
            "# Wrap FeatureLogger to limit queries and judgments per query\n"
        )
        # The query budget is PER LOGGER, not shared across all of them. It used
        # to be a module-level counter, which meant the first FeatureLogger in a
        # notebook consumed the whole budget and every later one was handed an
        # empty training set, so train() failed with "Training set is empty".
        # Notebooks that log features more than once -- tale-of-two-queries and
        # netfix movies both build two loggers -- could never pass. Per-instance
        # still bounds the work (loggers x max_queries) without starving anyone.
        training_set_patch += (
            "# Per-instance query budget: a shared counter would starve later loggers\n"
        )
        training_set_patch += "import ltr.log\n"
        training_set_patch += f"ltr.log._test_max_queries = {max_test_queries}\n"
        training_set_patch += (
            f"ltr.log._test_max_judgments_per_query = {max_test_judgments_per_query}\n"
        )
        training_set_patch += (
            "from ltr.log import FeatureLogger as _OriginalFeatureLogger\n"
        )
        training_set_patch += "class LimitedFeatureLogger(_OriginalFeatureLogger):\n"
        training_set_patch += "    def __init__(self, *args, **kwargs):\n"
        training_set_patch += "        super().__init__(*args, **kwargs)\n"
        training_set_patch += "        self._test_query_count = 0\n"
        training_set_patch += "    def log_for_qid(self, qid, judgments, keywords):\n"
        training_set_patch += (
            "        # Budget is per logger instance, so a notebook that builds\n"
        )
        training_set_patch += (
            "        # several loggers gets a usable training set from each\n"
        )
        training_set_patch += "        import ltr.log\n"
        training_set_patch += (
            "        if self._test_query_count >= ltr.log._test_max_queries:\n"
        )
        training_set_patch += "            print(f'[TEST MODE] Skipping query {qid} - this logger already processed {ltr.log._test_max_queries} queries for faster testing')\n"
        training_set_patch += "            return [], list(judgments)  # Return empty training set, all judgments discarded\n"
        training_set_patch += "        self._test_query_count += 1\n"
        training_set_patch += "        # Limit judgments per query\n"
        training_set_patch += "        judgments_list = list(judgments)\n"
        training_set_patch += (
            "        if len(judgments_list) > ltr.log._test_max_judgments_per_query:\n"
        )
        training_set_patch += "            print(f'[TEST MODE] Limiting query {qid} to {ltr.log._test_max_judgments_per_query} judgments (from {len(judgments_list)}) for faster testing')\n"
        training_set_patch += "            judgments_list = judgments_list[:ltr.log._test_max_judgments_per_query]\n"
        training_set_patch += (
            "        return super().log_for_qid(qid, judgments_list, keywords)\n"
        )
        training_set_patch += "\n"
        training_set_patch += "# Monkey-patch FeatureLogger\n"
        training_set_patch += "ltr.log.FeatureLogger = LimitedFeatureLogger\n"
        training_set_patch += f"print(f'[TEST MODE] Successfully patched FeatureLogger to limit to {max_test_queries} queries and {max_test_judgments_per_query} judgments per query')\n"

        training_set_cell = nbformat.v4.new_code_cell(source=training_set_patch)
        nb.cells.insert(insert_index, training_set_cell)
        insert_index += 1

    # Execute notebook with patched clients
    log(f"Executing {nb_name} ({len(nb.cells)} cells)...")
    if fail_fast:
        log("Fail-fast mode enabled: will stop on first error")
    if validation_fail_fast:
        log(
            "Validation fail-fast enabled: validation errors will stop execution immediately"
        )
    if debug_mode:
        log("Debug mode enabled: variable states will be captured on errors")
    print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Starting cell-by-cell execution:",
        flush=True,
    )
    # Use custom preprocessor for progress logging and error detection
    proc = PatchedExecutePreprocessor(
        timeout=timeout,
        kernel_name="python3",
        fail_fast=fail_fast,
        validation_fail_fast=validation_fail_fast,
        debug_mode=debug_mode,
    )
    # Only allow errors if not in fail-fast mode
    proc.allow_errors = not fail_fast

    try:
        # Pass notebook_path in resources for dependency validation
        proc.preprocess(
            nb, {"metadata": {"path": dirname}, "notebook_path": notebook_path}
        )
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stderr)
        raise

    execution_time = time.time() - start_time
    log(f"✓ Completed execution of {nb_name} (took {execution_time:.1f}s)")

    if save_nb_path:
        with open(save_nb_path, mode="w") as f:
            nbformat.write(nb, f)

    errors = []
    # Ensure log directory exists (if needed)
    # Don't fail if directory creation fails
    with suppress(Exception):
        log_dir = os.path.join(os.path.dirname(notebook_path), "logs")
        os.makedirs(log_dir, exist_ok=True)

    for cell_index, cell in enumerate(nb.cells):
        if "outputs" in cell:
            for output in cell["outputs"]:
                if output.output_type == "error":
                    # Enhance error with cell context
                    error_with_context = dict(output)
                    error_with_context["cell_index"] = cell_index
                    error_with_context["cell_source"] = cell.get("source", "")
                    # Truncate cell source if too long (first 500 chars)
                    if len(error_with_context["cell_source"]) > 500:
                        error_with_context["cell_source"] = (
                            error_with_context["cell_source"][:500] + "..."
                        )
                    # Log error details to stderr and file for debugging
                    errors.append(error_with_context)

    return nb, errors, execution_time
