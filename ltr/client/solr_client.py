"""Solr client implementation for Learn-to-Rank.

This module provides the Solr-specific implementation of the BaseClient
interface, handling Solr API calls and response formatting for LTR operations.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable, Iterator

import requests

from ltr.exceptions import LTRIndexError, ModelError, QueryError
from ltr.helpers.convert import convert
from ltr.helpers.handle_resp import resp_msg
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

# Retry configuration constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 0.1  # 100ms delay between retries
FEATURE_SET_MAX_RETRIES = 5
FEATURE_SET_RETRY_DELAY = 0.2  # 200ms initial delay


class SolrClient(BaseClient):
    """Solr client for Learn-to-Rank operations.

    Implements the BaseClient interface for Apache Solr, providing methods
    for index (core) management, feature store creation, model submission,
    and querying. Solr LTR is bound to specific cores/indices.

    Attributes:
        docker: Boolean indicating if running in Docker environment.
        solr: Requests session for making HTTP calls.
        solr_base_ep: Base Solr endpoint URL.
        host: Hostname for Solr server.
        port: Port number for Solr server connection.
    """

    def __init__(self, port: int | None = None) -> None:
        """Initialize a SolrClient.

        Sets up connection to Solr server, using Docker hostname if LTR_DOCKER
        environment variable is set, otherwise connecting to localhost.

        Args:
            port: Optional port number. If not provided, uses SOLR_PORT environment
                variable if set, otherwise defaults to 8983.
        """
        self.docker: bool = os.environ.get("LTR_DOCKER") is not None
        self.solr: requests.Session = requests.Session()

        # Determine port: explicit parameter > environment variable > default
        if port is None:
            port_env = os.environ.get("SOLR_PORT")
            if port_env:
                try:
                    port = int(port_env)
                except ValueError:
                    raise ValueError(
                        f"Invalid SOLR_PORT environment variable: '{port_env}'. Must be an integer."
                    )
            else:
                port = 8983
        self.port = port

        if self.docker:
            self.host = "solr"
            self.solr_base_ep = f"http://solr:{self.port}/solr"
        else:
            self.host = "localhost"
            self.solr_base_ep = f"http://localhost:{self.port}/solr"

    def get_host(self) -> str:
        """Get the Solr hostname.

        Returns:
            str: Hostname for the Solr server.
        """
        return self.host

    def name(self) -> str:
        """Get the client name.

        Returns:
            str: Always returns "solr".
        """
        return "solr"

    def check_index_exists(self, index: str) -> bool:
        """Check if a Solr core (index) exists.

        Args:
            index: Core name to check.

        Returns:
            bool: True if the core exists, False otherwise.
        """
        resp = requests.get(
            f"{self.solr_base_ep}/admin/cores?action=STATUS&core={index}"
        )
        return bool(re.search("instanceDir", str(resp.content)))

    def delete_index(self, index: str) -> None:
        """Delete a Solr core (index).

        Unloads the core and deletes its index, data directory, and instance directory.

        Args:
            index: Core name to delete.
        """
        params = {
            "action": "UNLOAD",
            "core": index,
            "deleteIndex": "true",
            "deleteDataDir": "true",
            "deleteInstanceDir": "true",
        }

        resp = requests.get(f"{self.solr_base_ep}/admin/cores?", params=params)
        resp_msg(msg=f"Deleted index {index}", resp=resp, throw=False)

    def create_index(self, index: str) -> None:
        """Create a Solr core (index) from a configset.

        Creates a new core using a configset with the same name as the index.
        Presumes there is a link between the Docker container and the 'index'
        directory under docker/solr/ (e.g., docker/solr/tmdb/ is linked into
        Docker container configsets).

        Args:
            index: Core name to create. A configset with the same name must exist.

        Raises:
            RuntimeError: If core creation fails (HTTP status >= 400).
            LTRIndexError: If core creation appears to succeed but verification fails
                (core cannot be found after creation).
        """
        params = {
            "action": "CREATE",
            "name": index,
            "configSet": index,
        }
        resp = requests.get(f"{self.solr_base_ep}/admin/cores?", params=params)
        resp_msg(msg=f"Created index {index}", resp=resp)

        # Verify index (core) was actually created and is accessible
        # Solr may return success but the core might not be immediately available
        # Retry a few times with small delays to handle potential timing issues
        max_retries = DEFAULT_MAX_RETRIES
        retry_delay = DEFAULT_RETRY_DELAY
        for attempt in range(max_retries):
            if self.check_index_exists(index):
                # Index exists - verification successful
                break
            # Index not found yet, retry if we have attempts left
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            # All retries exhausted, raise error
            raise LTRIndexError(
                f"Index (core) '{index}' creation appeared to succeed (HTTP 200), "
                f"but verification failed - the core could not be found. "
                f"This may indicate a persistence issue with Solr. "
                f"Please check:\n"
                f"  1. Solr is running and accessible\n"
                f"  2. The configset '{index}' exists\n"
                f"  3. Try creating the core again or check Solr logs for errors",
                index=index,
                operation="create_index",
                client_name="solr",
            )

    def index_documents(
        self,
        index: str,
        doc_src: Iterable[JSONDict] | Callable[[], Iterable[JSONDict]],
    ) -> None:
        """Index documents into Solr using batch updates.

        Processes documents in batches and commits at the end. Automatically
        appends "T00:00:00Z" to release_date fields if present.

        Args:
            index: Core name to index documents into.
            doc_src: Iterable of document dictionaries or a callable that returns
                an iterable. File paths (str) are not supported.

        Raises:
            ValueError: If doc_src is a string (file paths not supported).
        """

        def commit() -> None:
            """Commit pending changes to the index."""
            resp = requests.get(f"{self.solr_base_ep}/{index}/update?commit=true")
            resp_msg(msg=f"Committed index {index}", resp=resp)

        def flush(docs: JSONDictList) -> None:
            """Send a batch of documents to Solr for indexing.

            Args:
                docs: List of documents to index. The list is cleared after sending.
            """
            # print('Flushing {} docs'.format(len(docs)))
            requests.post(f"{self.solr_base_ep}/{index}/update", json=docs)
            # resp_msg(msg="Done", resp=resp)
            docs.clear()

        if isinstance(doc_src, str):
            raise ValidationError(
                "SolrClient.index_documents does not support file paths"
            )
        if callable(doc_src):
            doc_src = doc_src()

        batch_size = 5000
        docs: JSONDictList = []
        for doc in doc_src:
            if "release_date" in doc and doc["release_date"] is not None:
                doc["release_date"] += "T00:00:00Z"

            docs.append(doc)

            if len(docs) % batch_size == 0:
                flush(docs)

        flush(docs)
        commit()

    def reset_ltr(self, index: str) -> None:
        """Reset the Learn-to-Rank feature store and models for an index.

        Deletes all models and feature stores associated with the specified core.

        Args:
            index: Core name to reset LTR for.

        Raises:
            RuntimeError: If model or feature store deletion fails (HTTP status >= 400).
        """
        models = self.get_models(index)
        for model in models:
            resp = requests.delete(
                f"{self.solr_base_ep}/{index}/schema/model-store/{model}"
            )
            resp_msg(msg=f"Deleted {model} model", resp=resp)

        stores = self.get_feature_stores(index)
        for store in stores:
            resp = requests.delete(
                f"{self.solr_base_ep}/{index}/schema/feature-store/{store}"
            )
            resp_msg(msg=f"Deleted {store} Featurestore", resp=resp)

    def validate_featureset(self, name: str, config: JSONDictList) -> None:
        """Validate that all features in a config belong to the specified store.

        Args:
            name: Expected feature store name.
            config: List of feature configuration dictionaries.

        Raises:
            ValueError: If any feature doesn't have the correct store name.
        """
        for feature in config:
            if "store" not in feature or feature["store"] != name:
                raise ValidationError(
                    f'Feature {feature["name"]} needs to be created with "store": "{name}" '
                )

    def create_featureset(
        self, index: str, name: str, ftr_config: FeatureConfig
    ) -> None:
        """Create a feature store in Solr LTR.

        Args:
            index: Core name to create the feature store in.
            name: Name of the feature store to create.
            ftr_config: List of feature configuration dictionaries. All features
                must have "store" set to the feature store name.

        Raises:
            ValueError: If any feature doesn't have the correct store name.
        """
        if isinstance(ftr_config, dict):
            raise ValidationError(
                "SolrClient.create_featureset requires a list of features"
            )
        self.validate_featureset(name, ftr_config)
        resp = requests.put(
            f"{self.solr_base_ep}/{index}/schema/feature-store", json=ftr_config
        )
        resp_msg(msg=f"Created {name} feature store under {index}:", resp=resp)

    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Get the name of a feature by its index.

        Args:
            config: Feature configuration list.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.

        Raises:
            ValueError: If config is a dictionary instead of a list.
        """
        if isinstance(config, dict):
            raise ValidationError("SolrClient.get_feature_name requires a list config")
        return config[int(ftr_idx) - 1]["name"]

    def log_query(
        self,
        index: str,
        featureset: str,
        ids: list[str] | None,
        params: QueryParams,
    ) -> JSONDictList:
        """Execute a query and log feature values for specified documents.

        Uses Solr's LTR feature logging functionality to extract feature values
        for documents matching the given IDs, using the specified feature store.

        Args:
            index: Core name to query.
            featureset: Name of the feature store to use for logging.
            ids: List of document IDs to retrieve feature values for, or None
                to query all documents.
            params: Optional query parameters to pass as external feature inputs
                (default: empty dict).

        Returns:
            list: List of document dictionaries, each with an added "ltr_features"
                field containing the logged feature values.

        Raises:
            RuntimeError: If the feature set is not usable after retries, if no response
                is received after all retries, or if the response structure is invalid.
        """
        query_params = params.copy() if params else {}
        efi_options = []
        for key, val in query_params.items():
            efi_options.append(f'efi.{key}="{val}"')

        efi_str = " ".join(efi_options)

        query = "*:*" if ids is None else f"{{!terms f=id}}{','.join(ids)}"

        solr_params = {
            "fl": f"id,[features store={featureset} {efi_str}]",
            "q": query,
            "rows": 1000,
            "wt": "json",
        }

        # Retry logic for feature set timing issues
        # Solr LTR may need time to index feature sets after creation
        max_retries = FEATURE_SET_MAX_RETRIES
        retry_delay = FEATURE_SET_RETRY_DELAY
        resp_json = None

        for attempt in range(max_retries):
            resp = requests.post(
                f"{self.solr_base_ep}/{index}/select", data=solr_params
            )
            # resp_msg(msg='Searching {}'.format(index), resp=resp)
            resp_json = resp.json()

            # Check for error responses
            if "error" in resp_json:
                error_detail = resp_json.get("error", {})
                error_msg = error_detail.get("msg", "Unknown Solr error")

                # Check if it's a feature set timing issue
                # Common errors: "Unknown featureset", feature store not ready
                if (
                    "Unknown featureset" in error_msg
                    or "featureset" in error_msg.lower()
                    or "feature store" in error_msg.lower()
                    or (
                        "store" in error_msg.lower()
                        and "not found" in error_msg.lower()
                    )
                ):
                    if attempt < max_retries - 1:
                        # Feature set may not be ready yet, retry
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Gradual backoff
                        continue
                    else:
                        raise QueryError(
                            f"Solr log_query failed after {max_retries} attempts. "
                            f"Feature set '{featureset}' may not be ready for queries yet. "
                            f"Error: {error_msg}. "
                            f"Try waiting a moment and using the feature set again, or verify "
                            f"the feature set was created successfully.",
                            index=index,
                            client_name="solr",
                        )
                else:
                    # Non-timing error, raise immediately
                    raise QueryError(
                        f"Solr log_query failed: {error_msg}",
                        index=index,
                        client_name="solr",
                    )
            else:
                # No error, break out of retry loop
                break

        if resp_json is None:
            raise QueryError(
                f"Solr log_query failed: no response received after {max_retries} attempts",
                index=index,
                client_name="solr",
            )

        # Validate response structure
        if "response" not in resp_json:
            raise QueryError(
                f"Unexpected Solr response structure: missing 'response' key. "
                f"Response: {resp_json}",
                index=index,
                client_name="solr",
            )

        if "docs" not in resp_json["response"]:
            raise QueryError(
                f"Unexpected Solr response structure: missing 'docs' key in response. "
                f"Response: {resp_json}",
                index=index,
                client_name="solr",
            )

        def parse_features(features: str) -> list[float]:
            """Parse feature string into a list of float values.

            Args:
                features: Comma-separated string of feature=value pairs.

            Returns:
                list: List of feature values as floats.
            """
            fv = []

            all_features = features.split(",")

            for feature in all_features:
                elements = feature.split("=")
                fv.append(float(elements[1]))

            return fv

        # Clean up features to consistent format
        for doc in resp_json["response"]["docs"]:
            if "[features]" in doc:
                doc["ltr_features"] = parse_features(doc["[features]"])
            else:
                # If features are missing, set empty list
                doc["ltr_features"] = []

        return resp_json["response"]["docs"]

    def submit_model(
        self,
        featureset: str,
        index: str,
        model_name: str,
        model_payload: ModelPayload,
    ) -> None:
        """Submit a machine learning model to Solr LTR.

        Deletes any existing model with the same name, then creates a new model
        in the specified core.

        Args:
            featureset: Feature store name (unused, kept for API compatibility).
            index: Core name to create the model in.
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.

        Raises:
            RuntimeError: If model creation or deletion fails (HTTP status >= 400).
        """
        url = f"{self.solr_base_ep}/{index}/schema/model-store"
        resp = requests.delete(f"{url}/{model_name}")
        resp_msg(msg=f"Deleted Model {model_name}", resp=resp)

        resp = requests.put(url, json=model_payload)
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to Solr LTR, converting it to Solr representation.

        Retrieves the feature store configuration, maps feature indices to names,
        converts the RankLib model to Solr format, and submits it.

        Args:
            featureset: Name of the feature store to associate the model with.
            index: Core name to create the model in.
            model_name: Name of the model to create.
            model_payload: RankLib model definition string.

        Raises:
            RuntimeError: If feature store retrieval or model submission fails.
        """
        resp = requests.get(
            f"{self.solr_base_ep}/{index}/schema/feature-store/{featureset}"
        )
        resp_msg(msg=f"Submit Model {model_name} Ftr Set {featureset}", resp=resp)
        metadata = resp.json()
        features = metadata["features"]

        feature_dict = {}
        for idx, value in enumerate(features):
            feature_dict[idx + 1] = value["name"]

        feature_mapping, _ = self.feature_set(index, featureset)

        solr_model = convert(model_payload, model_name, featureset, feature_mapping)
        self.submit_model(featureset, index, model_name, solr_model)

    def model_query(
        self,
        index: str,
        model: str,
        model_params: QueryParams,
        query: QueryParams,
    ) -> JSONDictList:
        """Execute a query using an LTR model for reranking.

        Uses Solr's LTR reranking query parser to apply an LTR model to
        re-rank search results.

        Args:
            index: Core name to query.
            model: Name of the LTR model to use for reranking.
            model_params: Parameters to pass to the model (unused in Solr).
            query: Query parameters dictionary. Must contain a "q" key with the query string.

        Returns:
            list: List of document dictionaries with scores.

        Raises:
            TypeError: If query is not a dictionary.
            ValueError: If query dict does not contain a "q" key.
            RuntimeError: If the Solr response indicates an error or has unexpected structure.
        """
        # Extract query string from QueryParams dict
        # Solr's model_query expects a query string in the "q" parameter
        if not isinstance(query, dict):
            raise TypeError(f"query must be a dict (QueryParams), got {type(query)}")

        query_str = query.get("q")
        if query_str is None:
            raise ValidationError(
                'query dict must contain a "q" key with the query string'
            )

        url = f"{self.solr_base_ep}/{index}/select?"
        params = {
            "q": query_str,
            "fl": "score *",
            "rq": f"{{!ltr model={model}}}",
            "rows": 10000,
        }

        resp = requests.post(url, data=params)
        resp_msg(msg=f"Search keywords - {query_str}", resp=resp)
        resp_json = resp.json()

        # Check for error responses
        if "error" in resp_json:
            error_msg = resp_json.get("error", {}).get("msg", "Unknown Solr error")
            raise ModelError(
                f"Solr model_query failed: {error_msg}",
                model_name=model,
                context={"index": index},
            )

        # Validate response structure
        if "response" not in resp_json:
            raise ModelError(
                f"Unexpected Solr response structure: missing 'response' key. "
                f"Response: {resp_json}",
                model_name=model,
                context={"index": index},
            )

        if "docs" not in resp_json["response"]:
            raise ModelError(
                f"Unexpected Solr response structure: missing 'docs' key in response. "
                f"Response: {resp_json}",
                model_name=model,
                context={"index": index},
            )

        return resp_json["response"]["docs"]

    def query(self, index: str, query: QueryParams) -> JSONDictList:
        """Execute a search query against a Solr core.

        Args:
            index: Core name to query.
            query: Query parameters dictionary (e.g., {"q": "search terms", "wt": "json"}).

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Elasticsearch/OpenSearch (score -> _score).

        Raises:
            QueryError: If the query fails due to network errors, index not found,
                or other client-related issues.
            ValueError: If JSON parsing fails or response structure is invalid.
        """
        url = f"{self.solr_base_ep}/{index}/select?"

        try:
            resp = requests.post(url, data=query)
        except requests.exceptions.RequestException as e:
            query_str = str(query)[:200]
            raise QueryError(
                f"Solr network request failed: {e}",
                index=index,
                query=query_str,
                client_name="solr",
            ) from e

        # Check HTTP status code before parsing JSON
        if resp.status_code >= 400:
            query_str = str(query)[:200]
            try:
                # Try to parse error response as JSON
                error_json = resp.json()
                error_details = self._extract_solr_error_details(error_json)
                raise QueryError(
                    f"Solr query failed [HTTP {resp.status_code}]: {error_details}",
                    index=index,
                    query=query_str,
                    client_name="solr",
                )
            except ValueError:
                # If JSON parsing fails, use raw response text
                raise QueryError(
                    f"Solr query failed [HTTP {resp.status_code}]: {resp.text[:500]}",
                    index=index,
                    query=query_str,
                    client_name="solr",
                )

        # Parse JSON response
        try:
            resp_json = resp.json()
        except ValueError as e:
            query_str = str(query)[:200]
            raise QueryError(
                f"Failed to parse Solr response as JSON: {e}. "
                f"Response status: {resp.status_code}, "
                f"Response text (first 500 chars): {resp.text[:500]}",
                index=index,
                query=query_str,
                client_name="solr",
            ) from e

        # Check for error responses in JSON structure
        if "error" in resp_json:
            query_str = str(query)[:200]
            error_details = self._extract_solr_error_details(resp_json)
            raise QueryError(
                f"Solr query failed: {error_details}",
                index=index,
                query=query_str,
                client_name="solr",
            )

        # Validate response structure
        if "response" not in resp_json:
            raise QueryError(
                f"Unexpected Solr response structure for index '{index}': "
                f"missing 'response' key. Response keys: {list(resp_json.keys())}. "
                f"Full response (first 1000 chars): {str(resp_json)[:1000]}",
                index=index,
                client_name="solr",
            )

        if not isinstance(resp_json["response"], dict):
            raise QueryError(
                f"Unexpected Solr response structure for index '{index}': "
                f"'response' is not a dictionary (got {type(resp_json['response'])}). "
                f"Response: {resp_json['response']}",
                index=index,
                client_name="solr",
            )

        if "docs" not in resp_json["response"]:
            response_keys = list(resp_json["response"].keys())
            raise QueryError(
                f"Unexpected Solr response structure for index '{index}': "
                f"missing 'docs' key in response. Response keys: {response_keys}. "
                f"Response structure: {resp_json['response']}",
                index=index,
                client_name="solr",
            )

        if not isinstance(resp_json["response"]["docs"], list):
            raise QueryError(
                f"Unexpected Solr response structure for index '{index}': "
                f"'docs' is not a list (got {type(resp_json['response']['docs'])}). "
                f"Response: {resp_json['response']['docs']}",
                index=index,
                client_name="solr",
            )

        # Transform to be consistent
        for doc in resp_json["response"]["docs"]:
            if "score" in doc:
                doc["_score"] = doc["score"]

        return resp_json["response"]["docs"]

    def _extract_solr_error_details(self, error_json: JSONDict) -> str:
        """Extract error details from a Solr error response.

        Solr error responses can have different structures:
        - Simple: {"error": {"msg": "error message"}}
        - Detailed: {"error": {"msg": "...", "code": 400, "metadata": [...]}}
        - Multiple errors: {"error": {"msg": "...", "details": [...]}}

        Args:
            error_json: JSON dictionary containing error information.

        Returns:
            str: Formatted error message with all available details.
        """
        error_obj = error_json.get("error", {})

        if not isinstance(error_obj, dict):
            return f"Unknown error format: {error_obj}"

        # Extract primary error message
        error_msg = error_obj.get("msg", "Unknown Solr error")

        # Collect additional error details
        details = []

        # Add error code if present
        if "code" in error_obj:
            details.append(f"code={error_obj['code']}")

        # Add trace if present (often contains useful debugging info)
        if "trace" in error_obj:
            trace = error_obj["trace"]
            if isinstance(trace, str) and len(trace) > 0:
                # Truncate long traces
                trace_preview = trace[:200] + "..." if len(trace) > 200 else trace
                details.append(f"trace={trace_preview}")

        # Add metadata if present
        if "metadata" in error_obj:
            metadata = error_obj["metadata"]
            if isinstance(metadata, list) and len(metadata) > 0:
                details.append(f"metadata={metadata}")

        # Add details array if present (for multiple errors)
        if "details" in error_obj:
            error_details = error_obj["details"]
            if isinstance(error_details, list) and len(error_details) > 0:
                details.append(f"details={error_details}")

        # Construct final error message
        if details:
            return f"{error_msg} ({', '.join(details)})"
        return error_msg

    def analyze(self, index: str, fieldtype: str, text: str) -> JSONDict:
        """Analyze text using a Solr field type analyzer.

        Args:
            index: Core name to use for analysis.
            fieldtype: Field type name to use for analysis.
            text: Text to analyze.

        Returns:
            dict: Analysis result containing token stream information.
        """
        # http://localhost:8983/solr/msmarco/analysis/field
        url = f"{self.solr_base_ep}/{index}/analysis/field?"

        query = {"analysis.fieldtype": fieldtype, "analysis.fieldvalue": text}

        resp = requests.post(url, data=query)

        analysis_resp = resp.json()
        tok_stream = analysis_resp["analysis"]["field_types"]["text_general"]["index"]
        tok_stream_result = tok_stream[-1]
        return tok_stream_result

    def term_vectors_skip_to(self, index: str, q: str = "*:*", skip: int = 0) -> str:
        """Get a cursor mark for skipping to a specific position in term vectors.

        Uses Solr's term vector request handler to advance through documents
        and return a cursor mark for the specified skip position.

        Args:
            index: Core name to query.
            q: Query string to filter documents (default: "*:*").
            skip: Number of documents to skip (default: 0).

        Returns:
            str: Cursor mark string for the skip position.
        """
        url = f"{self.solr_base_ep}/{index}/tvrh/"
        query = {
            "q": q,
            "cursorMark": "*",
            "sort": "id asc",
            "fl": "id",
            "rows": str(skip),
        }
        tvrh_resp = requests.post(url, data=query)
        return tvrh_resp.json()["nextCursorMark"]

    def term_vectors(
        self, index: str, field: str, q: str = "*:*", start_cursor: str = "*"
    ) -> Iterator[tuple[str, JSONDict]]:
        """Extract all term vectors for a field using cursor-based pagination.

        Uses Solr's term vector request handler to iterate through all documents
        and extract term vectors for the specified field.

        Args:
            index: Core name to query.
            field: Field name to extract term vectors for.
            q: Query string to filter documents (default: "*:*").
            start_cursor: Initial cursor mark to start from (default: "*").

        Yields:
            tuple: Pairs of (doc_id, term_vector_dict) for each document.
                Term vector dict contains term frequencies and positions for the field.
        """
        # http://localhost:8983/solr/msmarco/tvrh?q=*:*&start=0&rows=10&fl=id,body&tvComponent=true&tv.positions=true
        url = f"{self.solr_base_ep}/{index}/tvrh/"

        next_cursor = start_cursor
        while True:
            query = {
                "q": q,
                "cursorMark": next_cursor,
                "fl": "id",
                "tv.fl": field,
                "tvComponent": "true",
                "tv.positions": "true",
                "sort": "id asc",
                "rows": "2000",
                "wt": "json",
            }

            tvrh_resp = requests.post(url, data=query).json()

            from ltr.client.solr_parse import parse_termvect_namedlist

            parsed = parse_termvect_namedlist(tvrh_resp["termVectors"], field=field)
            # parse_termvect_namedlist returns a dict (it calls .items() internally)
            parsed_dict: dict = parsed if isinstance(parsed, dict) else {}
            for doc_id, terms in parsed_dict.items():
                try:
                    yield doc_id, terms[field]
                except KeyError:
                    yield doc_id, {}

            next_cursor = tvrh_resp["nextCursorMark"]

            if query["cursorMark"] == next_cursor:
                break

    def get_feature_stores(self, index: str) -> list[str]:
        """Get list of feature store names for a core.

        Args:
            index: Core name to query.

        Returns:
            list: List of feature store names.
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/feature-store")
        response = resp.json()
        return response["featureStores"]

    def get_models(self, index: str) -> list[str]:
        """Get list of model names for a core.

        Args:
            index: Core name to query.

        Returns:
            list: List of model names.
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/model-store")
        response = resp.json()
        return [model["name"] for model in response["models"]]

    def feature_set(self, index: str, name: str) -> FeatureSetResult:
        """Retrieve a feature store configuration.

        Args:
            index: Core name to query.
            name: Name of the feature store to retrieve.

        Returns:
            tuple: A tuple containing:
                - mapping: List of dictionaries with feature names
                - raw_feature_set: Full feature store configuration list

        Raises:
            RuntimeError: If the feature store retrieval fails (HTTP status >= 400).
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/feature-store/{name}")
        resp_msg(msg=f"Feature Set {name}...", resp=resp)

        response = resp.json()

        raw_feature_set = response["features"]

        mapping = []
        for feature in response["features"]:
            mapping.append({"name": feature["name"]})

        return mapping, raw_feature_set

    def get_doc(self, doc_id: str, index: str) -> JSONDict:
        """Retrieve a single document by ID.

        Args:
            doc_id: Document ID to retrieve.
            index: Core name containing the document.

        Returns:
            dict: Document dictionary.

        Raises:
            IndexError: If the document is not found.
        """
        params = {"q": f"id:{doc_id}", "wt": "json"}

        resp_json = requests.post(
            f"{self.solr_base_ep}/{index}/select", data=params
        ).json()

        # Check for error responses
        if "error" in resp_json:
            error_msg = resp_json.get("error", {}).get("msg", "Unknown Solr error")
            raise QueryError(
                f"Solr get_doc failed: {error_msg}",
                index=index,
                client_name="solr",
            )

        # Validate response structure
        if "response" not in resp_json:
            raise QueryError(
                f"Unexpected Solr response structure: missing 'response' key. "
                f"Response: {resp_json}",
                index=index,
                client_name="solr",
            )

        if "docs" not in resp_json["response"]:
            raise QueryError(
                f"Unexpected Solr response structure: missing 'docs' key in response. "
                f"Response: {resp_json}",
                index=index,
                client_name="solr",
            )

        if not resp_json["response"]["docs"]:
            raise IndexError(f"Document {doc_id} not found in index {index}")

        return resp_json["response"]["docs"][0]
