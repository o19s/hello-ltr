"""
Pytest configuration and fixtures for hello-ltr test suite.

This module provides:
- Fixtures for notebook execution
- Custom pytest hooks for test reporting and collection
- Port conflict handling for parallel execution
- Slow test detection and ordering
- Per-worker Docker container isolation fixtures
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, suppress
from datetime import datetime
from pathlib import Path

import pytest
import requests

# Platform-specific file locking support
try:
    import fcntl

    _has_fcntl = True
except ImportError:
    _has_fcntl = False
HAS_FCNTL = _has_fcntl

# Check for Windows file locking support (msvcrt is imported when needed)
_has_msvcrt = False
if not HAS_FCNTL:
    try:
        import importlib.util

        if importlib.util.find_spec("msvcrt") is not None:
            _has_msvcrt = True
    except (ImportError, AttributeError):
        pass
HAS_MSVCRT = _has_msvcrt

# Known slow notebook patterns (notebooks that typically take > 60 seconds)
SLOW_PATTERNS = [
    "netfix",
    "bayesian-optimization",
    "bigger bot",
    "lambda-mart",
    "feature_search",
    "evaluation",
]

# Threshold for marking tests as slow based on execution time (seconds)
SLOW_TEST_THRESHOLD = 60.0

# Global registry for containers that need cleanup
# This ensures cleanup even if pytest is interrupted (Ctrl+C) or killed
_container_cleanup_registry = set()


def get_service_wait_timeout():
    """
    Get the service wait timeout from environment variable.

    Returns:
        int: Timeout in seconds (default: 300)
    """
    return int(os.environ.get("SERVICE_WAIT_TIMEOUT", "300"))


def get_worker_id():
    """
    Get the current pytest-xdist worker ID.

    Returns:
        str: Worker ID (e.g., "gw0", "gw1") or "main" if not in parallel mode
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    return worker if worker else "main"


def get_worker_num():
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


