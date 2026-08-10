"""
File locking utilities for hello-ltr test suite.

This module provides platform-specific file locking to prevent race conditions
in parallel test execution.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager, suppress
from pathlib import Path

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


def _is_lock_stale(lock_path: Path, max_age_seconds: int = 300) -> bool:
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
            with open(lock_path, encoding="utf-8") as f:
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
def file_lock(lock_file_path: str | Path, timeout: int = 30):
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
            lock_file = open(lock_path, "w", encoding="utf-8")  # noqa: SIM115

            # Platform-specific locking
            if HAS_FCNTL:
                # Unix/Linux: Use fcntl advisory locks
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # pyright: ignore[reportPossiblyUnboundVariable]
            elif HAS_MSVCRT:
                # Windows: Use msvcrt file locking
                # msvcrt.locking requires file descriptor and byte range
                # Lock the first byte (non-blocking)
                import msvcrt  # noqa: PLC0415

                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
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
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)  # pyright: ignore[reportPossiblyUnboundVariable]
                elif HAS_MSVCRT:
                    import msvcrt  # noqa: PLC0415

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            except OSError:
                pass  # Ignore unlock errors
            lock_file.close()
            # Remove lock file if possible (ignore errors)
            with suppress(OSError):
                lock_path.unlink(missing_ok=True)
