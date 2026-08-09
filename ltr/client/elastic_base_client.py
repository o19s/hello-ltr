"""Base client mixin for Elasticsearch and OpenSearch.

This module provides shared functionality between Elasticsearch and OpenSearch
clients, reducing code duplication. Both Elasticsearch and OpenSearch share
similar APIs and LTR plugin implementations, making this abstraction natural.

The mixin provides:
- Common response validation
- Common feature name extraction
- Common model submission helpers
- Common configuration file path resolution
- Common feature set verification query building
"""

from __future__ import annotations

import json
import os

from ltr.types import FeatureConfig, JSONDict, ModelPayload, QueryParams
from ltr.validation import (
    ValidationError,
    validate_index_name,
    validate_model_name,
)


class ElasticBaseClient:
    """Base mixin class for Elasticsearch and OpenSearch clients.

    This mixin provides common functionality shared between Elasticsearch and
    OpenSearch implementations. It should be used as a mixin alongside BaseClient.

    Example:
        class ElasticClient(ElasticBaseClient, BaseClient):
            ...
    """

    def _validate_search_response(
        self, resp: JSONDict, operation: str = "query"
    ) -> None:
        """Validate Elasticsearch/OpenSearch search response structure.

        Checks for error responses and missing 'hits' key, raising ValueError
        with descriptive messages if validation fails. The calling code will
        catch ValueError and re-raise as QueryError with additional context.

        Args:
            resp: Elasticsearch/OpenSearch search API response dictionary.
            operation: Operation name for error messages (e.g., "query", "model query").

        Raises:
            ValueError: If response contains an error or is missing the 'hits' key.
        """
        # Use self.name() to get the client name dynamically
        # Type ignore: name() is provided by BaseClient, which concrete classes inherit from
        client_name = self.name() if hasattr(self, "name") else "elastic/opensearch"  # type: ignore[attr-defined]

        if "error" in resp:
            error_detail = resp.get("error", {})
            if isinstance(error_detail, dict):
                error_msg: str = error_detail.get("reason", str(error_detail))
            else:
                error_msg = str(error_detail)
            raise ValueError(
                f"{client_name.capitalize()} {operation} failed: {error_msg}"
            )
        if "hits" not in resp:
            raise ValueError(
                f"Unexpected response structure: missing 'hits' key. Response: {json.dumps(resp, indent=2)[:500]}"
            )

    def get_feature_name(self, config: FeatureConfig, ftr_idx: int) -> str:
        """Get the name of a feature by its index.

        Args:
            config: Feature set configuration dictionary.
            ftr_idx: Feature index (1-based).

        Returns:
            str: Name of the feature at the specified index.

        Raises:
            ValidationError: If config is a list instead of a dictionary.
        """
        if isinstance(config, list):
            # Type ignore: name() is provided by BaseClient, which concrete classes inherit from
            client_name = self.name() if hasattr(self, "name") else "elastic/opensearch"  # type: ignore[attr-defined]
            raise ValidationError(
                f"{client_name.capitalize()}Client.get_feature_name requires a dict config"
            )
        return config["featureset"]["features"][int(ftr_idx) - 1]["name"]

    def submit_ranklib_model(
        self, featureset: str, index: str, model_name: str, model_payload: str
    ) -> None:
        """Submit a RankLib model to Elasticsearch/OpenSearch LTR.

        Args:
            featureset: Name of the feature set to associate the model with.
            index: Index name (unused, kept for API compatibility).
            model_name: Name of the model to create.
            model_payload: RankLib model definition string.

        Raises:
            ValidationError: If the index name, feature set name, or model name is invalid.
            RuntimeError: If model creation or verification fails (see submit_model).
        """
        featureset = validate_model_name(featureset)
        index = validate_index_name(index)
        model_name = validate_model_name(model_name)
        params = {
            "model": {
                "name": model_name,
                "model": {"type": "model/ranklib", "definition": model_payload},
            }
        }
        # Type ignore: submit_model() is provided by BaseClient, which concrete classes inherit from
        self.submit_model(featureset, index, model_name, params)  # type: ignore[attr-defined]

    def submit_xgboost_model(
        self,
        featureset: str,
        index: str,
        model_name: str,
        model_payload: ModelPayload,
    ) -> None:
        """Submit an XGBoost model to Elasticsearch/OpenSearch LTR.

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
        # Type ignore: submit_model() is provided by BaseClient, which concrete classes inherit from
        self.submit_model(featureset, index, model_name, params)  # type: ignore[attr-defined]

    def _resolve_config_path(self, index: str, configs_dir: str) -> str:
        """Resolve the path to an index configuration file.

        Attempts to find the configuration file in multiple locations:
        1. The specified configs_dir
        2. Standard notebook locations relative to project root
        3. Alternative notebook locations for blog indices

        Args:
            index: Index name to find configuration for.
            configs_dir: Base directory to search for configuration files.

        Returns:
            str: Path to the configuration file.

        Raises:
            FileNotFoundError: If the configuration file cannot be found in any location.
        """
        cfg_json_path = os.path.join(configs_dir, f"{index}_settings.json")

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
            # Order matters: try opensearch first if this is OpenSearchClient, elasticsearch first if ElasticClient
            # Type ignore: name() is provided by BaseClient, which concrete classes inherit from
            client_name = self.name() if hasattr(self, "name") else "elastic"  # type: ignore[attr-defined]
            primary_engine = (
                "opensearch" if client_name == "opensearch" else "elasticsearch"
            )
            secondary_engine = (
                "elasticsearch" if primary_engine == "opensearch" else "opensearch"
            )

            possible_paths = [
                os.path.join(
                    project_root,
                    f"notebooks/{primary_engine}/{index}/{index}_settings.json",
                ),
                os.path.join(
                    project_root,
                    f"notebooks/{secondary_engine}/{index}/{index}_settings.json",
                ),
                # Check osc-blog directory for blog index
                os.path.join(
                    project_root,
                    f"notebooks/{primary_engine}/osc-blog/{index}_settings.json",
                ),
                os.path.join(
                    project_root,
                    f"notebooks/{secondary_engine}/osc-blog/{index}_settings.json",
                ),
            ]
            for alt_path in possible_paths:
                if os.path.exists(alt_path):
                    cfg_json_path = alt_path
                    break

        return cfg_json_path

    def _build_feature_set_verification_query(
        self, featureset: str, test_query_params: QueryParams
    ) -> JSONDict:
        """Build a query to verify a feature set is usable.

        Creates a minimal query that uses the feature set to verify it's
        ready for use in actual queries.

        Args:
            featureset: Name of the feature set to verify.
            test_query_params: Parameters to pass to the feature set.

        Returns:
            dict: Query dictionary ready to execute.
        """
        return {
            "query": {
                "bool": {
                    "filter": [
                        {
                            "sltr": {
                                "_name": "test_features",
                                "featureset": featureset,
                                "params": test_query_params,
                            }
                        }
                    ]
                }
            },
            "size": 0,  # Don't return documents, just verify query works
        }

    def _extract_feature_set_params(self, ftr_config: FeatureConfig) -> QueryParams:
        """Extract required parameters from a feature set configuration.

        Extracts parameters needed by features in the feature set, providing
        default values when validation params are not available.

        Args:
            ftr_config: Feature set configuration dictionary.

        Returns:
            dict: Dictionary of parameter names to default values.
        """
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

        return test_query_params
