# Type Aliases Guide

## Overview

This codebase uses type aliases defined in `ltr/types.py` to improve code readability, maintainability, and consistency. Type aliases are a Python best practice when you have complex or frequently repeated type definitions.

## Benefits

1. **Readability**: `JSONDict` is clearer than `dict[str, Any]`
2. **Maintainability**: Change the type definition in one place
3. **Consistency**: Ensures the same type is used everywhere
4. **Documentation**: Type aliases serve as inline documentation

## Available Type Aliases

### JSON-like Structures
- `JSONDict` - `dict[str, Any]` - Dictionary representing JSON-like data
- `JSONDictList` - `list[dict[str, Any]]` - List of JSON dictionaries (common for search results)
- `NestedJSONDict` - `dict[str, dict[str, Any]]` - Nested dictionary structure

### Search Engine Types
- `QueryParams` - `dict[str, Any]` - Query parameters dictionary
- `SearchResult` - `dict[str, Any]` - Single search result document
- `SearchResults` - `list[dict[str, Any]]` - List of search results

### Document Source Types (for indexing)
- `DocSourceIterable` - `Iterable[dict[str, Any]]` - Iterable of document dictionaries
- `DocSourceCallable` - `Callable[[], DocSourceIterable]` - Callable returning doc iterable
- `DocSource` - `Union[str, DocSourceIterable, DocSourceCallable]` - All doc source types

### Feature & Model Types
- `FeatureMapping` - `dict[str, Any]` - Feature mapping dictionary
- `FeatureList` - `list[dict[str, Any]]` - List of feature dictionaries
- `FeatureConfig` - `Union[FeatureList, JSONDict]` - Feature configuration (list or dict)
- `ModelPayload` - `dict[str, Any]` - Model payload dictionary
- `FeatureSetResult` - `tuple[FeatureList, list[Any]]` - Feature set method return type

### Click Model Session Types
- `DocTuple` - `Union[tuple[Any, bool], tuple[Any, bool, Any]]` - Document tuple
- `DocTupleList` - `list[DocTuple]` - List of document tuples
- `SessionTuple` - `tuple[Any, DocTupleList]` - Session tuple
- `SessionTupleList` - `list[SessionTuple]` - List of session tuples

## Usage Examples

### Before (without type aliases)
```python
def query(self, index: str, query: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a search query."""
    ...
```

### After (with type aliases)
```python
from ltr.types import JSONDict, JSONDictList, QueryParams

def query(self, index: str, query: QueryParams) -> JSONDictList:
    """Execute a search query."""
    ...
```

### Complex Types
```python
# Before
def build_one(sess_tuple: tuple[Any, list[Union[tuple[Any, bool], tuple[Any, bool, Any]]]]) -> Session:
    ...

# After
from ltr.types import SessionTuple

def build_one(sess_tuple: SessionTuple) -> Session:
    ...
```

## When to Create New Type Aliases

Create a new type alias when:
1. **Complex types** - Types with 3+ levels of nesting
2. **Frequently repeated** - Same type appears 5+ times
3. **Domain concepts** - Types that represent domain concepts (e.g., `SessionTuple`)
4. **Future flexibility** - Types that might need to change (e.g., `JSONDict` could become `TypedDict`)

## Migration Strategy

1. **Start with most common** - Replace `dict[str, Any]` and `list[dict[str, Any]]` first
2. **Update incrementally** - Don't need to update everything at once
3. **Use IDE refactoring** - Most IDEs can help find and replace type references
4. **Test after changes** - Run type checker to ensure compatibility

## Best Practices

1. **Import from `ltr.types`** - Centralized location for all type aliases
2. **Use descriptive names** - `JSONDict` not `Dict`, `SessionTuple` not `ST`
3. **Document complex aliases** - Add docstrings for non-obvious types
4. **Keep aliases focused** - One concept per alias
5. **Don't over-alias** - Simple types like `str` or `int` don't need aliases

