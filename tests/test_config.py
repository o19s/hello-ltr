"""
Test configuration for hello-ltr test suite.

This module contains:
- Test paths and ignored notebooks configuration
- NotebookTestConfig class for discovering notebooks in test directories

Consolidated from test_config.py and nb_test_config.py to reduce configuration file count.
"""

import os
from typing import Optional

import nbformat

# Test configuration migrated from RunMostNotebooksTestCase
TEST_PATHS = [
    "./notebooks/",
    "./notebooks/solr/tmdb",
    "./notebooks/elasticsearch/tmdb",
    "./notebooks/elasticsearch/osc-blog",
    "./notebooks/opensearch/tmdb",
    "./notebooks/opensearch/osc-blog",
]

IGNORED_NOTEBOOKS = [
    # ========================================================================
    # Evaluation Notebooks
    # ========================================================================
    # These notebooks are excluded because they:
    # - Take 30+ minutes each to execute (too slow for CI/CD)
    # - Require significant computational resources (memory/CPU)
    # - Are primarily used for final validation, not development testing
    #
    # When to un-ignore:
    # - When you need to validate end-to-end evaluation workflows
    # - For release validation or pre-deployment checks
    # - When running manual validation suites
    #
    # What needs to be fixed to enable automated testing:
    # - Optimize evaluation logic to run faster (e.g., reduce dataset size)
    # - Add progress checkpoints to allow resuming long-running evaluations
    # - Consider splitting into smaller, focused evaluation notebooks
    # - Add resource usage monitoring and limits
    "./notebooks/solr/tmdb/evaluation (Solr).ipynb",
    "./notebooks/elasticsearch/tmdb/evaluation.ipynb",
    "./notebooks/opensearch/tmdb/evaluation.ipynb",
    # ========================================================================
    # XGBoost Notebooks
    # ========================================================================
    # These notebooks are excluded because they:
    # - Have complex dependencies (XGBoost + native libraries)
    # - Require specific system libraries (libgomp, etc.)
    # - May have platform-specific build requirements
    # - Can fail due to environment differences (Docker vs local)
    #
    # When to un-ignore:
    # - When XGBoost dependencies are fully stabilized across platforms
    # - For platform-specific test suites (e.g., Linux-only CI)
    # - When you need to validate XGBoost model training workflows
    #
    # What needs to be fixed to enable automated testing:
    # - Ensure XGBoost is properly installed in test Docker containers
    # - Add dependency validation before notebook execution
    # - Create platform-specific test configurations
    # - Add fallback handling for missing XGBoost dependencies
    # - Consider mocking XGBoost for faster unit tests
    "./notebooks/elasticsearch/tmdb/XGBoost.ipynb",
    "./notebooks/opensearch/tmdb/XGBoost.ipynb",
]

# Known slow notebook patterns (notebooks that typically take > 60 seconds)
# These match the patterns defined in tests/conftest.py
SLOW_PATTERNS = [
    "netfix",
    "bayesian-optimization",
    "bigger bot",
    "lambda-mart",
    "feature_search",
    "evaluation",
]


def _is_slow_notebook(notebook_path: str) -> bool:
    """
    Check if a notebook matches known slow patterns.

    Args:
        notebook_path: Path to the notebook file

    Returns:
        bool: True if notebook matches slow patterns
    """
    if not notebook_path:
        return False
    notebook_path_lower = notebook_path.lower()
    return any(pattern.lower() in notebook_path_lower for pattern in SLOW_PATTERNS)


def collect_notebooks() -> list[tuple[str, str, str]]:
    """
    Collect all notebooks to test.

    Notebooks are ordered to optimize test execution:
    1. Setup notebooks run first
    2. hello-ltr notebooks run before dependent notebooks
    3. Fast notebooks run before slow notebooks (slow notebooks run last)

    Slow notebooks are identified by matching patterns in SLOW_PATTERNS
    (e.g., "lambda-mart", "bigger bot", "netfix", "bayesian-optimization").

    Returns:
        List of tuples: (notebook_path, notebook_type, engine)

        notebook_type: 'setup' or 'test'
        engine: 'solr', 'elasticsearch', 'opensearch', or 'general'
    """
    notebooks = []

    for test_path in TEST_PATHS:
        # Skip if path doesn't exist
        if not os.path.exists(test_path):
            continue

        try:
            config = NotebookTestConfig(path=test_path)
        except Exception:
            # Skip paths that fail to load
            continue

        # Determine engine from path for automatic marking
        engine = "general"
        if "solr" in test_path:
            engine = "solr"
        elif "elasticsearch" in test_path:
            engine = "elasticsearch"
        elif "opensearch" in test_path:
            engine = "opensearch"

        # Add setup notebook if exists
        if config.setup:
            notebooks.append((config.setup, "setup", engine))

        # Add test notebooks (excluding ignored)
        # Sort: hello-ltr notebooks first, then fast notebooks, then slow notebooks last
        test_notebooks = [nb for nb in config.notebooks if nb not in IGNORED_NOTEBOOKS]
        test_notebooks.sort(
            key=lambda x: (
                0 if "hello-ltr" in x.lower() else 1,  # hello-ltr first
                1 if _is_slow_notebook(x) else 0,  # slow notebooks last
                x,  # then alphabetical
            )
        )
        for nb in test_notebooks:
            notebooks.append((nb, "test", engine))

    return notebooks


class NotebookTestConfig:
    """
    Configuration for discovering notebooks in a test directory.

    Provides functionality for discovering and organizing notebooks in test directories,
    with special handling for setup notebooks.
    """

    SETUP_NB = "setup.ipynb"

    def __init__(self, path: str) -> None:
        """
        Initialize notebook configuration from a directory path.

        Args:
            path: Directory path to scan for notebooks

        Raises:
            FileNotFoundError: If the path doesn't exist
            NotADirectoryError: If the path exists but is not a directory
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")

        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path is not a directory: {path}")

        self.notebooks: list[str] = []
        self.setup: Optional[str] = None

        try:
            for nb_path in os.listdir(path):
                full_nb_path = os.path.join(path, nb_path)
                if os.path.isfile(full_nb_path) and nb_path.endswith(".ipynb"):
                    if nb_path == NotebookTestConfig.SETUP_NB:
                        # Validate that setup notebook is actually a valid notebook
                        if self._is_valid_notebook(full_nb_path):
                            self.setup = full_nb_path
                        # If invalid, treat it as a regular notebook (don't fail silently)
                    else:
                        self.notebooks.append(full_nb_path)
        except OSError as e:
            raise OSError(f"Error reading directory {path}: {e}") from e

    @staticmethod
    def _is_valid_notebook(notebook_path: str) -> bool:
        """
        Validate that a file is a valid Jupyter notebook.

        Args:
            notebook_path: Path to the notebook file

        Returns:
            bool: True if valid notebook, False otherwise
        """
        try:
            with open(notebook_path, encoding="utf-8") as f:
                nbformat.read(f, as_version=4)
            return True
        except (nbformat.reader.NotJSONError, OSError, ValueError):
            return False
