# Naming Conventions Guide

**Last Updated:** December 21, 2025

This document outlines the naming conventions used in this project. All code should follow PEP 8 naming conventions unless explicitly documented exceptions apply.

## Standard PEP 8 Naming Conventions

### Functions and Variables
- **Use**: `snake_case`
- **Examples**:
  ```python
  def calculate_score():
      user_id = "123"
      feature_vector = [1, 2, 3]
  ```

### Classes
- **Use**: `PascalCase`
- **Examples**:
  ```python
  class SearchClient:
      pass
  
  class RanklibResult:
      pass
  ```

### Constants
- **Use**: `UPPER_SNAKE_CASE`
- **Examples**:
  ```python
  MAX_RESULTS = 1000
  DEFAULT_INDEX = "tmdb"
  API_BASE_URL = "https://api.example.com"
  ```

### Module Names
- **Use**: `snake_case`
- **Examples**: `mart_model.py`, `inject_typos.py`, `es_url_parse.py`

### Private Attributes/Methods
- **Use**: Leading underscore prefix (`_private_method`, `_private_attr`)
- **Examples**:
  ```python
  class MyClass:
      def _internal_helper(self):
          pass
      
      _private_cache = {}
  ```

## Intentional Violations

This project maintains a few intentional violations of PEP 8 naming conventions for specific reasons:

### 1. RanklibResult Class Attributes

**Location**: `ltr/helpers/ranklib_result.py`

**Violation**: camelCase attribute names (`trainingLogs`, `foldResults`, `kcvTestAvg`, etc.)

**Reason**: These classes mirror RankLib's (Java library) output format. Maintaining camelCase ensures consistency with the external API and makes the code easier to understand when working with RankLib output.

**Allowed Usage**:
```python
result = RanklibResult(...)
logs = result.trainingLogs  # ✅ Allowed - matches external API
avg = result.kcvTestAvg     # ✅ Allowed - matches external API
```

**When to Use**: Only when working with RankLib data structures. All new code should use `snake_case`.

### 2. Machine Learning Conventions in Notebooks

**Location**: Notebooks in `notebooks/` directory

**Violation**: Parameter name `X` for feature matrices (violates N803)

**Reason**: Follows sklearn/pandas/scipy conventions where `X` represents feature matrices and `y` represents target variables. This is widely accepted in the ML community.

**Allowed Usage**:
```python
def predict(self, X, use_original=False):  # ✅ Allowed in notebooks - ML convention
    pass
```

**When to Use**: Only in notebook code for ML-related functions. All library code should use descriptive names like `feature_matrix` or `features`.

**Suppression**: All instances are suppressed with `# noqa: N803` comments.

## Enforcement

### Automated Checks

Naming conventions are enforced automatically:

1. **Ruff Linter**: Runs locally and in CI/CD
   ```bash
   # Check Python files
   uv run ruff check --select N ltr/ rre/ utils/ tests/ *.py
   
   # Check notebooks
   uv run ruff check --select N notebooks/
   ```

2. **CI/CD Pipeline**: GitHub Actions workflow (`.github/workflows/lint-full.yml`) runs on every push and pull request, including naming convention checks via Ruff

### Violation Handling

- **New violations**: Will cause CI/CD to fail. Fix violations before merging.
- **Existing violations**: Documented in this document (see [Intentional Violations](#intentional-violations) section) with reasoning
- **Suppressing violations**: Use `# noqa: N803` (or appropriate code) with a comment explaining why

## Best Practices

### For New Code

1. **Always use PEP 8 naming**: Follow `snake_case` for functions/variables, `PascalCase` for classes
2. **Use descriptive names**: Prefer `feature_vector` over `fv`, `user_id` over `uid` (unless `uid` is a well-known abbreviation)
3. **Avoid abbreviations**: Unless the abbreviation is widely understood (e.g., `id`, `url`, `api`)
4. **Be consistent**: If you see a naming pattern in the codebase, follow it

### For Notebooks

1. **Follow ML conventions**: `X` and `y` are acceptable for feature matrices and targets
2. **Use descriptive names**: For non-ML code, use descriptive `snake_case` names
3. **Suppress intentionally**: If you need to use a non-PEP 8 name, add `# noqa: N803` with a comment

### When Working with External APIs

1. **Match external format**: If an external API uses camelCase (like RankLib), maintain that in the data structures
2. **Document the exception**: Add a comment explaining why the violation exists
3. **Isolate violations**: Keep API-compatibility violations in specific modules/classes

## Examples

### ✅ Good Examples

```python
# Functions and variables
def calculate_relevance_score(query, document):
    feature_vector = extract_features(query, document)
    return score_features(feature_vector)

# Classes
class ElasticsearchClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

# Constants
MAX_BATCH_SIZE = 1000
DEFAULT_TIMEOUT = 30

# Private methods
class MyClass:
    def _validate_input(self, data):
        pass
```

### ❌ Bad Examples

```python
# Don't use camelCase for functions/variables
def calculateRelevanceScore():  # ❌
    userId = "123"  # ❌

# Don't use snake_case for classes
class elasticsearch_client:  # ❌

# Don't use lowercase for constants
max_batch_size = 1000  # ❌ (unless it's a module-level variable, not a constant)
```

## Related Documentation

- **Violations**: All intentional violations are documented in the [Intentional Violations](#intentional-violations) section above
- **PEP 8**: [Python Enhancement Proposal 8](https://peps.python.org/pep-0008/)
- **Ruff Documentation**: [Ruff Naming Rules](https://docs.astral.sh/ruff/rules/#pep8-naming-n)
- **CI/CD Workflow**: See `.github/workflows/lint-full.yml` for automated enforcement

## Questions?

If you're unsure about a naming convention:
1. Check this document first
2. Look at similar code in the codebase
3. Run `ruff check --select N` to see if your code passes
4. When in doubt, follow PEP 8 strictly

