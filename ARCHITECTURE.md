# Architecture Documentation

**Project:** hello-ltr (Learning to Rank tutorial and examples)  
**Last Updated:** December 21, 2025

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Layers](#architecture-layers)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Client Abstraction Pattern](#client-abstraction-pattern)
6. [Module Organization](#module-organization)
7. [Key Design Patterns](#key-design-patterns)
8. [Integration Points](#integration-points)
9. [Deployment Architecture](#deployment-architecture)
10. [Type System](#type-system)

---

## System Overview

The hello-ltr project is a **Learning-to-Rank (LTR) tutorial and demonstration library** that provides a unified interface for working with LTR across three major search engines: **Elasticsearch**, **OpenSearch**, and **Solr**.

### Core Purpose

The system enables users to:
- Train RankLib models from relevance judgments
- Manage feature sets and models across different search engines
- Build training sets from query-document judgments
- Execute LTR queries and evaluate model performance
- Work with click models for implicit feedback

### Key Architectural Principles

1. **Abstraction over Implementation**: Unified API across different search engines
2. **Separation of Concerns**: Clear boundaries between clients, models, and utilities
3. **Extensibility**: Easy to add new search engine implementations
4. **Educational Focus**: Code serves as both library and tutorial examples

---

## Architecture Layers

The system is organized into four main layers:

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (Notebooks, Scripts, User-facing Functions)           │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│                      Library Layer                       │
│  (search, judgments, evaluate, ranklib, clickmodels)    │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│                    Client Abstraction Layer              │
│  (BaseClient ABC + Elastic/OpenSearch/Solr Clients)     │
└─────────────────────────────────────────────────────────┘
                         │
┌─────────────────────────────────────────────────────────┐
│                    Search Engine Layer                   │
│  (Elasticsearch, OpenSearch, Solr via HTTP APIs)       │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

1. **Application Layer**: Jupyter notebooks and utility scripts that demonstrate LTR workflows
2. **Library Layer**: Core LTR functionality (judgments, models, evaluation, search)
3. **Client Abstraction Layer**: Search engine-specific implementations behind a unified interface
4. **Search Engine Layer**: External search engines running in Docker containers

---

## Component Architecture

### High-Level Components

```
hello-ltr/
├── ltr/                    # Core library
│   ├── client/             # Search engine clients
│   ├── clickmodels/        # Click model implementations
│   ├── helpers/            # Utility functions
│   └── [core modules]      # Main LTR functionality
├── notebooks/              # Jupyter notebook examples
├── tests/                  # Test infrastructure
├── rre/                    # RRE evaluation configs
└── utils/                  # Utility scripts
```

### Core Library Components (`ltr/`)

#### 1. Client Module (`ltr/client/`)

**Purpose**: Abstract search engine operations behind a unified interface.

**Components**:
- `base_client.py`: Abstract base class (`BaseClient`) defining the interface
- `elastic_client.py`: Elasticsearch implementation
- `opensearch_client.py`: OpenSearch implementation
- `solr_client.py`: Solr implementation
- `solr_parse.py`: Solr-specific parsing utilities

**Key Interface Methods**:
- Index management: `create_index()`, `delete_index()`, `index_documents()`
- LTR operations: `reset_ltr()`, `create_featureset()`, `submit_model()`
- Query execution: `query()`, `log_query()`, `model_query()`
- Feature management: `feature_set()`, `get_feature_name()`

#### 2. Core Modules

**`search.py`**: LTR query construction and execution
- `es_ltr_query()`: Builds Elasticsearch/OpenSearch LTR queries
- `solr_ltr_query()`: Builds Solr LTR queries
- `search()`: Unified search function that works with any client

**`judgments.py`**: Relevance judgment data structures and I/O
- `Judgment`: Data class representing query-document-relevance triplets
- `JudgmentsReader`: Lazy reader for judgment files
- `JudgmentsWriter`: Buffered writer for judgment files
- File format: Header with queries, body with judgments

**`ranklib.py`**: RankLib model training and conversion
- Integration with RankLib Java library
- Model format conversion for different search engines
- Training set generation from judgments

**`evaluate.py`**: Model evaluation and metrics
- Integration with RRE (Relevance and Ranking Evaluation)
- Metric calculation (NDCG, MRR, etc.)
- Result table generation

**`log.py`**: Feature logging for training data collection
- Query execution with feature logging enabled
- Feature vector extraction from search results

**`index.py`**: Document indexing utilities
- Bulk indexing operations
- Document source handling (iterables, callables)

**`validation.py`**: Input validation and security
- Index name validation (prevents injection attacks)
- Model and feature set name validation
- Keyword validation for search queries
- Raises `ValidationError` for invalid inputs

**`logger.py`**: Centralized logging configuration
- Unified logging setup for the entire library
- Configurable log levels via environment variables
- Hierarchical logger naming (`ltr.module_name`)
- Console handler with consistent formatting

#### 3. Click Models (`ltr/clickmodels/`)

**Purpose**: Implement various click models for implicit feedback.

**Models**:
- `ubm.py`: User Browsing Model
- `pbm.py`: Position-Based Model
- `cascade.py`: Cascade Model
- `coec.py`: Click-Over-Expected-Click
- `sdbn.py`: Sequential DBN Model
- `conversion.py`: Conversion tracking
- `session.py`: Session management

**Pattern**: Each model implements a common interface for:
- Attractiveness estimation
- Satisfaction estimation
- CTR prediction

#### 4. Helper Modules (`ltr/helpers/`)

**Purpose**: Reusable utilities and domain-specific helpers.

**Key Helpers**:
- `movies.py`: TMDB movie data handling
- `handle_resp.py`: Response wrapper utilities
- `butterfingers.py`: Typo injection for robustness testing
- `convert.py`: Data format conversions
- `ranklib_result.py`: RankLib output parsing
- `solr_escape.py`: Solr query escaping
- `retry.py`: Retry logic with exponential backoff for transient failures
- `msmarco/evaluate.py`: MS MARCO dataset evaluation

---

## Data Flow

### LTR Workflow

```
┌─────────────┐
│  1. Index   │  Create index and load documents
│  Documents  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 2. Create   │  Define feature set (features to extract)
│ Feature Set │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 3. Collect  │  Execute queries with feature logging
│   Features  │  Generate training data
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 4. Create   │  Build judgments (query-doc-relevance)
│  Judgments  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 5. Train    │  Generate RankLib training set
│   Model     │  Train RankLib model
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 6. Submit   │  Convert and upload model to search engine
│   Model     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 7. Query    │  Execute LTR queries using trained model
│  & Evaluate │  Measure performance metrics
└─────────────┘
```

### Data Structures

**Judgment Format**:
```
# QueryID:Keywords:Weight
1:star wars:1
# QID:DocID:Relevance:Features
1:12345:4:1.0 2.5 3.2
1:67890:3:1.2 2.1 3.5
```

**Feature Set**: List of features to extract (e.g., BM25, TF-IDF, custom features)

**Model**: RankLib model (XML for Solr, JSON for Elasticsearch/OpenSearch)

---

## Client Abstraction Pattern

### Design Pattern: Strategy + Abstract Factory

The client architecture uses the **Strategy Pattern** for interchangeable search engine implementations and an **Abstract Base Class** to enforce a consistent interface.

### BaseClient Interface

```python
class BaseClient(ABC):
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    def create_index(self, index: str) -> None: ...
    
    @abstractmethod
    def query(self, index: str, query: QueryParams) -> JSONDictList: ...
    
    # ... 15+ more abstract methods
```

### Implementation Pattern

Each client implementation:
1. Inherits from `BaseClient`
2. Implements all abstract methods
3. Handles search engine-specific query formats
4. Converts between unified types and engine-specific formats

### Example: Query Execution

```python
# Unified interface
results = client.query(index, query_dict)

# Elasticsearch/OpenSearch implementation
def query(self, index: str, query: QueryParams) -> JSONDictList:
    response = self.es.search(index=index, body=query)
    return self._extract_results(response)

# Solr implementation  
def query(self, index: str, query: QueryParams) -> JSONDictList:
    response = self.solr.search(index, **query)
    return self._extract_results(response)
```

### Benefits

- **Code Reuse**: Library code works with any search engine
- **Testability**: Easy to mock clients for testing
- **Extensibility**: Add new engines by implementing `BaseClient`
- **Consistency**: Same operations across all engines

---

## Module Organization

### Package Structure

```
ltr/
├── __init__.py           # Public API exports
├── types.py              # Type aliases and shared types
├── logger.py             # Logging configuration
│
├── client/               # Search engine clients
│   ├── base_client.py
│   ├── elastic_client.py
│   ├── opensearch_client.py
│   └── solr_client.py
│
├── clickmodels/          # Click model implementations
│   ├── ubm.py
│   ├── pbm.py
│   └── ...
│
├── helpers/              # Utility modules
│   ├── movies.py
│   ├── handle_resp.py
│   └── ...
│
└── [core modules]        # Main LTR functionality
    ├── search.py
    ├── judgments.py
    ├── ranklib.py
    ├── evaluate.py
    └── ...
```

### Public API (`ltr/__init__.py`)

The public API is intentionally minimal:

```python
from ltr import download, evaluate, rre_table, search
```

This keeps the API surface small and discoverable.

### Type System (`ltr/types.py`)

Centralized type aliases for:
- JSON structures: `JSONDict`, `JSONDictList`
- Search types: `QueryParams`, `SearchResult`
- Feature types: `FeatureConfig`, `ModelPayload`
- Judgment types: `JudgmentList`, `QueryKeywordMap`

---

## Key Design Patterns

### 1. Abstract Base Class (ABC)

**Used in**: `BaseClient`

**Purpose**: Enforce interface contract across implementations

**Benefits**:
- Type safety
- Clear interface documentation
- Prevents incomplete implementations

### 2. Strategy Pattern

**Used in**: Client implementations, query builders

**Purpose**: Interchangeable algorithms (different search engines, query formats)

**Example**: `es_ltr_query()` vs `solr_ltr_query()` - same purpose, different implementation

### 3. Factory Pattern (Implicit)

**Used in**: Client instantiation

**Pattern**: Each client has its own constructor, but could be abstracted:

```python
# Current (implicit factory)
client = ElasticClient(url="http://localhost:9200")

# Potential explicit factory
client = create_client("elastic", url="http://localhost:9200")
```

### 4. Iterator Pattern

**Used in**: `JudgmentsReader`, document indexing

**Purpose**: Lazy evaluation, memory efficiency

**Example**: `JudgmentsReader` yields judgments one at a time rather than loading all into memory

### 5. Builder Pattern (Partial)

**Used in**: Query construction

**Pattern**: Functions build complex query dictionaries step by step

**Example**: `es_ltr_query()` builds Elasticsearch query structure

### 6. Retry Pattern with Exponential Backoff

**Used in**: `ltr/helpers/retry.py`, client operations

**Purpose**: Handle transient failures gracefully

**Pattern**: Retry operations with increasing delays between attempts

**Example**: `retry_on_connection_error()` retries connection failures with exponential backoff

---

## Integration Points

### External Dependencies

**Note:** For detailed dependency analysis, version concerns, and recommendations, see [`CODEBASE_REVIEW.md#dependencies`](CODEBASE_REVIEW.md#dependencies).

1. **Search Engines** (via HTTP APIs):
   - Elasticsearch 7.16.2
   - OpenSearch 2.2.0
   - Solr (via pysolr)

2. **ML Libraries**:
   - RankLib (Java, via subprocess)
   - scikit-learn
   - xgboost

3. **Data Processing**:
   - pandas
   - numpy

4. **Notebook Infrastructure**:
   - Jupyter
   - ipykernel

### Integration Architecture

```
┌─────────────────┐
│  hello-ltr      │
│  (Python)       │
└────────┬────────┘
         │
         ├─── HTTP ───► Elasticsearch/OpenSearch/Solr
         │
         ├─── Subprocess ───► RankLib (Java)
         │
         └─── File I/O ───► Judgment files, models
```

### Docker Integration

The system is designed to work with search engines running in Docker containers:

- **Development**: Local Python + Docker search engines
- **Full Docker**: Everything in containers (notebooks + search engines)

**Container Architecture**:
```
┌─────────────────┐
│  Jupyter        │  Port 8888
│  Container      │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬────────────┐
    │         │          │            │
┌───▼───┐ ┌──▼────┐ ┌───▼────┐ ┌─────▼────┐
│Elastic│ │OpenS. │ │ Solr   │ │ Kibana   │
│ 9200  │ │ 9201  │ │ 8983   │ │  5601    │
└───────┘ └───────┘ └────────┘ └──────────┘
```

---

## Deployment Architecture

### Development Setup

**Option 1: Full Docker**
```bash
docker compose up
```
- All services in containers
- Notebooks persist in container (ephemeral)

**Option 2: Hybrid**
```bash
# Search engines in Docker
cd notebooks/elasticsearch && docker compose up

# Jupyter locally
uv sync && uv run jupyter notebook
```
- Search engines containerized
- Jupyter runs locally with venv
- Notebooks persist on host

### Production Considerations

**Current State**: Tutorial/educational project, not production-ready

**Production Requirements** (if adapted):
- Connection pooling for clients
- Retry logic for network operations
- Authentication/authorization
- Error handling and monitoring
- Resource limits and quotas
- Model versioning and rollback

---

## Type System

**Note:** For comprehensive type alias documentation and usage guide, see [`TYPE_ALIASES_GUIDE.md`](TYPE_ALIASES_GUIDE.md).

### Type Aliases (`ltr/types.py`)

The project uses extensive type aliases for consistency. See [`TYPE_ALIASES_GUIDE.md`](TYPE_ALIASES_GUIDE.md) for complete list and usage examples.

**Key Type Categories:**
- JSON structures: `JSONDict`, `JSONDictList`
- Search types: `QueryParams`, `SearchResult`
- Feature types: `FeatureConfig`, `ModelPayload`
- Judgment types: `JudgmentList`, `QueryKeywordMap`

### Type Checking

**Note:** For detailed type checking configuration and current status, see [`CODEBASE_REVIEW.md`](CODEBASE_REVIEW.md) section 5.1 (Test Infrastructure Components - Type Checking in Tests).

- **Tool**: Pyright (configured in `standard` mode)
- **Coverage**: All library code and Python files in notebooks (excludes `.ipynb` files)
- **Status**: 0 errors, 2 warnings (library-related)
- **Current State**: No type annotations in most code (gradual addition needed)

### Benefits

- **Documentation**: Types serve as inline documentation
- **IDE Support**: Better autocomplete and error detection
- **Refactoring**: Safer code changes
- **Consistency**: Shared types ensure compatibility

---

## Extension Points

### Adding a New Search Engine

1. Create new client class inheriting from `BaseClient`
2. Implement all abstract methods
3. Handle engine-specific query formats
4. Add query builder function (if needed)
5. Update `search()` function to handle new engine

### Adding a New Click Model

1. Create module in `ltr/clickmodels/`
2. Implement attractiveness/satisfaction estimation
3. Follow existing model interface patterns
4. Add to `clickmodels/__init__.py` exports

### Adding New Features

1. Define feature in feature set configuration
2. Ensure feature extraction in `log_query()`
3. Update RankLib training set generation if needed

---

## Performance Considerations

**Note:** For test performance metrics, see [`tests/performance/PERFORMANCE_RESULTS.md`](tests/performance/PERFORMANCE_RESULTS.md). For code performance issues and recommendations, see [`CODEBASE_REVIEW.md#performance`](CODEBASE_REVIEW.md#performance).

### Current Optimizations

- **Lazy Iteration**: Judgments read on-demand
- **Bulk Operations**: Batch indexing where possible
- **Connection Reuse**: Client instances reuse HTTP connections
- **Retry Logic**: Exponential backoff for transient failures (`ltr/helpers/retry.py`)
  - Handles connection errors, timeouts, and timing-related errors
  - Configurable retry attempts and backoff multipliers

### Known Performance Issues

1. ✅ **Global Mutable State**: ~~`base_es_query` in `search.py` (thread-safety concern)~~ - **RESOLVED** (December 23, 2025) - No global mutable state found in `search.py`
2. ✅ **Inefficient Grouping**: ~~`_judgments_by_qid()` could use `itertools.groupby`~~ - **RESOLVED** (December 23, 2025) - Now uses `defaultdict(list)` for efficient grouping
3. ✅ **Memory Usage**: ~~Some operations load entire datasets~~ - **OPTIMIZED** (December 23, 2025) - Functions now accept iterators; `load_judgments()` optimized for single-pass statistics

### Optimization Opportunities

- ✅ Use `defaultdict` for judgment grouping - **COMPLETE** (December 23, 2025)
- ⚠️ Add caching for feature set lookups - **NOT IMPLEMENTED** (see CODEBASE_REVIEW.md)
- Implement connection pooling
- Add lazy loading for large datasets

---

## Security Considerations

### Current State

- **Credentials**: No hardcoded secrets (uses environment/config)
- **Input Validation**: Comprehensive validation module (`ltr/validation.py`)
  - Index name validation (alphanumeric, underscore, hyphen; max 255 chars)
  - Model/feature set name validation
  - Keyword validation (max 10,000 chars)
  - Prevents injection attacks through strict pattern matching
- **Query Sanitization**: Solr queries use `solr_escape.py` for escaping special characters
- **Retry Logic**: Exponential backoff for transient connection errors (`ltr/helpers/retry.py`)

### Security Recommendations

1. **Authentication**: Add auth support for production use
2. **HTTPS**: Use encrypted connections in production
3. **Rate Limiting**: Consider adding rate limits for API calls
4. **Audit Logging**: Add audit logs for sensitive operations (model submission, index deletion)

---

## Testing Architecture

**Note:** For comprehensive testing documentation, see [`tests/README.md`](tests/README.md) for test suite details and [`CODEBASE_REVIEW.md`](CODEBASE_REVIEW.md) section 5.1 for infrastructure status and improvements.

### Test Structure

```
tests/
├── unit/              # Unit tests for individual modules
├── integration/       # Integration tests with real search engines
├── notebooks/        # Notebook execution tests
└── conftest.py       # Shared fixtures and configuration
```

### Test Patterns

- **Unit Tests**: Mock clients, test logic in isolation (88 tests, 100% passing)
- **Integration Tests**: Real Docker containers, end-to-end workflows (8 tests, 100% passing)
- **Notebook Tests**: Execute notebooks, verify outputs (35 tests, 54%+ passing)

### Test Infrastructure

- **Docker**: Isolated search engine instances (per-worker containers)
- **Pytest**: Test framework with fixtures
- **Parallel Execution**: pytest-xdist with 12 workers
- **Coverage**: pytest-cov (32.24% overall coverage - see [`CODEBASE_REVIEW.md`](CODEBASE_REVIEW.md) section 5.1 for details)

---

## Future Architecture Considerations

### Potential Improvements

1. **Dependency Injection**: Better testability and flexibility
2. **Factory Pattern**: Explicit client factory function
3. **Context Managers**: Resource cleanup (connections, files)
4. **Async Support**: Async/await for concurrent operations
5. **Plugin System**: Dynamic loading of click models
6. **Configuration Management**: Centralized config (e.g., pydantic settings)

### Technical Debt

See `CODEBASE_REVIEW.md` for detailed technical debt items, including:
- Global mutable state
- Error handling improvements
- Dependency updates
- API documentation generation

---

## References

- **Architecture Decision Records**: See `adr/README.md` for historical architectural decisions
- **Codebase Review**: See `CODEBASE_REVIEW.md` for detailed code analysis
- **Test Documentation**: See `tests/README.md` for testing architecture
- **User Guide**: See `README.md` for usage instructions
- **Type Guide**: See `TYPE_ALIASES_GUIDE.md` for type system details

---

**Document Version**: 1.1  
**Last Updated**: December 21, 2025

