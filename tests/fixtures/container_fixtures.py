"""
Container fixtures for hello-ltr test suite.

This module provides:
- Container fixture management (_manage_container_fixture)
- Test type detection
- Container lifecycle management with health checks
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TypedDict, cast

import pytest
import requests

from ltr.logger import get_logger
from tests.fixtures.container_management import (
    check_ports_available,
    manage_docker_compose,
    register_container_for_cleanup,
    unregister_container_from_cleanup,
)
from tests.fixtures.file_locking import file_lock
from tests.fixtures.health_checks import get_service_wait_timeout, wait_for_service
from tests.port_management import (
    get_port_env_vars,
    get_worker_id,
    get_worker_ports,
    restore_port_env_vars,
    set_port_env_vars,
)


class EngineConfig(TypedDict):
    """Configuration for a search engine container fixture."""

    engine: str
    display_name: str
    port_config: dict[str, str]
    health_checks: list[tuple[str, str, str]]


logger = get_logger(__name__)


def _detect_test_type(request: pytest.FixtureRequest | None) -> str:
    """
    Detect the test type from the pytest request object.

    Args:
        request: Pytest request object

    Returns:
        str: Test type ("unit", "integration", "notebooks", or "general" if unknown)
    """
    # Try to get the test file path from the request
    test_path = None
    if hasattr(request, "node") and hasattr(request.node, "fspath"):
        test_path = str(request.node.fspath)
    elif hasattr(request, "module") and hasattr(request.module, "__file__"):
        test_path = request.module.__file__

    if test_path:
        test_path = test_path.replace("\\", "/")  # Normalize path separators
        if "/tests/unit/" in test_path:
            return "unit"
        elif "/tests/integration/" in test_path:
            return "integration"
        elif "/tests/notebooks/" in test_path:
            return "notebooks"

    # Default to "general" if we can't determine the type
    return "general"


def _manage_container_fixture(
    engine_config: EngineConfig,
    request: pytest.FixtureRequest | None = None,
) -> Iterator[bool]:
    """
    Shared implementation for container fixtures (solr, elasticsearch, opensearch).

    This function eliminates duplication across the three container fixtures by
    handling all common logic: port management, environment variable handling,
    client patching, port availability checks, file locking, container startup,
    health checks, and cleanup.

    Args:
        engine_config: Dict with keys:
            - engine: Engine name ("solr", "elasticsearch", "opensearch")
            - display_name: Display name for logging (e.g., "Solr", "Elasticsearch")
            - port_config: Dict mapping port env var names to default values
                           (e.g., {"SOLR_PORT": "18983"})
            - health_checks: List of tuples (port_key, service_name, health_endpoint)
                             (e.g., [("SOLR_PORT", "Solr", "/solr/admin/info/system")])
        request: Pytest request object (optional, used to detect test type)

    Yields:
        bool: True if container is ready (or skipped)
    """
    engine = engine_config["engine"]
    display_name = engine_config["display_name"]
    port_config = engine_config["port_config"]
    health_checks = engine_config["health_checks"]

    # Check if we should use per-worker containers (now default)
    # Set USE_WORKER_CONTAINERS=false to use shared containers (legacy mode)
    use_worker_containers = (
        os.environ.get("USE_WORKER_CONTAINERS", "true").lower() == "true"
    )

    if not use_worker_containers:
        # Skip fixture - containers managed externally (e.g., test.sh or manual setup)
        yield True
        return

    # Detect test type from request
    test_type = _detect_test_type(request) if request else "general"
    worker_id = get_worker_id()
    project_name = f"test-{test_type}-{engine}-{worker_id}"

    # CRITICAL SAFETY CHECK: Ensure project name matches test pattern
    # This prevents accidentally operating on manually started containers
    # Manually started containers use default project names (directory names like "elasticsearch", "solr", "opensearch")
    # or containers from root docker-compose.yml which use "hello-ltr-" prefix
    # Test containers ALWAYS use pattern: "test-{test_type}-{engine}-{worker_id}"
    if not project_name.startswith("test-"):
        raise RuntimeError(
            f"CRITICAL: Test project name '{project_name}' does not match test pattern. "
            "This is a safety check to prevent tests from modifying manually started containers. "
            "Test project names must start with 'test-'."
        )

    # Get worker-specific ports using centralized port management
    worker_ports = get_worker_ports()
    ports: dict[str, int]
    if worker_ports:
        # Use worker-specific ports if available
        ports = {
            port_name: worker_ports.get(port_name, int(port_config[port_name]))
            for port_name in port_config
        }
    else:
        # Use defaults from environment or port_config
        ports = {}
        for port_name, default in port_config.items():
            env_value = os.environ.get(port_name)
            if env_value:
                ports[port_name] = int(env_value)
            else:
                ports[port_name] = int(default)

    # Save original environment variable values to restore later
    original_env_vars = get_port_env_vars(list(port_config.keys()))

    # CRITICAL: Set environment variables BEFORE starting containers
    # This ensures patch_clients_for_test_ports() can read the correct ports
    # even if called before containers are ready
    set_port_env_vars(ports)

    # CRITICAL: Patch requests library for URL rewriting (hardcoded ports in URLs)
    # Note: Client port configuration is now handled via explicit dependency injection
    # using factory functions (tests.client_factory). This patching only handles
    # rewriting hardcoded URLs in requests calls, not client initialization.
    try:
        from tests.patch_clients_for_tests import patch_clients_for_test_ports

        patch_clients_for_test_ports()
    except ImportError:
        # If patching module not available, log warning but continue
        logger.warning(
            f"[Worker {worker_id}] Could not import patch_clients_for_test_ports"
        )
    except RuntimeError as e:
        # If patching validation fails, log error but continue
        # This allows tests to continue even if patching fails
        logger.error(
            f"[Worker {worker_id}] Patching validation failed: {e}. "
            "Tests may fail due to incorrect port configuration."
        )

    # Track whether we should clean up containers at the end
    # We clean up containers if:
    # 1. We started them in this session, OR
    # 2. They exist for our test project name (they're test containers, even if from a previous run)
    # We DON'T clean up if USE_WORKER_CONTAINERS=false (containers managed externally)
    should_cleanup = True
    elapsed = 0.0  # Initialize elapsed time for timing information

    # Register container for cleanup in global registry
    # This ensures cleanup even if pytest is interrupted
    # Convert ports dict to frozenset of tuples for hashing (dicts are unhashable)
    # Convert int values to str for consistency with cleanup registry type
    ports_hashable = frozenset((k, str(v)) for k, v in ports.items()) if ports else None
    container_info = (engine, project_name, ports_hashable)
    register_container_for_cleanup(container_info)

    try:
        # CRITICAL: Use file-based locking to prevent race conditions
        # Multiple workers might try to start containers simultaneously
        lock_file_path = (
            Path(tempfile.gettempdir()) / f"test-{test_type}-{engine}-{worker_id}.lock"
        )
        with file_lock(lock_file_path, timeout=60):
            # Check if containers for this project already exist
            ports_for_docker = {k: str(v) for k, v in ports.items()}
            # Type cast: str is compatible with str | int for this function
            check_result = manage_docker_compose(
                engine,
                "ps",
                project_name=project_name,
                ports=cast("dict[str, str | int] | None", ports_for_docker),
            )
            containers_exist = (
                check_result.returncode == 0 and check_result.stdout.strip()
            )

            # Only check port availability if containers don't exist
            # If containers exist, they're using the ports, which is fine
            if not containers_exist:
                # Convert int values to str for check_ports_available
                ports_for_check = {k: str(v) for k, v in ports.items()}
                # Type cast: str is compatible with str | int for this function
                all_available, unavailable_ports = check_ports_available(
                    cast("dict[str, str | int]", ports_for_check)
                )
                if not all_available:
                    raise RuntimeError(
                        f"Ports not available for worker {worker_id}: {', '.join(unavailable_ports)}. "
                        "This may indicate a port conflict or leftover containers from a previous run."
                    )

            if containers_exist:
                # Containers already exist for this test project - check if they're healthy
                print(
                    f"\n[Worker {worker_id}] {display_name} containers already exist for project {project_name}",
                    file=sys.stderr,
                    flush=True,
                )
                # Verify health checks pass
                # Use shorter timeout for existing containers (10s) - if they're not ready quickly, restart them
                # This prevents hanging on unhealthy containers
                all_healthy = True
                for port_key, service_name, health_endpoint in health_checks:
                    port_value = ports.get(port_key)
                    if port_value is None:
                        raise ValueError(
                            f"Port {port_key} not found in ports configuration"
                        )
                    port = int(port_value)
                    if not wait_for_service(
                        port,
                        service_name,
                        health_endpoint,
                        timeout=10,  # Short timeout for existing containers - if not ready, restart
                    ):
                        print(
                            f"[Worker {worker_id}] Existing {service_name} on port {port} not healthy, will start new containers",
                            file=sys.stderr,
                            flush=True,
                        )
                        all_healthy = False
                        break

                if all_healthy:
                    # Double-check containers are actually running (health check might pass on stopping containers)
                    check_result = subprocess.run(
                        [
                            "docker",
                            "ps",
                            "--filter",
                            f"name={project_name}",
                            "--format",
                            "{{.Names}}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    running_containers = [
                        line.strip()
                        for line in check_result.stdout.splitlines()
                        if line.strip()
                    ]
                    if not running_containers:
                        print(
                            f"[Worker {worker_id}] Health check passed but containers not running, restarting...",
                            file=sys.stderr,
                            flush=True,
                        )
                        all_healthy = False
                    else:
                        print(
                            f"[Worker {worker_id}] ✓ Reusing existing {display_name} containers ({len(running_containers)} running)",
                            file=sys.stderr,
                            flush=True,
                        )
                        # We'll still clean them up at the end since they're test containers
                else:
                    # Containers exist but aren't healthy - clean them up and start fresh
                    print(
                        f"[Worker {worker_id}] Cleaning up unhealthy containers...",
                        file=sys.stderr,
                        flush=True,
                    )
                    ports_for_docker = {k: str(v) for k, v in ports.items()}
                    # Type cast: str is compatible with str | int for this function
                    manage_docker_compose(
                        engine,
                        "down",
                        project_name=project_name,
                        ports=cast("dict[str, str | int] | None", ports_for_docker),
                    )
                    containers_exist = False

            if not containers_exist:
                # Start timing container startup
                start_time = time.time()

                # Start containers
                port_list = ", ".join(f"{k}={v}" for k, v in ports.items())
                print(
                    f"\n[Worker {worker_id}] Starting {display_name} containers (project: {project_name}, ports: {port_list})",
                    file=sys.stderr,
                    flush=True,
                )
                # Convert int values to str for manage_docker_compose
                ports_for_docker = {k: str(v) for k, v in ports.items()}
                # Type cast: str is compatible with str | int for this function
                result = manage_docker_compose(
                    engine,
                    "up",
                    project_name=project_name,
                    ports=cast("dict[str, str | int] | None", ports_for_docker),
                )

                if result.returncode != 0:
                    # Include stdout in error message for better debugging
                    error_msg = (
                        f"Failed to start {display_name} containers:\n"
                        f"STDOUT: {result.stdout}\n"
                        f"STDERR: {result.stderr}"
                    )
                    raise RuntimeError(error_msg)

                # CRITICAL: Health checks inside lock to prevent race conditions
                # If health check fails, containers are cleaned up before lock is released
                # Initialize ltr_ready before the loop so it's always in scope
                ltr_ready = (
                    True  # Default to True (not checked for non-OpenSearch services)
                )
                for port_key, service_name, health_endpoint in health_checks:
                    port_value = ports.get(port_key)
                    if port_value is None:
                        raise ValueError(
                            f"Port {port_key} not found in ports configuration"
                        )
                    port = int(port_value)
                    print(
                        f"[Worker {worker_id}] Waiting for {service_name} on port {port}...",
                        file=sys.stderr,
                        flush=True,
                    )

                    # First, wait for basic service health
                    health_check_result = wait_for_service(
                        port, service_name, health_endpoint, timeout=None
                    )

                    # For OpenSearch, also wait for LTR plugin readiness
                    # This is critical - notebooks use LTR features, so the plugin must be ready
                    if (
                        engine == "opensearch"
                        and port_key == "OPENSEARCH_PORT"
                        and health_check_result
                    ):
                        ltr_endpoint = f"http://localhost:{port}/_ltr"
                        print(
                            f"[Worker {worker_id}] Waiting for OpenSearch LTR plugin on {ltr_endpoint}...",
                            file=sys.stderr,
                            flush=True,
                        )
                        ltr_ready = False
                        ltr_start_time = time.time()
                        ltr_timeout = get_service_wait_timeout()

                        # Wait for LTR plugin to be ready
                        while time.time() - ltr_start_time < ltr_timeout:
                            try:
                                # Use original requests.get if available (to avoid double retries)
                                get_func = getattr(
                                    requests, "_original_get", requests.get
                                )
                                ltr_resp = get_func(ltr_endpoint, timeout=2)
                                ltr_status_code = ltr_resp.status_code
                                ltr_ready = 200 <= ltr_status_code < 300
                                if ltr_ready:
                                    print(
                                        f"[Worker {worker_id}] ✓ OpenSearch LTR plugin ready on {ltr_endpoint}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                    break  # LTR plugin is ready
                                else:
                                    print(
                                        f"[Worker {worker_id}] OpenSearch LTR plugin not ready on {ltr_endpoint}, "
                                        f"status: {ltr_status_code}, retrying...",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                            except Exception as e:
                                logger.debug(
                                    f"[Worker {worker_id}] OpenSearch LTR plugin check failed (will retry): {e}"
                                )

                            # Wait before next attempt
                            time.sleep(2)

                        # Update health_check_result based on LTR plugin status
                        if not ltr_ready:
                            health_check_result = False
                            print(
                                f"[Worker {worker_id}] OpenSearch LTR plugin did not become ready within timeout",
                                file=sys.stderr,
                                flush=True,
                            )

                    # Final health check result
                    # For OpenSearch, both service and LTR plugin must be ready
                    # For other services, only service health check is needed

                    if not health_check_result:
                        print(
                            f"[Worker {worker_id}] {service_name} health check failed, cleaning up containers...",
                            file=sys.stderr,
                            flush=True,
                        )
                        ports_for_docker = {k: str(v) for k, v in ports.items()}
                        # Type cast: str is compatible with str | int for this function
                        manage_docker_compose(
                            engine,
                            "down",
                            project_name=project_name,
                            ports=cast("dict[str, str | int] | None", ports_for_docker),
                        )
                        should_cleanup = False  # Cleanup already done
                        error_details = []
                        # Check if LTR plugin failed (ltr_ready is always initialized, so check its value)
                        if (
                            engine == "opensearch"
                            and port_key == "OPENSEARCH_PORT"
                            and not ltr_ready
                        ):
                            error_details.append("LTR plugin not ready")
                        else:
                            error_details.append("service health check failed")
                        raise RuntimeError(
                            f"{service_name} did not become ready within timeout on port {port}. "
                            f"Details: {', '.join(error_details)}"
                        )

                # Log timing information
                elapsed = time.time() - start_time
                print(
                    f"[Worker {worker_id}] ✓ {display_name} containers ready",
                    file=sys.stderr,
                    flush=True,
                )
        print(
            f"[Worker {worker_id}] ✓ Containers started in {elapsed:.1f}s",
            file=sys.stderr,
            flush=True,
        )

        yield True

    finally:
        # Restore original environment variable values
        # These variables are test-specific (production docker-compose.yml uses hardcoded ports),
        # but we restore original values in case someone had them set for manual testing
        restore_port_env_vars(original_env_vars)

        # Clean up containers for this test project ONLY
        # Verify containers exist for our project name before attempting cleanup
        # This prevents accidentally cleaning up manually started containers with different project names
        if should_cleanup:
            # Double-check that containers exist for our project before cleaning up
            ports_for_docker = {k: str(v) for k, v in ports.items()}
            # Type cast: str is compatible with str | int for this function
            check_result = manage_docker_compose(
                engine,
                "ps",
                project_name=project_name,
                ports=cast("dict[str, str | int] | None", ports_for_docker),
            )
            containers_exist = (
                check_result.returncode == 0 and check_result.stdout.strip()
            )

            if containers_exist:
                print(
                    f"\n[Worker {worker_id}] Stopping {display_name} containers (project: {project_name})...",
                    file=sys.stderr,
                    flush=True,
                )
                ports_for_docker = {k: str(v) for k, v in ports.items()}
                # Type cast: str is compatible with str | int for this function
                result = manage_docker_compose(
                    engine,
                    "down",
                    project_name=project_name,
                    ports=cast("dict[str, str | int] | None", ports_for_docker),
                )
                if result.returncode != 0:
                    print(
                        f"[Worker {worker_id}] WARNING: Cleanup failed (return code {result.returncode}):\n"
                        f"STDOUT: {result.stdout}\n"
                        f"STDERR: {result.stderr}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    print(
                        f"[Worker {worker_id}] ✓ {display_name} containers stopped",
                        file=sys.stderr,
                        flush=True,
                    )
            else:
                print(
                    f"\n[Worker {worker_id}] No containers found for project {project_name}, skipping cleanup",
                    file=sys.stderr,
                    flush=True,
                )

        # Remove from cleanup registry after cleanup completes
        unregister_container_from_cleanup(container_info)
