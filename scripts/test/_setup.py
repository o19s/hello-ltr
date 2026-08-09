"""Shared setup module for test scripts.

This module handles sys.path setup and re-exports commonly used imports
to avoid import resolution issues in type checkers.
"""

import sys
from pathlib import Path

# Add project root to path for imports
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import and re-export from constants and utils
# This allows scripts to import from _setup instead of directly,
# which helps type checkers resolve imports correctly
from scripts.test import (  # noqa: E402
    constants,
    utils,
)

# Re-export commonly used items
from scripts.test.constants import (  # noqa: E402
    DEFAULT_TIMEOUT,
    FAILING_NOTEBOOKS_BY_ENGINE_EXTENDED,
    FAILING_NOTEBOOKS_BY_ENGINE_MINIMAL,
    FAILING_TESTS_FLAT,
    FAILING_TESTS_FLAT_EXTENDED,
    LONG_TIMEOUT,
    SLOW_PATTERNS,
)
from scripts.test.utils import (  # noqa: E402
    extract_error_count,
    extract_errors,
    extract_summary,
    get_test_name,
    is_slow_notebook,
    print_test_summary,
    run_notebook_test,
    save_test_results,
    strip_ansi_codes,
)

__all__ = [
    # Constants
    "DEFAULT_TIMEOUT",
    "FAILING_NOTEBOOKS_BY_ENGINE_EXTENDED",
    "FAILING_NOTEBOOKS_BY_ENGINE_MINIMAL",
    "FAILING_TESTS_FLAT",
    "FAILING_TESTS_FLAT_EXTENDED",
    "LONG_TIMEOUT",
    "SLOW_PATTERNS",
    # Utils
    "extract_error_count",
    "extract_errors",
    "extract_summary",
    "get_test_name",
    "is_slow_notebook",
    "print_test_summary",
    "run_notebook_test",
    "save_test_results",
    "strip_ansi_codes",
    # Modules (for advanced usage)
    "constants",
    "utils",
]
