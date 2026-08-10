"""File download utilities.

This module provides functions for downloading files from URLs
with support for resuming downloads and force re-downloading.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from os import path

import requests

from ltr.logger import get_logger

logger = get_logger(__name__)


def download_one(uri: str, dest: str = "data/", force: bool = False) -> None:
    """Download a single file from a URI to a destination directory.

    Args:
        uri: URL of the file to download.
        dest: Destination directory path (default: "data/"). Will be created
            if it doesn't exist.
        force: If True, re-download even if file already exists (default: False).

    Returns:
        None: File is written to disk, nothing is returned.

    Raises:
        ValueError: If dest exists but is not a directory.
        requests.HTTPError: If the server returns an error status. The
            destination file is left untouched.

    Note:
        Downloads are streamed in 1KB chunks into a temporary file in dest and
        renamed into place only once the transfer completes, so an interrupted
        download leaves nothing behind. If the file already exists and is
        non-empty and force=False, the download is skipped.

        A zero-byte file counts as absent. Downloads used to be written
        straight to the destination, so a failed transfer left an empty file
        that the existence check then treated as a valid cache entry forever -
        one bad network moment became a permanent failure that surfaced much
        later as an empty training set. See issue #119.
    """
    if not os.path.exists(dest):
        os.makedirs(dest)

    if not os.path.isdir(dest):
        raise ValueError(f"dest {dest} is not a directory")

    filename = uri[uri.rfind("/") + 1 :]
    filepath = os.path.join(dest, filename)
    if path.exists(filepath):
        if os.path.getsize(filepath) == 0:
            # Almost certainly the residue of a failed download from before
            # this function wrote atomically. Re-fetch rather than trust it.
            logger.info(f"{filepath} exists but is empty, downloading again")
        elif not force:
            logger.info(f"{filepath} already exists")
            return
        else:
            logger.info("File exists but force=True, downloading anyway")

    # Write to a temporary file in the destination directory so the rename is
    # atomic (same filesystem) and a partial transfer never occupies filepath.
    handle, partial_path = tempfile.mkstemp(
        dir=dest, prefix=f".{filename}.", suffix=".part"
    )
    try:
        with os.fdopen(handle, "wb") as out:
            logger.info(f"GET {uri}")
            resp = requests.get(uri, stream=True)
            # Without this an error page is written out as if it were the file.
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    out.write(chunk)
        os.replace(partial_path, filepath)
    except BaseException:
        with suppress(OSError):
            os.remove(partial_path)
        raise


def download(
    uris: list[str] | Iterable[str], dest: str = "data/", force: bool = False
) -> None:
    """Download multiple files from URIs to a destination directory.

    Args:
        uris: List or iterable of URLs to download.
        dest: Destination directory path (default: "data/"). Will be created
            if it doesn't exist.
        force: If True, re-download even if files already exist (default: False).

    Returns:
        None: Files are written to disk, nothing is returned.

    Example:
        >>> download(["http://example.com/file1.txt", "http://example.com/file2.txt"])
    """
    for uri in uris:
        download_one(uri=uri, dest=dest, force=force)
