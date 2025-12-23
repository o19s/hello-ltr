"""
Centralized Port Management for hello-ltr Tests

This module provides a single source of truth for port management in tests,
eliminating scattered port logic across multiple files.

Port Management Features:
- Base port definitions for all services
- Worker-specific port calculation for parallel execution
- Environment variable management
- Port configuration for each search engine

Port Allocation Strategy:
- Base ports: Solr=18983, ES=19200, OpenSearch=19201
- Worker offset: worker_id * 1000 (e.g., gw0=+0, gw1=+1000, gw2=+2000)
- Each worker gets a range of 1000 ports to avoid conflicts

Usage:
    from tests.port_management import (
        get_worker_ports,
        get_port,
        get_base_ports,
        set_port_env_vars,
    )

    # Get worker-specific ports
    ports = get_worker_ports()
    if ports:
        solr_port = ports["SOLR_PORT"]

    # Get a specific port (with worker offset if in parallel mode)
    solr_port = get_port("SOLR_PORT")

    # Get base ports (without worker offset)
    base_ports = get_base_ports()

    # Set environment variables for all ports
    set_port_env_vars(ports)
"""

from __future__ import annotations

import os
from typing import TypedDict, cast


# Type definition for engine port configuration
class EnginePortConfig(TypedDict):
    """Port configuration structure for a search engine."""

    port_config: dict[str, str]  # Maps port env var names to default string values
    health_checks: list[
        tuple[str, str, str]
    ]  # List of (port_key, service_name, health_endpoint)


# Base port definitions (default ports for non-parallel execution)
BASE_PORTS = {
    "SOLR_PORT": 18983,
    "ELASTICSEARCH_PORT": 19200,
    "OPENSEARCH_PORT": 19201,
    "KIBANA_PORT": 15601,
    "OPENSEARCH_PA_PORT": 19600,
    "OPENSEARCH_DASHBOARDS_PORT": 15602,
}

# Port configuration for each search engine
ENGINE_PORT_CONFIGS = {
    "solr": {
        "port_config": {
            "SOLR_PORT": "18983",
        },
        "health_checks": [
            ("SOLR_PORT", "Solr", "/solr/admin/info/system"),
        ],
    },
    "elasticsearch": {
        "port_config": {
            "ELASTICSEARCH_PORT": "19200",
            "KIBANA_PORT": "15601",
        },
        "health_checks": [
            ("ELASTICSEARCH_PORT", "Elasticsearch", "/_cluster/health"),
            ("KIBANA_PORT", "Kibana", "/api/status"),
        ],
    },
    "opensearch": {
        "port_config": {
            "OPENSEARCH_PORT": "19201",
            "OPENSEARCH_PA_PORT": "19600",
            "OPENSEARCH_DASHBOARDS_PORT": "15602",
        },
        "health_checks": [
            ("OPENSEARCH_PORT", "OpenSearch", "/_cluster/health"),
            ("OPENSEARCH_DASHBOARDS_PORT", "OpenSearch Dashboards", "/api/status"),
        ],
    },
}