def get_worker_ports():
    """
    Get worker-specific ports for parallel execution.

    When running with pytest-xdist in parallel, each worker needs unique ports
    to avoid conflicts. This function calculates port offsets based on worker ID.

    Returns:
        dict: Port values for SOLR_PORT, ELASTICSEARCH_PORT, OPENSEARCH_PORT, etc.
              If not running in parallel, returns None (use defaults from test.sh)

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

    # Base ports from test.sh defaults
    base_ports = {
        "SOLR_PORT": 18983,
        "ELASTICSEARCH_PORT": 19200,
        "OPENSEARCH_PORT": 19201,
        "KIBANA_PORT": 15601,
        "OPENSEARCH_PA_PORT": 19600,
        "OPENSEARCH_DASHBOARDS_PORT": 15602,
    }

    # Apply offset to each port and validate
    worker_ports = {}
    max_valid_port = 65535
    for port_name, base_port in base_ports.items():
        calculated_port = base_port + port_offset
        if calculated_port > max_valid_port:
            max_base_port = max(base_ports.values())
            max_workers = (max_valid_port - max_base_port) // 1000
            raise ValueError(
                f"Calculated port {calculated_port} for {port_name} exceeds maximum port number ({max_valid_port}). "
                f"Worker {worker_num} with offset {port_offset} would cause overflow. "
                f"Maximum supported workers: {max_workers}"
            )
        worker_ports[port_name] = calculated_port

    return worker_ports


# Cache for docker compose command detection
_docker_compose_cmd_cache = None


def get_docker_compose_cmd():
    """
    Get the docker compose command to use.

    Returns:
        str: Either "docker compose" or "docker-compose" depending on what's available
    """
    global _docker_compose_cmd_cache
    if _docker_compose_cmd_cache is not None:
        return _docker_compose_cmd_cache

    if shutil.which("docker"):
        # Check if "docker compose" is available (Docker Compose V2)
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            _docker_compose_cmd_cache = "docker compose"
            return _docker_compose_cmd_cache

    # Fallback to docker-compose (V1)
    if shutil.which("docker-compose"):
        _docker_compose_cmd_cache = "docker-compose"
        return _docker_compose_cmd_cache

    raise RuntimeError(
        "Neither 'docker compose' nor 'docker-compose' found. Please install Docker."
    )


def wait_for_service(
    port, service_name, health_endpoint="/", timeout=None, check_interval=2
):
    """
    Wait for a service to be ready by checking its health endpoint.

    Uses exponential backoff retry logic to handle transient network failures.

    Args:
        port: Port number to check
        service_name: Name of the service (for logging)
        health_endpoint: Health check endpoint path
        timeout: Maximum time to wait in seconds (defaults to SERVICE_WAIT_TIMEOUT env var or 300)
        check_interval: Time between checks in seconds

    Returns:
        bool: True if service is ready, False if timeout
    """
    if timeout is None:
        timeout = get_service_wait_timeout()
    start_time = time.time()
    url = f"http://localhost:{port}{health_endpoint}"
    max_retries = 3
    base_retry_delay = 0.1  # Start with 100ms

    while time.time() - start_time < timeout:
        # Try with exponential backoff retry logic for transient failures
        for retry_attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=2)
                # Only accept 2xx status codes as ready (successful responses)
                if 200 <= response.status_code < 300:
                    return True
                # If we get a non-2xx response, break retry loop and wait for next check interval
                break
            except (requests.exceptions.RequestException, ConnectionError):
                # If this is the last retry attempt, break and move to next check interval
                if retry_attempt == max_retries - 1:
                    break
                # Exponential backoff: 0.1s, 0.2s, 0.4s
                retry_delay = base_retry_delay * (2**retry_attempt)
                time.sleep(retry_delay)

        # Wait for check_interval before next health check attempt
        time.sleep(check_interval)

    return False


def _is_lock_stale(lock_path, max_age_seconds=300):
    """
    Check if lock file is stale (process dead or too old).

    Args:
        lock_path: Path to lock file
        max_age_seconds: Maximum age in seconds before considering stale

    Returns:
        bool: True if lock is stale, False otherwise
    """
    try:
        if not lock_path.exists():
            return False  # No lock file, not stale

        stat = lock_path.stat()
        age = time.time() - stat.st_mtime
        if age > max_age_seconds:
            return True  # Lock file too old

        # Check if PID in lock file is still alive
        try:
            with open(lock_path) as f:
                pid_line = f.readline().strip()
                pid = int(pid_line)
                # Signal 0 just checks if process exists (doesn't kill it)
                os.kill(pid, 0)
                return False  # Process is alive, lock is valid
        except (ValueError, OSError):
            return True  # PID invalid or process dead, lock is stale
    except OSError:
        return True  # Can't read lock file, assume stale


@contextmanager
def file_lock(lock_file_path, timeout=30):
    """
    Context manager for file-based locking to prevent race conditions.

    Uses platform-specific locking mechanisms:
    - Unix/Linux: fcntl advisory locks
    - Windows: msvcrt file locking
    - Fallback: Warning and no-op if no locking available

    Args:
        lock_file_path: Path to lock file
        timeout: Maximum time to wait for lock (seconds)

    Yields:
        None (lock is held during context)

    Raises:
        RuntimeError: If lock cannot be acquired within timeout
    """
    lock_path = Path(lock_file_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    # If no locking mechanism available, warn and provide no-op
    if not HAS_FCNTL and not HAS_MSVCRT:
        print(
            "WARNING: File locking not available on this platform. "
            "Race conditions may occur in parallel test execution.",
            file=sys.stderr,
            flush=True,
        )
        yield
        return

    # Check if existing lock is stale and remove it
    if _is_lock_stale(lock_path):
        with suppress(OSError):
            lock_path.unlink(missing_ok=True)

    lock_file = None
    start_time = time.time()

    while True:
        try:
            # Open file for writing (create if it doesn't exist)
            # Note: We intentionally don't use context manager here because we need
            # to keep the file open while holding the lock
            lock_file = open(lock_path, "w")  # noqa: SIM115

            # Platform-specific locking
            if HAS_FCNTL:
                # Unix/Linux: Use fcntl advisory locks
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif HAS_MSVCRT:
                # Windows: Use msvcrt file locking
                # msvcrt.locking requires file descriptor and byte range
                # Lock the first byte (non-blocking)
                import msvcrt  # noqa: PLC0415

                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    # Lock is held by another process
                    raise OSError("Lock is held by another process")

            # Lock acquired successfully - write PID and timestamp
            lock_file.write(f"{os.getpid()}\n{time.time()}\n")
            lock_file.flush()
            break
        except OSError:
            # Lock is held by another process
            if lock_file:
                lock_file.close()
            lock_file = None

            # Check if lock became stale while waiting
            if _is_lock_stale(lock_path):
                with suppress(OSError):
                    lock_path.unlink(missing_ok=True)
                continue  # Retry acquiring lock

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise RuntimeError(
                    f"Could not acquire lock {lock_path} within {timeout}s. "
                    "Another process may be starting containers. "
                    f"Try removing stale lock files: rm {lock_path}"
                )
            time.sleep(0.1)  # Wait before retrying

    try:
        yield
    finally:
        if lock_file:
            try:
                if HAS_FCNTL:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                elif HAS_MSVCRT:
                    import msvcrt  # noqa: PLC0415

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass  # Ignore unlock errors
            lock_file.close()
            # Remove lock file if possible (ignore errors)
            with suppress(OSError):
                lock_path.unlink(missing_ok=True)


def check_ports_available(ports_dict):
    """
    Check if all ports in the dictionary are available.

    Args:
        ports_dict: Dictionary mapping port names to port numbers

    Returns:
        tuple: (all_available: bool, unavailable_ports: list[str])
    """
    try:
        from .integration.test_env_validation import check_port_available
    except ImportError:
        # If check function not available, log warning and assume ports are available
        print(
            "WARNING: Could not import check_port_available from test_env_validation. "
            "Skipping port availability check. This may lead to port conflicts.",
            file=sys.stderr,
            flush=True,
        )
        return True, []

    unavailable = []
    for port_name, port_value in ports_dict.items():
        try:
            port_num = int(port_value)
            available, error = check_port_available(port_num)
            if not available:
                unavailable.append(f"{port_name} ({port_num}): {error}")
        except Exception as e:
            # If port check fails, include error but don't fail completely
            unavailable.append(f"{port_name} ({port_value}): Error checking port: {e}")

    return len(unavailable) == 0, unavailable


def manage_docker_compose(engine, action, project_name=None, ports=None):
    """
    Manage docker-compose containers for a specific engine.

    CRITICAL SAFETY: This function ONLY operates on containers with test project names.
    Test project names MUST start with "test-" followed by test type (e.g., "test-unit-", "test-integration-", "test-notebooks-")
    to prevent accidentally modifying manually started containers (which use default project names like "elasticsearch", "solr", "opensearch",
    or containers started with docker-compose.yml which use "hello-ltr-" prefix).

    Args:
        engine: Engine name ("solr", "elasticsearch", "opensearch")
        action: Action to perform ("up", "down", "ps")
        project_name: Docker Compose project name (for isolation)
                     MUST start with "test-{test_type}-" for test containers
                     (e.g., "test-unit-solr-gw0", "test-integration-opensearch-gw0", "test-notebooks-elasticsearch-gw0")
        ports: Dict of port environment variables to set

    Returns:
        subprocess.CompletedProcess: Result of the docker-compose command

    Raises:
        RuntimeError: If project_name is provided but doesn't match test pattern
    """
    # CRITICAL SAFETY CHECK: Never operate on containers without test project name
    # This prevents tests from accidentally modifying manually started containers
    if project_name and not project_name.startswith("test-"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Attempted to {action} containers with project name '{project_name}'. "
            f"Test containers MUST use project names starting with 'test-{{test_type}}-' "
            f"(e.g., 'test-unit-{engine}-gw0', 'test-integration-{engine}-gw0', 'test-notebooks-{engine}-gw0'). "
            f"Manually started containers use default project names (like '{engine}') or 'hello-ltr-*' "
            f"and must NEVER be modified by tests. "
            f"This check prevents accidental deletion or modification of manually started containers."
        )

    docker_cmd = get_docker_compose_cmd()
    cmd_parts = docker_cmd.split()

    engine_path = Path(__file__).parent.parent / "notebooks" / engine

    if not engine_path.exists():
        raise ValueError(f"Engine path not found: {engine_path}")

    # Build command
    # CRITICAL: For test containers, use ONLY docker-compose.test.yml which includes
    # all necessary configuration and overrides ports completely
    # This prevents conflicts with manually started containers using base docker-compose.yml
    compose_files = [
        str(engine_path / "docker-compose.yml"),
        str(engine_path / "docker-compose.test.yml"),
    ]

    # Check if test file exists
    if not Path(compose_files[1]).exists():
        compose_files = [compose_files[0]]
    else:
        # For test containers, we need to ensure ports from base file don't conflict
        # Docker Compose merges ports arrays, so we need to handle this carefully
        # The test override file should completely override ports, but Docker Compose
        # merges arrays. We'll rely on the test override file having the correct ports
        # and ensure environment variables are set correctly
        pass

    cmd = cmd_parts + ["-f", compose_files[0]]
    if len(compose_files) > 1:
        cmd.extend(["-f", compose_files[1]])

    # CRITICAL: Always use project name for test containers to ensure isolation
    # Without -p flag, docker compose uses default project name (directory name)
    # which would conflict with manually started containers
    if project_name:
        cmd.extend(["-p", project_name])
    else:
        # If no project_name provided, this is a programming error
        # Tests should ALWAYS provide a project_name starting with "test-{test_type}-"
        raise RuntimeError(
            f"CRITICAL: manage_docker_compose called without project_name for {action} on {engine}. "
            "Tests must always specify a project_name starting with 'test-{test_type}-' "
            "(e.g., 'test-unit-solr-gw0') to avoid conflicts with manually started containers."
        )

    cmd.append(action)

    if action == "up":
        cmd.append("-d")  # Run in detached mode

    if action == "down":
        cmd.append("-v")  # Remove volumes

    # Set up environment with ports
    env = os.environ.copy()
    if ports:
        env.update({k: str(v) for k, v in ports.items()})

    # Run command
    result = subprocess.run(
        cmd, cwd=str(engine_path), env=env, capture_output=True, text=True
    )

    return result


def _detect_test_type(request):
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


def _manage_container_fixture(engine_config, request=None):
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

    # Get worker-specific ports
    worker_ports = get_worker_ports()
    if worker_ports:
        # Use worker-specific ports if available
        ports = {
            port_name: worker_ports.get(port_name, port_config[port_name])
            for port_name in port_config
        }
    else:
        # Use defaults from environment or port_config
        ports = {
            port_name: os.environ.get(port_name, default)
            for port_name, default in port_config.items()
        }

    # Save original environment variable values to restore later
    original_env_vars = {}
    for port_name in port_config:
        original_env_vars[port_name] = os.environ.get(port_name)

    # CRITICAL: Set environment variables BEFORE starting containers
    # This ensures patch_clients_for_test_ports() can read the correct ports
    # even if called before containers are ready
    for port_name, port_value in ports.items():
        os.environ[port_name] = str(port_value)

    # CRITICAL: Patch clients immediately after setting environment variables
    # This ensures any clients imported later will use the correct ports
    try:
        from tests.patch_clients_for_tests import patch_clients_for_test_ports

        patch_clients_for_test_ports()
    except ImportError:
        # If patching module not available, log warning but continue
        print(
            f"[Worker {worker_id}] WARNING: Could not import patch_clients_for_test_ports",
            file=sys.stderr,
            flush=True,
        )

    # CRITICAL: Check port availability before starting containers
    # This prevents race conditions where multiple workers try to use the same port
    all_available, unavailable_ports = check_ports_available(ports)
    if not all_available:
        raise RuntimeError(
            f"Ports not available for worker {worker_id}: {', '.join(unavailable_ports)}. "
            "This may indicate a port conflict or leftover containers from a previous run."
        )

    # Track whether we should clean up containers at the end
    # We clean up containers if:
    # 1. We started them in this session, OR
    # 2. They exist for our test project name (they're test containers, even if from a previous run)
    # We DON'T clean up if USE_WORKER_CONTAINERS=false (containers managed externally)
    should_cleanup = True

    # Register container for cleanup in global registry
    # This ensures cleanup even if pytest is interrupted
    # Convert ports dict to frozenset of tuples for hashing (dicts are unhashable)
    ports_hashable = frozenset(ports.items()) if ports else None
    container_info = (engine, project_name, ports_hashable)
    _container_cleanup_registry.add(container_info)

    try:
        # CRITICAL: Use file-based locking to prevent race conditions
        # Multiple workers might try to start containers simultaneously
        lock_file_path = (
            Path(tempfile.gettempdir()) / f"test-{test_type}-{engine}-{worker_id}.lock"
        )
        with file_lock(lock_file_path, timeout=60):
            # Check if containers for this project already exist
            check_result = manage_docker_compose(
                engine, "ps", project_name=project_name, ports=ports
            )
            containers_exist = (
                check_result.returncode == 0 and check_result.stdout.strip()
            )

            if containers_exist:
                # Containers already exist for this test project - check if they're healthy
                print(
                    f"\n[Worker {worker_id}] {display_name} containers already exist for project {project_name}",
                    file=sys.stderr,
                    flush=True,
                )
                # Verify health checks pass
                all_healthy = True
                for port_key, service_name, health_endpoint in health_checks:
                    port = int(ports[port_key])
                    if not wait_for_service(
                        port, service_name, health_endpoint, timeout=10
                    ):
                        print(
                            f"[Worker {worker_id}] Existing {service_name} on port {port} not healthy, will start new containers",
                            file=sys.stderr,
                            flush=True,
                        )
                        all_healthy = False
                        break

                if all_healthy:
                    print(
                        f"[Worker {worker_id}] ✓ Reusing existing {display_name} containers",
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
                    manage_docker_compose(
                        engine, "down", project_name=project_name, ports=ports
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
                result = manage_docker_compose(
                    engine, "up", project_name=project_name, ports=ports
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
                for port_key, service_name, health_endpoint in health_checks:
                    port = int(ports[port_key])
                    print(
                        f"[Worker {worker_id}] Waiting for {service_name} on port {port}...",
                        file=sys.stderr,
                        flush=True,
                    )
                    if not wait_for_service(port, service_name, health_endpoint):
                        print(
                            f"[Worker {worker_id}] {service_name} health check failed, cleaning up containers...",
                            file=sys.stderr,
                            flush=True,
                        )
                        manage_docker_compose(
                            engine, "down", project_name=project_name, ports=ports
                        )
                        should_cleanup = False  # Cleanup already done
                        raise RuntimeError(
                            f"{service_name} did not become ready within timeout on port {port}"
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
        for port_name, original_value in original_env_vars.items():
            if original_value is not None:
                os.environ[port_name] = original_value
            elif port_name in os.environ:
                # Remove if it wasn't set originally (clean up test value)
                del os.environ[port_name]

        # Clean up containers for this test project ONLY
        # Verify containers exist for our project name before attempting cleanup
        # This prevents accidentally cleaning up manually started containers with different project names
        if should_cleanup:
            # Double-check that containers exist for our project before cleaning up
            check_result = manage_docker_compose(
                engine, "ps", project_name=project_name, ports=ports
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
                result = manage_docker_compose(
                    engine, "down", project_name=project_name, ports=ports
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
        _container_cleanup_registry.discard(container_info)


@pytest.fixture
def notebook_runner():
    """
    Fixture providing the notebook execution function.

    Returns a callable that executes a notebook and returns structured results.

    Usage:
        def test_my_notebook(notebook_runner):
            result = notebook_runner('path/to/notebook.ipynb')
            assert result['errors'] == []
    """
    from .notebooks.runner import run_notebook

    def runner(notebook_path, timeout=None, save_nb_path="tests/last_run.ipynb"):
        """
        Run a notebook and return results.

        Args:
            notebook_path: Path to the notebook to execute
            timeout: Optional timeout in seconds (default: 5 minutes from env)
            save_nb_path: Where to save the executed notebook

        Returns:
            dict with keys:
                - 'notebook': The executed notebook object
                - 'errors': List of errors encountered
                - 'execution_time': Time taken in seconds
                - 'path': Path to the notebook
        """
        nb, errors, exec_time = run_notebook(
            notebook_path, timeout=timeout, save_nb_path=save_nb_path
        )
        return {
            "notebook": nb,
            "errors": errors,
            "execution_time": exec_time,
            "path": notebook_path,
        }

    return runner


# Per-worker Docker container fixtures
# These fixtures provide isolated containers for each pytest-xdist worker
# when running tests in parallel. When not in parallel mode, they can be
# skipped if containers are already running (via test.sh).


@pytest.fixture(scope="session")
def solr_container(request):
    """
    Start Solr container for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.

    Usage:
        def test_something(solr_container):
            # solr_container is True if container is ready
            # Port is available via SOLR_PORT environment variable
            pass
    """
    engine_config = {
        "engine": "solr",
        "display_name": "Solr",
        "port_config": {
            "SOLR_PORT": "18983",
        },
        "health_checks": [
            ("SOLR_PORT", "Solr", "/solr/admin/info/system"),
        ],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(scope="session")
def elasticsearch_container(request):
    """
    Start Elasticsearch and Kibana containers for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.
    """
    engine_config = {
        "engine": "elasticsearch",
        "display_name": "Elasticsearch",
        "port_config": {
            "ELASTICSEARCH_PORT": "19200",
            "KIBANA_PORT": "15601",
        },
        "health_checks": [
            ("ELASTICSEARCH_PORT", "Elasticsearch", "/_cluster/health"),
            ("KIBANA_PORT", "Kibana", "/api/status"),
        ],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(scope="session")
def opensearch_container(request):
    """
    Start OpenSearch and OpenSearch Dashboards containers for this worker session.

    Provides per-worker isolation when running with pytest-xdist.
    Containers are automatically cleaned up when the session ends.
    """
    engine_config = {
        "engine": "opensearch",
        "display_name": "OpenSearch",
        "port_config": {
            "OPENSEARCH_PORT": "19201",
            "OPENSEARCH_PA_PORT": "19600",
            "OPENSEARCH_DASHBOARDS_PORT": "15602",
        },
        "health_checks": [
            ("OPENSEARCH_PORT", "OpenSearch", "/_cluster/health"),
            ("OPENSEARCH_DASHBOARDS_PORT", "OpenSearch Dashboards", "/api/status"),
        ],
    }
    yield from _manage_container_fixture(engine_config, request)


@pytest.fixture(autouse=True)
def add_error_context(request):
    """
    Automatically add context to test failures for better debugging.

    This fixture runs for every test and adds context information to failures,
    such as test name, parameters, and local variables.
    """
    # Store test context for use in error reporting
    request.node.user_properties.append(("test_name", request.node.name))
    if hasattr(request.node, "callspec") and request.node.callspec:
        request.node.user_properties.append(
            ("test_params", dict(request.node.callspec.params))
        )

    yield

    # After test, we could add cleanup or logging here if needed


@pytest.fixture
def cleanup_registry(request):
    """
    Registry for cleanup functions that should run after a test completes.

    This fixture allows tests to register cleanup functions that will be
    executed after the test completes, regardless of whether it passes or fails.

    Usage:
        def test_something(cleanup_registry):
            # Create a resource
            file_path = create_temp_file()
            # Register cleanup
            cleanup_registry.register(lambda: os.remove(file_path))

            # Test code...
            # Cleanup will run automatically after test completes

    Returns:
        CleanupRegistry: Object with register() method for registering cleanup functions
    """
    cleanup_functions = []

    class CleanupRegistry:
        """Registry for cleanup functions to be executed after tests.

        Provides a way to register cleanup functions that will be called
        in reverse order after the test completes, even if the test fails.
        """

        def register(self, cleanup_func, *args, **kwargs):
            """Register a cleanup function to be called after the test."""
            if args or kwargs:
                cleanup_functions.append((cleanup_func, args, kwargs))
            else:
                cleanup_functions.append((cleanup_func, (), {}))

    registry = CleanupRegistry()

    yield registry

    # Execute all registered cleanup functions in reverse order
    for cleanup_func, args, kwargs in reversed(cleanup_functions):
        try:
            cleanup_func(*args, **kwargs)
        except Exception as e:
            # Log cleanup failures but don't fail the test
            print(f"WARNING: Cleanup function failed: {e}", file=sys.stderr, flush=True)


@pytest.fixture
def temp_file(cleanup_registry, tmp_path):
    """
    Create a temporary file that is automatically cleaned up after the test.

    This fixture provides a temporary file path and ensures it's cleaned up
    after the test completes, even if the test fails.

    Usage:
        def test_something(temp_file):
            # temp_file is a Path object pointing to a temporary file
            temp_file.write_text("test content")
            # File is automatically deleted after test

    Returns:
        pathlib.Path: Path to a temporary file
    """
    temp_file_path = tmp_path / "test_file"
    temp_file_path.touch()

    # Register cleanup (though tmp_path fixture already handles this)
    # This is explicit for clarity and documentation
    cleanup_registry.register(lambda: temp_file_path.unlink(missing_ok=True))

    return temp_file_path


@pytest.fixture
def temp_dir(cleanup_registry, tmp_path):
    """
    Create a temporary directory that is automatically cleaned up after the test.

    This fixture provides a temporary directory path and ensures it's cleaned up
    after the test completes, even if the test fails.

    Usage:
        def test_something(temp_dir):
            # temp_dir is a Path object pointing to a temporary directory
            (temp_dir / "subdir").mkdir()
            (temp_dir / "file.txt").write_text("content")
            # Directory and contents are automatically deleted after test

    Returns:
        pathlib.Path: Path to a temporary directory
    """
    import shutil

    temp_dir_path = tmp_path / "test_dir"
    temp_dir_path.mkdir()

    # Register cleanup (though tmp_path fixture already handles this)
    # This is explicit for clarity and documentation
    cleanup_registry.register(lambda: shutil.rmtree(temp_dir_path, ignore_errors=True))

    return temp_dir_path


def pytest_runtest_makereport(item, call):
    """
    Hook to enhance test reports with additional context.

    This adds debugging information to test failure reports.
    """
    if call.when == "call" and call.excinfo is not None:
        # Add context to failure reports
        excinfo = call.excinfo
        if excinfo.typename == "AssertionError":
            # For assertion errors, try to add more context
            # The actual error message enhancement is done in the assertion itself
            pass


def pytest_runtest_logfinish(nodeid, location):
    """
    Hook called when a test finishes execution.

    Records test execution time in pytest cache for future slow test detection.
    """
    # This hook is called after test execution, but we need the actual duration
    # We'll record it in pytest_runtest_logreport instead
    pass


def pytest_runtest_logreport(report):
    """
    Hook called for each test reporting event.

    Records execution time when test completes successfully.
    """
    if report.when == "call" and report.outcome == "passed":
        # Record execution time for successful tests
        duration = getattr(report, "duration", None)
        if duration is not None and duration > 0:
            # Store in cache for future runs
            config = getattr(report, "config", None)
            if config is not None:
                cache = getattr(config, "cache", None)
                if cache is not None:
                    execution_times = cache.get("test_execution_times", {})
                    if not isinstance(execution_times, dict):
                        execution_times = {}
                    execution_times[report.nodeid] = duration
                    cache.set("test_execution_times", execution_times)


def _cleanup_all_test_containers():
    """
    Clean up all test containers registered in the cleanup registry.

    This function is called:
    - On normal test completion (via pytest_sessionfinish)
    - On interruption (SIGINT/SIGTERM signal handlers)
    - On pytest session finish (even if interrupted)

    Only cleans up containers with test project names (starting with "test-{test_type}-").

    To skip cleanup (e.g., when doing manual notebook development), set:
    SKIP_CONTAINER_CLEANUP=1

    Note: For manual notebook development, start containers using the engine-specific
    docker-compose files (e.g., notebooks/opensearch/docker-compose.yml) which use
    default project names that won't be cleaned up by tests.
    """
    # Allow skipping cleanup via environment variable (useful for manual development)
    if os.environ.get("SKIP_CONTAINER_CLEANUP", "").lower() in ("1", "true", "yes"):
        print("\n" + "=" * 80, file=sys.stderr)
        print(
            "Skipping container cleanup (SKIP_CONTAINER_CLEANUP is set)",
            file=sys.stderr,
        )
        print("=" * 80 + "\n", file=sys.stderr, flush=True)
        _container_cleanup_registry.clear()
        return

    if not _container_cleanup_registry:
        return

    print("\n" + "=" * 80, file=sys.stderr)
    print("Cleaning up test containers...", file=sys.stderr)
    print("=" * 80, file=sys.stderr, flush=True)

    cleaned_count = 0
    for engine, project_name, ports_hashable in list(_container_cleanup_registry):
        try:
            # Convert ports back from frozenset to dict
            ports = dict(ports_hashable) if ports_hashable else None
            # Verify containers exist before attempting cleanup
            check_result = manage_docker_compose(
                engine, "ps", project_name=project_name, ports=ports
            )
            containers_exist = (
                check_result.returncode == 0 and check_result.stdout.strip()
            )

            if containers_exist:
                print(
                    f"Stopping {engine} containers (project: {project_name})...",
                    file=sys.stderr,
                    flush=True,
                )
                result = manage_docker_compose(
                    engine, "down", project_name=project_name, ports=ports
                )
                if result.returncode == 0:
                    print(f"✓ {engine} containers stopped", file=sys.stderr, flush=True)
                    cleaned_count += 1
                else:
                    print(
                        f"WARNING: Failed to stop {engine} containers (project: {project_name}):\n"
                        f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}",
                        file=sys.stderr,
                        flush=True,
                    )
        except Exception as e:
            print(
                f"WARNING: Error cleaning up {engine} containers (project: {project_name}): {e}",
                file=sys.stderr,
                flush=True,
            )

    if cleaned_count > 0:
        print(
            f"\n✓ Cleaned up {cleaned_count} container project(s)",
            file=sys.stderr,
            flush=True,
        )
    print("=" * 80 + "\n", file=sys.stderr, flush=True)

    # Clear registry after cleanup attempt
    _container_cleanup_registry.clear()


def _setup_signal_handlers():
    """
    Set up signal handlers for SIGINT (Ctrl+C) and SIGTERM to ensure cleanup.

    This ensures containers are cleaned up even if pytest is interrupted.
    """

    def signal_handler(signum, frame):
        """Handle interrupt signals by cleaning up containers."""
        signal_name = signal.Signals(signum).name
        print(
            f"\n\nReceived {signal_name}, cleaning up test containers...",
            file=sys.stderr,
            flush=True,
        )
        _cleanup_all_test_containers()
        # Re-raise the signal to allow pytest to handle it normally
        # Use default handler to avoid recursion
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    # Only set up signal handlers on main process (not workers)
    # Workers will be cleaned up by the main process
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None
    if not is_worker:
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError):
            # Signal handling may not be available on all platforms
            # (e.g., Windows has limited signal support)
            pass


def pytest_configure(config):
    """
    Pytest hook to configure custom markers and settings.

    This is called once at the start of the test session.
    Also sets up worker-specific ports for parallel execution.
    Validates test environment before running tests.
    Sets up signal handlers for cleanup on interruption.
    """
    # Set up signal handlers for cleanup on interruption (main process only)
    _setup_signal_handlers()

    # Only run environment validation on the main process (not workers)
    # Workers will inherit the validated environment
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None

    if not is_worker:
        # Validate test environment
        try:
            from .integration.test_env_validation import check_test_environment
        except ImportError:
            # If check function not available (e.g., when running individual test files),
            # skip environment validation
            print(
                "WARNING: Could not import check_test_environment from test_env_validation. "
                "Skipping environment validation. This may occur when running individual test files.",
                file=sys.stderr,
                flush=True,
            )
            return

        # Skip port checks if running in parallel (ports will be assigned per worker)
        # Skip Docker check if test.sh is handling it (can be disabled via env var)
        skip_port_check = os.environ.get("SKIP_PORT_CHECK", "false").lower() == "true"
        skip_docker_check = (
            os.environ.get("SKIP_DOCKER_CHECK", "false").lower() == "true"
        )

        verbose = config.option.verbose > 0
        all_ok, issues = check_test_environment(
            check_docker=not skip_docker_check,
            check_ports=not skip_port_check,
            check_packages=True,
            check_disk=True,
            verbose=verbose,
        )

        if not all_ok:
            # Separate errors from warnings
            errors = [issue for issue in issues if not issue.startswith("Port:")]
            warnings = [issue for issue in issues if issue.startswith("Port:")]

            if errors:
                print("\n" + "=" * 80, file=sys.stderr)
                print("TEST ENVIRONMENT VALIDATION FAILED", file=sys.stderr)
                print("=" * 80, file=sys.stderr)
                for error in errors:
                    print(f"  ✗ {error}", file=sys.stderr)
                if warnings:
                    print("\nWarnings (non-fatal):", file=sys.stderr)
                    for warning in warnings:
                        print(f"  ⚠ {warning}", file=sys.stderr)
                print("=" * 80 + "\n", file=sys.stderr)
                # Don't exit - let pytest handle it, but warn the user
                print(
                    "WARNING: Some environment checks failed. Tests may not run correctly.",
                    file=sys.stderr,
                )
            elif warnings:
                # Only warnings, not errors
                if verbose:
                    print("\nEnvironment validation warnings:", file=sys.stderr)
                    for warning in warnings:
                        print(f"  ⚠ {warning}", file=sys.stderr)
                    print(
                        "(These are non-fatal - test.sh will handle port conflicts)\n",
                        file=sys.stderr,
                    )

    # Set up worker-specific ports if running in parallel
    worker_ports = get_worker_ports()
    if worker_ports:
        # Update environment variables for this worker
        for port_name, port_value in worker_ports.items():
            # Only set if not already set (allow manual override)
            if port_name not in os.environ:
                os.environ[port_name] = str(port_value)

        # Log port assignment for debugging
        worker = os.environ.get("PYTEST_XDIST_WORKER", "unknown")
        print(f"\n[Worker {worker}] Using ports:", file=sys.stderr)
        for port_name, port_value in worker_ports.items():
            print(f"  {port_name}={port_value}", file=sys.stderr)
        print("", file=sys.stderr, flush=True)

    # Register custom markers (also defined in pytest.ini for documentation)
    config.addinivalue_line("markers", "solr: Solr-specific tests")
    config.addinivalue_line("markers", "elasticsearch: Elasticsearch-specific tests")
    config.addinivalue_line("markers", "opensearch: OpenSearch-specific tests")
    config.addinivalue_line("markers", "slow: Slow-running tests (> 5 minutes)")
    config.addinivalue_line(
        "markers", "setup: Setup notebooks that prepare test environments"
    )
    config.addinivalue_line("markers", "fast: Fast-running tests (< 1 minute)")


def _load_test_execution_times(config):
    """
    Load test execution times from pytest cache.

    Returns:
        dict: Mapping of test nodeid to execution time in seconds
    """
    cache = getattr(config, "cache", None)
    if cache is None:
        return {}

    # Get execution times from cache
    execution_times = cache.get("test_execution_times", {})
    return execution_times if isinstance(execution_times, dict) else {}


def _is_slow_test(notebook_path, execution_times, nodeid):
    """
    Determine if a test should be marked as slow.

    Checks both pattern-based detection and execution time from previous runs.

    Args:
        notebook_path: Path to the notebook file
        execution_times: Dict mapping nodeid to execution time
        nodeid: Test nodeid for looking up execution time

    Returns:
        bool: True if test should be marked as slow
    """
    if not notebook_path:
        return False

    notebook_path_lower = notebook_path.lower()

    # Check against known slow patterns
    for pattern in SLOW_PATTERNS:
        if pattern.lower() in notebook_path_lower:
            return True

    # Check execution time from previous runs
    if nodeid in execution_times:
        exec_time = execution_times[nodeid]
        if isinstance(exec_time, (int, float)) and exec_time >= SLOW_TEST_THRESHOLD:
            return True

    return False


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to modify test items after collection.

    Applies markers dynamically based on test parameters and reorders tests
    so slow tests run last.
    """
    # Load execution times from cache
    execution_times = _load_test_execution_times(config)

    # First pass: apply markers
    for item in items:
        # Only process parametrized tests (from notebooks/test_notebooks.py)
        if not hasattr(item, "callspec") or not item.callspec:
            continue

        # Check if this is a parametrized test with our expected parameters
        params = item.callspec.params
        if "engine" not in params or "notebook_path" not in params:
            continue

        engine = params.get("engine", "general")
        notebook_type = params.get("notebook_type", "test")
        notebook_path = params.get("notebook_path", "")

        # Apply engine markers
        if engine == "solr":
            item.add_marker(pytest.mark.solr)
        elif engine == "elasticsearch":
            item.add_marker(pytest.mark.elasticsearch)
        elif engine == "opensearch":
            item.add_marker(pytest.mark.opensearch)

        # Apply type markers
        if notebook_type == "setup":
            item.add_marker(pytest.mark.setup)

        # Mark slow tests based on patterns and execution history
        if _is_slow_test(notebook_path, execution_times, item.nodeid):
            item.add_marker(pytest.mark.slow)

    # Second pass: reorder tests - fast tests first, slow tests last
    # Maintain relative order within each group
    fast_tests = []
    slow_tests = []

    for item in items:
        # Check if test has slow marker
        has_slow_marker = any(marker.name == "slow" for marker in item.iter_markers())

        if has_slow_marker:
            slow_tests.append(item)
        else:
            fast_tests.append(item)

    # Reorder: fast tests first, slow tests last
    items[:] = fast_tests + slow_tests


