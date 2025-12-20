"""Elasticsearch client implementation for Learn-to-Rank.

This module provides the Elasticsearch-specific implementation of the BaseClient
interface, handling Elasticsearch API calls and response formatting for LTR operations.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable
from typing import Any

import elasticsearch.helpers
import requests
from elasticsearch import Elasticsearch

from ltr.helpers.handle_resp import resp_msg
from ltr.logger import get_logger
from ltr.types import (
    FeatureConfig,
    FeatureSetResult,
    JSONDict,
    JSONDictList,
    ModelPayload,
    QueryParams,
)

from .base_client import BaseClient

logger = get_logger(__name__)


class ElasticResp:
    """Response wrapper for Elasticsearch API responses.

    Converts Elasticsearch JSON responses into a format compatible with
    the resp_msg error handling function.

    Attributes:
        status_code: HTTP status code (200 for success, 400 for errors).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize an ElasticResp wrapper.

        Args:
            resp: Elasticsearch API response dictionary.
        """
        self.status_code: int = 400
        if "acknowledged" in resp and resp["acknowledged"]:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text: str = json.dumps(resp, indent=2)


class BulkResp:
    """Response wrapper for Elasticsearch bulk operation responses.

    Attributes:
        status_code: HTTP status code (201 if documents indexed, 400 otherwise).
    """

    def __init__(self, resp: tuple[int, Any]) -> None:
        """Initialize a BulkResp wrapper.

        Args:
            resp: Elasticsearch bulk operation response tuple.
        """
        self.status_code: int = 400
        if resp[0] > 0:
            self.status_code = 201


class SearchResp:
    """Response wrapper for Elasticsearch search responses.

    Attributes:
        status_code: HTTP status code (200 if hits are found, 400 otherwise).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize a SearchResp wrapper.

        Args:
            resp: Elasticsearch search API response dictionary.
        """
        self.status_code: int = 400
        if "hits" in resp:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text: str = json.dumps(resp, indent=2)


class ElasticClient(BaseClient):
    """Elasticsearch client for Learn-to-Rank operations.

    Implements the BaseClient interface for Elasticsearch, providing methods
    for index management, feature set creation, model submission, and querying.

    Note: Elasticsearch LTR is not bound to an index like Solr LTR, so many
    calls take an index parameter but do not use it. In the future, we may
    wish to isolate an index's feature store to a feature store of the same
    name as the index.

    Attributes:
        docker: Boolean indicating if running in a Docker environment.
        configs_dir: Directory containing Elasticsearch configuration files.
        elastic_ep: Base Elasticsearch endpoint URL.
        host: Hostname for Elasticsearch server.
    """

    def __init__(self, configs_dir: str = ".") -> None:
        """Initialize an ElasticClient.

        Args:
            configs_dir: Directory containing Elasticsearch configuration files
                (default: current directory, or NOTEBOOK_CONFIGS_DIR env var if set).
        """
        self.docker: bool = os.environ.get("LTR_DOCKER") is not None
        # Use NOTEBOOK_CONFIGS_DIR environment variable if set (for notebook tests)
        # Otherwise use the provided configs_dir parameter
        notebook_configs_dir = os.environ.get("NOTEBOOK_CONFIGS_DIR")
        if configs_dir == "." and notebook_configs_dir:
            configs_dir = notebook_configs_dir
        self.configs_dir: str = configs_dir  # location of elastic configs

        if self.docker:
            self.host = "elastic"
        else:
            self.host = "localhost"

        self.elastic_ep: str = f"http://{self.host}:9200/_ltr"
        self.es: Elasticsearch = Elasticsearch(f"http://{self.host}:9200")

    def _validate_search_response(
        self, resp: JSONDict, operation: str = "query"
    ) -> None:
        """Validate Elasticsearch search response structure.

        Checks for error responses and missing 'hits' key, raising ValueError
        with descriptive messages if validation fails.

        Args:
            resp: Elasticsearch search API response dictionary.
            operation: Operation name for error messages (e.g., "query", "model query").

        Raises:
            ValueError: If response contains an error or is missing the 'hits' key.
        """
        if "error" in resp:
            error_detail = resp.get("error", {})
            if isinstance(error_detail, dict):
                error_msg = error_detail.get("reason", str(error_detail))
            else:
                error_msg = str(error_detail)
            raise ValueError(f"Elasticsearch {operation} failed: {error_msg}")
        if "hits" not in resp:
            raise ValueError(
                f"Unexpected response structure: missing 'hits' key. Response: {json.dumps(resp, indent=2)[:500]}"
            )

    def get_host(self) -> str:
        """Get the Elasticsearch hostname.

        Returns:
            str: Hostname for the Elasticsearch server.
        """
        return self.host

    def name(self) -> str:
        """Get the client name.

        Returns:
            str: Always returns "elastic".
        """
        return "elastic"

    def check_index_exists(self, index: str) -> bool:
        """Check if an index exists.

        Args:
            index: Index name to check.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return self.es.indices.exists(index=index)

    def delete_index(self, index: str) -> None:
        """Delete an Elasticsearch index.

        Args:
            index: Index name to delete.

        Note:
            Does not raise exceptions if the index doesn't exist (404) or
            if there are other client errors (400).
        """
        resp = self.es.indices.delete(index=index, ignore=[400, 404])
        resp_msg(
            msg=f"Deleted index {index}",
            resp=ElasticResp(resp),
            throw=False,
            ignore=[400, 404],
        )

    def create_index(self, index: str) -> None:
        """Take the local config files for Elasticsearch for index, reload
        them into ES"""
        cfg_json_path = os.path.join(self.configs_dir, f"{index}_settings.json")

        # If the config file doesn't exist at the specified path, try common alternative locations
        # This handles cases where tests run from project root but configs are in notebook directories
        if not os.path.exists(cfg_json_path):
            # Try to find the project root by looking for pyproject.toml
            project_root = os.getcwd()
            search_dir = project_root
            # Navigate up to project root if we're in a subdirectory (max 10 levels)
            for _ in range(10):
                if os.path.exists(os.path.join(search_dir, "pyproject.toml")):
                    project_root = search_dir
                    break
                parent = os.path.dirname(search_dir)
                if parent == search_dir:  # Reached filesystem root
                    break
                search_dir = parent

            # Try standard notebook locations relative to project root
            possible_paths = [
                os.path.join(
                    project_root,
                    f"notebooks/elasticsearch/{index}/{index}_settings.json",
                ),
                os.path.join(
                    project_root, f"notebooks/opensearch/{index}/{index}_settings.json"
                ),
            ]
            for alt_path in possible_paths:
                if os.path.exists(alt_path):
                    cfg_json_path = alt_path
                    break

        with open(cfg_json_path) as src:
            settings = json.load(src)
            resp = self.es.indices.create(index=index, body=settings)
            resp_msg(msg=f"Created index {index}", resp=ElasticResp(resp))

    def index_documents(
        self,
        index: str,
        doc_src: Iterable[JSONDict] | Callable[[], Iterable[JSONDict]],
    ) -> None:
        """Index documents into Elasticsearch using bulk operations.

        Args:
            index: Index name to index documents into.
            doc_src: Iterable of document dictionaries or a callable that returns
                an iterable. Each document must have an "id" field that uniquely
                identifies it. File paths (str) are not supported.

        Raises:
            ValueError: If a document is missing the required "id" field, or if
                doc_src is a string (file paths not supported).
        """

        def bulk_docs(
            doc_src: Iterable[JSONDict],
        ) -> Iterable[JSONDict]:
            """Generate bulk index commands for documents.

            Args:
                doc_src: Iterable of document dictionaries.

            Yields:
                dict: Bulk index command dictionary.
            """
            for doc in doc_src:
                if "id" not in doc:
                    raise ValueError(
                        "Expecting docs to have field 'id' that uniquely "
                        "identifies document"
                    )
                add_cmd = {"_index": index, "_id": doc["id"], "_source": doc}
                yield add_cmd

        if isinstance(doc_src, str):
            raise ValueError(
                "ElasticClient.index_documents does not support file paths"
            )
        if callable(doc_src):
            doc_src = doc_src()
        resp = elasticsearch.helpers.bulk(self.es, bulk_docs(doc_src), chunk_size=100)
        self.es.indices.refresh(index=index)
        resp_msg(msg=f"Streaming Bulk index DONE {index}", resp=BulkResp(resp))

    def reset_ltr(self, index: str) -> None:
        """Reset the Learn-to-Rank feature store.

        Deletes and recreates the default LTR feature store. Note that the
        index parameter is accepted for API compatibility but not used, as
        Elasticsearch LTR is not bound to a specific index.

        After resetting, waits a brief moment to ensure the LTR store is fully
        initialized before feature sets are created.

        Args:
            index: Index name (unused, kept for API compatibility).
        """
        resp = requests.delete(self.elastic_ep)
        resp_msg(
            msg="Removed Default LTR feature store".format(), resp=resp, throw=False
        )
        resp = requests.put(self.elastic_ep)
        resp_msg(msg="Initialize Default LTR feature store".format(), resp=resp)

        # Small delay to ensure LTR store is fully initialized
        # This helps prevent timing issues when creating feature sets immediately after reset
        time.sleep(0.2)  # 200ms delay

    def create_featureset(
        self, index: str, name: str, ftr_config: FeatureConfig
    ) -> None:
        """Create a new feature set in Elasticsearch.

        Args:
            index: Name of the index where the feature set will be created.
            name: Name of the feature set.
            ftr_config: Feature configuration dictionary with featureset.features structure.

        Raises:
            RuntimeError: If the index doesn't exist or feature set creation fails.
        """
        # Check if index exists before attempting to create feature set
        if not self.check_index_exists(index):
            raise RuntimeError(
                f"Cannot create feature set '{name}': index '{index}' does not exist. "
                f"Please create the index first using create_index('{index}')."
            )
        """Create a feature set in Elasticsearch LTR.

        Args:
            index: Index name (used for validation - index must exist).
            name: Name of the feature set to create.
            ftr_config: Feature set configuration dictionary.

        Raises:
            RuntimeError: If the index does not exist or feature set creation fails.
        """
        # Check if index exists before creating feature set
        # Elasticsearch LTR validates feature sets against indices, so the index must exist
        if not self.check_index_exists(index):
            raise RuntimeError(
                f"Cannot create feature set '{name}': index '{index}' does not exist. "
                f"Please create the index first using create_index('{index}')."
            )

        resp = requests.post(f"{self.elastic_ep}/_featureset/{name}", json=ftr_config)

        # Enhanced error handling for index_not_found_exception in API response
        if resp.status_code >= 400:
            try:
                error_json = resp.json()
                # Check for index_not_found_exception in the error response
                if "error" in error_json:
                    error_detail = error_json.get("error", {})
                    if isinstance(error_detail, dict):
                        # Check root cause for index_not_found_exception
                        root_causes = error_detail.get("root_cause", [])
                        for root_cause in root_causes:
                            if root_cause.get("type") == "index_not_found_exception":
                                missing_index = root_cause.get("index", index)
                                raise RuntimeError(
                                    f"Cannot create feature set '{name}': index '{missing_index}' does not exist. "
                                    f"Please create the index first using create_index('{missing_index}')."
                                )
                        # Check caused_by for nested index_not_found_exception
                        caused_by = error_detail.get("caused_by", {})
                        if (
                            isinstance(caused_by, dict)
                            and caused_by.get("type") == "index_not_found_exception"
                        ):
                            missing_index = caused_by.get("index", index)
                            raise RuntimeError(
                                f"Cannot create feature set '{name}': index '{missing_index}' does not exist. "
                                f"Please create the index first using create_index('{missing_index}')."
                            )
            except (ValueError, KeyError, TypeError):
                # If JSON parsing fails or structure is unexpected, fall through to resp_msg
                pass

        resp_msg(msg=f"Create {name} feature set", resp=resp)

        # Verify feature set was actually created and persisted
        # Elasticsearch LTR may return 200 but not persist the feature set in some cases
        # Retry a few times with small delays to handle potential timing issues
        max_retries = 3
        retry_delay = 0.1  # 100ms delay between retries
        for attempt in range(max_retries):
            try:
                # Try to retrieve the feature set to verify it was persisted
                self.feature_set(index=index, name=name)
                # If we get here, feature set exists - verification successful
                logger.debug(f"Verified feature set '{name}' was created successfully")
                break
            except RuntimeError:
                # Feature set not found yet, retry if we have attempts left
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                # All retries exhausted, raise error
                raise RuntimeError(
                    f"Feature set '{name}' creation appeared to succeed (HTTP {resp.status_code}), "
                    f"but verification failed - the feature set could not be retrieved. "
                    f"This may indicate a persistence issue with the Elasticsearch LTR plugin. "
                    f"Please check:\n"
                    f"  1. The index '{index}' exists and is accessible\n"
                    f"  2. The LTR plugin is properly installed and configured\n"
                    f"  3. Try creating the feature set again or check Elasticsearch logs for errors"
                )

        # Verify feature set is usable in queries (not just retrievable)
        # Feature sets may exist but not be immediately usable due to internal indexing delays
        # Try a simple test query to ensure the feature set is ready for use
        max_query_retries = 5
        query_retry_delay = 0.2  # 200ms delay between query attempts
        for attempt in range(max_query_retries):
            try:
                # Try a simple log_query with empty params to verify feature set is usable
                # Use a minimal query that should work if the feature set is ready
                test_params = {
                    "query": {
                        "bool": {
                            "filter": [
                                {
                                    "sltr": {
                                        "_name": "test_features",
                                        "featureset": name,
                                        "params": {},
                                    }
                                }
                            ]
                        }
                    },
                    "size": 0,  # Don't return documents, just verify query works
                }
                test_resp = self.es.search(index=index, body=test_params)

                # Check if query succeeded (no error in response)
                if "error" not in test_resp:
                    logger.debug(f"Verified feature set '{name}' is usable in queries")
                    return
                else:
                    # Query returned an error, check if it's a feature set issue
                    error_detail = test_resp.get("error", {})
                    if isinstance(error_detail, dict):
                        error_reason = error_detail.get("reason", "")
                        # If it's a feature set parsing issue or timing issue, retry
                        # "Unknown featureset" can occur when the featureset was just created
                        # and Elasticsearch hasn't fully indexed it yet
                        if (
                            "NullPointerException" in error_reason
                            or "getAndParse" in error_reason
                            or "Unknown featureset" in error_reason
                        ):
                            if attempt < max_query_retries - 1:
                                logger.debug(
                                    f"Feature set '{name}' not yet usable (attempt {attempt + 1}/{max_query_retries}), retrying..."
                                )
                                time.sleep(query_retry_delay)
                                query_retry_delay *= 1.5  # Gradual backoff
                                continue
                            else:
                                raise RuntimeError(
                                    f"Feature set '{name}' exists but is not usable in queries after {max_query_retries} attempts. "
                                    f"Error: {error_reason}. This may indicate a timing issue with the Elasticsearch LTR plugin. "
                                    f"Try waiting a moment and using the feature set again."
                                )
                    # Other errors should be raised immediately
                    raise RuntimeError(
                        f"Feature set '{name}' verification query failed: {error_detail}"
                    )
            except Exception as e:
                # Check if it's a feature set not ready error
                error_str = str(e)
                # "Unknown featureset" can occur when the featureset was just created
                # and Elasticsearch hasn't fully indexed it yet
                if (
                    "NullPointerException" in error_str
                    or "getAndParse" in error_str
                    or "Unknown featureset" in error_str
                ):
                    if attempt < max_query_retries - 1:
                        logger.debug(
                            f"Feature set '{name}' not yet usable (attempt {attempt + 1}/{max_query_retries}), retrying..."
                        )
                        time.sleep(query_retry_delay)
                        query_retry_delay *= 1.5
                        continue
                    else:
                        raise RuntimeError(
                            f"Feature set '{name}' exists but is not usable in queries after {max_query_retries} attempts. "
                            f"Error: {error_str}. This may indicate a timing issue with the Elasticsearch LTR plugin."
                        )
                # Re-raise other exceptions
                raise

    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Get the name of a feature by its index.

        Args:
            config: Feature set configuration dictionary.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.
        """
        if isinstance(config, list):
            raise ValueError("ElasticClient.get_feature_name requires a dict config")
        return config["featureset"]["features"][int(ftr_idx) - 1]["name"]

    def log_query(
        self,
        index: str,
        featureset: str,
        ids: list[str] | None,
        params: QueryParams,
    ) -> JSONDictList:
        """Execute a query and log feature values for specified documents.

        Uses Elasticsearch's LTR logging functionality to extract feature values
        for documents matching the given IDs, using the specified feature set.

        Includes retry logic to handle cases where feature sets are not immediately
        usable after creation.

        Args:
            index: Index name to query.
            featureset: Name of the feature set to use for logging.
            ids: List of document IDs to retrieve feature values for.
            params: Optional query parameters to pass to the feature set
                (default: empty dict).

        Returns:
            list: List of document dictionaries, each with an added "ltr_features"
                field containing the logged feature values.

        Raises:
            RuntimeError: If the feature set is not usable after retries.
        """
        query_params = params.copy() if params else {}
        query_body = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "sltr": {
                                "_name": "logged_features",
                                "featureset": featureset,
                                "params": query_params,
                            }
                        }
                    ]
                }
            },
            "ext": {
                "ltr_log": {
                    "log_specs": {
                        "name": "ltr_features",
                        "named_query": "logged_features",
                    }
                }
            },
            "size": 1000,
        }

        terms_query = [{"terms": {"_id": ids}}]

        if ids is not None:
            query_body["query"]["bool"]["must"] = terms_query

        # Retry logic for feature set timing issues
        max_retries = 5
        retry_delay = 0.2  # 200ms initial delay
        resp = None
        for attempt in range(max_retries):
            try:
                resp = self.es.search(index=index, body=query_body)
                # resp_msg(msg="Searching {} - {}".format(index, str(terms_query)[:20]), resp=SearchResp(resp))

                # Check for feature set not ready errors before validation
                if "error" in resp:
                    error_detail = resp.get("error", {})
                    if isinstance(error_detail, dict):
                        error_reason = error_detail.get("reason", "")
                        # Check if it's a feature set parsing/optimization error
                        if (
                            "NullPointerException" in error_reason
                            or "getAndParse" in error_reason
                            or "optimize()" in error_reason
                            or "StoredFeatureSet" in error_reason
                        ):
                            if attempt < max_retries - 1:
                                logger.debug(
                                    f"Feature set '{featureset}' not yet usable in query "
                                    f"(attempt {attempt + 1}/{max_retries}), retrying..."
                                )
                                time.sleep(retry_delay)
                                retry_delay *= 1.5  # Gradual backoff
                                continue
                            else:
                                raise RuntimeError(
                                    f"Feature set '{featureset}' is not usable in queries after {max_retries} attempts. "
                                    f"Error: {error_reason}. The feature set may need more time to be fully indexed. "
                                    f"Try waiting a moment and using the feature set again."
                                )
                        # For other errors, validate normally (will raise ValueError)
                    # Fall through to validation for non-feature-set errors

                self._validate_search_response(resp, operation="query")
                break  # Success, exit retry loop
            except ValueError as e:
                # Check if it's a feature set error
                error_str = str(e)
                if (
                    "NullPointerException" in error_str
                    or "getAndParse" in error_str
                    or "optimize()" in error_str
                ):
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"Feature set '{featureset}' not yet usable (attempt {attempt + 1}/{max_retries}), retrying..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    else:
                        raise RuntimeError(
                            f"Feature set '{featureset}' is not usable in queries after {max_retries} attempts. "
                            f"Error: {error_str}"
                        )
                # Re-raise other ValueError exceptions
                raise

        # Ensure resp was set (should always be set if we reach here due to exception handling above)
        if resp is None:
            raise RuntimeError(
                f"Feature set '{featureset}' query failed: no response received after {max_retries} attempts"
            )

        # Extract feature values from response
        matches = []
        for hit in resp["hits"]["hits"]:
            hit["_source"]["ltr_features"] = []

            for feature in hit["fields"]["_ltrlog"][0]["ltr_features"]:
                value = 0.0
                if "value" in feature:
                    value = feature["value"]

                hit["_source"]["ltr_features"].append(value)

            matches.append(hit["_source"])

        return matches

    def submit_model(
        self,
        featureset: str,
        index: str,
        model_name: str,
        model_payload: ModelPayload,
    ) -> None:
        """Submit a machine learning model to Elasticsearch LTR.

        Deletes any existing model with the same name, then creates a new model
        associated with the specified feature set. Verifies the model was actually
        created and persisted before returning.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.

        Raises:
            RuntimeError: If model creation appears to succeed but verification fails.
        """
        model_ep = f"{self.elastic_ep}/_model/"
        create_ep = f"{self.elastic_ep}/_featureset/{featureset}/_createmodel"

        resp = requests.delete(f"{model_ep}{model_name}")
        logger.info(f"Delete model {model_name}: {resp.status_code}")

        resp = requests.post(create_ep, json=model_payload)
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

        # Verify model was actually created and persisted
        # Elasticsearch LTR may return 200 but not persist the model in some cases
        # Retry a few times with small delays to handle potential timing issues
        max_retries = 3
        retry_delay = 0.1  # 100ms delay between retries
        for attempt in range(max_retries):
            try:
                # Try to retrieve the model to verify it was persisted
                verify_resp = requests.get(f"{model_ep}{model_name}")
                if verify_resp.status_code == 200:
                    # Model exists - verification successful
                    logger.debug(
                        f"Verified model '{model_name}' was created successfully"
                    )
                    return
                elif verify_resp.status_code == 404:
                    # Model not found yet, retry if we have attempts left
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    # All retries exhausted, raise error
                    raise RuntimeError(
                        f"Model '{model_name}' creation appeared to succeed (HTTP {resp.status_code}), "
                        f"but verification failed - the model could not be retrieved. "
                        f"This may indicate a persistence issue with the Elasticsearch LTR plugin. "
                        f"Please check:\n"
                        f"  1. The feature set '{featureset}' exists and is accessible\n"
                        f"  2. The LTR plugin is properly installed and configured\n"
                        f"  3. Try creating the model again or check Elasticsearch logs for errors"
                    )
                else:
                    # Unexpected status code
                    resp_msg(msg=f"Verify model {model_name}", resp=verify_resp)
                    return
            except requests.RequestException as e:
                # Network/request error, retry if we have attempts left
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Error verifying model '{model_name}' (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                # All retries exhausted, raise error
                raise RuntimeError(
                    f"Model '{model_name}' creation appeared to succeed, but verification failed "
                    f"due to request error: {e}"
                )

    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to Elasticsearch LTR.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: RankLib model definition string.
        """
        params = {
            "model": {
                "name": model_name,
                "model": {"type": "model/ranklib", "definition": model_payload},
            }
        }
        self.submit_model(featureset, index, model_name, params)

    def submit_xgboost_model(
        self,
        featureset: str,
        index: str,
        model_name: str,
        model_payload: ModelPayload,
    ) -> None:
        """Submit an XGBoost model to Elasticsearch LTR.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: XGBoost model definition (JSON format).
        """
        params = {
            "model": {
                "name": model_name,
                "model": {"type": "model/xgboost+json", "definition": model_payload},
            }
        }
        self.submit_model(featureset, index, model_name, params)

    def model_query(
        self,
        index: str,
        model: str,
        model_params: QueryParams,
        query: QueryParams,
    ) -> JSONDictList:
        """Execute a query using an LTR model for rescoring.

        Uses Elasticsearch's rescore functionality to apply an LTR model to
        re-rank search results.

        Args:
            index: Index name to query.
            model: Name of the LTR model to use for rescoring.
            model_params: Parameters to pass to the model.
            query: Base query dictionary to execute.

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Solr.
        """
        params = {
            "query": query,
            "rescore": {
                "window_size": 1000,
                "query": {
                    "rescore_query": {"sltr": {"params": model_params, "model": model}}
                },
            },
            "size": 1000,
        }

        resp = self.es.search(index=index, body=params)
        # resp_msg(msg="Searching {} - {}".format(index, str(query)[:20]), resp=SearchResp(resp))

        self._validate_search_response(resp, operation="model query")

        # Transform to a consistent format between ES/Solr
        matches = []
        for hit in resp["hits"]["hits"]:
            match = hit["_source"]
            match["score"] = hit["_score"]
            matches.append(match)

        return matches

    def query(self, index: str, query: QueryParams) -> JSONDictList:
        """Execute a search query against an Elasticsearch index.

        Args:
            index: Index name to query.
            query: Query dictionary in Elasticsearch query DSL format.

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Solr.
        """
        resp = self.es.search(index=index, body=query)
        # resp_msg(msg="Searching {} - {}".format(index, str(query)[:20]), resp=SearchResp(resp))

        self._validate_search_response(resp, operation="query")

        # Transform to a consistent format between ES/Solr
        matches = []
        for hit in resp["hits"]["hits"]:
            hit["_source"]["_score"] = hit["_score"]
            matches.append(hit["_source"])

        return matches

    def feature_set(self, index: str, name: str) -> FeatureSetResult:
        """Retrieve a feature set configuration.

        Args:
            index: Index name (unused, kept for API compatibility).
            name: Name of the feature set to retrieve.

        Returns:
            tuple: A tuple containing:
                - mapping: List of dictionaries with feature names
                - raw_feature_set: Full feature set configuration dictionary

        Raises:
            RuntimeError: If the feature set is not found.
        """
        resp = requests.get(f"{self.elastic_ep}/_featureset/{name}")

        # Check HTTP status code first
        if resp.status_code == 404:
            raise RuntimeError(
                f"Feature set '{name}' not found. "
                f"Please ensure the feature set has been created using "
                f"client.create_featureset(index='{index}', name='{name}', ftr_config=...). "
                f"If the index doesn't exist, create it first using client.create_index('{index}')."
            )

        json_resp = resp.json()
        if not json_resp.get("found", False):
            # Provide helpful error message with suggestions
            error_msg = f"Feature set '{name}' not found"
            if "error" in json_resp:
                error_detail = json_resp.get("error", {})
                if isinstance(error_detail, dict):
                    error_reason = error_detail.get("reason", "")
                    if error_reason:
                        error_msg += f": {error_reason}"

            error_msg += (
                f". Please ensure the feature set has been created using "
                f"client.create_featureset(index='{index}', name='{name}', ftr_config=...). "
                f"If the index doesn't exist, create it first using client.create_index('{index}')."
            )
            raise RuntimeError(error_msg)

        resp_msg(msg=f"Fetched FeatureSet {name}", resp=resp)

        raw_feature_set = json_resp["_source"]["featureset"]["features"]

        mapping = []
        for feature in raw_feature_set:
            mapping.append({"name": feature["name"]})

        return mapping, raw_feature_set

    def get_doc(self, doc_id: str, index: str) -> JSONDict:
        """Retrieve a single document by ID.

        Args:
            doc_id: Document ID to retrieve.
            index: Index name containing the document.

        Returns:
            dict: Document source dictionary.
        """
        resp = self.es.get(index=index, id=doc_id)
        # resp_msg(msg="Fetched Doc".format(docId), resp=ElasticResp(resp), throw=False)
        return resp["_source"]
