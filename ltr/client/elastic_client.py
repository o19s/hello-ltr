"""Elasticsearch client implementation for Learn-to-Rank.

This module provides the Elasticsearch-specific implementation of the BaseClient
interface, handling Elasticsearch API calls and response formatting for LTR operations.
"""

import json
import os

import elasticsearch.helpers
import requests
from elasticsearch import Elasticsearch

from ltr.helpers.handle_resp import resp_msg

from .base_client import BaseClient


class ElasticResp:
    """Response wrapper for Elasticsearch API responses.

    Converts Elasticsearch JSON responses into a format compatible with
    the resp_msg error handling function.

    Attributes:
        status_code: HTTP status code (200 for success, 400 for errors).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp):
        """Initialize an ElasticResp wrapper.

        Args:
            resp: Elasticsearch API response dictionary.
        """
        self.status_code = 400
        if "acknowledged" in resp and resp["acknowledged"]:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text = json.dumps(resp, indent=2)


class BulkResp:
    """Response wrapper for Elasticsearch bulk operation responses.

    Attributes:
        status_code: HTTP status code (201 if documents indexed, 400 otherwise).
    """

    def __init__(self, resp):
        """Initialize a BulkResp wrapper.

        Args:
            resp: Elasticsearch bulk operation response tuple.
        """
        self.status_code = 400
        if resp[0] > 0:
            self.status_code = 201


class SearchResp:
    """Response wrapper for Elasticsearch search responses.

    Attributes:
        status_code: HTTP status code (200 if hits are found, 400 otherwise).
        text: JSON-formatted response text (only present on errors).
    """

    def __init__(self, resp):
        """Initialize a SearchResp wrapper.

        Args:
            resp: Elasticsearch search API response dictionary.
        """
        self.status_code = 400
        if "hits" in resp:
            self.status_code = 200
        else:
            self.status_code = resp["status"]
            self.text = json.dumps(resp, indent=2)


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

    def __init__(self, configs_dir="."):
        """Initialize an ElasticClient.

        Args:
            configs_dir: Directory containing Elasticsearch configuration files
                (default: current directory).
        """
        self.docker = os.environ.get("LTR_DOCKER") is not None
        self.configs_dir = configs_dir  # location of elastic configs

        if self.docker:
            self.host = "elastic"
        else:
            self.host = "localhost"

        self.elastic_ep = f"http://{self.host}:9200/_ltr"
        self.es = Elasticsearch(f"http://{self.host}:9200")

    def get_host(self):
        """Get the Elasticsearch hostname.

        Returns:
            str: Hostname for the Elasticsearch server.
        """
        return self.host

    def name(self):
        """Get the client name.

        Returns:
            str: Always returns "elastic".
        """
        return "elastic"

    def check_index_exists(self, index):
        """Check if an index exists.

        Args:
            index: Index name to check.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return self.es.indices.exists(index=index)

    def delete_index(self, index):
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

    def create_index(self, index):
        """Take the local config files for Elasticsearch for index, reload them into ES"""
        cfg_json_path = os.path.join(self.configs_dir, f"{index}_settings.json")
        with open(cfg_json_path) as src:
            settings = json.load(src)
            resp = self.es.indices.create(index=index, body=settings)
            resp_msg(msg=f"Created index {index}", resp=ElasticResp(resp))

    def index_documents(self, index, doc_src):
        """Index documents into Elasticsearch using bulk operations.

        Args:
            index: Index name to index documents into.
            doc_src: Iterable of document dictionaries. Each document must
                have an "id" field that uniquely identifies it.

        Raises:
            ValueError: If a document is missing the required "id" field.
        """

        def bulkDocs(doc_src):
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
                addCmd = {"_index": index, "_id": doc["id"], "_source": doc}
                yield addCmd

        resp = elasticsearch.helpers.bulk(self.es, bulkDocs(doc_src), chunk_size=100)
        self.es.indices.refresh(index=index)
        resp_msg(msg=f"Streaming Bulk index DONE {index}", resp=BulkResp(resp))

    def reset_ltr(self, index):
        """Reset the Learn-to-Rank feature store.

        Deletes and recreates the default LTR feature store. Note that the
        index parameter is accepted for API compatibility but not used, as
        Elasticsearch LTR is not bound to a specific index.

        Args:
            index: Index name (unused, kept for API compatibility).
        """
        resp = requests.delete(self.elastic_ep)
        resp_msg(
            msg="Removed Default LTR feature store".format(), resp=resp, throw=False
        )
        resp = requests.put(self.elastic_ep)
        resp_msg(msg="Initialize Default LTR feature store".format(), resp=resp)

    def create_featureset(self, index, name, ftr_config):
        """Create a feature set in Elasticsearch LTR.

        Args:
            index: Index name (unused, kept for API compatibility).
            name: Name of the feature set to create.
            ftr_config: Feature set configuration dictionary.
        """
        resp = requests.post(f"{self.elastic_ep}/_featureset/{name}", json=ftr_config)
        resp_msg(msg=f"Create {name} feature set", resp=resp)

    def get_feature_name(self, config, ftr_idx):
        """Get the name of a feature by its index.

        Args:
            config: Feature set configuration dictionary.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.
        """
        return config["featureset"]["features"][int(ftr_idx) - 1]["name"]

    def log_query(self, index, featureset, ids, params=None):
        """Execute a query and log feature values for specified documents.

        Uses Elasticsearch's LTR logging functionality to extract feature values
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
        if params is None:
            params = {}
        params = {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "sltr": {
                                "_name": "logged_features",
                                "featureset": featureset,
                                "params": params,
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

        resp = self.es.search(index=index, body=params)
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

    def submit_model(self, featureset, index, model_name, model_payload):
        """Submit a machine learning model to Elasticsearch LTR.

        Deletes any existing model with the same name, then creates a new model
        associated with the specified feature set.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.
        """
        model_ep = f"{self.elastic_ep}/_model/"
        create_ep = f"{self.elastic_ep}/_featureset/{featureset}/_createmodel"

        resp = requests.delete(f"{model_ep}{model_name}")
        print(f"Delete model {model_name}: {resp.status_code}")

        resp = requests.post(create_ep, json=model_payload)
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

    def submit_ranklib_model(self, featureset, index, model_name, model_payload):
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

    def submit_xgboost_model(self, featureset, index, model_name, model_payload):
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

    def model_query(self, index, model, model_params, query):
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

        # Transform to a consistent format between ES/Solr
        matches = []
        for hit in resp["hits"]["hits"]:
            match = hit["_source"]
            match["score"] = hit["_score"]
            matches.append(match)

        return matches

    def query(self, index, query):
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

        # Transform to a consistent format between ES/Solr
        matches = []
        for hit in resp["hits"]["hits"]:
            hit["_source"]["_score"] = hit["_score"]
            matches.append(hit["_source"])

        return matches

    def feature_set(self, index, name):
        """Retrieve a feature set configuration.

        Args:
            index: Index name (unused, kept for API compatibility).
            name: Name of the feature set to retrieve.

        Returns:
            tuple: A tuple containing:
                - mapping: List of dictionaries with feature names
                - rawFeatureSet: Full feature set configuration dictionary

        Raises:
            RuntimeError: If the feature set is not found.
        """
        resp = requests.get(f"{self.elastic_ep}/_featureset/{name}")

        jsonResp = resp.json()
        if not jsonResp["found"]:
            raise RuntimeError(f"Unable to find {name}")

        resp_msg(msg=f"Fetched FeatureSet {name}", resp=resp)

        rawFeatureSet = jsonResp["_source"]["featureset"]["features"]

        mapping = []
        for feature in rawFeatureSet:
            mapping.append({"name": feature["name"]})

        return mapping, rawFeatureSet

    def get_doc(self, doc_id, index):
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
