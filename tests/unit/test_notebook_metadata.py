"""Unit tests for notebook metadata.

Tests cover:
- kernelspec sanity across every shipped notebook
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted((PROJECT_ROOT / "notebooks").rglob("*.ipynb"))

# The only kernel this project installs is the stock ipykernel that `uv sync`
# provides. A notebook pinned to any other kernel name fails to open in Jupyter
# ("no such kernel") and cannot be executed by nbconvert. Notebook tests do not
# catch this because tests/notebooks/runner.py passes kernel_name="python3"
# explicitly rather than honouring the notebook's own metadata.
EXPECTED_KERNEL = "python3"


def _notebook_ids():
    return [str(nb.relative_to(PROJECT_ROOT)) for nb in NOTEBOOKS]


def test_notebooks_are_discovered():
    """Test that the notebook glob actually found notebooks."""
    # Arrange / Act / Assert
    assert NOTEBOOKS, f"no notebooks found under {PROJECT_ROOT / 'notebooks'}"


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=_notebook_ids())
def test_notebook_uses_installed_kernel(notebook):
    """Test that every notebook references the kernel this project installs."""
    # Arrange
    with open(notebook, encoding="utf-8") as f:
        doc = json.load(f)
    # Act
    kernel_name = doc.get("metadata", {}).get("kernelspec", {}).get("name")
    # Assert
    assert kernel_name == EXPECTED_KERNEL
