"""Type stubs for sklearn (scikit-learn) library.

Note: scikit-learn 1.3.0+ includes built-in type annotations. However, pyright
may still report warnings in some cases. This stub provides a permissive
fallback that allows all sklearn operations while suppressing warnings.
"""

from typing import Any

# Module-level functions - permissive to allow all sklearn functions
def __getattr__(name: str) -> Any: ...

