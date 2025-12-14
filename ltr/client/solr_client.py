"""Solr client implementation for Learn-to-Rank.

This module provides the Solr-specific implementation of the BaseClient
interface, handling Solr API calls and response formatting for LTR operations.
"""

import os
import re

import requests

from ltr.helpers.convert import convert
from ltr.helpers.handle_resp import resp_msg

from .base_client import BaseClient


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
    """

    def __init__(self):
        """Initialize a SolrClient.

        Sets up connection to Solr server, using Docker hostname if LTR_DOCKER
        environment variable is set, otherwise connecting to localhost.
        """
        self.docker = os.environ.get("LTR_DOCKER") is not None
        self.solr = requests.Session()

        if self.docker:
            self.host = "solr"
            self.solr_base_ep = "http://solr:8983/solr"
        else:
            self.host = "localhost"
            self.solr_base_ep = "http://localhost:8983/solr"

    def get_host(self):
        """Get the Solr hostname.

        Returns:
            str: Hostname for the Solr server.
        """
        return self.host

    def name(self):
        """Get the client name.

        Returns:
            str: Always returns "solr".
        """
        return "solr"

    def check_index_exists(self, index):
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

    def delete_index(self, index):
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

    def create_index(self, index):
        """Create a Solr core (index) from a configset.

        Creates a new core using a configset with the same name as the index.
        Presumes there is a link between the Docker container and the 'index'
        directory under docker/solr/ (e.g., docker/solr/tmdb/ is linked into
        Docker container configsets).

        Args:
            index: Core name to create. A configset with the same name must exist.
        """
        params = {
            "action": "CREATE",
            "name": index,
            "configSet": index,
        }
        resp = requests.get(f"{self.solr_base_ep}/admin/cores?", params=params)
        resp_msg(msg=f"Created index {index}", resp=resp)

    def index_documents(self, index, doc_src):
        """Index documents into Solr using batch updates.

        Processes documents in batches and commits at the end. Automatically
        appends "T00:00:00Z" to release_date fields if present.

        Args:
            index: Core name to index documents into.
            doc_src: Iterable of document dictionaries to index.
        """

        def commit():
            """Commit pending changes to the index."""
            resp = requests.get(f"{self.solr_base_ep}/{index}/update?commit=true")
            resp_msg(msg=f"Committed index {index}", resp=resp)

        def flush(docs):
            """Send a batch of documents to Solr for indexing.

            Args:
                docs: List of documents to index. The list is cleared after sending.
            """
            # print('Flushing {} docs'.format(len(docs)))
            requests.post(f"{self.solr_base_ep}/{index}/update", json=docs)
            # resp_msg(msg="Done", resp=resp)
            docs.clear()

        BATCH_SIZE = 5000
        docs = []
        for doc in doc_src:
            if "release_date" in doc and doc["release_date"] is not None:
                doc["release_date"] += "T00:00:00Z"

            docs.append(doc)

            if len(docs) % BATCH_SIZE == 0:
                flush(docs)

        flush(docs)
        commit()

    def reset_ltr(self, index):
        """Reset the Learn-to-Rank feature store and models for an index.

        Deletes all models and feature stores associated with the specified core.

        Args:
            index: Core name to reset LTR for.
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

    def validate_featureset(self, name, config):
        """Validate that all features in a config belong to the specified store.

        Args:
            name: Expected feature store name.
            config: List of feature configuration dictionaries.

        Raises:
            ValueError: If any feature doesn't have the correct store name.
        """
        for feature in config:
            if "store" not in feature or feature["store"] != name:
                raise ValueError(
                    f'Feature {feature["name"]} needs to be created with "store": "{name}" '
                )

    def create_featureset(self, index, name, ftr_config):
        """Create a feature store in Solr LTR.

        Args:
            index: Core name to create the feature store in.
            name: Name of the feature store to create.
            ftr_config: List of feature configuration dictionaries. All features
                must have "store" set to the feature store name.

        Raises:
            ValueError: If any feature doesn't have the correct store name.
        """
        self.validate_featureset(name, ftr_config)
        resp = requests.put(
            f"{self.solr_base_ep}/{index}/schema/feature-store", json=ftr_config
        )
        resp_msg(msg=f"Created {name} feature store under {index}:", resp=resp)

    def get_feature_name(self, config, ftr_idx):
        """Get the name of a feature by its index.

        Args:
            config: Feature configuration list.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.
        """
        return config[int(ftr_idx) - 1]["name"]

    def log_query(self, index, featureset, ids, params=None):
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
        """
        if params is None:
            params = {}
        efi_options = []
        for key, val in params.items():
            efi_options.append(f'efi.{key}="{val}"')

        efi_str = " ".join(efi_options)

        query = "*:*" if ids is None else f"{{!terms f=id}}{','.join(ids)}"

        params = {
            "fl": f"id,[features store={featureset} {efi_str}]",
            "q": query,
            "rows": 1000,
            "wt": "json",
        }
        resp = requests.post(f"{self.solr_base_ep}/{index}/select", data=params)
        # resp_msg(msg='Searching {}'.format(index), resp=resp)
        resp = resp.json()

        def parseFeatures(features):
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
        for doc in resp["response"]["docs"]:
            doc["ltr_features"] = parseFeatures(doc["[features]"])

        return resp["response"]["docs"]

    def submit_model(self, featureset, index, model_name, model_payload):
        """Submit a machine learning model to Solr LTR.

        Deletes any existing model with the same name, then creates a new model
        in the specified core.

        Args:
            featureset: Feature store name (unused, kept for API compatibility).
            index: Core name to create the model in.
            model_name: Name of the model to create.
            model_payload: Model configuration dictionary.
        """
        url = f"{self.solr_base_ep}/{index}/schema/model-store"
        resp = requests.delete(f"{url}/{model_name}")
        resp_msg(msg=f"Deleted Model {model_name}", resp=resp)

        resp = requests.put(url, json=model_payload)
        resp_msg(msg=f"Created Model {model_name}", resp=resp)

    def submit_ranklib_model(self, featureset, index, model_name, model_payload):
        """Submit a RankLib model to Solr LTR, converting it to Solr representation.

        Retrieves the feature store configuration, maps feature indices to names,
        converts the RankLib model to Solr format, and submits it.

        Args:
            featureset: Name of the feature store to associate the model with.
            index: Core name to create the model in.
            model_name: Name of the model to create.
            model_payload: RankLib model definition string.
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

    def model_query(self, index, model, model_params, query):
        """Execute a query using an LTR model for reranking.

        Uses Solr's LTR reranking query parser to apply an LTR model to
        re-rank search results.

        Args:
            index: Core name to query.
            model: Name of the LTR model to use for reranking.
            model_params: Parameters to pass to the model (unused in Solr).
            query: Base query string to execute.

        Returns:
            list: List of document dictionaries with scores.
        """
        url = f"{self.solr_base_ep}/{index}/select?"
        params = {
            "q": query,
            "fl": "score *",
            "rq": f"{{!ltr model={model}}}",
            "rows": 10000,
        }

        resp = requests.post(url, data=params)
        resp_msg(msg=f"Search keywords - {query}", resp=resp)
        return resp.json()["response"]["docs"]

    def query(self, index, query):
        """Execute a search query against a Solr core.

        Args:
            index: Core name to query.
            query: Query parameters dictionary (e.g., {"q": "search terms", "wt": "json"}).

        Returns:
            list: List of document dictionaries with scores, transformed to
                a format consistent with Elasticsearch/OpenSearch (score -> _score).
        """
        url = f"{self.solr_base_ep}/{index}/select?"

        resp = requests.post(url, data=query)
        # resp_msg(msg='Query {}...'.format(str(query)[:20]), resp=resp)
        resp = resp.json()

        # Transform to be consistent
        for doc in resp["response"]["docs"]:
            if "score" in doc:
                doc["_score"] = doc["score"]

        return resp["response"]["docs"]

    def analyze(self, index, fieldtype, text):
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

    def term_vectors_skip_to(self, index, q="*:*", skip=0):
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

    def term_vectors(self, index, field, q="*:*", start_cursor="*"):
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

    def get_feature_stores(self, index):
        """Get list of feature store names for a core.

        Args:
            index: Core name to query.

        Returns:
            list: List of feature store names.
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/feature-store")
        response = resp.json()
        return response["featureStores"]

    def get_models(self, index):
        """Get list of model names for a core.

        Args:
            index: Core name to query.

        Returns:
            list: List of model names.
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/model-store")
        response = resp.json()
        return [model["name"] for model in response["models"]]

    def feature_set(self, index, name):
        """Retrieve a feature store configuration.

        Args:
            index: Core name to query.
            name: Name of the feature store to retrieve.

        Returns:
            tuple: A tuple containing:
                - mapping: List of dictionaries with feature names
                - rawFeatureSet: Full feature store configuration list
        """
        resp = requests.get(f"{self.solr_base_ep}/{index}/schema/feature-store/{name}")
        resp_msg(msg=f"Feature Set {name}...", resp=resp)

        response = resp.json()

        rawFeatureSet = response["features"]

        mapping = []
        for feature in response["features"]:
            mapping.append({"name": feature["name"]})

        return mapping, rawFeatureSet

    def get_doc(self, doc_id, index):
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

        resp = requests.post(f"{self.solr_base_ep}/{index}/select", data=params).json()
        return resp["response"]["docs"][0]
