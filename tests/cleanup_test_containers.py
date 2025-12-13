#!/usr/bin/env python3
"""
Utility script to clean up leftover test containers from interrupted test runs.

This script finds and stops all Docker containers with test project names
(starting with "test-") that may have been left running after test
interruptions or failures.

Usage:
    python tests/cleanup_test_containers.py
    # Or make it executable and run directly:
    ./tests/cleanup_test_containers.py

Options:
    --dry-run: Show what would be cleaned up without actually stopping containers
    --verbose: Show detailed output
    --help: Show this help message
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_docker_compose_cmd():
    """
    Get the docker compose command to use.

    Returns:
        str: Either "docker compose" or "docker-compose" depending on what's available
    """
    import shutil

    if shutil.which("docker"):
        # Check if "docker compose" is available (Docker Compose V2)
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return "docker compose"

    # Fallback to docker-compose (V1)
    if shutil.which("docker-compose"):
        return "docker-compose"

    raise RuntimeError(
        "Neither 'docker compose' nor 'docker-compose' found. Please install Docker."
    )


def find_test_containers():
    """
    Find all test containers (those with project names starting with "test-").

    Returns:
        list: List of tuples (project_name, engine, containers)
    """
    # Get all containers with "test-" prefix in the name
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=test-", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error running docker ps: {result.stderr}", file=sys.stderr)
        return []

    container_names = [
        name.strip() for name in result.stdout.strip().split("\n") if name.strip()
    ]

    # Group containers by project name
    # Container names follow pattern: test-{test_type}-{engine}-{worker}-{service}-{number}
    projects = {}

    for container_name in container_names:
        # Test containers have pattern: test-{test_type}-{engine}-{worker}-{service}
        parts = container_name.split("-")
        if len(parts) < 4:
            # Not a valid test container name (needs at least test-{type}-{engine}), skip it
            continue

        # Extract project name: test-{test_type}-{engine}-{worker}
        # Container name: test-{test_type}-{engine}-{worker}-{service}-{number}
        # First part should be "test", second is test type (unit/integration/notebooks), third is engine
        if parts[0] != "test":
            continue

        project_parts = parts[:3]  # test-{test_type}-{engine}
        # Check if 4th part looks like a worker ID (gw0, gw1, etc.)
        if len(parts) >= 4 and (parts[3].startswith("gw") or parts[3] == "main"):
            project_parts = parts[:4]  # test-{test_type}-{engine}-{worker}

        project_name = "-".join(project_parts)
        engine = parts[2] if len(parts) > 2 else "unknown"

        if project_name not in projects:
            projects[project_name] = {"engine": engine, "containers": []}
        projects[project_name]["containers"].append(container_name)

    # Convert to list of tuples
    return [
        (project_name, info["engine"], info["containers"])
        for project_name, info in projects.items()
    ]


def cleanup_project(project_name, engine, containers, dry_run=False, verbose=False):
    """
    Clean up containers for a specific project.

    Args:
        project_name: Docker Compose project name
        engine: Engine name (solr, elasticsearch, opensearch)
        containers: List of container names
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output

    Returns:
        bool: True if cleanup succeeded
    """
    if dry_run:
        print(f"Would clean up project: {project_name} ({engine})")
        print(f"  Containers: {', '.join(containers)}")
        return True

    # Use docker compose down to clean up the project
    docker_cmd = get_docker_compose_cmd()
    cmd_parts = docker_cmd.split()

    # Find the docker-compose.yml file for this engine
    project_root = Path(__file__).parent.parent
    engine_path = project_root / "notebooks" / engine

    if not engine_path.exists():
        print(f"WARNING: Engine path not found: {engine_path}", file=sys.stderr)
        # Fallback: use docker stop/rm for individual containers
        return cleanup_containers_directly(containers, verbose)

    # Build compose files list
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

    cmd.extend(["-p", project_name, "down", "-v"])

    if verbose:
        print(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=str(engine_path), capture_output=True, text=True)

    if result.returncode == 0:
        if verbose:
            print(f"✓ Cleaned up {project_name}")
        return True
    else:
        # Fallback to direct container cleanup
        if verbose:
            print("docker compose down failed, trying direct container cleanup...")
        return cleanup_containers_directly(containers, verbose)


def cleanup_containers_directly(containers, verbose=False):
    """
    Clean up containers directly using docker stop/rm.

    Args:
        containers: List of container names
        verbose: If True, show detailed output

    Returns:
        bool: True if cleanup succeeded
    """
    success = True
    for container in containers:
        # Stop container
        result = subprocess.run(
            ["docker", "stop", container], capture_output=True, text=True
        )
        if result.returncode != 0:
            if verbose:
                print(
                    f"WARNING: Failed to stop {container}: {result.stderr}",
                    file=sys.stderr,
                )
            success = False
        else:
            if verbose:
                print(f"✓ Stopped {container}")

        # Remove container
        result = subprocess.run(
            ["docker", "rm", container], capture_output=True, text=True
        )
        if result.returncode != 0:
            if verbose:
                print(
                    f"WARNING: Failed to remove {container}: {result.stderr}",
                    file=sys.stderr,
                )
            success = False
        elif verbose:
            print(f"✓ Removed {container}")

    return success


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up leftover test containers from interrupted test runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned up without actually stopping containers",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    args = parser.parse_args()

    print("Finding test containers...", file=sys.stderr)
    projects = find_test_containers()

    if not projects:
        print("No test containers found.", file=sys.stderr)
        return 0

    print(f"\nFound {len(projects)} test container project(s):", file=sys.stderr)
    for project_name, engine, containers in projects:
        print(
            f"  {project_name} ({engine}): {len(containers)} container(s)",
            file=sys.stderr,
        )

    if args.dry_run:
        print("\n[DRY RUN] Would clean up:", file=sys.stderr)
        for project_name, engine, containers in projects:
            cleanup_project(
                project_name, engine, containers, dry_run=True, verbose=args.verbose
            )
        print("", file=sys.stderr)  # Add blank line at end
        return 0

    print("\nCleaning up containers...", file=sys.stderr)
    cleaned_count = 0
    failed_count = 0

    for project_name, engine, containers in projects:
        if cleanup_project(
            project_name, engine, containers, dry_run=False, verbose=args.verbose
        ):
            cleaned_count += 1
        else:
            failed_count += 1

    print(f"\n{'='*80}", file=sys.stderr)
    print("Cleanup complete:", file=sys.stderr)
    print(f"  ✓ Cleaned: {cleaned_count}", file=sys.stderr)
    if failed_count > 0:
        print(f"  ✗ Failed: {failed_count}", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
