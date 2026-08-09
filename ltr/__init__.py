"""Learn-to-Rank library for Elasticsearch, OpenSearch, and Solr.

This package provides a unified interface for working with Learn-to-Rank (LTR)
across multiple search engines. It includes functionality for:
- Training RankLib models
- Managing feature sets and models
- Building training sets from judgments
- Executing LTR queries
- Evaluating model performance

Main public API:
    - download: Download files from URLs
    - evaluate: Run RRE evaluations
    - rre_table: Display evaluation results
    - search: Execute LTR search queries
"""

# Make the most important pieces just available as
# ie - from ltr import download
from .download import download
from .evaluate import evaluate, rre_table
from .search import search

# Explicitly declare public API exports to satisfy linters and make the module's
# public interface clear. This allows 'from ltr import download' to work while
# preventing linter warnings about unused imports in __init__.py
__all__ = ["download", "evaluate", "rre_table", "search"]
