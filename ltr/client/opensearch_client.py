"""OpenSearch client implementation for Learn-to-Rank.

This module provides the OpenSearch-specific implementation of the BaseClient
interface, handling OpenSearch API calls and response formatting for LTR operations.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable
from typing import Any

import requests
from opensearchpy import OpenSearch, helpers

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


class OpenSearchResp:
    """Response wrapper for OpenSearch API responses.

    Converts OpenSearch JSON responses into a format compatible with
    the resp_msg error handling function.

    Attributes:
        status_code: HTTP status code (200 for success, 400 for errors).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize an OpenSearchResp wrapper.

        Args:
            resp: OpenSearch API response dictionary.
        """
        self.status_code: int = 400
        if "acknowledged" in resp and resp["acknowledged"]:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text: str = json.dumps(resp, indent=2)


class BulkResp:
    """Response wrapper for OpenSearch bulk operation responses.

    Attributes:
        status_code: HTTP status code (201 if documents indexed, 400 otherwise).
    """

    def __init__(self, resp: tuple[int, Any]) -> None:
        """Initialize a BulkResp wrapper.

        Args:
            resp: OpenSearch bulk operation response tuple.
        """
        self.status_code: int = 400
        if resp[0] > 0:
            self.status_code = 201


class SearchResp:
    """Response wrapper for OpenSearch search responses.

    Attributes:
        status_code: HTTP status code (200 if hits found, 400 otherwise).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp: JSONDict) -> None:
        """Initialize a SearchResp wrapper.

        Args:
            resp: OpenSearch search API response dictionary.
        """
        self.status_code: int = 400
        if "hits" in resp:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text: str = json.dumps(resp, indent=2)


