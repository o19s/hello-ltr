"""
Test environment validation utilities.

This module provides functions to validate that the test environment
is properly configured before running tests.
"""
import os
import shutil
import socket
import subprocess
import sys
from typing import Optional


def check_docker_installed() -> tuple[bool, Optional[str]]:
    """
    Check if Docker is installed and accessible.

    Returns:
        Tuple of (is_installed, error_message)
    """
    if not shutil.which('docker'):
        return False, "Docker is not installed or not in PATH"

    try:
        # Check if Docker daemon is running
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False, f"Docker daemon is not running: {result.stderr.strip()}"
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Docker daemon check timed out"
    except Exception as e:
        return False, f"Error checking Docker: {str(e)}"


def check_docker_compose() -> tuple[bool, Optional[str]]:
    """
    Check if Docker Compose is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    # Try 'docker compose' (newer syntax)
    result = subprocess.run(
        ['docker', 'compose', 'version'],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        return True, None

    # Fall back to 'docker-compose' (older syntax)
    if shutil.which('docker-compose'):
        return True, None

    return False, "Docker Compose is not available (neither 'docker compose' nor 'docker-compose' found)"


def check_port_available(port: int, host: str = 'localhost') -> tuple[bool, Optional[str]]:
    """
    Check if a port is available (not in use).

    Args:
        port: Port number to check
        host: Host to check (default: localhost)

    Returns:
        Tuple of (is_available, error_message)
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            if result == 0:
                return False, f"Port {port} is already in use"
            return True, None
    except Exception:
        # If we can't check, assume it's available (might be a permission issue)
        return True, None


def check_test_ports() -> tuple[bool, list[str]]:
    """
    Check if test ports are available.

    Returns:
        Tuple of (all_available, list_of_errors)
    """
    errors = []

    # Get test ports from environment or use defaults
    test_ports = {
        'SOLR_PORT': int(os.environ.get('SOLR_PORT', 18983)),
        'ELASTICSEARCH_PORT': int(os.environ.get('ELASTICSEARCH_PORT', 19200)),
        'OPENSEARCH_PORT': int(os.environ.get('OPENSEARCH_PORT', 19201)),
    }

    for port_name, port in test_ports.items():
        available, error = check_port_available(port)
        if not available:
            errors.append(f"{port_name} ({port}): {error}")

    return len(errors) == 0, errors


def check_python_packages() -> tuple[bool, list[str]]:
    """
    Check if required Python packages are installed.

    Returns:
        Tuple of (all_installed, list_of_missing_packages)
    """
    import importlib

    # Core test dependencies - map package name to import name
    # pytest-xdist imports as 'xdist', others use their package name with underscores
    required_packages = {
        'pytest': 'pytest',
        'pytest-xdist': 'xdist',
        'pytest-timeout': 'pytest_timeout',
        'pytest-html': 'pytest_html',
        'pytest-cov': 'pytest_cov',
    }

    missing = []
    for package_name, import_name in required_packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(package_name)

    return len(missing) == 0, missing


def check_disk_space(min_gb: float = 1.0, path: str = '.') -> tuple[bool, Optional[str]]:
    """
    Check if there's sufficient disk space available.

    Args:
        min_gb: Minimum disk space required in GB
        path: Path to check disk space for

    Returns:
        Tuple of (has_space, error_message)
    """
    try:
        import shutil
        stat = shutil.disk_usage(path)
        available_gb = stat.free / (1024 ** 3)

        if available_gb < min_gb:
            return False, f"Insufficient disk space: {available_gb:.2f} GB available, {min_gb} GB required"
        return True, None
    except Exception:
        # If we can't check, assume it's OK (might be a permission issue)
        return True, None


def check_test_environment(
    check_docker: bool = True,
    check_ports: bool = True,
    check_packages: bool = True,
    check_disk: bool = True,
    min_disk_gb: float = 1.0,
    verbose: bool = False
) -> tuple[bool, list[str]]:
    """
    Verify all test dependencies and environment are ready.

    Args:
        check_docker: Whether to check Docker installation
        check_ports: Whether to check test ports availability
        check_packages: Whether to check Python packages
        check_disk: Whether to check disk space
        min_disk_gb: Minimum disk space required in GB
        verbose: Print detailed information

    Returns:
        Tuple of (all_checks_passed, list_of_errors)
    """
    errors = []
    warnings = []

    if verbose:
        print("Validating test environment...", file=sys.stderr)

    # Check Docker
    if check_docker:
        if verbose:
            print("  Checking Docker...", file=sys.stderr)
        docker_ok, docker_error = check_docker_installed()
        if not docker_ok:
            errors.append(f"Docker: {docker_error}")
        else:
            # Check Docker Compose
            compose_ok, compose_error = check_docker_compose()
            if not compose_ok:
                errors.append(f"Docker Compose: {compose_error}")
            elif verbose:
                print("    ✓ Docker and Docker Compose available", file=sys.stderr)

    # Check ports
    if check_ports:
        if verbose:
            print("  Checking test ports...", file=sys.stderr)
        ports_ok, port_errors = check_test_ports()
        if not ports_ok:
            # Port conflicts are warnings, not errors (test.sh handles them)
            warnings.extend([f"Port: {err}" for err in port_errors])
        elif verbose:
            print("    ✓ Test ports available", file=sys.stderr)

    # Check Python packages
    if check_packages:
        if verbose:
            print("  Checking Python packages...", file=sys.stderr)
        packages_ok, missing = check_python_packages()
        if not packages_ok:
            errors.append(f"Missing Python packages: {', '.join(missing)}")
        elif verbose:
            print("    ✓ Required packages installed", file=sys.stderr)

    # Check disk space
    if check_disk:
        if verbose:
            print("  Checking disk space...", file=sys.stderr)
        disk_ok, disk_error = check_disk_space(min_disk_gb)
        if not disk_ok:
            warnings.append(disk_error)
        elif verbose:
            print("    ✓ Sufficient disk space available", file=sys.stderr)

    # Combine errors and warnings
    all_issues = errors + warnings

    if verbose and len(all_issues) == 0:
        print("  ✓ All checks passed!", file=sys.stderr)

    # Return True only if no errors (warnings are OK)
    return len(errors) == 0, all_issues

