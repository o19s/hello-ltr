"""
Health check utilities for hello-ltr test suite.

This module provides:
- Service health check functions with retry logic
- Progressive interval calculation for health checks
- Service wait timeout configuration
"""

from __future__ import annotations

import os
import time

import requests

# Retry configuration constants
HEALTH_CHECK_MAX_RETRIES = 3
HEALTH_CHECK_BASE_RETRY_DELAY = 0.1


def get_service_wait_timeout() -> int:
    """
    Get the service wait timeout from environment variable.

    Returns:
        int: Timeout in seconds (default: 300)
    """
    return int(os.environ.get("SERVICE_WAIT_TIMEOUT", "300"))


def _perform_single_health_check(url: str) -> tuple[bool, bool]:
    """
    Perform a single health check HTTP request.

    Args:
        url: URL to check

    Returns:
        tuple: (success: bool, should_retry: bool) where success indicates
               service is ready and should_retry indicates if retry is needed
    """
    try:
        # Use original requests.get if available (to avoid double retries from patched version)
        # Health checks have their own retry logic, so we don't need the patched retry logic
        get_func = getattr(requests, "_original_get", requests.get)
        response = get_func(url, timeout=2)
        # Only accept 2xx status codes as ready (successful responses)
        if 200 <= response.status_code < 300:
            return True, False
        # Non-2xx response: don't retry, wait for next check interval
        return False, False
    except (requests.exceptions.RequestException, ConnectionError):
        # Transient failure: retry is needed
        return False, True


def _check_health_with_retries(
    url: str,
    max_retries: int = HEALTH_CHECK_MAX_RETRIES,
    base_retry_delay: float = HEALTH_CHECK_BASE_RETRY_DELAY,
) -> bool:
    """
    Check health endpoint with exponential backoff retry logic.

    Args:
        url: URL to check
        max_retries: Maximum number of retry attempts
        base_retry_delay: Base delay in seconds for exponential backoff

    Returns:
        bool: True if service is ready, False otherwise
    """
    for retry_attempt in range(max_retries):
        success, should_retry = _perform_single_health_check(url)
        if success:
            return True
        if not should_retry:
            # Non-retryable failure (e.g., non-2xx response)
            return False
        # If this is the last retry attempt, don't sleep
        if retry_attempt == max_retries - 1:
            return False
        # Exponential backoff: 0.1s, 0.2s, 0.4s
        retry_delay = base_retry_delay * (2**retry_attempt)
        time.sleep(retry_delay)
    return False


def _get_progressive_interval(
    elapsed_time: float, timeout: float, check_interval: float, current_index: int
) -> tuple[float, int]:
    """
    Calculate progressive check interval based on elapsed time.

    Progressive intervals start shorter and increase as time passes to balance
    early responsiveness with efficiency for long waits.

    Args:
        elapsed_time: Time elapsed since start
        timeout: Total timeout duration
        check_interval: Base check interval
        current_index: Current interval index (0, 1, or 2)

    Returns:
        tuple: (interval: float, new_index: int) where interval is the delay
               to use and new_index is the updated interval index
    """
    progressive_intervals = [check_interval, check_interval * 1.5, check_interval * 2]
    new_index = current_index

    # Progressively increase interval as more time passes
    if elapsed_time > timeout * 0.75 and current_index < len(progressive_intervals) - 1:
        new_index = 2
    elif (
        elapsed_time > timeout * 0.5 and current_index < len(progressive_intervals) - 1
    ):
        new_index = 1

    return progressive_intervals[new_index], new_index


def wait_for_service(
    port: int,
    service_name: str,
    health_endpoint: str = "/",
    timeout: int | None = None,
    check_interval: float = 2,
) -> bool:
    """
    Wait for a service to be ready by checking its health endpoint.

    Uses exponential backoff retry logic to handle transient network failures.
    Implements progressive check intervals: starts with shorter intervals and increases
    them as time passes to balance responsiveness with efficiency.

    Args:
        port: Port number to check
        service_name: Name of the service (for logging)
        health_endpoint: Health check endpoint path
        timeout: Maximum time to wait in seconds (defaults to SERVICE_WAIT_TIMEOUT env var or 300)
        check_interval: Base time between checks in seconds (will increase progressively)

    Returns:
        bool: True if service is ready, False if timeout
    """
    if timeout is None:
        timeout = get_service_wait_timeout()
    start_time = time.time()
    url = f"http://localhost:{port}{health_endpoint}"
    interval_index = 0

    while time.time() - start_time < timeout:
        # Check health with retry logic for transient failures
        if _check_health_with_retries(url):
            return True

        # Wait with progressive interval before next health check attempt
        elapsed = time.time() - start_time
        current_interval, interval_index = _get_progressive_interval(
            elapsed, timeout, check_interval, interval_index
        )
        time.sleep(current_interval)

    return False
