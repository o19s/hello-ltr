"""
Unit tests for evaluate.py module.

Tests cover:
- evaluate function
- rre_table function
- Docker command execution
"""

import importlib
import json
from unittest.mock import mock_open, patch

import pytest

from ltr.evaluate import evaluate, rre_table

# ltr/__init__.py does `from .evaluate import evaluate, rre_table`, which rebinds the
# attribute `ltr.evaluate` to the function and shadows the submodule of the same
# name, so string patch targets naming that submodule cannot be resolved by
# mock.patch. Grab the real module object and patch attributes on it instead.
evaluate_module = importlib.import_module("ltr.evaluate")


class TestEvaluate:
    """Test evaluate function."""

    def test_evaluate_valid_mode_elastic(self):
        """Test evaluate with valid 'elastic' mode."""
        # Arrange
        with (
            patch.object(evaluate_module, "quiet_run") as mock_quiet,
            patch.object(evaluate_module, "log_run") as mock_log,
        ):
            # Act
            evaluate("elastic")
            # Assert
            assert mock_quiet.call_count >= 2  # build and rm
            assert mock_log.call_count >= 2  # run and cp

    def test_evaluate_valid_mode_solr(self):
        """Test evaluate with valid 'solr' mode."""
        # Arrange
        with (
            patch.object(evaluate_module, "quiet_run") as mock_quiet,
            patch.object(evaluate_module, "log_run") as mock_log,
        ):
            # Act
            evaluate("solr")
            # Assert
            assert mock_quiet.call_count >= 2
            assert mock_log.call_count >= 2

    def test_evaluate_valid_mode_opensearch(self):
        """Test evaluate with valid 'opensearch' mode."""
        # Arrange
        with (
            patch.object(evaluate_module, "quiet_run") as mock_quiet,
            patch.object(evaluate_module, "log_run") as mock_log,
        ):
            # Act
            evaluate("opensearch")
            # Assert
            assert mock_quiet.call_count >= 2
            assert mock_log.call_count >= 2

    def test_evaluate_invalid_mode(self):
        """Test evaluate raises ValueError for invalid mode."""
        # Act & Assert
        with pytest.raises(ValueError, match="is not a supported value"):
            evaluate("invalid_mode")  # type: ignore[arg-type]

    def test_evaluate_builds_docker_image(self):
        """Test evaluate builds Docker image with correct path."""
        # Arrange
        with (
            patch.object(evaluate_module, "quiet_run") as mock_quiet,
            patch.object(evaluate_module, "log_run"),
        ):
            # Act
            evaluate("elastic")
            # Assert
            build_call = mock_quiet.call_args_list[0]
            assert "docker build" in build_call[0][0]
            assert "rre/elastic" in build_call[0][0]

    def test_evaluate_copies_reports(self):
        """Test evaluate copies evaluation reports."""
        # Arrange
        with (
            patch.object(evaluate_module, "quiet_run"),
            patch.object(evaluate_module, "log_run") as mock_log,
        ):
            # Act
            evaluate("elastic")
            # Assert
            # Check for copy commands
            copy_calls = [
                call[0][0]
                for call in mock_log.call_args_list
                if "docker cp" in call[0][0]
            ]
            assert len(copy_calls) >= 2
            assert any("evaluation.json" in call for call in copy_calls)
            assert any("rre-report.xlsx" in call for call in copy_calls)


class TestRreTable:
    """Test rre_table function."""

    @patch.object(evaluate_module, "iplot")
    @patch.object(evaluate_module, "init_notebook_mode")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=json.dumps(
            {
                "metrics": {
                    "P": {
                        "versions": {
                            "baseline": {"value": 0.5},
                            "classic": {"value": 0.6},
                            "latest": {"value": 0.7},
                        }
                    },
                    "R": {
                        "versions": {
                            "baseline": {"value": 0.4},
                            "classic": {"value": 0.5},
                            "latest": {"value": 0.6},
                        }
                    },
                    "ERR@30": {
                        "versions": {
                            "baseline": {"value": 0.3},
                            "classic": {"value": 0.4},
                            "latest": {"value": 0.5},
                        }
                    },
                }
            }
        ),
    )
    def test_rre_table_loads_data(self, mock_file, mock_init, mock_iplot):
        """Test rre_table loads evaluation data."""
        # Act
        rre_table()
        # Assert
        mock_file.assert_called_once_with("data/rre-evaluation.json", encoding="utf-8")
        mock_iplot.assert_called_once()

    @patch.object(evaluate_module, "iplot")
    @patch.object(evaluate_module, "init_notebook_mode")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=json.dumps(
            {
                "metrics": {
                    "P": {
                        "versions": {
                            "baseline": {"value": 0.5},
                            "classic": {"value": 0.6},
                            "latest": {"value": 0.7},
                        }
                    },
                    "R": {
                        "versions": {
                            "baseline": {"value": 0.4},
                            "classic": {"value": 0.5},
                            "latest": {"value": 0.6},
                        }
                    },
                    "ERR@30": {
                        "versions": {
                            "baseline": {"value": 0.3},
                            "classic": {"value": 0.4},
                            "latest": {"value": 0.5},
                        }
                    },
                }
            }
        ),
    )
    def test_rre_table_extracts_metrics(self, mock_file, mock_init, mock_iplot):
        """Test rre_table extracts correct metrics."""
        # Act
        rre_table()
        # Assert
        call_args = mock_iplot.call_args
        data = call_args[0][0]
        assert len(data) == 1
        table = data[0]
        # plotly.Table header values might be tuple or list
        header_values = table["header"]["values"]
        assert header_values == ["", "Precision", "Recall", "ERR"] or header_values == (
            "",
            "Precision",
            "Recall",
            "ERR",
        )
        assert len(table["cells"]["values"]) == 4
