"""Type stubs for plotly library.

Plotly 5.x has built-in type annotations, but pyright may not detect them
in all cases. These stubs provide fallback type information.
"""

from typing import Any

# Re-export common plotly modules
graph_objs: Any
offline: Any

