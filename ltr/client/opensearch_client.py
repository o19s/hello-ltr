"""OpenSearch client implementation for Learn-to-Rank.

This module provides the OpenSearch-specific implementation of the BaseClient
interface, handling OpenSearch API calls and response formatting for LTR operations.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable

import requests
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import (
    ConnectionError as OpenSearchConnectionError,
)
from opensearchpy.exceptions import (
    RequestError,
    TransportError,
)

from ltr.exceptions import LTRConnectionError, LTRIndexError, ModelError, QueryError
from ltr.helpers.handle_resp import resp_msg
from ltr.helpers.retry import (
    is_feature_set_timing_error,
    is_model_timing_error,
    is_opensearch_connection_error,
    is_requests_connection_error,
    retry_feature_set_query,
    retry_model_query,
    retry_on_connection_error,
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
from ltr.validation import (
    ValidationError,
    validate_index_name,
    validate_model_name,
)

from .base_client import BaseClient
from .elastic_base_client import ElasticBaseClient
from .responses import APIResp, BulkResp

# Retry configuration constants
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_DELAY = 0.5
CLIENT_INIT_MAX_RETRIES = 3
CLIENT_INIT_RETRY_DELAY = 0.1
VERIFICATION_MAX_RETRIES = 3
VERIFICATION_RETRY_DELAY = 0.1
QUERY_VERIFICATION_RETRY_DELAY = 0.2

logger = get_logger(__name__)

# Alias for backward compatibility
OpenSearchResp = APIResp


class OpenSearchClient(ElasticBaseClient, BaseClient):
    """OpenSearch client for Learn-to-Rank operations.

    Implements the BaseClient interface for OpenSearch, providing methods
    for index management, feature set creation, model submission, and querying.

    Note: OpenSearch LTR is not bound to an index like Solr LTR, so many
    calls take an index parameter but do not use it. In the future, we may
    wish to isolate an index's feature store to a feature store of the same
    name as the index.

    Attributes:
        docker: Boolean indicating if running in Docker environment.
        configs_dir: Directory containing OpenSearch configuration files.
        opensearch_ep: Base OpenSearch endpoint URL.
        host: Hostname for OpenSearch server.
        port: Port number for OpenSearch server connection.
    """

    def __init__(self, configs_dir: str = ".", port: int | None = None) -> None:
        """Initialize an OpenSearchClient.

        Args:
            configs_dir: Directory containing OpenSearch configuration files
                (default: current directory, or NOTEBOOK_CONFIGS_DIR env var if set).
            port: Optional port number. If not provided, uses OPENSEARCH_PORT environment
                variable if set, otherwise defaults to 9201.
        """
        self.docker: bool = os.environ.get("LTR_DOCKER") is not None
        # Use NOTEBOOK_CONFIGS_DIR environment variable if set (for notebook tests)
        # Otherwise use the provided configs_dir parameter
        notebook_configs_dir = os.environ.get("NOTEBOOK_CONFIGS_DIR")
        if configs_dir == "." and notebook_configs_dir:
            configs_dir = notebook_configs_dir
        self.configs_dir: str = configs_dir  # location of elastic configs

        # Determine port: explicit parameter > environment variable > default
        if port is None:
            port_env = os.environ.get("OPENSEARCH_PORT")
            if port_env:
                try:
                    port = int(port_env)
                except ValueError:
                    raise ValueError(
                        f"Invalid OPENSEARCH_PORT environment variable: '{port_env}'. Must be an integer."
                    )
            else:
                port = 9201
        self.port = port

        if self.docker:
            self.host = "opensearch-node1"
        else:
            self.host = "localhost"

        self.opensearch_ep: str = f"http://{self.host}:{self.port}/_ltr"
        # Create OpenSearch client - note that OpenSearch() constructor doesn't connect immediately
        # Connection happens lazily on first API call, so this shouldn't fail here
        # In test environments, retry logic is handled via dependency injection
        try:
            self.opensearch: OpenSearch = OpenSearch(f"http://{self.host}:{self.port}")
        except Exception:
            # If creation fails, let it fail immediately
            raise
        logger.debug(f"OpenSearch endpoint: {self.opensearch_ep}")

    def get_host(self) -> str:
        """Get the OpenSearch hostname.

        Returns:
            str: Hostname for the OpenSearch server.
        """
        return self.host

    def name(self) -> str:
        """Get the client name.

        Returns:
            str: Always returns "opensearch".
        """
        return "opensearch"

    def check_index_exists(self, index: str) -> bool:
        """Check if an index exists.

        Args:
            index: Index name to check.

        Returns:
            bool: True if the index exists, False otherwise.

        Raises:
            ValidationError: If the index name is invalid.
        """
        index = validate_index_name(index)

        def check_index() -> bool:
            return self.opensearch.indices.exists(index=index)

        try:
            return retry_on_connection_error(
                check_index,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_opensearch_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when checking index '{index}' after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="check_index_exists",
            ) from e

    def delete_index(self, index: str) -> None:
        """Delete an OpenSearch index.

        Args:
            index: Index name to delete.

        Raises:
            ValidationError: If the index name is invalid.

        Note:
            Does not raise exceptions if the index doesn't exist (404) or
            if there are other client errors (400).
        """
        index = validate_index_name(index)

        def delete_index() -> None:
            resp = self.opensearch.indices.delete(index=index, ignore=[400, 404])
            resp_msg(
                msg=f"Deleted index {index}",
                resp=OpenSearchResp(resp),
                throw=False,
                ignore=[400, 404],
            )

        try:
            retry_on_connection_error(
                delete_index,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_opensearch_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when deleting index '{index}' after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="delete_index",
            ) from e

    def create_index(self, index: str) -> None:
        """Create an OpenSearch index from local configuration files.

        Loads index settings from a JSON file and creates the index in OpenSearch.

        Args:
            index: Index name to create. The configuration file should be named
                "{index}_settings.json" in the configs_dir directory.

        Raises:
            ValidationError: If the index name is invalid.
            FileNotFoundError: If the configuration file cannot be found.
            ClientError: If index creation fails (HTTP status >= 400).
            LTRConnectionError: If connection to OpenSearch fails during creation or verification.
            LTRIndexError: If index creation appears to succeed but verification fails
                (index cannot be found after creation).
        """
        index = validate_index_name(index)
        cfg_json_path = self._resolve_config_path(index, self.configs_dir)

        with open(cfg_json_path) as src:
            settings = json.load(src)

            def create_index() -> JSONDict:
                return self.opensearch.indices.create(index=index, body=settings)

            try:
                resp = retry_on_connection_error(
                    create_index,
                    max_retries=DEFAULT_MAX_RETRIES,
                    initial_delay=DEFAULT_RETRY_DELAY,
                    is_connection_error=is_opensearch_connection_error,
                )
                # Validate response after successful retry - don't retry response validation errors
                resp_msg(msg=f"Created index {index}", resp=OpenSearchResp(resp))
            except RuntimeError as e:
                raise LTRConnectionError(
                    f"Failed to connect to OpenSearch when creating index '{index}' after {DEFAULT_MAX_RETRIES} attempts. "
                    f"OpenSearch container may not be ready. Error: {e}",
                    client_name="opensearch",
                    operation="create_index",
                ) from e

        # Verify index was actually created and is accessible
        # OpenSearch may return success but the index might not be immediately available
        def check_index() -> bool:
            try:
                return self.check_index_exists(index)
            except LTRConnectionError:
                # Connection error during verification - return False to retry
                return False

        try:
            retry_until_true(
                check_func=check_index,
                max_retries=VERIFICATION_MAX_RETRIES,
                initial_delay=VERIFICATION_RETRY_DELAY,
                error_message=(
                    f"Index '{index}' creation appeared to succeed (HTTP 200), "
                    f"but verification failed - the index could not be found. "
                    f"This may indicate a persistence issue with OpenSearch."
                ),
            )
            logger.debug(f"Verified index '{index}' was created successfully")
        except RuntimeError as e:
            raise LTRIndexError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. OpenSearch is running and accessible\n"
                f"  2. The index settings are valid\n"
                f"  3. Try creating the index again or check OpenSearch logs for errors",
                index=index,
                operation="create_index",
                client_name="opensearch",
            ) from e

    def index_documents(
        self,
        index: str,
        doc_src: Iterable[JSONDict] | Callable[[], Iterable[JSONDict]],
    ) -> None:
        """Index documents into OpenSearch using bulk operations.

        Args:
            index: Index name to index documents into.
            doc_src: Iterable of document dictionaries or a callable that returns
                an iterable. Each document must have an "id" field that uniquely
                identifies it. File paths (str) are not supported.

        Raises:
            ValidationError: If the index name is invalid.
            ValueError: If a document is missing the required "id" field, or if
                doc_src is a string (file paths not supported).
        """
        index = validate_index_name(index)

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
                        "Expecting docs to have field 'id' that uniquely identifies document"
                    )
                add_cmd = {"_index": index, "_id": doc["id"], "_source": doc}
                yield add_cmd

        if isinstance(doc_src, str):
            raise ValidationError(
                "OpenSearchClient.index_documents does not support file paths"
            )
        if callable(doc_src):
            doc_src = doc_src()
        resp = helpers.bulk(self.opensearch, bulk_docs(doc_src), chunk_size=100)

        def refresh_index() -> None:
            self.opensearch.indices.refresh(index=index)

        try:
            retry_on_connection_error(
                refresh_index,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_opensearch_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to refresh index '{index}' after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="index_documents",
            ) from e
        resp_msg(msg=f"Streaming Bulk index DONE {index}", resp=BulkResp(resp))

    def reset_ltr(self, index: str) -> None:
        """Reset the Learn-to-Rank feature store.

        Deletes and recreates the default LTR feature store. Note that the
        index parameter is accepted for API compatibility but not used, as
        OpenSearch LTR is not bound to a specific index.

        After resetting, waits a brief moment to ensure the LTR store is fully
        initialized before feature sets are created.

        Args:
            index: Index name (unused, kept for API compatibility).

        Raises:
            ValidationError: If the index name is invalid.
            RuntimeError: If LTR store initialization fails (HTTP status >= 400).
        """
        index = validate_index_name(index)

        # Delete LTR store with retry
        def delete_ltr_store() -> requests.Response:
            return requests.delete(self.opensearch_ep, timeout=10)

        try:
            delete_resp = retry_on_connection_error(
                delete_ltr_store,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_requests_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when deleting LTR store after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="reset_ltr",
            ) from e

        if delete_resp is not None:
            resp_msg(
                msg="Removed Default LTR feature store".format(),
                resp=delete_resp,
                throw=False,
            )

        # Create LTR store with retry
        def create_ltr_store() -> requests.Response:
            return requests.put(self.opensearch_ep, timeout=10)

        try:
            create_resp = retry_on_connection_error(
                create_ltr_store,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_requests_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when creating LTR store after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="reset_ltr",
            ) from e

        if create_resp is None:
            raise LTRConnectionError(
                "Failed to reset LTR: No response received for PUT request",
                client_name="opensearch",
                operation="reset_ltr",
            )

        resp_msg(msg="Initialize Default LTR feature store".format(), resp=create_resp)

        # Small delay to ensure LTR store is fully initialized
        # This helps prevent timing issues when creating feature sets immediately after reset
        time.sleep(0.2)  # 200ms delay

    def create_featureset(
        self, index: str, name: str, ftr_config: FeatureConfig
    ) -> None:
        """Create a new feature set in OpenSearch.

        Args:
            index: Name of the index where the feature set will be created.
            name: Name of the feature set.
            ftr_config: Feature configuration dictionary with featureset.features structure.

        Raises:
            ValidationError: If the index name or feature set name is invalid.
            RuntimeError: If the index doesn't exist or feature set creation fails.
        """
        index = validate_index_name(index)
        name = validate_model_name(name)
        # Check if index exists before attempting to create feature set
        # OpenSearch LTR validates feature sets against indices, so the index must exist
        if not self.check_index_exists(index):
            raise LTRIndexError(
                f"Cannot create feature set '{name}': index '{index}' does not exist. "
                f"Please create the index first using create_index('{index}').",
                index=index,
                client_name="opensearch",
            )

        # Retry logic for connection errors when creating feature sets
        # This handles cases where OpenSearch container is starting up or temporarily unavailable
        def create_feature_set() -> requests.Response:
            return requests.post(
                f"{self.opensearch_ep}/_featureset/{name}",
                json=ftr_config,
                timeout=10,
            )

        try:
            resp = retry_on_connection_error(
                create_feature_set,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_requests_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when creating feature set '{name}' after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
            ) from e

        if resp is None:
            raise QueryError(
                f"Failed to create feature set '{name}': No response received",
                index=index,
                client_name="opensearch",
            )

        # Enhanced error handling for index_not_found_exception in API response
        if resp.status_code >= 400:
            try:
                error_json = resp.json()
                # Check for index_not_found_exception in the error response
                if "error" in error_json:
                    error_detail: JSONDict = error_json.get("error", {})
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
                                    client_name="opensearch",
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
                                client_name="opensearch",
                            )
            except (ValueError, KeyError, TypeError):
                # If JSON parsing fails or structure is unexpected, fall through to resp_msg
                pass

        resp_msg(msg=f"Create {name} feature set", resp=resp)

        # Verify feature set was actually created and persisted
        # OpenSearch LTR may return 200 but not persist the feature set in some cases
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
                max_retries=VERIFICATION_MAX_RETRIES,
                initial_delay=VERIFICATION_RETRY_DELAY,
                error_message=(
                    f"Feature set '{name}' creation appeared to succeed (HTTP {resp.status_code}), "
                    f"but verification failed - the feature set could not be retrieved. "
                    f"This may indicate a persistence issue with the OpenSearch LTR plugin."
                ),
            )
        except RuntimeError as e:
            raise QueryError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. The index '{index}' exists and is accessible\n"
                f"  2. The LTR plugin is properly installed and configured\n"
                f"  3. Try creating the feature set again or check OpenSearch logs for errors",
                index=index,
                client_name="opensearch",
            ) from e

        # Add a small delay after verification to ensure feature set is ready for queries
        # OpenSearch LTR may need additional time to index the feature set for query use
        time.sleep(0.3)  # 300ms delay to allow feature set to be fully indexed

        # Verify feature set is usable in queries (not just retrievable)
        # Feature sets may exist but not be immediately usable due to internal indexing delays
        # Try a simple test query to ensure the feature set is ready for use
        max_query_retries = DEFAULT_MAX_RETRIES
        query_retry_delay = QUERY_VERIFICATION_RETRY_DELAY

        # Extract required parameters from feature set configuration
        test_query_params = self._extract_feature_set_params(ftr_config)

        # Verify feature set is usable in queries using shared helper
        def execute_verification_query() -> JSONDict:
            test_params = self._build_feature_set_verification_query(
                name, test_query_params
            )
            try:
                test_resp = self.opensearch.search(index=index, body=test_params)
            except (OpenSearchConnectionError, TransportError) as e:
                # Connection error - convert to LTRConnectionError for retry logic
                raise LTRConnectionError(
                    f"Failed to connect to OpenSearch when verifying feature set '{name}'. "
                    f"OpenSearch container may not be ready. Error: {e}",
                    client_name="opensearch",
                ) from e

            # Check if query succeeded (no error in response)
            if "error" not in test_resp:
                logger.debug(f"Verified feature set '{name}' is usable in queries")
                return test_resp
            # Query returned an error - check if it's a feature set issue
            error_detail = test_resp.get("error", {})
            if isinstance(error_detail, dict):
                error_reason = error_detail.get("reason", "")
                # Check if it's a timing issue
                if (
                    "NullPointerException" in error_reason
                    or "getAndParse" in error_reason
                ):
                    # This is a timing error - will be retried by retry_feature_set_query
                    raise ValueError(f"Feature set not ready: {error_reason}")
            # Other errors should be raised immediately
            raise QueryError(
                f"Feature set '{name}' verification query failed: {error_detail}",
                index=index,
                client_name="opensearch",
            )

        retry_feature_set_query(
            query_func=execute_verification_query,
            featureset=name,
            index=index,
            client_name="opensearch",
            max_retries=max_query_retries,
            initial_delay=query_retry_delay,
        )

    def log_query(
        self,
        index: str,
        featureset: str,
        ids: list[str] | None,
        params: QueryParams,
    ) -> JSONDictList:
        """Execute a query and log feature values for specified documents.

        Uses OpenSearch's LTR logging functionality to extract feature values
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
            ValidationError: If the index name or feature set name is invalid.
            RuntimeError: If the feature set is not usable after retries.
            ValueError: If the response contains an error or has an invalid structure.
        """
        index = validate_index_name(index)
        featureset = validate_model_name(featureset)
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
            try:
                resp = self.opensearch.search(index=index, body=query_body)
                # Validate response (will raise ValueError if invalid)
                self._validate_search_response(resp, operation="query")
                return resp
            except RequestError as e:
                # OpenSearch client raises RequestError for API errors
                # Check if it's a feature set timing issue
                if is_feature_set_timing_error(e):
                    # Convert to ValueError so retry helper can catch it
                    raise ValueError(str(e)) from e
                # Re-raise other RequestError exceptions
                raise

        resp = retry_feature_set_query(
            query_func=execute_and_validate_query,
            featureset=featureset,
            index=index,
            client_name="opensearch",
            max_retries=DEFAULT_MAX_RETRIES,
            initial_delay=DEFAULT_RETRY_DELAY,
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
        """Submit a machine learning model to OpenSearch LTR.

        Deletes any existing model with the same name, then creates a new model
        associated with the specified feature set. Verifies the model was actually
        created and persisted before returning.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.

        Raises:
            ValidationError: If the index name, feature set name, or model name is invalid.
            RuntimeError: If model creation appears to succeed but verification fails.
        """
        featureset = validate_model_name(featureset)
        index = validate_index_name(index)
        model_name = validate_model_name(model_name)
        model_ep = f"{self.opensearch_ep}/_model/"
        create_ep = f"{self.opensearch_ep}/_featureset/{featureset}/_createmodel"

        resp = requests.delete(f"{model_ep}{model_name}")
        logger.info(f"Delete model {model_name}: {resp.status_code}")

        resp = requests.post(create_ep, json=model_payload)
        # Log the full response for debugging
        logger.info(
            f"Create model {model_name} response: status={resp.status_code}, "
            f"text={resp.text[:500] if resp.text else 'None'}"
        )
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

        # Verify model was actually created and persisted
        # OpenSearch LTR may return 200 but not persist the model in some cases
        def verify_model_exists() -> bool:
            try:
                verify_resp = requests.get(f"{model_ep}{model_name}")
                logger.debug(
                    f"Model verification: status={verify_resp.status_code}, "
                    f"text={verify_resp.text[:200] if verify_resp.text else 'None'}"
                )
                if verify_resp.status_code == 200:
                    logger.info(
                        f"Verified model '{model_name}' was created successfully"
                    )
                    # Add a small delay to allow cache to refresh before returning
                    time.sleep(0.1)
                    return True
                elif verify_resp.status_code == 404:
                    logger.warning(f"Model '{model_name}' not found yet, will retry...")
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
                max_retries=VERIFICATION_MAX_RETRIES,
                initial_delay=VERIFICATION_RETRY_DELAY,
                error_message=(
                    f"Model '{model_name}' creation appeared to succeed (HTTP {resp.status_code}), "
                    f"but verification failed - the model could not be retrieved. "
                    f"This may indicate a persistence issue with the OpenSearch LTR plugin."
                ),
            )
        except RuntimeError as e:
            logger.error(
                f"Model '{model_name}' verification failed. "
                f"Creation response: status={resp.status_code}, text={resp.text[:500] if resp.text else 'None'}"
            )
            raise ModelError(
                f"{str(e)} "
                f"Please check:\n"
                f"  1. The feature set '{featureset}' exists and is accessible\n"
                f"  2. The LTR plugin is properly installed and configured\n"
                f"  3. Check OpenSearch logs for errors during model creation\n"
                f"  4. Creation endpoint: {create_ep}\n"
                f"  5. Verification endpoint: {model_ep}{model_name}",
                model_name=model_name,
                operation="submit",
                context={"featureset": featureset, "index": index},
            ) from e

    def model_query(
        self,
        index: str,
        model: str,
        model_params: QueryParams,
        query: QueryParams,
    ) -> JSONDictList:
        """Execute a query using an LTR model for rescoring.

        Uses OpenSearch's rescore functionality to apply an LTR model to
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
            ValidationError: If the index name or model name is invalid.
            RuntimeError: If the model is not available after retries.
            ValueError: If the response contains an error or has an invalid structure.
        """
        index = validate_index_name(index)
        model = validate_model_name(model)
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
        # Note: Connection errors are handled within the helper by catching and re-raising
        def execute_and_validate_query() -> JSONDict:
            try:
                resp = self.opensearch.search(index=index, body=params)
                # Validate response (will raise ValueError if invalid)
                self._validate_search_response(resp, operation="model query")
                return resp
            except RequestError as e:
                # OpenSearch client raises RequestError for API errors
                # Check if it's a model timing issue
                if is_model_timing_error(e):
                    # Convert to ValueError so retry_model_query can catch it
                    raise ValueError(str(e)) from e
                # Re-raise other RequestError exceptions (will propagate, not retried)
                raise
            except (OpenSearchConnectionError, TransportError) as e:
                # Check if this is actually an application error or a real connection error
                if is_model_timing_error(e):
                    # This is an application error, not a connection error
                    raise ValueError(str(e)) from e
                # Real connection errors - wrap and re-raise for outer handling
                raise LTRConnectionError(
                    f"Failed to connect to OpenSearch for model query. "
                    f"OpenSearch container may not be ready. Error: {e}",
                    client_name="opensearch",
                    operation="model_query",
                ) from e

        # Use retry_on_connection_error to handle connection errors first
        def execute_with_connection_retry() -> JSONDict:
            try:
                return retry_on_connection_error(
                    execute_and_validate_query,
                    max_retries=DEFAULT_MAX_RETRIES,
                    initial_delay=DEFAULT_RETRY_DELAY,
                    is_connection_error=is_opensearch_connection_error,
                )
            except RuntimeError as e:
                # retry_on_connection_error wraps failures in RuntimeError
                # Check if it's actually a connection error or something else
                if "connection" in str(e).lower() or "connect" in str(e).lower():
                    raise LTRConnectionError(
                        f"Failed to connect to OpenSearch for model query after {DEFAULT_MAX_RETRIES} attempts. "
                        f"OpenSearch container may not be ready. Error: {e}",
                        client_name="opensearch",
                        operation="model_query",
                    ) from e
                raise

        # Use retry_model_query to handle model timing errors
        resp = retry_model_query(
            query_func=execute_with_connection_retry,
            model_name=model,
            index=index,
            client_name="opensearch",
            max_retries=DEFAULT_MAX_RETRIES,
            initial_delay=DEFAULT_RETRY_DELAY,
        )

        # Transform to consistent format between ES/Solr
        matches = []
        for hit in resp["hits"]["hits"]:
            match = hit["_source"]
            match["score"] = hit["_score"]
            matches.append(match)

        return matches

    def query(self, index: str, query: QueryParams) -> JSONDictList:
        """Execute a search query against an OpenSearch index.

        Args:
            index: Index name to query.
            query: Query dictionary in OpenSearch query DSL format.

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Solr.

        Raises:
            ValidationError: If the index name is invalid.
            QueryError: If the query fails due to network errors, index not found,
                or other client-related issues.
            ValueError: If the response contains an error or has an invalid structure.
        """
        index = validate_index_name(index)
        logger.debug(f"OpenSearch query: {query}")

        # Retry logic for connection errors with exponential backoff
        # This handles cases where OpenSearch container is starting up or temporarily unavailable
        def execute_query() -> JSONDict:
            return self.opensearch.search(index=index, body=query)

        try:
            resp = retry_on_connection_error(
                execute_query,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_opensearch_connection_error,
            )
        except RuntimeError as e:
            query_str = str(query)[:200]
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch after {DEFAULT_MAX_RETRIES} attempts. "
                f"This usually means the OpenSearch container is not running or not ready yet. "
                f"Error: {e}. "
                f"Please ensure OpenSearch containers are started and healthy before running notebooks.",
                client_name="opensearch",
                operation="query",
            ) from e
        except (OpenSearchConnectionError, TransportError, RequestError) as e:
            query_str = str(query)[:200]
            raise QueryError(
                f"OpenSearch query failed: {e}",
                index=index,
                query=query_str,
                client_name="opensearch",
            ) from e

        try:
            self._validate_search_response(resp, operation="query")
        except ValueError as e:
            query_str = str(query)[:200]
            raise QueryError(
                f"Invalid OpenSearch query response: {e}",
                index=index,
                query=query_str,
                client_name="opensearch",
            ) from e

        # Transform to consistent format between ES/Solr
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
            ValidationError: If the index name or feature set name is invalid.
            RuntimeError: If the feature set is not found.
        """
        index = validate_index_name(index)
        name = validate_model_name(name)
        resp = requests.get(f"{self.opensearch_ep}/_featureset/{name}")

        # Check HTTP status code first
        if resp.status_code == 404:
            raise QueryError(
                f"Feature set '{name}' not found. "
                f"Please ensure the feature set has been created using "
                f"client.create_featureset(index='{index}', name='{name}', ftr_config=...). "
                f"If the index doesn't exist, create it first using client.create_index('{index}').",
                index=index,
                client_name="opensearch",
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
                client_name="opensearch",
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

        Raises:
            ValidationError: If the index name is invalid.
        """
        index = validate_index_name(index)

        # Retry logic for connection errors
        def get_document() -> JSONDict:
            resp = self.opensearch.get(index=index, id=doc_id)
            return resp["_source"]

        try:
            return retry_on_connection_error(
                get_document,
                max_retries=DEFAULT_MAX_RETRIES,
                initial_delay=DEFAULT_RETRY_DELAY,
                is_connection_error=is_opensearch_connection_error,
            )
        except RuntimeError as e:
            raise LTRConnectionError(
                f"Failed to connect to OpenSearch when getting document '{doc_id}' from index '{index}' after {DEFAULT_MAX_RETRIES} attempts. "
                f"OpenSearch container may not be ready. Error: {e}",
                client_name="opensearch",
                operation="get_doc",
            ) from e
