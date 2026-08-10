"""
Container management utilities for hello-ltr test suite.

This module provides:
- Docker Compose command detection and execution
- Container lifecycle management (start, stop, check)
- Container cleanup registry
- Port availability checking
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ltr.logger import get_logger

logger = get_logger(__name__)

# Cache for docker compose command detection
_docker_compose_cmd_cache = None

# Global registry for containers that need cleanup
# This ensures cleanup even if pytest is interrupted (Ctrl+C) or killed
_container_cleanup_registry = set()


def get_docker_compose_cmd() -> str:
    """
    Get the docker compose command to use.

    Returns:
        str: Either "docker compose" or "docker-compose" depending on what's available

    Raises:
        RuntimeError: If neither docker compose nor docker-compose is found
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


def check_ports_available(
    ports_dict: dict[str, str | int],
) -> tuple[bool, list[str]]:
    """
    Check if all ports in the dictionary are available.

    Args:
        ports_dict: Dictionary mapping port names to port numbers

    Returns:
        tuple: (all_available: bool, unavailable_ports: list[str])
    """
    try:
        from tests.integration.test_env_validation import check_port_available
    except ImportError:
        # If check function not available, log warning and assume ports are available
        logger.warning(
            "Could not import check_port_available from test_env_validation. "
            "Skipping port availability check. This may lead to port conflicts."
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


def manage_docker_compose(
    engine: str,
    action: str,
    project_name: str | None = None,
    ports: dict[str, str | int] | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Manage docker-compose containers for a specific engine.

    CRITICAL SAFETY: This function ONLY operates on containers with test project names.
    Test project names MUST start with "test-" followed by test type (e.g., "test-unit-", "test-integration-", "test-notebooks-")
    to prevent accidentally modifying manually started containers (which use default project names like "elasticsearch", "solr", "opensearch",
    or containers started with docker-compose.yml which use "hello-ltr-" prefix).

    Args:
        engine: Engine name ("solr", "elasticsearch", "opensearch")
        action: Action to perform ("up", "down", "ps", "build")
        project_name: Docker Compose project name (for isolation)
                     MUST start with "test-{test_type}-" for test containers
                     (e.g., "test-unit-solr-gw0", "test-integration-opensearch-gw0", "test-notebooks-elasticsearch-gw0")
        ports: Dict of port environment variables to set

    Returns:
        subprocess.CompletedProcess: Result of the docker-compose command

    Raises:
        RuntimeError: If project_name is provided but doesn't match test pattern
        ValueError: If engine path not found
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

    engine_path = Path(__file__).parent.parent.parent / "notebooks" / engine

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
        # CRITICAL: --build forces Docker Compose to re-evaluate the `build:`
        # directives before starting. Without it, an already-built image for this
        # project is reused and a changed base image in
        # notebooks/*/.docker/*/Dockerfile is silently ignored - so an engine
        # version bump can pass the whole suite without ever being exercised.
        # This repo pins engine versions in Dockerfiles rather than in compose
        # `image:` directives, so this is the primary way versions change.
        # The flag is close to free when nothing changed: Docker layer-caches
        # the build. See issue #110.
        cmd.append("--build")

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


def _docker_inspect(target: str, fmt: str) -> str | None:
    """
    Run `docker inspect` against a container or image and return the formatted value.

    Args:
        target: Container name/ID or image reference to inspect
        fmt: Go template passed to `--format`

    Returns:
        str | None: The trimmed output, or None if the target does not exist or
                    docker could not be reached
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", fmt, target],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0:
        return None

    value = result.stdout.strip()
    return value or None


def find_stale_containers(project_name: str) -> list[str]:
    """
    Find running containers whose image is no longer the current build.

    Adding `--build` to `docker compose up` only helps when containers are being
    created. A previous run can leave healthy containers behind, and the fixture
    reuses those without calling `up` at all - so a Dockerfile change would still
    go unnoticed. This detects that case so the caller can tear them down.

    The comparison is made against the image Docker Compose builds for each
    service, which it tags `<project>-<service>`. Services declared with `image:`
    rather than `build:` have no such tag; they cannot go stale from a Dockerfile
    edit, so they are skipped.

    This must be called *after* a build, otherwise the tagged image is itself
    stale and every container looks current.

    Args:
        project_name: Docker Compose project name to inspect

    Returns:
        list[str]: Names of running containers running an out-of-date image.
                   Empty if everything is current, or if Docker could not be
                   queried (fail open - staleness detection must never be the
                   reason a test run cannot start).
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"label=com.docker.compose.project={project_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        return []

    if result.returncode != 0:
        return []

    stale = []
    for name in (line.strip() for line in result.stdout.splitlines()):
        if not name:
            continue

        running_image = _docker_inspect(name, "{{.Image}}")
        service = _docker_inspect(
            name, '{{index .Config.Labels "com.docker.compose.service"}}'
        )
        if not running_image or not service:
            continue

        # Compose tags images it builds as <project>-<service>. A missing tag
        # means the service uses a pre-built `image:`, which cannot go stale here.
        current_image = _docker_inspect(f"{project_name}-{service}", "{{.Id}}")
        if current_image and current_image != running_image:
            stale.append(name)

    return stale


def get_container_cleanup_registry() -> set[
    tuple[str, str, frozenset[tuple[str, str]] | None]
]:
    """
    Get the global container cleanup registry.

    Returns:
        set: The container cleanup registry
    """
    return _container_cleanup_registry


def register_container_for_cleanup(
    container_info: tuple[str, str, frozenset[tuple[str, str]] | None],
) -> None:
    """
    Register a container for cleanup.

    Args:
        container_info: Tuple of (engine, project_name, ports_hashable)
    """
    _container_cleanup_registry.add(container_info)


def unregister_container_from_cleanup(
    container_info: tuple[str, str, frozenset[tuple[str, str]] | None],
) -> None:
    """
    Unregister a container from cleanup.

    Args:
        container_info: Tuple of (engine, project_name, ports_hashable)
    """
    _container_cleanup_registry.discard(container_info)


def cleanup_all_test_containers() -> None:
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
            logger.warning(
                f"Error cleaning up {engine} containers (project: {project_name}, non-critical): {e}",
                exc_info=True,
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
