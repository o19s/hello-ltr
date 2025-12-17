"""Common type aliases for the hello-ltr codebase.

This module provides type aliases for commonly used type patterns to improve
readability, maintainability, and consistency across the codebase.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Union

# JSON-like dictionary structures
"""Dictionary representing JSON-like data structures."""
JSONDict = dict[str, Any]

"""List of JSON-like dictionaries, commonly used for search results."""
JSONDictList = list[JSONDict]

"""Nested dictionary structure (e.g., dict[str, dict[str, Any]])."""
NestedJSONDict = dict[str, JSONDict]

# Search engine related types
"""Query parameters dictionary for search engines."""
QueryParams = dict[str, Any]

"""Search result document dictionary."""
SearchResult = dict[str, Any]

"""List of search result documents."""
SearchResults = list[SearchResult]

# Document source types (for indexing)
"""Iterable of document dictionaries."""
DocSourceIterable = Iterable[JSONDict]

"""Callable that returns an iterable of document dictionaries."""
DocSourceCallable = Callable[[], DocSourceIterable]

"""Union type for document sources (string path, iterable, or callable)."""
DocSource = Union[str, DocSourceIterable, DocSourceCallable]

# Feature and model related types
"""Feature mapping dictionary."""
FeatureMapping = dict[str, Any]

"""List of feature dictionaries."""
FeatureList = list[JSONDict]

"""Union type for feature configurations (list or dict format)."""
FeatureConfig = Union[FeatureList, JSONDict]

"""Model payload dictionary."""
ModelPayload = dict[str, Any]

"""Tuple returned by feature_set methods: (mapping, raw_config)."""
FeatureSetResult = tuple[FeatureList, list[Any]]

# Judgment types
"""List of Judgment objects."""
JudgmentList = list[Any]  # Using Any to avoid circular import with Judgment

"""Dictionary mapping query IDs to (keywords, weight) tuples."""
QueryKeywordMap = dict[int, tuple[str, int]]

# Click model session types
"""Document tuple: (doc_id, click) or (doc_id, click, conversion)."""
DocTuple = Union[tuple[Any, bool], tuple[Any, bool, Any]]

"""List of document tuples."""
DocTupleList = list[DocTuple]

"""Session tuple: (query, list of doc tuples)."""
SessionTuple = tuple[Any, DocTupleList]

"""List of session tuples."""
SessionTupleList = list[SessionTuple]

# Click model types
"""Query-document pair: (query_id, doc_id) tuple used as dictionary keys."""
QueryDocPair = tuple[str, Any]  # doc_id can be any hashable type (str, int, etc.)

"""Dictionary mapping query-document pairs to attractiveness/satisfaction values."""
AttractivenessMap = dict[QueryDocPair, float]

"""Dictionary mapping rank positions to CTR (Click-Through Rate) values."""
CTRByRank = dict[int, float]

"""Dictionary mapping document IDs to cost values."""
CostMap = dict[str, float]

"""Dictionary mapping feature IDs to impact/importance values."""
FeatureImpactMap = dict[str, float]

"""UBM rank pair: (last_click_position, current_rank) tuple."""
UBMRankPair = tuple[int, int]
