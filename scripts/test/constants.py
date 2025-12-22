"""Constants for notebook test scripts."""

# Slow notebook patterns (matches tests/notebooks/test_notebooks.py)
# These notebooks typically take > 60 seconds to execute
SLOW_PATTERNS = [
    "netfix",
    "bayesian-optimization",
    "bigger bot",
    "lambda-mart",
    "feature_search",
    "evaluation",
    "ai-powered-search",  # Also slow
]

# Default timeout values (in seconds)
DEFAULT_TIMEOUT = 300  # 5 minutes
LONG_TIMEOUT = 600  # 10 minutes

# Common pytest arguments
DEFAULT_PYTEST_ARGS = ["-n", "1", "-v", "--no-cov", "--tb=short"]

# Failing notebooks lists
# NOTE: Different scripts use different lists for different purposes:
#
# 1. FAILING_TESTS_FLAT: Used by run_failing_tests.py and run_test_batch.py
#    - Flat list, ordered with fast tests first, slow tests last
#    - Used for sequential test runs with filtering options
#
# 2. FAILING_NOTEBOOKS_BY_ENGINE: Used by document_notebook_errors.py and analyze_notebook_tests.py
#    - Dictionary organized by engine (opensearch, elasticsearch, solr)
#    - Used for engine-specific analysis and documentation
#
# These lists may intentionally differ based on:
# - Which notebooks are actively being debugged
# - Whether the script needs engine-specific organization
# - Whether ordering matters (fast vs slow tests)

# Flat list of failing tests (ordered: fast first, slow last)
FAILING_TESTS_FLAT = [
    # Fast tests first (OpenSearch)
    "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
    "./notebooks/opensearch/tmdb/raw-opensearch-commands.ipynb",
    "./notebooks/opensearch/tmdb/sandbox.ipynb",
    "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
    "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
    # Fast tests first (Elasticsearch)
    "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
    "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # Fast tests first (Solr)
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
    # Slow tests last (will timeout after 5 minutes)
    "./notebooks/opensearch/tmdb/gonna need a bigger bot (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies.ipynb",
    "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
]

# Extended flat list (includes additional notebooks like Dataframes, tale-of-two-queries)
FAILING_TESTS_FLAT_EXTENDED = [
    # OpenSearch Notebooks
    "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/Dataframes.ipynb",
    "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
    "./notebooks/opensearch/tmdb/raw-opensearch-commands.ipynb",
    "./notebooks/opensearch/tmdb/sandbox.ipynb",
    "./notebooks/opensearch/tmdb/tale-of-two-queries (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/opensearch/tmdb/gonna need a bigger bot (OpenSearch).ipynb",
    "./notebooks/opensearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/opensearch/tmdb/netfix movies.ipynb",
    "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
    "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
    # Elasticsearch Notebooks
    "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
    "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
    "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
    "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
    "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
    "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
    "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
    "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    # Solr Notebooks
    "./notebooks/solr/tmdb/ai-powered-search.ipynb",
    "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
    "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
    "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
]

# Dictionary organized by engine (minimal set for error documentation)
FAILING_NOTEBOOKS_BY_ENGINE_MINIMAL = {
    "opensearch": [
        "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
        "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
        "./notebooks/opensearch/tmdb/sandbox.ipynb",
        "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
        "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
    ],
    "elasticsearch": [
        "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
        "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
        "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
        "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
        "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
        "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
        "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
        "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
    ],
    "solr": [
        "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
        "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
        "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
    ],
}

# Dictionary organized by engine (extended set for analysis)
FAILING_NOTEBOOKS_BY_ENGINE_EXTENDED = {
    "opensearch": [
        "./notebooks/opensearch/tmdb/hello-ltr (OpenSearch).ipynb",
        "./notebooks/opensearch/tmdb/opensearch-ltr-basics-project.ipynb",
        "./notebooks/opensearch/tmdb/sandbox.ipynb",
        "./notebooks/opensearch/tmdb/gonna need a bigger bot (OpenSearch).ipynb",
        "./notebooks/opensearch/tmdb/lambda-mart-in-python.ipynb",
        "./notebooks/opensearch/tmdb/netfix movies-random-forests.ipynb",
        "./notebooks/opensearch/tmdb/netfix movies.ipynb",
        "./notebooks/opensearch/osc-blog/osc-blog.ipynb",
        "./notebooks/opensearch/tmdb/term-stat-query.ipynb",
    ],
    "elasticsearch": [
        "./notebooks/elasticsearch/tmdb/hello-ltr (ES).ipynb",
        "./notebooks/elasticsearch/tmdb/term-stat-query.ipynb",
        "./notebooks/elasticsearch/tmdb/es-ltr-basics-project.ipynb",
        "./notebooks/elasticsearch/tmdb/raw-es-commands.ipynb",
        "./notebooks/elasticsearch/tmdb/sandbox.ipynb",
        "./notebooks/elasticsearch/tmdb/bayesian-optimization.ipynb",
        "./notebooks/elasticsearch/tmdb/gonna need a bigger bot (ES).ipynb",
        "./notebooks/elasticsearch/tmdb/lambda-mart-in-python.ipynb",
        "./notebooks/elasticsearch/tmdb/netfix movies-random-forests.ipynb",
        "./notebooks/elasticsearch/osc-blog/osc-blog.ipynb",
    ],
    "solr": [
        "./notebooks/solr/tmdb/ai-powered-search.ipynb",
        "./notebooks/solr/tmdb/gonna need a bigger bot (Solr).ipynb",
        "./notebooks/solr/tmdb/raw-solr-commands.ipynb",
        "./notebooks/solr/tmdb/tale-of-two-queries (Solr).ipynb",
    ],
}
