# Advanced Usage Patterns

**Last Updated:** December 31, 2025

This document covers advanced usage patterns for users who need more control and flexibility than the minimal public API provides. For basic usage, see the [README.md](README.md) and notebook examples.

---

## Table of Contents

1. [Overview](#overview)
2. [Direct Client Access](#direct-client-access)
3. [Accessing Underlying Search Engine Clients](#accessing-underlying-search-engine-clients)
4. [Custom Feature Extraction](#custom-feature-extraction)
5. [Click Models](#click-models)
6. [Custom Retry Logic](#custom-retry-logic)
7. [Custom Query Building](#custom-query-building)
8. [Advanced Judgments Processing](#advanced-judgments-processing)
9. [Direct RankLib Usage](#direct-ranklib-usage)
10. [Environment Configuration](#environment-configuration)

---

## Overview

The hello-ltr library provides a **minimal public API** (see [ADR-011](adr/011-minimal-public-api.md)):

```python
from ltr import download, evaluate, rre_table, search
```

For advanced use cases, you can import directly from submodules to access additional functionality:

```python
from ltr.client import ElasticClient, create_elastic_client
from ltr.judgments import Judgment, JudgmentsReader, JudgmentsWriter
from ltr.log import FeatureLogger
from ltr.clickmodels import ubm, pbm, cascade
from ltr.helpers.retry import retry_on_connection_error
```

---

## Direct Client Access

### Using Factory Functions

Factory functions provide explicit dependency injection for port configuration, making them suitable for both development and test environments:

```python
from ltr.client import create_solr_client, create_elastic_client, create_opensearch_client

# Factory functions use environment variables for port configuration
# In test environments: set SOLR_PORT, ELASTICSEARCH_PORT, OPENSEARCH_PORT
# In development: uses default ports (8983, 9200, 9201)

client = create_solr_client()  # Uses SOLR_PORT env var or default 8983
client = create_elastic_client()  # Uses ELASTICSEARCH_PORT env var or default 9200
client = create_opensearch_client()  # Uses OPENSEARCH_PORT env var or default 9201
```

### Direct Client Instantiation

For more control, you can instantiate clients directly:

```python
from ltr.client import SolrClient, ElasticClient, OpenSearchClient

# Direct instantiation with explicit port
solr_client = SolrClient(port=8983)
elastic_client = ElasticClient(port=9200, configs_dir="./configs")
opensearch_client = OpenSearchClient(port=9201, configs_dir="./configs")
```

### Client Factory Pattern Benefits

- **Explicit dependency injection**: Ports configured via constructor parameters
- **Environment-aware**: Test ports vs development ports
- **No runtime patching**: Cleaner than monkey-patching
- **Consistent pattern**: All notebooks use factory functions

---

## Accessing Underlying Search Engine Clients

For advanced use cases, you may need direct access to the underlying search engine client objects (Elasticsearch, OpenSearch, Solr).

### Elasticsearch

`ElasticClient` exposes the underlying client via the `.es` attribute:

```python
from ltr.client import create_elastic_client

client = create_elastic_client()

# Access underlying Elasticsearch client
es_client = client.es  # elasticsearch.Elasticsearch instance

# Use native Elasticsearch API
response = es_client.search(
    index="tmdb",
    body={
        "query": {"match_all": {}},
        "size": 10
    }
)

# Access cluster info
cluster_health = es_client.cluster.health()

# Use Elasticsearch-specific features not exposed by BaseClient
es_client.indices.put_settings(
    index="tmdb",
    body={"index": {"number_of_replicas": 2}}
)
```

### OpenSearch

`OpenSearchClient` exposes the underlying client via the `.opensearch` attribute:

```python
from ltr.client import create_opensearch_client

client = create_opensearch_client()

# Access underlying OpenSearch client
opensearch_client = client.opensearch  # opensearchpy.OpenSearch instance

# Use native OpenSearch API
response = opensearch_client.search(
    index="tmdb",
    body={
        "query": {"match_all": {}},
        "size": 10
    }
)

# Access cluster info
cluster_health = opensearch_client.cluster.health()

# Use OpenSearch-specific features not exposed by BaseClient
opensearch_client.indices.put_settings(
    index="tmdb",
    body={"index": {"number_of_replicas": 2}}
)
```

### Solr

`SolrClient` uses a `requests.Session` object for HTTP calls:

```python
from ltr.client import create_solr_client

client = create_solr_client()

# Access underlying requests session
solr_session = client.solr  # requests.Session instance

# Make direct HTTP calls to Solr
response = solr_session.get(
    f"{client.solr_base_ep}/tmdb/admin/ping"
)

# Use Solr-specific endpoints not exposed by BaseClient
response = solr_session.post(
    f"{client.solr_base_ep}/tmdb/update",
    json={"add": {"doc": {"id": "123", "title": "Test"}}},
    params={"commit": "true"}
)
```

### When to Use Direct Access

Use direct access when you need:
- **Search engine-specific features** not exposed by `BaseClient`
- **Performance optimizations** (e.g., bulk operations, connection pooling)
- **Administrative operations** (cluster management, index settings)
- **Custom query DSL** beyond what `BaseClient` provides
- **Debugging** search engine interactions

**Warning**: Direct access bypasses the abstraction layer and may break cross-engine compatibility. Use sparingly and document why it's necessary.

---

## Custom Feature Extraction

The `FeatureLogger` class provides fine-grained control over feature extraction:

### Basic Feature Logging

```python
from ltr.client import create_elastic_client
from ltr.log import FeatureLogger
from ltr.judgments import judgments_open
from itertools import groupby

client = create_elastic_client()
ftr_logger = FeatureLogger(
    client=client,
    index="tmdb",
    feature_set="my_featureset",
    drop_missing=True  # Discard judgments for missing documents
)

# Log features for judgments
with judgments_open("data/judgments.txt") as judgment_list:
    for qid, query_judgments in groupby(judgment_list, key=lambda j: j.qid):
        training_set, discarded = ftr_logger.log_for_qid(
            qid=qid,
            judgments=query_judgments,
            keywords=judgment_list.keywords(qid)
        )
        # training_set contains judgments with features attached
        # discarded contains judgments that were dropped (if drop_missing=True)
```

### Advanced Feature Logging

```python
from ltr.log import FeatureLogger

# Create logger with custom settings
ftr_logger = FeatureLogger(
    client=client,
    index="tmdb",
    feature_set="my_featureset",
    drop_missing=False  # Keep judgments even if documents are missing
)

# Clear logged judgments for reuse
ftr_logger.clear()

# Log features for specific query
training_set, discarded = ftr_logger.log_for_qid(
    qid=1,
    judgments=my_judgments,
    keywords="star wars"
)

# Access logged judgments
all_logged = ftr_logger.logged  # List of all judgments with features
```

### Batch Feature Extraction

For large datasets, you can process judgments in batches:

```python
from ltr.log import FeatureLogger
from ltr.judgments import Judgment

ftr_logger = FeatureLogger(client, index="tmdb", feature_set="features")

# Process judgments in batches
batch_size = 1000
all_training_data = []

with judgments_open("large_judgments.txt") as judgment_list:
    batch = []
    for judgment in judgment_list:
        batch.append(judgment)
        if len(batch) >= batch_size:
            # Process batch
            for qid, query_judgments in groupby(batch, key=lambda j: j.qid):
                training_set, _ = ftr_logger.log_for_qid(
                    qid=qid,
                    judgments=query_judgments,
                    keywords=judgment_list.keywords(qid)
                )
                all_training_data.extend(training_set)
            batch = []
            ftr_logger.clear()  # Clear for next batch
```

---

## Click Models

The library provides several click model implementations for implicit feedback:

### Available Click Models

```python
from ltr.clickmodels import ubm, pbm, cascade, coec, sdbn

# User Browsing Model (UBM)
from ltr.clickmodels.ubm import Model, update_attractiveness

# Position-Based Model (PBM)
from ltr.clickmodels.pbm import Model, update_attractiveness

# Cascade Model
from ltr.clickmodels.cascade import Model, update_attractiveness

# Click-Over-Expected-Click (COEC)
from ltr.clickmodels.coec import Model, update_attractiveness

# Sequential DBN Model
from ltr.clickmodels.sdbn import Model, update_attractiveness
```

### Using Click Models

```python
from ltr.clickmodels.ubm import Model, update_attractiveness

# Initialize model
model = Model()

# Process click data
clicks = [
    {"doc_id": "123", "position": 1, "clicked": True},
    {"doc_id": "456", "position": 2, "clicked": False},
    {"doc_id": "789", "position": 3, "clicked": True},
]

# Update attractiveness estimates
for click in clicks:
    update_attractiveness(
        model=model,
        doc_id=click["doc_id"],
        position=click["position"],
        clicked=click["clicked"]
    )

# Get attractiveness estimate
attractiveness = model.attractiveness("123")
```

### Custom Click Model Implementation

You can implement custom click models by following the pattern:

```python
from ltr.clickmodels.session import Session

class MyCustomModel:
    def __init__(self):
        self.attractiveness_estimates = {}
    
    def attractiveness(self, doc_id: str) -> float:
        return self.attractiveness_estimates.get(doc_id, 0.0)

def update_attractiveness(model: MyCustomModel, doc_id: str, position: int, clicked: bool):
    # Custom logic here
    if clicked:
        model.attractiveness_estimates[doc_id] = 1.0 / position
```

---

## Custom Retry Logic

The library provides retry utilities for handling transient failures:

### Basic Retry

```python
from ltr.helpers.retry import retry_on_connection_error

# Retry a function call on connection errors
result = retry_on_connection_error(
    func=lambda: client.query(index="tmdb", query={"match_all": {}}),
    max_retries=5,
    initial_delay=0.5,
    backoff_multiplier=1.5
)
```

### Custom Connection Error Detection

```python
from ltr.helpers.retry import retry_on_connection_error, is_opensearch_connection_error

# Use custom error detection
result = retry_on_connection_error(
    func=lambda: opensearch_operation(),
    max_retries=5,
    initial_delay=0.5,
    backoff_multiplier=1.5,
    is_connection_error=is_opensearch_connection_error
)
```

### Feature Set Query Retry

```python
from ltr.helpers.retry import retry_feature_set_query

# Retry feature set queries with timing error handling
response = retry_feature_set_query(
    query_func=lambda: client.feature_set(index="tmdb", name="my_featureset"),
    featureset="my_featureset",
    index="tmdb",
    client_name=client.name(),
    max_retries=5,
    initial_delay=0.2,
    backoff_multiplier=1.5
)
```

### Model Query Retry

```python
from ltr.helpers.retry import retry_model_query

# Retry model queries with timing error handling
response = retry_model_query(
    query_func=lambda: client.model_query(index="tmdb", model="my_model", keywords="test"),
    model_name="my_model",
    index="tmdb",
    client_name=client.name(),
    max_retries=5,
    initial_delay=0.5,
    backoff_multiplier=1.5
)
```

### Retry Until True

```python
from ltr.helpers.retry import retry_until_true

# Retry until a condition is met
retry_until_true(
    check_func=lambda: client.feature_set(index="tmdb", name="my_featureset") is not None,
    max_retries=3,
    initial_delay=0.1,
    backoff_multiplier=2.0,
    error_message="Feature set not available"
)
```

---

## Custom Query Building

Instead of using the high-level `search()` function, you can build queries manually:

### Elasticsearch/OpenSearch Queries

```python
from ltr.search import es_ltr_query
from ltr.client import create_elastic_client

client = create_elastic_client()

# Build LTR query manually
query = es_ltr_query(keywords="star wars", model_name="my_model")

# Execute query
results = client.query(index="tmdb", query=query)

# Custom query with additional parameters
custom_query = {
    "query": {
        "sltr": {
            "params": {"keywords": "star wars"},
            "model": "my_model"
        }
    },
    "size": 20,
    "_source": ["title", "overview"]
}
results = client.query(index="tmdb", query=custom_query)
```

### Solr Queries

```python
from ltr.search import solr_ltr_query
from ltr.client import create_solr_client

client = create_solr_client()

# Build LTR query manually
query = solr_ltr_query(keywords="star wars", model_name="my_model")

# Execute query
results = client.query(index="tmdb", query=query)

# Custom query with additional parameters
custom_query = {
    "q": "*:*",
    "rq": "{!ltr model=my_model reRankDocs=1000}",
    "fl": "id,title,score",
    "rows": 20
}
results = client.query(index="tmdb", query=custom_query)
```

### Direct Query Execution

```python
from ltr.client import create_elastic_client

client = create_elastic_client()

# Use log_query for feature extraction
feature_results = client.log_query(
    index="tmdb",
    featureset="my_featureset",
    ids=["123", "456"],  # Restrict to specific documents
    params={"keywords": "star wars"}
)

# Use model_query for LTR ranking
ranked_results = client.model_query(
    index="tmdb",
    model="my_model",
    keywords="star wars"
)
```

---

## Advanced Judgments Processing

### Reading Judgments

```python
from ltr.judgments import JudgmentsReader, Judgment, judgments_open

# Using context manager (recommended)
with judgments_open("data/judgments.txt") as judgment_list:
    for judgment in judgment_list:
        print(f"QID: {judgment.qid}, DocID: {judgment.docId}, Relevance: {judgment.grade}")
    
    # Access query keywords
    keywords = judgment_list.keywords(qid=1)

# Using JudgmentsReader directly
reader = JudgmentsReader("data/judgments.txt")
for judgment in reader:
    print(judgment)
reader.close()
```

### Writing Judgments

```python
from ltr.judgments import JudgmentsWriter, Judgment

# Create judgments
judgments = [
    Judgment(qid=1, docId="123", grade=4),
    Judgment(qid=1, docId="456", grade=3),
    Judgment(qid=2, docId="789", grade=5),
]

# Write judgments
with JudgmentsWriter("output/judgments.txt") as writer:
    # Add query
    writer.add_query(qid=1, keywords="star wars", weight=1)
    writer.add_query(qid=2, keywords="batman", weight=1)
    
    # Add judgments
    for judgment in judgments:
        writer.add_judgment(judgment)
```

### Custom Judgments Processing

```python
from ltr.judgments import Judgment, judgments_open
from collections import defaultdict

# Group judgments by query
query_judgments = defaultdict(list)

with judgments_open("data/judgments.txt") as judgment_list:
    for judgment in judgment_list:
        query_judgments[judgment.qid].append(judgment)

# Process each query's judgments
for qid, judgments in query_judgments.items():
    keywords = judgment_list.keywords(qid)
    print(f"Query {qid}: {keywords}")
    print(f"  {len(judgments)} judgments")
    
    # Filter by relevance grade
    high_relevance = [j for j in judgments if j.grade >= 4]
    print(f"  {len(high_relevance)} high relevance judgments")
```

---

## Direct RankLib Usage

For advanced model training, you can use RankLib functions directly:

```python
from ltr.ranklib import train, convert_model

# Train a model directly
model_output = train(
    training_set="data/training.txt",
    algorithm="lambdamart",
    params={"trees": 1000, "leaves": 10}
)

# Convert model for specific search engine
solr_model = convert_model(model_output, target="solr")
elasticsearch_model = convert_model(model_output, target="elasticsearch")
opensearch_model = convert_model(model_output, target="opensearch")
```

### Custom Training Parameters

```python
from ltr.ranklib import train

# Train with custom parameters
model = train(
    training_set="data/training.txt",
    algorithm="lambdamart",
    params={
        "trees": 2000,
        "leaves": 20,
        "shrinkage": 0.1,
        "tc": 256,
        "estop": 100
    }
)
```

---

## Environment Configuration

### Port Configuration

Factory functions use environment variables for port configuration:

```python
import os

# Set ports for test environments
os.environ["SOLR_PORT"] = "8984"
os.environ["ELASTICSEARCH_PORT"] = "9201"
os.environ["OPENSEARCH_PORT"] = "9202"

# Factory functions will use these ports
from ltr.client import create_solr_client
client = create_solr_client()  # Uses port 8984
```

### Docker Environment

```python
import os

# Indicate Docker environment
os.environ["LTR_DOCKER"] = "1"

# Clients will use Docker hostnames (e.g., "solr", "elasticsearch")
from ltr.client import create_solr_client
client = create_solr_client()  # Connects to "solr" hostname
```

### Configuration Directory

```python
import os

# Set configuration directory for Elasticsearch/OpenSearch
os.environ["NOTEBOOK_CONFIGS_DIR"] = "/path/to/configs"

# Factory functions will use this directory
from ltr.client import create_elastic_client
client = create_elastic_client()  # Uses /path/to/configs
```

---

## Best Practices

### When to Use Advanced Patterns

1. **Direct Client Access**: When you need search engine-specific features
2. **Custom Feature Extraction**: When you need fine-grained control over feature logging
3. **Click Models**: When working with implicit feedback data
4. **Custom Retry Logic**: When you need specialized retry behavior
5. **Custom Query Building**: When you need queries beyond the standard LTR pattern
6. **Advanced Judgments Processing**: When processing large or complex judgment files

### Performance Considerations

- **Batch Operations**: Use batch processing for large datasets
- **Connection Reuse**: Reuse client instances rather than creating new ones
- **Lazy Iteration**: Use iterators for large judgment files
- **Retry Configuration**: Adjust retry parameters based on your environment

### Error Handling

- **Validation Errors**: Use `ltr.validation` functions for input validation
- **Connection Errors**: Use retry utilities for transient failures
- **Query Errors**: Handle `QueryError` exceptions appropriately
- **Model Errors**: Handle `ModelError` exceptions for model operations

---

## Related Documentation

- [Architecture Documentation](ARCHITECTURE.md) - System architecture and design patterns
- [ADR-011: Minimal Public API](adr/011-minimal-public-api.md) - Public API design rationale
- [Type Aliases Guide](TYPE_ALIASES_GUIDE.md) - Type system documentation
- [Error Handling Strategy](adr/025-error-handling-strategy.md) - Error handling patterns

---

**Document Version**: 1.0  
**Last Updated**: December 31, 2025
