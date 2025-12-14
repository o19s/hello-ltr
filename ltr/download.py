"""File download utilities.

This module provides functions for downloading files from URLs
with support for resuming downloads and force re-downloading.
"""

from os import path

import requests


def download_one(uri, dest="data/", force=False):
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

    Note:
        Downloads are streamed in 1KB chunks. If the file already exists
        and force=False, the download is skipped.
    """
    import os

    if not os.path.exists(dest):
        os.makedirs(dest)

    if not os.path.isdir(dest):
        raise ValueError(f"dest {dest} is not a directory")

    filename = uri[uri.rfind("/") + 1 :]
    filepath = os.path.join(dest, filename)
    if path.exists(filepath):
        if not force:
            print(filepath + " already exists")
            return
        print("exists but force=True, Downloading anyway")

    with open(filepath, "wb") as out:
        print(f"GET {uri}")
        resp = requests.get(uri, stream=True)
        for chunk in resp.iter_content(chunk_size=1024):
            if chunk:
                out.write(chunk)


def download(uris, dest="data/", force=False):
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
