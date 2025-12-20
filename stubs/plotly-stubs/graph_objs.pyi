"""Type stubs for plotly.graph_objs module."""

from typing import Any

# Common plotly graph objects
def Table(*args: Any, **kwargs: Any) -> Any: ...
def Scatter(*args: Any, **kwargs: Any) -> Any: ...
def Bar(*args: Any, **kwargs: Any) -> Any: ...

class Figure:
    """Type stub for plotly.graph_objs.Figure."""
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...

# Re-export as go for convenience
go: Any

