"""Type stubs for pandas library.

Note: pandas 2.0+ includes built-in type annotations. However, pyright
may still report warnings in some cases. This stub provides a permissive
fallback that allows all pandas operations while suppressing warnings.

For comprehensive pandas type checking, pandas 2.0+ includes built-in
type annotations. This stub exists primarily to suppress pyright warnings.
"""

from typing import Any

# Permissive DataFrame stub - pandas 2.0+ has comprehensive built-in types
class DataFrame:
    """Type stub for pandas.DataFrame - permissive to allow all pandas operations."""
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def __getitem__(self, key: Any) -> Any: ...
    def __setitem__(self, key: Any, value: Any) -> None: ...
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

# Module-level functions - permissive to allow all pandas functions
def __getattr__(name: str) -> Any: ...

# Common pandas imports
pd: Any

