# TODO Maybe

This file contains potential future improvements that are not currently prioritized but may be worth considering.
## Testing Infrastructure

### Notebook Test Issues
- **Description**: Some notebooks still timing out (1-2 notebooks with expensive operations not covered by automatic patching)
- **Status**: These are notebook content issues, not test infrastructure issues
- **Priority**: Low - infrastructure is working, content needs optimization

### Test Coverage Improvements
- **Description**: Increase coverage for client implementations and helper modules
- **Benefit**: Better test coverage, more confidence in code quality
- **Effort**: Medium - requires writing additional tests
- **Status**: Low priority
- **Current State**: Overall code coverage is 32.24% (as of December 2025). Client implementations may have lower coverage (estimated 19-30% range).

### Property-Based Testing
- **Description**: Consider adding property-based tests using Hypothesis
- **Benefit**: Can find edge cases and unexpected behaviors automatically
- **Effort**: Medium - requires learning Hypothesis and refactoring some tests
- **Status**: Low priority

### Mutation Testing
- **Description**: Add mutation testing (mutmut) for critical paths
- **Benefit**: Helps identify weak tests and improve test quality
- **Effort**: Medium - requires setup and analysis of mutation test results
- **Status**: Low priority

### Strict Mode Type Checking
- **Description**: Address ~100+ type issues in clickmodels and client modules revealed by strict mode testing
- **Benefit**: Would enable upgrading to stricter type checking, better type safety
- **Effort**: High - requires significant refactoring across multiple modules
- **Status**: Not prioritized - current type checking works well for most use cases

### Optional Dependency Groups
- **Description**: Move test dependencies to optional dependency groups in `pyproject.toml`
- **Benefit**: Cleaner separation of production vs test dependencies
- **Effort**: Low - straightforward configuration change
- **Status**: Not prioritized - current approach (all deps in one list) works fine and is simpler

**Example:**
```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-xdist>=3.5.0",
    "pytest-timeout>=2.2.0",
    "pytest-html>=4.1.0",
    "pytest-cov>=4.0.0",
]
```

### Test Fixtures and Factories
- **Description**: Expand test data factories and extract additional reusable fixtures
- **Benefit**: More maintainable test code, easier to create test data
- **Effort**: Medium - requires refactoring existing tests and creating additional factories
- **Status**: Low priority - basic fixture infrastructure exists (`tests/fixtures/`, `tests/client_factory.py`)

**Current State:**
- Container fixtures exist (`tests/fixtures/container_fixtures.py`)
- Client factory exists (`tests/client_factory.py`)
- Health check and container management fixtures exist

**Potential Improvements:**
- Create test data factories for common objects (judgments, queries, feature sets)
- Extract more reusable fixtures for test data scenarios
- Consider using `factory_boy` or similar for complex test data
- Document fixture usage patterns
- Create notebook-specific test data fixtures (as mentioned in `NOTEBOOK_TESTING_RECOMMENDATIONS.md`)

### Test Data Versioning
- **Description**: Version test data fetched from external URLs
- **Benefit**: Tests won't break if external data changes
- **Effort**: Low - add versioning/checksums to external data fetches
- **Status**: Low priority

**Current Issue:**
- Test data fetched from external URL without versioning (e.g., `http://es-learn-to-rank.labs.o19s.com/tmdb.json`)
- External dependency can change, causing test failures

## Development Metrics

- **Description**: Measurement infrastructure is in place via `measure_dev_metrics.py` script. All workflows are now active and configured with build time tracking.
- **Status**: Infrastructure ready, awaiting workflow data
- **Last Updated**: 2025-12-31
- **Note**: To measure these metrics, ensure GitHub CLI (`gh`) is authenticated (`gh auth login`) and run the measurement script. The script queries GitHub API for workflow runs, PRs, and issues. Once workflows start running, build time data will be available for measurement.

## Other Potential Improvements

_Add other low-priority items here as they come up..._

