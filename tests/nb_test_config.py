"""
Notebook test configuration loader.

This module provides NotebookTestConfig class for discovering and organizing
notebooks in test directories, with special handling for setup notebooks.
"""

import os

import nbformat


class NotebookTestConfig:
    """Configuration for discovering notebooks in a test directory."""

    SETUP_NB = "setup.ipynb"

    def __init__(self, path):
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

        self.notebooks = []
        self.setup = None

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
    def _is_valid_notebook(notebook_path):
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
