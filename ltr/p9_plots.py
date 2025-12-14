"""Plotnine-based visualization utilities for judgment analysis.

This module provides functions for creating statistical visualizations of
judgment data using plotnine (ggplot2 for Python).
"""


def plot_grades(dat):
    """Plot distribution of relevance grades by query.

    Creates a bar chart showing the distribution of relevance grades,
    faceted by query keywords.

    Args:
        dat: DataFrame containing 'grade' and 'keywords' columns.

    Returns:
        dict: Dictionary containing plotnine plot object (for compatibility).

    Note:
        Requires plotnine and pandas. Designed for use in Jupyter notebooks.
    """
    import plotnine as p9

    p = {p9.ggplot(dat, p9.aes("grade")) + p9.geom_bar() + p9.facet_wrap("keywords")}

    return p


def plot_features(dat):
    """Plot feature values against relevance grades.

    Creates a jitter plot showing the relationship between feature values
    and relevance grades, faceted by feature ID and colored by query keywords.

    Args:
        dat: DataFrame containing 'grade', 'features', 'feature_id', and 'keywords' columns.

    Returns:
        dict: Dictionary containing plotnine plot object (for compatibility).

    Note:
        Requires plotnine and pandas. Designed for use in Jupyter notebooks.
    """
    import plotnine as p9

    p = {
        p9.ggplot(dat, p9.aes("grade", "features", color="keywords"))
        + p9.geom_jitter(alpha=0.5)
        + p9.facet_wrap("feature_id", scales="free_y", labeller="label_both")
        + p9.labs(y="Feature values", x="Relevance grade")
    }

    return p