class OpenSearchClient(BaseClient):
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
    """

    def __init__(self, configs_dir: str = ".") -> None:
        """Initialize an OpenSearchClient.

        Args:
            configs_dir: Directory containing OpenSearch configuration files
                (default: current directory).
        """
        self.docker: bool = os.environ.get("LTR_DOCKER") is not None
        self.configs_dir: str = configs_dir  # location of elastic configs

        if self.docker:
            self.host = "opensearch-node1"
        else:
            self.host = "localhost"

        self.opensearch_ep: str = f"http://{self.host}:9201/_ltr"
        self.opensearch: OpenSearch = OpenSearch(f"http://{self.host}:9201")
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
        """
        return self.opensearch.indices.exists(index=index)

    def delete_index(self, index: str) -> None:
        """Delete an OpenSearch index.

        Args:
            index: Index name to delete.

        Note:
            Does not raise exceptions if the index doesn't exist (404) or
            if there are other client errors (400).
        """
        resp = self.opensearch.indices.delete(index=index, ignore=[400, 404])
        resp_msg(
            msg=f"Deleted index {index}",
            resp=OpenSearchResp(resp),
            throw=False,
            ignore=[400, 404],
        )

    def create_index(self, index: str) -> None:
        """Create an OpenSearch index from local configuration files.

        Loads index settings from a JSON file and creates the index in OpenSearch.

        Args:
            index: Index name to create. The configuration file should be named
                "{index}_settings.json" in the configs_dir directory.
        """
        cfg_json_path = os.path.join(self.configs_dir, f"{index}_settings.json")
        with open(cfg_json_path) as src:
            settings = json.load(src)
            resp = self.opensearch.indices.create(index=index, body=settings)
            resp_msg(msg=f"Created index {index}", resp=OpenSearchResp(resp))

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
                        "Expecting docs to have field 'id' that uniquely identifies document"
                    )
                add_cmd = {"_index": index, "_id": doc["id"], "_source": doc}
                yield add_cmd

        if isinstance(doc_src, str):
            raise ValueError(
                "OpenSearchClient.index_documents does not support file paths"
            )
        if callable(doc_src):
            doc_src = doc_src()
        resp = helpers.bulk(self.opensearch, bulk_docs(doc_src), chunk_size=100)
        self.opensearch.indices.refresh(index=index)
        resp_msg(msg=f"Streaming Bulk index DONE {index}", resp=BulkResp(resp))

    def reset_ltr(self, index: str) -> None:
        """Reset the Learn-to-Rank feature store.

        Deletes and recreates the default LTR feature store. Note that the
        index parameter is accepted for API compatibility but not used, as
        OpenSearch LTR is not bound to a specific index.

        Args:
            index: Index name (unused, kept for API compatibility).
        """
        resp = requests.delete(self.opensearch_ep)
        resp_msg(
            msg="Removed Default LTR feature store".format(), resp=resp, throw=False
        )
        resp = requests.put(self.opensearch_ep)
        resp_msg(msg="Initialize Default LTR feature store".format(), resp=resp)

    def create_featureset(
        self, index: str, name: str, ftr_config: FeatureConfig
    ) -> None:
        """Create a feature set in OpenSearch LTR.

        Args:
            index: Index name (used for validation - index must exist).
            name: Name of the feature set to create.
            ftr_config: Feature set configuration dictionary.

        Raises:
            RuntimeError: If the index does not exist or feature set creation fails.
        """
        # Check if index exists before creating feature set
        # OpenSearch LTR validates feature sets against indices, so the index must exist
        if not self.check_index_exists(index):
            raise RuntimeError(
                f"Cannot create feature set '{name}': index '{index}' does not exist. "
                f"Please create the index first using create_index('{index}')."
            )

        resp = requests.post(
            f"{self.opensearch_ep}/_featureset/{name}", json=ftr_config
        )

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

    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Get the name of a feature by its index.

        Args:
            config: Feature set configuration dictionary.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.
        """
        if isinstance(config, list):
            raise ValueError("OpenSearchClient.get_feature_name requires a dict config")
        return config["featureset"]["features"][int(ftr_idx) - 1]["name"]

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

        Args:
            index: Index name to query.
            featureset: Name of the feature set to use for logging.
            ids: List of document IDs to retrieve feature values for.
            params: Optional query parameters to pass to the feature set
                (default: empty dict).

        Returns:
            list: List of document dictionaries, each with an added "ltr_features"
                field containing the logged feature values.
        """
        query_params = params.copy() if params else {}
        params = {
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
            params["query"]["bool"]["must"] = terms_query

        resp = self.opensearch.search(index=index, body=params)
        # resp_msg(msg="Searching {} - {}".format(index, str(terms_query)[:20]), resp=SearchResp(resp))

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
        """Submit a machine learning model to OpenSearch LTR.

        Deletes any existing model with the same name, then creates a new model
        associated with the specified feature set.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.
        """
        model_ep = f"{self.opensearch_ep}/_model/"
        create_ep = f"{self.opensearch_ep}/_featureset/{featureset}/_createmodel"

        resp = requests.delete(f"{model_ep}{model_name}")
        logger.info(f"Delete model {model_name}: {resp.status_code}")

        resp = requests.post(create_ep, json=model_payload)
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to OpenSearch LTR.

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
        """Submit an XGBoost model to OpenSearch LTR.

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

        Uses OpenSearch's rescore functionality to apply an LTR model to
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

        resp = self.opensearch.search(index=index, body=params)
        # resp_msg(msg="Searching {} - {}".format(index, str(query)[:20]), resp=SearchResp(resp))

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
        """
        logger.debug(f"OpenSearch query: {query}")
        resp = self.opensearch.search(index=index, body=query)
        # resp_msg(msg="Searching {} - {}".format(index, str(query)[:20]), resp=SearchResp(resp))

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
            RuntimeError: If the feature set is not found.
        """
        resp = requests.get(f"{self.opensearch_ep}/_featureset/{name}")

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
        resp = self.opensearch.get(index=index, id=doc_id)
        return resp["_source"]