def get_worker_id() -> str:
    """
    Get the current pytest-xdist worker ID.

    Returns:
        str: Worker ID (e.g., "gw0", "gw1") or "main" if not in parallel mode
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    return worker if worker else "main"


def get_worker_num() -> int:
    """
    Get the numeric worker ID for port calculation.

    Returns:
        int: Worker number (0, 1, 2, ...) or 0 if not in parallel mode
    """
    worker_id = get_worker_id()
    if worker_id == "main":
        return 0

    try:
        return int(worker_id.replace("gw", ""))
    except (ValueError, AttributeError):
        return 0


def get_base_ports() -> dict[str, int]:
    """
    Get base port definitions without worker offset.

    Returns:
        dict: Base port values for all services
    """
    return BASE_PORTS.copy()


def get_worker_ports() -> dict[str, int] | None:
    """
    Get worker-specific ports for parallel execution.

    When running with pytest-xdist in parallel, each worker needs unique ports
    to avoid conflicts. This function calculates port offsets based on worker ID.

    Returns:
        dict: Port values for SOLR_PORT, ELASTICSEARCH_PORT, OPENSEARCH_PORT, etc.
              If not running in parallel, returns None (use defaults from BASE_PORTS)

    Port allocation strategy:
    - Base ports: Solr=18983, ES=19200, OpenSearch=19201
    - Worker offset: worker_id * 1000 (e.g., gw0=+0, gw1=+1000, gw2=+2000)
    - This gives each worker a range of 1000 ports to avoid conflicts

    Note: This is primarily useful when each worker has its own Docker containers.
    When using test.sh, containers are started once before pytest runs. For best
    results with Docker, use --dist loadgroup to group tests by engine, ensuring
    each worker only needs one engine's containers.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker:
        # Not running in parallel, return None to use defaults
        return None

    # Extract worker number from worker ID (e.g., "gw0" -> 0, "gw1" -> 1)
    worker_num = get_worker_num()

    # Calculate port offset (1000 ports per worker should be plenty)
    port_offset = worker_num * 1000

    # Apply offset to each port and validate
    worker_ports = {}
    max_valid_port = 65535
    for port_name, base_port in BASE_PORTS.items():
        calculated_port = base_port + port_offset
        if calculated_port > max_valid_port:
            max_base_port = max(BASE_PORTS.values())
            max_workers = (max_valid_port - max_base_port) // 1000
            raise ValueError(
                f"Calculated port {calculated_port} for {port_name} exceeds maximum port number ({max_valid_port}). "
                f"Worker {worker_num} with offset {port_offset} would cause overflow. "
                f"Maximum supported workers: {max_workers}"
            )
        worker_ports[port_name] = calculated_port

    return worker_ports


def get_port(port_name: str, default: int | None = None) -> int | None:
    """
    Get a port value, considering worker offsets and environment variables.

    Priority:
    1. Environment variable (if set)
    2. Worker-specific port (if in parallel mode)
    3. Base port (from BASE_PORTS)
    4. Default value (if provided)

    Args:
        port_name: Name of the port environment variable (e.g., "SOLR_PORT")
        default: Default value if port is not found (optional)

    Returns:
        int: Port number, or None if not found and no default provided
    """
    # First check environment variable (highest priority)
    env_value = os.environ.get(port_name)
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass

    # Check worker-specific ports (if in parallel mode)
    worker_ports = get_worker_ports()
    if worker_ports and port_name in worker_ports:
        return worker_ports[port_name]

    # Check base ports
    if port_name in BASE_PORTS:
        return BASE_PORTS[port_name]

    # Return default if provided
    return default


def set_port_env_vars(ports: dict[str, int]) -> None:
    """
    Set port environment variables from a dictionary.

    Args:
        ports: Dictionary mapping port names to port values
    """
    for port_name, port_value in ports.items():
        os.environ[port_name] = str(port_value)


def get_port_env_vars(
    port_names: list[str] | None = None,
) -> dict[str, str | None]:
    """
    Get port environment variables.

    Args:
        port_names: List of port names to get (default: all ports in BASE_PORTS)

    Returns:
        dict: Mapping of port names to their environment variable values (or None if not set)
    """
    if port_names is None:
        port_names = list(BASE_PORTS.keys())

    return {port_name: os.environ.get(port_name) for port_name in port_names}


def restore_port_env_vars(original_values: dict[str, str | None]) -> None:
    """
    Restore port environment variables to their original values.

    Args:
        original_values: Dictionary mapping port names to their original values
                         (None means the variable should be removed)
    """
    for port_name, original_value in original_values.items():
        if original_value is not None:
            os.environ[port_name] = original_value
        elif port_name in os.environ:
            # Remove if it wasn't set originally (clean up test value)
            del os.environ[port_name]


def get_engine_port_config(engine: str) -> EnginePortConfig:
    """
    Get port configuration for a specific search engine.

    Args:
        engine: Engine name ("solr", "elasticsearch", "opensearch")

    Returns:
        EnginePortConfig: Port configuration with keys:
            - port_config: Dict mapping port env var names to default values
            - health_checks: List of tuples (port_key, service_name, health_endpoint)

    Raises:
        ValueError: If engine is not recognized
    """
    if engine not in ENGINE_PORT_CONFIGS:
        raise ValueError(
            f"Unknown engine: {engine}. Must be one of: {list(ENGINE_PORT_CONFIGS.keys())}"
        )
    return cast(EnginePortConfig, ENGINE_PORT_CONFIGS[engine].copy())
