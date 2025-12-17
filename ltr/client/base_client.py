"""Abstract base client for Learn-to-Rank search engines.

This module provides the BaseClient abstract base class that defines the interface
for all search engine clients (Elasticsearch, OpenSearch, Solr). The goal is to
abstract away server-specific details and highlight the steps required to work
with LTR, keeping examples agnostic about which backend is being used.

The implementations of each client serve as useful references for those getting
started with LTR on their specific platform.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from ltr.types import (
    FeatureConfig,
    FeatureSetResult,
    JSONDict,
    JSONDictList,
    ModelPayload,
    QueryParams,
)


class BaseClient(ABC):
    """Abstract base class for search engine clients.

    This class defines the interface that all search engine clients (Elasticsearch,
    OpenSearch, Solr) must implement. It abstracts away server-specific details
    to provide a unified API for Learn-to-Rank operations.
    """

    @abstractmethod
    def get_host(self) -> str:
        """Get the hostname or address of the search engine.

        Returns:
            str: Hostname or IP address of the search engine server.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Get the name/type of the search engine client.

        Returns:
            str: Client name, one of: "elastic", "opensearch", or "solr".
        """
        pass

    @abstractmethod
    def delete_index(self, index: str) -> None:
        """Delete a search index.

        Args:
            index: Name of the index to delete.
        """
        pass

    @abstractmethod
    def create_index(self, index: str) -> None:
        """Create a new search index.

        Args:
            index: Name of the index to create.
        """
        pass

    @abstractmethod
    def index_documents(
        self,
        index: str,
        doc_src: Iterable[JSONDict] | Callable[[], Iterable[JSONDict]],
    ) -> None:
        """Index documents into a search index.

        Args:
            index: Name of the target index.
            doc_src: Source of documents. Can be an iterable of document
                dictionaries or a callable that returns an iterable. Each
                document must have an 'id' field. Note: File paths (str) are
                not supported by implementations.
        """
        pass

    @abstractmethod
    def reset_ltr(self, index: str) -> None:
        """Reset Learn-to-Rank configuration for an index.

        Removes all existing models and feature stores, then reinitializes
        the default LTR feature store.

        Args:
            index: Name of the index to reset LTR for.
        """
        pass

    @abstractmethod
    def create_featureset(
        self, index: str, name: str, ftr_config: FeatureConfig
    ) -> None:
        """Create a new feature set in the search engine.

        Args:
            index: Name of the index where the feature set will be created.
            name: Name of the feature set.
            ftr_config: Feature configuration. Format depends on search engine:
                - Solr: List of feature dictionaries
                - Elasticsearch/OpenSearch: Dictionary with featureset.features
                    structure
        """
        pass

    @abstractmethod
    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Extract feature name from configuration by index.

        Args:
            config: Feature configuration (format depends on search engine).
            ftr_idx: Feature index (1-based) to look up.

        Returns:
            str: Name of the feature at the given index.
        """
        pass

    @abstractmethod
    def query(self, index: str, query: QueryParams) -> JSONDictList:
        """Execute a search query.

        Args:
            index: Name of the index to search.
            query: Query dictionary in search engine-specific format.

        Returns:
            list[dict]: List of search results, each containing at least:
                - _score: Relevance score
                - id: Document ID
                - Other document fields as specified in the query
        """
        pass

    @abstractmethod
    def get_doc(self, doc_id: str, index: str) -> JSONDict:
        """Retrieve a single document by ID.

        Args:
            doc_id: Document ID to retrieve.
            index: Name of the index containing the document.

        Returns:
            dict: Document dictionary with all stored fields.

        Note:
            Parameter order may differ between implementations (Solr uses
            index first, Elasticsearch/OpenSearch use doc_id first).
        """
        pass

    @abstractmethod
    def log_query(
        self,
        index: str,
        featureset: str,
        ids: list[str] | None,
        params: QueryParams,
    ) -> JSONDictList:
        """Execute a query with feature logging enabled.

        Args:
            index: Name of the index to query.
            featureset: Name of the feature set to use for logging.
            ids: Optional list of document IDs to restrict logging to.
                If None, logs features for all matching documents.
            params: Query parameters dictionary (e.g., keywords, fuzzy_keywords).

        Returns:
            list[dict]: List of documents with the ltr_features field containing
                feature vectors for each document.
        """
        pass

    @abstractmethod
    def submit_model(
        self,
        featureset: str,
        index: str,
        model_name: str,
        model_payload: ModelPayload,
    ) -> None:
        """Submit a model to the search engine.

        Args:
            featureset: Name of the feature set to associate with the model.
            index: Name of the index where the model will be stored.
            model_name: Name to assign to the model.
            model_payload: Model definition dictionary in search engine-specific format.
        """
        pass

    @abstractmethod
    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to the search engine.

        Converts RankLib model format to search engine-specific format and submits it.

        Args:
            featureset: Name of the feature set to associate with the model.
            index: Name of the index where the model will be stored.
            model_name: Name to assign to the model.
            model_payload: RankLib model definition (XML string for Solr, JSON
                for others).
        """
        pass

    @abstractmethod
    def model_query(
        self,
        index: str,
        model: str,
        model_params: QueryParams,
        query: QueryParams,
    ) -> JSONDictList:
        """Execute a query using a Learn-to-Rank model.

        Args:
            index: Name of the index to search.
            model: Name of the LTR model to use for ranking.
            model_params: Additional model parameters (search engine-specific).
            query: Base query dictionary (will be enhanced with LTR rescoring).

        Returns:
            list[dict]: List of search results ranked by the LTR model.
        """
        pass

    @abstractmethod
    def feature_set(self, index: str, name: str) -> FeatureSetResult:
        """Retrieve a feature set configuration.

        Args:
            index: Name of the index containing the feature set.
            name: Name of the feature set to retrieve.

        Returns:
            tuple: A tuple containing:
                - mapping: List of dictionaries mapping feature indices to names.
                - raw_features: Raw feature list in search engine-specific format.
        """
        pass
