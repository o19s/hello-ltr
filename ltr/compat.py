"""Backwards compatibility helpers for the public API.

Several public functions had camelCase keyword arguments renamed to snake_case.
hello-ltr's API is quoted verbatim in published material - the OSC blog posts
and the *AI Powered Search* book chapters - where readers copy and paste calls
like ``train(..., modelName='title', featureSet='movies')``. Those readers
cannot edit the published text, so the old keyword names keep working and emit
a ``DeprecationWarning`` pointing at the new name.

Positional arguments were not reordered, so positional calls are unaffected.
"""

from __future__ import annotations

import functools
import warnings
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def accepts_legacy_kwargs(**aliases: str) -> Callable[[F], F]:
    """Accept pre-rename keyword names, warning when one is used.

    Args:
        **aliases: Mapping of legacy keyword name to its current name, e.g.
            ``accepts_legacy_kwargs(modelName="model_name")``.

    Returns:
        A decorator that rewrites legacy keywords to their current names before
        calling the wrapped function.

    Raises:
        TypeError: If a call supplies both the legacy and the current name.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for legacy, current in aliases.items():
                if legacy not in kwargs:
                    continue
                if current in kwargs:
                    raise TypeError(
                        f"{func.__name__}() got both {legacy!r} and {current!r}; "
                        f"pass only {current!r}"
                    )
                warnings.warn(
                    f"{func.__name__}({legacy}=...) is deprecated, "
                    f"use {current}=... instead",
                    DeprecationWarning,
                    stacklevel=2,
                )
                kwargs[current] = kwargs.pop(legacy)
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
