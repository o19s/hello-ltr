"""Plotnine-based visualization utilities for judgment analysis.

This module provides functions for creating statistical visualizations of
judgment data using plotnine (ggplot2 for Python).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


def plot_grades(dat: pd.DataFrame) -> set[Any]:
    """Plot distribution of relevance grades by query.

    Creates a bar chart showing the distribution of relevance grades,
    faceted by query keywords.

    Args:
        dat: DataFrame containing 'grade' and 'keywords' columns.

    Returns:
        set: Set containing plotnine plot object (for compatibility).

    Note:
        Requires plotnine and pandas. Designed for use in Jupyter notebooks.
    """
    from plotnine import aes, facet_wrap, geom_bar
    from plotnine.ggplot import ggplot

    p = {ggplot(dat, aes("grade")) + geom_bar() + facet_wrap("keywords")}

    return p


def plot_features(dat: pd.DataFrame) -> set[Any]:
    """Plot feature values against relevance grades.

    Creates a jitter plot showing the relationship between feature values
    and relevance grades, faceted by feature ID and colored by query keywords.

    Args:
        dat: DataFrame containing 'grade', 'features', 'feature_id', and 'keywords' columns.

    Returns:
        set: Set containing plotnine plot object (for compatibility).

    Note:
        Requires plotnine and pandas. Designed for use in Jupyter notebooks.
    """
    from plotnine import aes, facet_wrap, geom_jitter, labs
    from plotnine.ggplot import ggplot

    p = {
        ggplot(dat, aes("grade", "features", color="keywords"))
        + geom_jitter(alpha=0.5)
        + facet_wrap("feature_id", scales="free_y", labeller="label_both")
        + labs(y="Feature values", x="Relevance grade")
    }

    return p
