"""
Unit tests for notebook runner functionality, including debug mode.

Tests the PatchedExecutePreprocessor and debug mode features.
"""

import os
from unittest.mock import MagicMock, patch

import nbformat

from tests.notebooks.runner import (
    PatchedExecutePreprocessor,
    inspect_notebook_variables,
    run_notebook,
)


class TestDebugMode:
    """Tests for debug mode functionality."""

    def test_debug_mode_disabled_by_default(self):
        """Test that debug mode is disabled by default."""
        # Clear environment variable to ensure default
        with patch.dict(os.environ, {}, clear=True):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is False

    def test_debug_mode_enabled_via_env_var(self):
        """Test that debug mode can be enabled via NOTEBOOK_DEBUG_MODE environment variable."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "1"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "yes"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is True

    def test_debug_mode_disabled_via_env_var(self):
        """Test that debug mode can be explicitly disabled."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "false"}, clear=False):
            preprocessor = PatchedExecutePreprocessor()
            assert preprocessor.debug_mode is False

    def test_debug_mode_parameter_override(self):
        """Test that debug_mode parameter overrides environment variable."""
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            preprocessor = PatchedExecutePreprocessor(debug_mode=False)
            assert preprocessor.debug_mode is False

        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "false"}, clear=False):
            preprocessor = PatchedExecutePreprocessor(debug_mode=True)
            assert preprocessor.debug_mode is True

    def test_kernel_manager_stored_when_debug_mode_enabled(self):
        """Test that kernel manager is stored when debug mode is enabled."""
        preprocessor = PatchedExecutePreprocessor(debug_mode=True)
        mock_km = MagicMock()
        mock_nb = nbformat.v4.new_notebook()
        mock_nb.cells = [nbformat.v4.new_code_cell("print('test')")]

        preprocessor.preprocess(mock_nb, resources={}, km=mock_km)

        assert preprocessor.kernel_manager is mock_km

    def test_inspect_notebook_variables_no_kernel_manager(self):
        """Test that inspect_notebook_variables handles missing kernel manager gracefully."""
        result = inspect_notebook_variables(None)
        assert "error" in result
        assert "No kernel manager available" in result["error"]

    def test_inspect_notebook_variables_no_client(self):
        """Test that inspect_notebook_variables handles kernel manager without client."""
        mock_km = MagicMock()
        mock_km.client = None

        result = inspect_notebook_variables(mock_km)
        assert "error" in result
        assert "doesn't have a client available" in result["error"]

    def test_inspect_notebook_variables_execution_error(self):
        """Test that inspect_notebook_variables handles execution errors gracefully."""
        mock_km = MagicMock()
        mock_client = MagicMock()
        mock_km.client = mock_client

        # Simulate execution error
        mock_client.execute.side_effect = Exception("Kernel error")

        result = inspect_notebook_variables(mock_km)
        assert "error" in result
        assert "Exception while inspecting variables" in result["error"]


class TestDebugModeIntegration:
    """Integration tests for debug mode with actual notebook execution."""

    def test_debug_mode_captures_variables_on_error(self, tmp_path):
        """Test that debug mode captures variable states when a cell fails."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell(
                "# Set up some variables\nftr_logger = type('obj', (object,), {'logged': [1, 2, 3]})()\ntraining_set = [1, 2, 3]"
            ),
            nbformat.v4.new_code_cell(
                "# This will fail\nraise ValueError('Test error')"
            ),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Run with debug mode enabled
        with patch.dict(os.environ, {"NOTEBOOK_DEBUG_MODE": "true"}, clear=False):
            # Capture stderr to check for debug output
            import sys
            from io import StringIO

            old_stderr = sys.stderr
            sys.stderr = captured_stderr = StringIO()

            try:
                # Run notebook (will fail, but we want to see debug output)
                # Use a short timeout to avoid hanging
                _, errors, _ = run_notebook(
                    str(notebook_path), timeout=30, fail_fast=True
                )

                # Check that we got an error
                assert len(errors) > 0

                # Check that debug output was captured
                stderr_output = captured_stderr.getvalue()
                # Note: Variable inspection might fail if kernel manager doesn't support it,
                # but we should at least see the attempt
                assert (
                    "DEBUG MODE" in stderr_output
                    or "Variable States" in stderr_output
                    or "Could not inspect variables" in stderr_output
                )
            finally:
                sys.stderr = old_stderr

    def test_debug_mode_not_called_when_disabled(self, tmp_path, monkeypatch):
        """Test that variable inspection is not called when debug mode is disabled."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell("raise ValueError('Test error')"),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Mock inspect_notebook_variables to verify it's not called
        with patch("tests.notebooks.runner.inspect_notebook_variables") as mock_inspect:
            # Ensure debug mode is disabled
            monkeypatch.delenv("NOTEBOOK_DEBUG_MODE", raising=False)

            # Run notebook
            run_notebook(str(notebook_path), timeout=30, fail_fast=True)

            # Verify inspect_notebook_variables was not called
            mock_inspect.assert_not_called()

    def test_debug_mode_called_when_enabled(self, tmp_path, monkeypatch):
        """Test that variable inspection is called when debug mode is enabled."""
        # Create a simple notebook that will fail
        nb = nbformat.v4.new_notebook()
        nb.cells = [
            nbformat.v4.new_code_cell("raise ValueError('Test error')"),
        ]

        notebook_path = tmp_path / "test_notebook.ipynb"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Mock inspect_notebook_variables to verify it's called
        with patch("tests.notebooks.runner.inspect_notebook_variables") as mock_inspect:
            mock_inspect.return_value = {"test_var": {"exists": False}}

            # Enable debug mode
            monkeypatch.setenv("NOTEBOOK_DEBUG_MODE", "true")

            # Run notebook
            run_notebook(str(notebook_path), timeout=30, fail_fast=True)

            # Verify inspect_notebook_variables was called
            # Note: It might be called multiple times if there are multiple errors
            assert mock_inspect.called


class TestPatchedExecutePreprocessor:
    """Tests for PatchedExecutePreprocessor class."""

    def test_preprocessor_initialization(self):
        """Test that preprocessor initializes correctly."""
        preprocessor = PatchedExecutePreprocessor()
        assert preprocessor.cell_count == 0
        assert preprocessor.total_cells == 0
        assert preprocessor.fail_fast is False
        assert preprocessor.debug_mode is False
        assert preprocessor.kernel_manager is None

    def test_preprocessor_stores_kernel_manager(self):
        """Test that preprocessor stores kernel manager reference."""
        preprocessor = PatchedExecutePreprocessor(debug_mode=True)
        mock_km = MagicMock()
        mock_nb = nbformat.v4.new_notebook()
        mock_nb.cells = [nbformat.v4.new_code_cell("print('test')")]

        preprocessor.preprocess(mock_nb, resources={}, km=mock_km)

        assert preprocessor.kernel_manager is mock_km
