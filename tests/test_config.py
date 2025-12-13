"""
Test configuration constants for hello-ltr test suite.

This module contains test paths and ignored notebooks configuration.
Separated from conftest.py to avoid import anti-patterns.
"""

# Test configuration migrated from RunMostNotebooksTestCase
TEST_PATHS = [
    "./notebooks/",
    "./notebooks/solr/tmdb",
    "./notebooks/elasticsearch/tmdb",
    "./notebooks/elasticsearch/osc-blog",
    "./notebooks/opensearch/tmdb",
    "./notebooks/opensearch/osc-blog",
]

IGNORED_NOTEBOOKS = [
    # ========================================================================
    # Evaluation Notebooks
    # ========================================================================
    # These notebooks are excluded because they:
    # - Take 30+ minutes each to execute (too slow for CI/CD)
    # - Require significant computational resources (memory/CPU)
    # - Are primarily used for final validation, not development testing
    #
    # When to un-ignore:
    # - When you need to validate end-to-end evaluation workflows
    # - For release validation or pre-deployment checks
    # - When running manual validation suites
    #
    # What needs to be fixed to enable automated testing:
    # - Optimize evaluation logic to run faster (e.g., reduce dataset size)
    # - Add progress checkpoints to allow resuming long-running evaluations
    # - Consider splitting into smaller, focused evaluation notebooks
    # - Add resource usage monitoring and limits
    "./notebooks/solr/tmdb/evaluation (Solr).ipynb",
    "./notebooks/elasticsearch/tmdb/evaluation.ipynb",
    "./notebooks/opensearch/tmdb/evaluation.ipynb",
    # ========================================================================
    # XGBoost Notebooks
    # ========================================================================
    # These notebooks are excluded because they:
    # - Have complex dependencies (XGBoost + native libraries)
    # - Require specific system libraries (libgomp, etc.)
    # - May have platform-specific build requirements
    # - Can fail due to environment differences (Docker vs local)
    #
    # When to un-ignore:
    # - When XGBoost dependencies are fully stabilized across platforms
    # - For platform-specific test suites (e.g., Linux-only CI)
    # - When you need to validate XGBoost model training workflows
    #
    # What needs to be fixed to enable automated testing:
    # - Ensure XGBoost is properly installed in test Docker containers
    # - Add dependency validation before notebook execution
    # - Create platform-specific test configurations
    # - Add fallback handling for missing XGBoost dependencies
    # - Consider mocking XGBoost for faster unit tests
    "./notebooks/elasticsearch/tmdb/XGBoost.ipynb",
    "./notebooks/opensearch/tmdb/XGBoost.ipynb",
]
