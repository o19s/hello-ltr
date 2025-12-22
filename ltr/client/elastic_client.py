"""Elasticsearch client implementation for Learn-to-Rank.

This module provides the Elasticsearch-specific implementation of the BaseClient
interface, handling Elasticsearch API calls and response formatting for LTR operations.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable

import elasticsearch.helpers
import requests
from elasticsearch import Elasticsearch

from ltr.exceptions import LTRIndexError, ModelError, QueryError
from ltr.helpers.handle_resp import resp_msg
from ltr.helpers.retry import (
    retry_feature_set_query,
    retry_model_query,
    retry_until_true,
)
from ltr.logger import get_logger
from ltr.types import (
    FeatureConfig,
    FeatureSetResult,
    JSONDict,
    JSONDictList,
    ModelPayload,
    QueryParams,
)
from ltr.validation import ValidationError

from .base_client import BaseClient
from .responses import APIResp, BulkResp

logger = get_logger(__name__)

# Retry configuration constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.1  # 100ms delay between retries
FEATURE_SET_MAX_RETRIES = 5
FEATURE_SET_RETRY_DELAY = 0.2  # 200ms initial delay
QUERY_RETRY_DELAY = 0.2  # 200ms delay between query attempts
MODEL_QUERY_MAX_RETRIES = 5
MODEL_QUERY_RETRY_DELAY = 0.5  # 500ms initial delay

# Alias for backward compatibility
ElasticResp = APIResp


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
                error_msg: str = error_detail.get("reason", str(error_detail))
            else:
                error_msg = str(error_detail)
            raise QueryError(
                f"Elasticsearch {operation} failed: {error_msg}",
                client_name="elastic",
            )
        if "hits" not in resp:
            raise QueryError(
                f"Unexpected response structure: missing 'hits' key. Response: {json.dumps(resp, indent=2)[:500]}",
                client_name="elastic",
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
        them into ES.

        Args:
            index: Index name to create. The configuration file should be named
                "{index}_settings.json" in the configs_dir directory.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
            RuntimeError: If index creation fails (HTTP status >= 400).
            LTRIndexError: If index creation appears to succeed but verification fails
                (index cannot be found after creation).
        """
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
                # Check osc-blog directory for blog index
                os.path.join(
                    project_root,
                    f"notebooks/elasticsearch/osc-blog/{index}_settings.json",
                ),
                os.path.join(
                    project_root, f"notebooks/opensearch/osc-blog/{index}_settings.json"
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

        # Verify index was actually created and is accessible
        # Elasticsearch may return success but the index might not be immediately available
        try:
            retry_until_true(
                check_func=lambda: self.check_index_exists(index),
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                error_message=(
                    f"Index '{index}' creation appeared to succeed (HTTP 200), "
                    f"but verification failed - the index could not be found. "
                    f"This may indicate a persistence issue with Elasticsearch."
                ),
            )
            logger.debug(f"Verified index '{index}' was created successfully")
        except RuntimeError as e:
            raise LTRIndexError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. Elasticsearch is running and accessible\n"
                f"  2. The index settings are valid\n"
                f"  3. Try creating the index again or check Elasticsearch logs for errors",
                index=index,
                operation="create_index",
                client_name="elastic",
            ) from e

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
                    raise ValidationError(
                        "Expecting docs to have field 'id' that uniquely "
                        "identifies document"
                    )
                add_cmd = {"_index": index, "_id": doc["id"], "_source": doc}
                yield add_cmd

        if isinstance(doc_src, str):
            raise ValidationError(
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

        Raises:
            RuntimeError: If LTR store initialization fails (HTTP status >= 400).
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
        # Elasticsearch LTR validates feature sets against indices, so the index must exist
        if not self.check_index_exists(index):
            raise LTRIndexError(
                f"Cannot create feature set '{name}': index '{index}' does not exist. "
                f"Please create the index first using create_index('{index}').",
                index=index,
                operation="create_featureset",
                client_name="elastic",
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
                        root_causes: list[JSONDict] = error_detail.get("root_cause", [])
                        for root_cause in root_causes:
                            if (
                                isinstance(root_cause, dict)
                                and root_cause.get("type")
                                == "index_not_found_exception"
                            ):
                                missing_index_root: str = root_cause.get("index", index)
                                raise LTRIndexError(
                                    f"Cannot create feature set '{name}': index '{missing_index_root}' does not exist. "
                                    f"Please create the index first using create_index('{missing_index_root}').",
                                    index=missing_index_root,
                                    client_name="elastic",
                                )
                        # Check caused_by for nested index_not_found_exception
                        caused_by: JSONDict = error_detail.get("caused_by", {})
                        if (
                            isinstance(caused_by, dict)
                            and caused_by.get("type") == "index_not_found_exception"
                        ):
                            missing_index_caused: str = caused_by.get("index", index)
                            raise LTRIndexError(
                                f"Cannot create feature set '{name}': index '{missing_index_caused}' does not exist. "
                                f"Please create the index first using create_index('{missing_index_caused}').",
                                index=missing_index_caused,
                                client_name="elastic",
                            )
            except (ValueError, KeyError, TypeError):
                # If JSON parsing fails or structure is unexpected, fall through to resp_msg
                pass

        resp_msg(msg=f"Create {name} feature set", resp=resp)

        # Verify feature set was actually created and persisted
        # Elasticsearch LTR may return 200 but not persist the feature set in some cases
        def verify_feature_set_exists() -> bool:
            try:
                self.feature_set(index=index, name=name)
                logger.debug(f"Verified feature set '{name}' was created successfully")
                return True
            except RuntimeError:
                return False  # Feature set not found yet, will retry

        try:
            retry_until_true(
                check_func=verify_feature_set_exists,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                error_message=(
                    f"Feature set '{name}' creation appeared to succeed (HTTP {resp.status_code}), "
                    f"but verification failed - the feature set could not be retrieved. "
                    f"This may indicate a persistence issue with the Elasticsearch LTR plugin."
                ),
            )
        except RuntimeError as e:
            raise QueryError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. The index '{index}' exists and is accessible\n"
                f"  2. The LTR plugin is properly installed and configured\n"
                f"  3. Try creating the feature set again or check Elasticsearch logs for errors",
                index=index,
                client_name="elastic",
            ) from e

        # Verify feature set is usable in queries (not just retrievable)
        # Feature sets may exist but not be immediately usable due to internal indexing delays
        # Try a simple test query to ensure the feature set is ready for use
        max_query_retries = 5
        query_retry_delay = QUERY_RETRY_DELAY

        # Extract required parameters from feature set configuration
        # First check if validation section provides default params
        test_query_params = {}
        if isinstance(ftr_config, dict) and "validation" in ftr_config:
            validation: JSONDict = ftr_config.get("validation", {})
            if isinstance(validation, dict) and "params" in validation:
                params = validation["params"]
                if isinstance(params, dict):
                    test_query_params = params.copy()

        # If no validation params, extract from features
        if not test_query_params and isinstance(ftr_config, dict):
            featureset: JSONDict = ftr_config.get("featureset", {})
            if isinstance(featureset, dict):
                features: list[JSONDict] = featureset.get("features", [])
                # Collect all unique params from all features
                required_params: set[str] = set()
                for feature in features:
                    if isinstance(feature, dict) and "params" in feature:
                        feature_params: list[str] = feature.get("params", [])
                        if isinstance(feature_params, list):
                            required_params.update(feature_params)

                # Provide default values for required params
                # Detect param types based on naming conventions and template usage
                for param in required_params:
                    if param not in test_query_params:
                        # Check if param name suggests it should be an array/list
                        param_lower: str = param.lower()
                        if "list" in param_lower or "array" in param_lower:
                            # Param name suggests it's an array (e.g., "keywordsList")
                            test_query_params[param] = []
                        else:
                            # Default to empty string for most params (keywords, query, etc.)
                            # This allows the query to execute even if the param value isn't meaningful
                            test_query_params[param] = ""

        # Verify feature set is usable in queries using shared helper
        def execute_verification_query() -> JSONDict:
            test_params = {
                "query": {
                    "bool": {
                        "filter": [
                            {
                                "sltr": {
                                    "_name": "test_features",
                                    "featureset": name,
                                    "params": test_query_params,
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
                return test_resp
            # Query returned an error - check if it's a feature set issue
            error_detail: JSONDict = test_resp.get("error", {})
            if isinstance(error_detail, dict):
                error_reason: str = error_detail.get("reason", "")
                # Check if it's a timing issue
                if (
                    "NullPointerException" in error_reason
                    or "getAndParse" in error_reason
                    or "Unknown featureset" in error_reason
                ):
                    # This is a timing error - will be retried by retry_feature_set_query
                    raise ValueError(f"Feature set not ready: {error_reason}")
            # Other errors should be raised immediately
            raise QueryError(
                f"Feature set '{name}' verification query failed: {error_detail}",
                index=index,
                client_name="elastic",
            )

        retry_feature_set_query(
            query_func=execute_verification_query,
            featureset=name,
            index=index,
            client_name="elastic",
            max_retries=max_query_retries,
            initial_delay=query_retry_delay,
        )

    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Get the name of a feature by its index.

        Args:
            config: Feature set configuration dictionary.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.

        Raises:
            ValueError: If config is a list instead of a dictionary.
        """
        if isinstance(config, list):
            raise ValidationError(
                "ElasticClient.get_feature_name requires a dict config"
            )
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
            ValueError: If the response contains an error or has an invalid structure.
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

        # Retry logic for feature set timing issues using shared helper
        def execute_and_validate_query() -> JSONDict:
            resp = self.es.search(index=index, body=query_body)
            # Validate response (will raise ValueError if invalid)
            self._validate_search_response(resp, operation="query")
            return resp

        resp = retry_feature_set_query(
            query_func=execute_and_validate_query,
            featureset=featureset,
            index=index,
            client_name="elastic",
            max_retries=FEATURE_SET_MAX_RETRIES,
            initial_delay=FEATURE_SET_RETRY_DELAY,
        )

        # Extract feature values from response
        matches = []
        for hit in resp["hits"]["hits"]:
            hit["_source"]["ltr_features"] = []

            for feature in hit["fields"]["_ltrlog"][0]["ltr_features"]:
                value = 0.0
                if "value" in feature:
                    value = feature["value"]
                    # Ensure None values and string "None" are converted to 0.0 for RankLib compatibility
                    if (
                        value is None
                        or value == "None"
                        or isinstance(value, str)
                        and value.lower() == "none"
                    ):
                        value = 0.0

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
        def verify_model_exists() -> bool:
            try:
                verify_resp = requests.get(f"{model_ep}{model_name}")
                if verify_resp.status_code == 200:
                    logger.debug(
                        f"Verified model '{model_name}' was created successfully"
                    )
                    return True
                elif verify_resp.status_code == 404:
                    return False  # Model not found yet, will retry
                else:
                    # Unexpected status code - log but consider it success
                    resp_msg(msg=f"Verify model {model_name}", resp=verify_resp)
                    return True
            except requests.RequestException as e:
                # Network/request error - log and retry
                logger.warning(f"Error verifying model '{model_name}': {e}")
                return False

        try:
            retry_until_true(
                check_func=verify_model_exists,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                error_message=(
                    f"Model '{model_name}' creation appeared to succeed (HTTP {resp.status_code}), "
                    f"but verification failed - the model could not be retrieved. "
                    f"This may indicate a persistence issue with the Elasticsearch LTR plugin."
                ),
            )
        except RuntimeError as e:
            raise ModelError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. The feature set '{featureset}' exists and is accessible\n"
                f"  2. The LTR plugin is properly installed and configured\n"
                f"  3. Try creating the model again or check Elasticsearch logs for errors",
                model_name=model_name,
                operation="submit",
                context={"featureset": featureset, "index": index},
            ) from e

    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to Elasticsearch LTR.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: RankLib model definition string.

        Raises:
            RuntimeError: If model creation or verification fails (see submit_model).
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

        Raises:
            RuntimeError: If model creation or verification fails (see submit_model).
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

        Includes retry logic to handle cases where models are not immediately
        available after creation.

        Args:
            index: Index name to query.
            model: Name of the LTR model to use for rescoring.
            model_params: Parameters to pass to the model.
            query: Base query dictionary to execute.

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Solr.

        Raises:
            RuntimeError: If the model is not available after retries.
            ValueError: If the response contains an error or has an invalid structure.
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

        # Retry logic for model timing issues using shared helper
        def execute_and_validate_query() -> JSONDict:
            resp = self.es.search(index=index, body=params)
            # Validate response (will raise ValueError if invalid)
            self._validate_search_response(resp, operation="model query")
            return resp

        resp = retry_model_query(
            query_func=execute_and_validate_query,
            model_name=model,
            index=index,
            client_name="elastic",
            max_retries=MODEL_QUERY_MAX_RETRIES,
            initial_delay=MODEL_QUERY_RETRY_DELAY,
        )

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

        Raises:
            QueryError: If the query fails due to network errors, index not found,
                or other client-related issues.
            ValueError: If the response contains an error or has an invalid structure.
        """
        try:
            resp = self.es.search(index=index, body=query)
        except Exception as e:
            # Wrap Elasticsearch client exceptions with context
            query_str = str(query)[:200]  # Truncate for security/logging
            raise QueryError(
                f"Elasticsearch query failed: {e}",
                index=index,
                query=query_str,
                client_name="elastic",
            ) from e

        try:
            self._validate_search_response(resp, operation="query")
        except ValueError as e:
            # Re-raise validation errors with query context
            query_str = str(query)[:200]
            raise QueryError(
                f"Invalid Elasticsearch query response: {e}",
                index=index,
                query=query_str,
                client_name="elastic",
            ) from e

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
            raise QueryError(
                f"Feature set '{name}' not found. "
                f"Please ensure the feature set has been created using "
                f"client.create_featureset(index='{index}', name='{name}', ftr_config=...). "
                f"If the index doesn't exist, create it first using client.create_index('{index}').",
                index=index,
                client_name="elastic",
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
            raise QueryError(
                error_msg,
                index=index,
                client_name="elastic",
            )

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