def pytest_collection_finish(session):
    """
    Hook called after test collection is complete.

    Prints summary of collected tests.
    """
    if session.config.option.collectonly:
        return

    # Count tests from notebooks/test_notebooks.py
    num_tests = len(
        [
            item
            for item in session.items
            if hasattr(item, "path") and Path(item.path).name == "test_notebooks.py"
        ]
    )

    if num_tests > 0:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Found {num_tests} notebook(s) to execute", flush=True)
        print(f"[{timestamp}] {'='*60}\n", flush=True)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Hook called at the end of test session to generate custom summary report.

    Provides detailed summary report with passed/failed/skipped counts and
    slow test statistics.
    """
    # Collect test results (these are TestReport objects, not test items)
    passed_reports = terminalreporter.stats.get("passed", [])
    failed_reports = terminalreporter.stats.get("failed", [])
    skipped_reports = terminalreporter.stats.get("skipped", [])

    # Get session to access actual test items
    session = getattr(terminalreporter, "_session", None)
    if session:
        # Build a mapping of nodeid to test item for marker checking
        nodeid_to_item = {item.nodeid: item for item in session.items}

        # Separate slow tests from fast tests by checking markers on actual items
        slow_passed = [
            report
            for report in passed_reports
            if report.nodeid in nodeid_to_item
            and any(
                m.name == "slow" for m in nodeid_to_item[report.nodeid].iter_markers()
            )
        ]
        slow_failed = [
            report
            for report in failed_reports
            if report.nodeid in nodeid_to_item
            and any(
                m.name == "slow" for m in nodeid_to_item[report.nodeid].iter_markers()
            )
        ]
    else:
        # Fallback: can't check markers without session
        slow_passed = []
        slow_failed = []

    slow_total = len(slow_passed) + len(slow_failed)

    passed = len(passed_reports)
    failed = len(failed_reports)
    skipped = len(skipped_reports)
    total = passed + failed + skipped

    # Get total execution time from session
    session = getattr(terminalreporter, "_session", None)
    total_time = getattr(session, "duration", 0) if session else 0

    # Print summary report
    print(f"\n{'='*80}", file=sys.stderr)
    print("TEST SUMMARY REPORT", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    print(f"Total notebooks in test set: {total}", file=sys.stderr)
    print(f"  ✓ Passed: {passed}", file=sys.stderr)
    print(f"  ✗ Failed: {failed}", file=sys.stderr)
    if skipped > 0:
        print(f"  ⊳ Skipped: {skipped}", file=sys.stderr)

    if total_time > 0:
        print(
            f"\nTotal execution time: {total_time:.1f}s ({total_time/60:.1f} minutes)",
            file=sys.stderr,
        )

    # Show slow test statistics
    if slow_total > 0:
        print(
            f"\nSlow tests: {slow_total} ({len(slow_passed)} passed, {len(slow_failed)} failed)",
            file=sys.stderr,
        )
        print("  Tip: Skip slow tests with: pytest -m 'not slow'", file=sys.stderr)
        print("  Tip: Run only slow tests with: pytest -m slow", file=sys.stderr)
        print("  Tip: See slowest tests with: pytest --durations=10", file=sys.stderr)

    # Note: For slowest tests, use pytest --durations=10
    # Pytest's built-in duration reporting is more reliable than trying to extract
    # durations from internal structures which vary by pytest version

    # Show failed notebooks
    if failed > 0:
        print("\nFailed notebooks:", file=sys.stderr)
        for report in failed_reports:
            name = _extract_notebook_name_from_report(report, session)
            print(f"  ✗ {name}", file=sys.stderr)

    print(f"{'='*80}\n", file=sys.stderr)


def pytest_sessionfinish(session, exitstatus):
    """
    Pytest hook called when the test session is finishing.

    This hook is called even if tests are interrupted (Ctrl+C) or pytest is killed.
    It ensures all test containers are cleaned up regardless of how the session ends.

    Args:
        session: The pytest session object
        exitstatus: The exit status code (0=passed, 1=failed, 2=interrupted, etc.)
    """
    # Only run cleanup on main process (not workers)
    # Workers' containers will be cleaned up by their own fixtures or by the main process
    is_worker = os.environ.get("PYTEST_XDIST_WORKER") is not None
    if not is_worker:
        _cleanup_all_test_containers()


def _extract_notebook_name(item):
    """
    Extract notebook path from test item name.

    Handles parametrized test names like:
    test_notebook_executes_without_errors[./notebooks/solr/tmdb/sandbox.ipynb-test-solr]
    """
    # Try to get name from item
    name = getattr(item, "name", None)
    if not name:
        name = str(item)

    # For parametrized tests, extract notebook path from parameter
    if hasattr(item, "callspec") and item.callspec:
        params = item.callspec.params
        notebook_path = params.get("notebook_path", "")
        if notebook_path:
            return notebook_path

    # Fallback: try to parse from test name
    if "[" in name and "]" in name:
        # Parametrized test name format: test_name[param1-param2-param3]
        # We want the first param (notebook_path)
        notebook_part = name.split("[")[1].split("]")[0]
        # Split by '-' and take first part (notebook path)
        parts = notebook_part.split("-")
        if parts:
            return parts[0]

    return name


def _extract_notebook_name_from_report(report, session):
    """
    Extract notebook path from test report.

    First tries to get the actual test item from session, then falls back
    to parsing the nodeid.
    """
    # Try to get the actual test item from session
    if session:
        for item in session.items:
            if item.nodeid == report.nodeid:
                return _extract_notebook_name(item)

    # Fallback: parse from nodeid
    nodeid = getattr(report, "nodeid", "")
    if "[" in nodeid and "]" in nodeid:
        # Parametrized test name format: test_name[param1-param2-param3]
        notebook_part = nodeid.split("[")[1].split("]")[0]
        parts = notebook_part.split("-")
        if parts:
            return parts[0]

    return nodeid
