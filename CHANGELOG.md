# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Type alias system with comprehensive type aliases guide (`TYPE_ALIASES_GUIDE.md`)
- Centralized logging configuration module (`ltr/logger.py`)
- Pyright type checking configuration and integration
- CI/CD workflow with GitHub Actions (`.github/workflows/tests.yml`) for automated testing
- Dependabot configuration for automated dependency updates (`.github/dependabot.yml`)
- Input validation module (`ltr/validation.py`) for security and data integrity
- Type stubs for third-party libraries (pandas, plotly, plotnine, sklearn) in `stubs/` directory
- CI linting workflow
- Naming conventions documentation (`NAMING_CONVENTIONS.md`)
- Pre-commit hooks infrastructure (commit-msg hook, wrapper script, setup script)
- Scripts for running failing notebook tests individually (`run_failing_tests.py`)
- Script to run all notebook tests (`run_all_notebook_tests.py`)
- Slow test detection and reporting
- Test performance measurement utilities
- Test cleanup utilities (`tests/cleanup_test_containers.py`)
- Test investigation utilities (`tests/investigate_fast_failures.py`)
- Test comparison utilities (`tests/compare_performance.py`)
- Docker compose test files for test isolation
- `SEARCH_FOR_DEVELOPERS.md` documentation with definitions for judgment lists and corpus
- Comprehensive docstrings throughout the codebase
- Comprehensive test coverage for validation module (`tests/unit/test_validation.py`)
- Significant expansion of judgment list tests (`tests/unit/test_judg_list.py`)
- Centralized exception classes (`ltr/exceptions.py`) with structured exception hierarchy
- Retry logic with exponential backoff (`ltr/helpers/retry.py`) for handling transient failures
- Response type definitions (`ltr/client/responses.py`) for Elasticsearch/OpenSearch clients
- Client factory functions for test environments (`tests/client_factory.py`) using dependency injection
- Fast fail for validation error handling in tests
- Debug mode for tests with enhanced verbosity
- Performance optimization: using `defaultdict` for efficient judgment grouping in `_judgments_by_qid`
- `ElasticBaseClient` mixin class (`ltr/client/elastic_base_client.py`) for shared Elasticsearch/OpenSearch functionality, reducing code duplication
- Modular test fixture architecture with separate modules for container management, health checks, file locking, and pytest hooks
- Enhanced error handling in RankLib integration with detailed error messages and timeout handling
- Comprehensive test coverage for download, exceptions, logger, client factory, and patch utilities
- Advanced usage documentation (`ADVANCED_USAGE.md`) covering direct client access, custom retry logic, and advanced patterns
- Notebook testing recommendations document (`NOTEBOOK_TESTING_RECOMMENDATIONS.md`) with tool evaluation and best practices
- Script to update notebooks with factory functions (`scripts/dev/update_notebooks_factory_functions.py`)
- Dependency update tracking document (`REMAINING_DEPENDENCY_UPDATES.md`)

### Changed
- Migrated from `requirements.txt` to `pyproject.toml` for dependency management
- Updated all code to use centralized logging configuration
- Updated notebooks to work with new type system and API changes
- Reorganized tests into `unit/`, `integration/`, and `notebooks/` directories
- Improved test infrastructure with shared helpers (`client_test_helpers.py`)
- Migrated test framework to pytest with parallelized testing
- Updated Docker documentation to emphasize `docker compose` (replacing deprecated `docker-compose`)
- Improved Docker configuration with modern best practices
- Updated code to use f-strings for better readability
- Replaced unnecessary list comprehensions with simple lists
- Removed empty parentheses from class definitions
- Updated shell interaction code to be less exploitable
- Improved error messaging in tests
- Enhanced notebook error logging
- Updated search query functions (`ltr/search.py`) to use input validation
- Improved click models (PBM, UBM) to use centralized logging instead of print statements
- Enhanced test coverage for search functionality (`tests/unit/test_search.py`)
- Updated architecture documentation (`ARCHITECTURE.md`) with:
  - Documentation for validation, logging, and retry helper modules
  - Updated Security Considerations section reflecting current validation implementation
  - Updated Performance Considerations section with retry logic details
  - Added Retry Pattern with Exponential Backoff to design patterns section
  - Fixed date inconsistencies throughout document
- Updated main README with improved documentation
- Replaced monkey patching with dependency injection for client ports in tests
- Disabled parallelization for Docker tests by default to reduce resource consumption and prevent timeouts
- Refactored Elasticsearch and OpenSearch clients for improved error handling and retry logic
- Simplified test fixtures: removed `cleanup_registry` fixture, now using pytest's built-in `tmp_path` fixture
- Refactored test infrastructure: split monolithic `tests/conftest.py` into modular fixture modules (`tests/fixtures/`) for better maintainability
- Refactored Elasticsearch and OpenSearch clients to use `ElasticBaseClient` mixin, reducing code duplication
- Enhanced RankLib error handling with detailed error messages, timeout support, and better exception handling
- Updated all notebooks to use factory functions for client creation
- Updated dependencies

### Fixed
- Fixed bug in Dockerfile requiring use of `uv`
- Fixed invalid search response handling in OpenSearch and Elasticsearch clients
- Fixed feature set not found error handling (NullPointerException)
- Improved handling of TransportError: unknown
- Fixed errors in notebooks causing tests to fail
- Better handling of errors with featuresets and models
- Fixed timeout issues in test runner
- Fixed port availability handling when running tests
- Fixed Docker container dependency issues
- Fixed linting and typing errors throughout codebase
- Fixed RankLib error handling when None values are passed, preventing runtime errors
- Improved error messages for RankLib download and training operations

### Security
- Updated code when interacting with shell to do so in a less exploitable manner
- Added input validation for index names, model names, and keywords to prevent injection attacks
- Implemented query sanitization for Solr queries to prevent query injection
- Added validation for all user-provided inputs in search functions (`es_ltr_query`, `solr_ltr_query`)

## [0.1.0] - 2024-08-26

### Added
- Support for multiple search engines (Elasticsearch, OpenSearch, Solr)
- Learning to Rank (LTR) functionality across all supported search engines
- RankLib integration for model training
- Click models implementation (Cascade, COEC, Conversion, PBM, SDBN, UBM)
- Jupyter notebook tutorials organized by search engine
- Docker-based development environment
- RRE (Relevance Ranking Evaluation) integration
- Type system with comprehensive annotations
- Test infrastructure with unit, integration, and notebook tests

### Changed
- Updated Elasticsearch and Kibana versions
- Improved OpenSearch test coverage and fixes
- Updated Solr and Python library dependencies

### Fixed
- Fixed test failures across multiple search engines
- Fixed Docker container dependencies
- Fixed various bugs in OpenSearch integration

---

[Unreleased]: https://github.com/your-org/hello-ltr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/hello-ltr/releases/tag/v0.1.0

